from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from database.models import Module, VaultKey
from services.vault_service import VaultService
from tests.vault_test_utils import MemoryKeyStore


class VaultServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = create_engine(f"sqlite:///{self.root / 'vault.db'}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.key_path = self.root / '.iris_vault.key'
        self.key_store = MemoryKeyStore()
        self.service = VaultService(self.factory, self.key_path, key_store=self.key_store)

    def test_create_encrypts_and_lists_only_metadata(self):
        self.assertFalse(self.key_path.exists())
        self.service.create(' notes_access_key ', 'demo-private-value', 'Notas')
        with self.factory() as db:
            key = db.query(VaultKey).one()
            self.assertEqual('NOTES_ACCESS_KEY', key.name)
            self.assertNotIn('demo-private-value', key.encrypted_value)
            self.assertEqual('demo-private-value', Fernet(self.key_store.key).decrypt(key.encrypted_value).decode())
            self.assertFalse(key.allow_iris_update)
        with patch.object(self.service, '_decrypt', side_effect=AssertionError('Não deve ler valores')):
            keys = self.service.list_metadata()
        self.assertEqual('NOTES_ACCESS_KEY', keys[0]['name'])
        self.assertNotIn('encrypted_value', keys[0])
        self.assertNotIn('value', keys[0])
        self.assertNotIn('demo-private-value', str(keys))

    def test_decrypts_unicode_and_reuses_master_key(self):
        self.service.create('FIRST', 'demonstração ç🔑')
        original_key = self.key_store.key
        service = VaultService(self.factory, self.key_path, key_store=self.key_store)
        service.create('SECOND', 'outro valor')
        self.assertEqual(original_key, self.key_store.key)
        self.assertEqual(1, self.key_store.writes)
        self.assertFalse(self.key_path.exists())
        self.assertEqual('demonstração ç🔑', service.get_value('first'))
        self.assertIsNone(service.get_value('MISSING'))

    def test_update_empty_clears_value_and_preserves_name(self):
        self.service.create('FIXED', 'original')
        key_id = self.service.list_metadata()[0]['id']
        self.service.update(key_id, description='Nova descrição', new_value='', allow_iris_update=True)
        with self.factory() as db:
            key = db.get(VaultKey, key_id)
            self.assertIsNone(key.encrypted_value)
            self.assertEqual('FIXED', key.name)
            self.assertEqual('Nova descrição', key.description)
            self.assertTrue(key.allow_iris_update)
        self.assertIsNone(self.service.get_value('FIXED'))

    def test_user_can_update_value_without_iris_permission(self):
        self.service.create('FIXED', 'original')
        self.service.update(self.service.list_metadata()[0]['id'], new_value='replaced')
        self.assertEqual('replaced', self.service.get_value('FIXED'))

    def test_update_can_preserve_existing_encrypted_value(self):
        self.service.create('FIXED', 'original')
        key_id = self.service.list_metadata()[0]['id']
        with self.factory() as db:
            original_ciphertext = db.get(VaultKey, key_id).encrypted_value
        self.service.update(key_id, description='Atualizada',
                            new_value='••••••••', keep_existing_value=True)
        with self.factory() as db:
            key = db.get(VaultKey, key_id)
            self.assertEqual(original_ciphertext, key.encrypted_value)
            self.assertEqual('Atualizada', key.description)
        self.assertEqual('original', self.service.get_value('FIXED'))

    def test_delete_does_not_need_decryption(self):
        self.service.create('FIXED', 'original')
        key_id = self.service.list_metadata()[0]['id']
        self.key_store.key = None
        self.service.delete(key_id)
        self.assertEqual([], self.service.list_metadata())
        self.assertIsNone(self.service.get_value('FIXED'))

    def test_invalid_names_null_values_and_duplicates(self):
        for name in ('', '1ABC', 'A-B', 'A B', 'A.B', 'AÇÃO', 'ß', None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.service.create(name, 'example')
        self.service.create('EMPTY', None)
        self.assertIsNone(self.service.get_value('EMPTY'))
        self.assertFalse(next(key['has_value'] for key in self.service.list_metadata()
                              if key['name'] == 'EMPTY'))
        self.service.create('DUPLICATE', 'one')
        with self.assertRaisesRegex(ValueError, 'já está cadastrada'):
            self.service.create('duplicate', 'two')

    def test_first_null_key_can_receive_value_later(self):
        self.service.create('TOKEN_NOTAS', None, allow_iris_update=True)
        self.assertFalse(self.key_path.exists())
        self.assertEqual(0, self.key_store.writes)
        self.service.update_value_by_iris('TOKEN_NOTAS', 'issued-token')
        self.assertEqual('issued-token', self.service.get_value('TOKEN_NOTAS'))
        self.assertFalse(self.key_path.exists())
        self.assertEqual(1, self.key_store.writes)

    def test_iris_update_is_blocked_by_default(self):
        self.service.create('FIXED', 'original')
        with self.assertRaisesRegex(ValueError, 'permissão'):
            self.service.update_value_by_iris('FIXED', 'replaced')
        self.assertEqual('original', self.service.get_value('FIXED'))

    def test_iris_update_is_allowed_when_enabled(self):
        self.service.create('FIXED', 'original', allow_iris_update=True)
        self.service.update_value_by_iris('fixed', 'replaced')
        self.assertEqual('replaced', self.service.get_value('FIXED'))

    def test_modules_using_are_computed_from_declarations(self):
        self.service.create('FIXED', 'original')
        with self.factory() as db:
            db.add_all([
                Module(module_public_key='declares', name='Usa', call_name='usa', vault_keys_json='["FIXED"]'),
                Module(module_public_key='other', name='Outro', call_name='outro', vault_keys_json='["FIXED_SUFFIX"]'),
            ])
            db.commit()
        self.assertEqual(['Usa'], [module['name'] for module in self.service.modules_using('fixed')])
        self.assertEqual(['Usa'], [module['name'] for module in self.service.list_metadata()[0]['modules']])

    def test_available_names_include_only_declared_configured_keys(self):
        self.service.create('AVAILABLE', 'original')
        self.service.create('OTHER', 'other')
        self.service.create('EMPTY', None)
        with self.factory() as db:
            module = Module(
                module_public_key='available',
                name='Available',
                call_name='available',
                vault_keys_json='["AVAILABLE","EMPTY","MISSING"]',
            )
            db.add(module)
            db.commit()
            module_id = module.id
        with patch.object(self.service, '_decrypt', side_effect=AssertionError('must not decrypt')):
            self.assertEqual(('AVAILABLE',), self.service.available_names(module_id))

    def test_missing_master_key_is_not_replaced(self):
        self.service.create('FIXED', 'original')
        self.key_store.key = None
        with self.assertRaisesRegex(ValueError, 'indisponível'):
            self.service.get_value('FIXED')
        with self.assertRaises(ValueError):
            self.service.create('SECOND', 'another')
        self.assertFalse(self.key_path.exists())
        self.assertEqual(1, len(self.service.list_metadata()))
        self.assertIsNone(self.key_store.key)
        self.assertEqual(1, self.key_store.writes)

    def test_corruption_and_wrong_key_do_not_expose_values(self):
        self.service.create('FIXED', 'original-private-value')
        with self.factory() as db:
            record = db.query(VaultKey).one()
            ciphertext = record.encrypted_value
            record.encrypted_value = 'corrupt-demo-value'
            db.commit()
        with self.assertRaisesRegex(ValueError, 'descriptografar') as caught:
            self.service.get_value('FIXED')
        self.assertNotIn('corrupt-demo-value', str(caught.exception))
        with self.factory() as db:
            db.query(VaultKey).one().encrypted_value = ciphertext
            db.commit()
        self.key_store.key = Fernet.generate_key().decode('ascii')
        with self.assertRaisesRegex(ValueError, 'descriptografar') as caught:
            self.service.get_value('FIXED')
        self.assertNotIn(ciphertext, str(caught.exception))
        self.key_store.key = 'invalid-local-key'
        with self.assertRaisesRegex(ValueError, 'inválida') as caught:
            self.service.get_value('FIXED')
        self.assertNotIn('invalid-local-key', str(caught.exception))

    def test_concurrent_first_use_reuses_one_key(self):
        def create(index):
            VaultService(self.factory, self.key_path, key_store=self.key_store).create(f'KEY_{index}', f'value-{index}')
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(create, range(4)))
        for index in range(4):
            self.assertEqual(f'value-{index}', self.service.get_value(f'KEY_{index}'))
        self.assertEqual(1, self.key_store.writes)
        self.assertFalse(self.key_path.exists())

    def prepare_legacy(self):
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        values = {
            'FIRST': Fernet(key).encrypt('demonstração'.encode()).decode('ascii'),
            'SECOND': Fernet(key).encrypt(b'another-test-value').decode('ascii'),
        }
        with self.factory() as db:
            db.add_all([VaultKey(name=name, encrypted_value=value) for name, value in values.items()])
            db.add(VaultKey(name='EMPTY', encrypted_value=None))
            db.commit()
        return key.decode('ascii'), values

    def assert_ciphertexts(self, expected):
        with self.factory() as db:
            actual = {row.name: row.encrypted_value for row in db.query(VaultKey)
                      if row.encrypted_value is not None}
        self.assertEqual(expected, actual)

    def test_migration_preserves_key_ciphertexts_and_is_idempotent(self):
        key, values = self.prepare_legacy()
        self.assertEqual('demonstração', self.service.get_value('FIRST'))
        self.assertFalse(self.key_path.exists())
        self.assertEqual(key, self.key_store.key)
        self.assertEqual(1, self.key_store.writes)
        service = VaultService(self.factory, self.key_path, key_store=self.key_store)
        self.assertEqual('another-test-value', service.get_value('SECOND'))
        self.assertEqual(1, self.key_store.writes)
        self.assert_ciphertexts(values)

    def test_interruption_after_write_is_resumed_without_overwrite(self):
        key, values = self.prepare_legacy()
        with patch.object(self.key_store, 'read', side_effect=[None, ValueError('Leitura indisponível')]):
            with self.assertRaisesRegex(ValueError, 'Leitura indisponível'):
                self.service.get_value('FIRST')
        self.assertEqual(key, self.key_path.read_text())
        self.assertEqual(key, self.key_store.key)
        self.assertEqual('demonstração', self.service.get_value('FIRST'))
        self.assertFalse(self.key_path.exists())
        self.assertEqual(1, self.key_store.writes)
        self.assert_ciphertexts(values)

    def test_failed_write_preserves_legacy_and_database(self):
        key, values = self.prepare_legacy()
        with patch.object(self.key_store, 'write', side_effect=ValueError('Gravação indisponível')):
            with self.assertRaisesRegex(ValueError, 'Gravação indisponível'):
                self.service.get_value('FIRST')
        self.assertEqual(key, self.key_path.read_text())
        self.assertIsNone(self.key_store.key)
        self.assert_ciphertexts(values)

    def test_failed_confirmation_preserves_legacy_and_database(self):
        key, values = self.prepare_legacy()
        with patch.object(self.key_store, 'read', side_effect=[None, None]):
            with self.assertRaisesRegex(ValueError, 'confirmar'):
                self.service.get_value('FIRST')
        self.assertEqual(key, self.key_path.read_text())
        self.assertEqual(key, self.key_store.key)
        self.assert_ciphertexts(values)
        self.assertEqual('demonstração', self.service.get_value('FIRST'))
        self.assertEqual(1, self.key_store.writes)

    def test_different_confirmation_preserves_legacy_without_overwriting_credential(self):
        key, values = self.prepare_legacy()
        other_key = Fernet.generate_key().decode('ascii')
        def write_conflicting_key(value):
            self.key_store.key = other_key
        with patch.object(self.key_store, 'write', side_effect=write_conflicting_key):
            with self.assertRaisesRegex(ValueError, 'confirmar'):
                self.service.get_value('FIRST')
        with self.assertRaisesRegex(ValueError, 'conflito'):
            self.service.get_value('FIRST')
        self.assertEqual(key, self.key_path.read_text())
        self.assertEqual(other_key, self.key_store.key)
        self.assert_ciphertexts(values)

    def test_failed_removal_can_be_retried(self):
        key, values = self.prepare_legacy()
        with patch.object(Path, 'unlink', side_effect=PermissionError('sensitive-file-details')):
            with self.assertRaisesRegex(ValueError, 'remover') as caught:
                self.service.get_value('FIRST')
        self.assertNotIn('sensitive-file-details', str(caught.exception))
        self.assertEqual(key, self.key_path.read_text())
        self.assertEqual(key, self.key_store.key)
        self.assertEqual('demonstração', self.service.get_value('FIRST'))
        self.assertEqual(1, self.key_store.writes)
        self.assertFalse(self.key_path.exists())
        self.assert_ciphertexts(values)

    def test_conflicting_or_invalid_credential_preserves_both_keys(self):
        key, values = self.prepare_legacy()
        for stored in (Fernet.generate_key().decode('ascii'), '', 'invalid-key', 'não-ascii'):
            with self.subTest(stored_valid=bool(stored)):
                self.key_store.key = stored
                with self.assertRaises(ValueError) as caught:
                    self.service.get_value('FIRST')
                self.assertNotIn(key, str(caught.exception))
                self.assertEqual(key, self.key_path.read_text())
                self.assertEqual(stored, self.key_store.key)
                self.assertEqual(0, self.key_store.writes)
                self.assert_ciphertexts(values)

    def test_invalid_legacy_file_is_never_replaced(self):
        for key in (b'', b'invalid-key', b'\xff\xfe'):
            with self.subTest(key=key):
                self.key_path.write_bytes(key)
                with self.assertRaisesRegex(ValueError, 'inválid'):
                    self.service.create('FIRST', 'test-value')
                self.assertEqual(key, self.key_path.read_bytes())
                self.assertIsNone(self.key_store.key)
                self.assertEqual([], self.service.list_metadata())
        self.assertEqual(0, self.key_store.writes)

    def test_migration_checks_all_non_null_values_before_writing_or_removing(self):
        key, values = self.prepare_legacy()
        with self.factory() as db:
            db.query(VaultKey).filter_by(name='SECOND').one().encrypted_value = 'corrupt-ciphertext'
            db.commit()
        values['SECOND'] = 'corrupt-ciphertext'
        for stored in (None, key):
            with self.subTest(credential_exists=stored is not None):
                self.key_store.key = stored
                with self.assertRaisesRegex(ValueError, 'validar') as caught:
                    self.service.get_value('FIRST')
                self.assertNotIn('corrupt-ciphertext', str(caught.exception))
                self.assertEqual(key, self.key_path.read_text())
                self.assertEqual(0, self.key_store.writes)
                self.assert_ciphertexts(values)

    def test_valid_but_wrong_legacy_key_is_preserved(self):
        _, values = self.prepare_legacy()
        wrong_key = Fernet.generate_key()
        self.key_path.write_bytes(wrong_key)
        with self.assertRaisesRegex(ValueError, 'validar'):
            self.service.get_value('FIRST')
        self.assertEqual(wrong_key, self.key_path.read_bytes())
        self.assertIsNone(self.key_store.key)
        self.assert_ciphertexts(values)

    def test_concurrent_migration_writes_once(self):
        key, values = self.prepare_legacy()
        def read(index):
            return VaultService(self.factory, self.key_path, key_store=self.key_store).get_value('FIRST')
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(['demonstração'] * 8, list(pool.map(read, range(8))))
        self.assertEqual(key, self.key_store.key)
        self.assertEqual(1, self.key_store.writes)
        self.assertFalse(self.key_path.exists())
        self.assert_ciphertexts(values)

    def test_first_write_requires_confirmed_credential(self):
        with patch.object(self.key_store, 'read', return_value=None):
            with self.assertRaisesRegex(ValueError, 'confirmar'):
                self.service.create('FIRST', 'test-value')
        self.assertEqual([], self.service.list_metadata())
        self.assertFalse(self.key_path.exists())
        # A gravação anterior pode ter funcionado; reutilize em vez de substituir.
        self.service.create('FIRST', 'test-value')
        self.assertEqual(1, self.key_store.writes)
        self.assertEqual('test-value', self.service.get_value('FIRST'))

    def test_empty_key_and_metadata_operations_never_access_master_key(self):
        self.service.create('FIXED', 'test-value')
        with self.factory() as db:
            module = Module(module_public_key='metadata', name='Metadados', call_name='metadados',
                            vault_keys_json='["FIXED","EMPTY"]')
            db.add(module)
            db.commit()
            module_id = module.id
        master_key = self.key_store.key
        with patch.object(self.key_store, 'locked', side_effect=AssertionError('must not access store')):
            self.service.create('EMPTY', None, allow_iris_update=True)
            self.service.create('ALSO_EMPTY', '')
            self.assertIsNone(self.service.get_value('EMPTY'))
            self.assertEqual(('FIXED',), self.service.available_names(module_id))
            self.assertEqual(('FIXED', 'EMPTY'), self.service.declared_names(module_id))
            self.assertEqual(1, len(self.service.modules_using('FIXED')))
            self.service.ensure_iris_update_allowed('EMPTY')
            key_id = next(key['id'] for key in self.service.list_metadata() if key['name'] == 'FIXED')
            self.service.update(key_id, description='Descrição', keep_existing_value=True)
            self.service.update(key_id, new_value='')
            self.service.delete(key_id)
        self.assertEqual(master_key, self.key_store.key)

    def test_metadata_is_available_outside_windows_and_crypto_fails_lazily(self):
        with patch('services.vault_key_store.sys.platform', 'linux'):
            service = VaultService(self.factory, self.key_path)
            service.create('EMPTY', None)
            self.assertFalse(service.list_metadata()[0]['has_value'])
            with self.assertRaisesRegex(ValueError, 'indisponível.*sistema'):
                service.create('FIRST', 'test-value')
            service.delete(service.list_metadata()[0]['id'])
        self.assertFalse(self.key_path.exists())

    def test_missing_credential_rechecks_database_even_with_stale_allow_create(self):
        self.service.create('FIRST', 'test-value')
        self.key_store.key = None
        with patch('services.vault_service.Fernet.generate_key') as generate:
            with self.assertRaisesRegex(ValueError, 'indisponível'):
                self.service._fernet(allow_create=True)
        generate.assert_not_called()
        self.assertIsNone(self.key_store.key)
