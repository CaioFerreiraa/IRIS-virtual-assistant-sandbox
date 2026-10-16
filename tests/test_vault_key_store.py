from contextlib import contextmanager
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import VaultKey
from services.vault_key_store import WindowsVaultKeyStore
from services.vault_service import VaultService


class ProcessMemoryKeyStore(WindowsVaultKeyStore):
    # Compartilhado somente entre os processos de teste; não usa Credential Manager.
    def __init__(self, state):
        self.state = state

    def read(self):
        key = self.state.key
        if key is None:
            # Amplia a janela de corrida para detectar a ausência do mutex.
            time.sleep(0.1)
        return key

    def write(self, key):
        self.state.writes += 1
        self.state.key = key


def create_in_process(root, state, ready, results, index):
    engine = create_engine(f"sqlite:///{Path(root) / 'vault.db'}")
    try:
        service = VaultService(sessionmaker(bind=engine), Path(root) / '.iris_vault.key',
                               key_store=ProcessMemoryKeyStore(state))
        ready.wait(10)
        service.create(f'KEY_{index}', f'value-{index}')
        results.put(None)
    except Exception as error:
        results.put(str(error))
    finally:
        engine.dispose()


class WindowsVaultKeyStoreTests(unittest.TestCase):
    @contextmanager
    def backend_mock(self):
        backend = Mock()
        constructor = Mock(return_value=backend)
        modules = {
            'keyring': SimpleNamespace(),
            'keyring.backends': SimpleNamespace(),
            'keyring.backends.Windows': SimpleNamespace(WinVaultKeyring=constructor),
        }
        with patch.dict(sys.modules, modules), patch('services.vault_key_store.sys.platform', 'win32'):
            yield backend, constructor

    def test_explicit_local_backend_and_stable_identifiers(self):
        with self.backend_mock() as (backend, constructor):
            backend.get_password.return_value = 'test-key'
            store = WindowsVaultKeyStore()
            constructor.assert_not_called()
            self.assertEqual('test-key', store.read())
            store.write('test-key')
            backend.get_password.assert_called_once_with('IRIS.Vault', 'master-key-v1')
            backend.set_password.assert_called_once_with('IRIS.Vault', 'master-key-v1', 'test-key')
            self.assertEqual('local machine', backend.persist)
            self.assertEqual(2, constructor.call_count)

    def test_backend_errors_never_escape_with_sensitive_details(self):
        with self.backend_mock() as (backend, constructor):
            backend.get_password.side_effect = RuntimeError('sensitive-master-key')
            backend.set_password.side_effect = RuntimeError('sensitive-master-key')
            store = WindowsVaultKeyStore()
            for action in (store.read, lambda: store.write('sensitive-master-key')):
                with self.assertRaisesRegex(ValueError, 'Windows Credential Manager') as caught:
                    action()
                self.assertNotIn('sensitive-master-key', str(caught.exception))
                self.assertTrue(caught.exception.__suppress_context__)
            constructor.side_effect = ImportError('private-installation-path')
            with self.assertRaises(ValueError) as caught:
                store.read()
            self.assertNotIn('private-installation-path', str(caught.exception))

    def test_non_windows_does_not_import_backend(self):
        with patch('services.vault_key_store.sys.platform', 'linux'):
            store = WindowsVaultKeyStore()
            for action in (store.read, lambda: store.write('test-key')):
                with self.assertRaisesRegex(ValueError, 'indisponível'):
                    action()
            with self.assertRaisesRegex(ValueError, 'indisponível'):
                with store.locked():
                    self.fail('Lock should be unavailable')

    @unittest.skipUnless(sys.platform == 'win32', 'Backend nativo exige Windows')
    def test_real_keyring_backend_with_mocked_credential_api(self):
        # Nenhuma chamada chega ao cofre: ambas as APIs nativas são substituídas.
        from keyring.backends import Windows
        key = Fernet.generate_key().decode('ascii')
        missing = Windows.pywintypes.error(1168, 'CredRead', 'not found')
        credential = {'UserName': 'master-key-v1', 'CredentialBlob': key.encode('utf-16')}
        with patch.object(Windows.win32cred, 'CredRead', side_effect=[missing, credential]), \
                patch.object(Windows.win32cred, 'CredWrite') as write, \
                patch('keyring.set_keyring') as set_global:
            store = WindowsVaultKeyStore()
            store.write(key)
            self.assertEqual(key, store.read())
            set_global.assert_not_called()
        write.assert_called_once()
        saved = write.call_args.args[0]
        self.assertEqual('IRIS.Vault', saved['TargetName'])
        self.assertEqual('master-key-v1', saved['UserName'])
        self.assertEqual(Windows.win32cred.CRED_PERSIST_LOCAL_MACHINE, saved['Persist'])
        self.assertEqual(key, saved['CredentialBlob'])

    @unittest.skipUnless(sys.platform == 'win32', 'Mutex nativo exige Windows')
    def test_native_mutex_serializes_creation_and_migration_between_processes(self):
        context = multiprocessing.get_context('spawn')
        for migration in (False, True):
            with self.subTest(migration=migration), tempfile.TemporaryDirectory() as root:
                engine = create_engine(f"sqlite:///{Path(root) / 'vault.db'}")
                try:
                    Base.metadata.create_all(engine)
                    legacy_key = Fernet.generate_key()
                    if migration:
                        (Path(root) / '.iris_vault.key').write_bytes(legacy_key)
                        with sessionmaker(bind=engine)() as db:
                            db.add(VaultKey(name='LEGACY', encrypted_value=Fernet(legacy_key).encrypt(b'legacy').decode()))
                            db.commit()
                    with context.Manager() as manager:
                        state = manager.Namespace()
                        state.key = None
                        state.writes = 0
                        ready = context.Barrier(2)
                        results = context.Queue()
                        processes = [context.Process(target=create_in_process,
                            args=(root, state, ready, results, index)) for index in range(2)]
                        try:
                            for process in processes:
                                process.start()
                            for process in processes:
                                process.join(20)
                                self.assertEqual(0, process.exitcode)
                            self.assertEqual([None, None], [results.get(timeout=2) for _ in processes])
                            self.assertEqual(1, state.writes)
                            if migration:
                                self.assertEqual(legacy_key.decode(), state.key)
                            cipher = Fernet(state.key)
                            with sessionmaker(bind=engine)() as db:
                                for index in range(2):
                                    value = db.query(VaultKey).filter_by(name=f'KEY_{index}').one().encrypted_value
                                    self.assertEqual(f'value-{index}', cipher.decrypt(value).decode())
                            self.assertFalse((Path(root) / '.iris_vault.key').exists())
                        finally:
                            for process in processes:
                                if process.is_alive():
                                    process.terminate()
                                    process.join(5)
                            results.close()
                finally:
                    engine.dispose()
