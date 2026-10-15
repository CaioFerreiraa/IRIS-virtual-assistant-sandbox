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
        self.service = VaultService(self.factory, self.key_path)

    def test_create_encrypts_and_lists_only_metadata(self):
        self.assertFalse(self.key_path.exists())
        self.service.create(' notes_access_key ', 'demo-private-value', 'Notas')
        with self.factory() as db:
            key = db.query(VaultKey).one()
            self.assertEqual('NOTES_ACCESS_KEY', key.name)
            self.assertNotIn('demo-private-value', key.encrypted_value)
            self.assertEqual('demo-private-value', Fernet(self.key_path.read_bytes()).decrypt(key.encrypted_value).decode())
            self.assertFalse(key.allow_iris_update)
        with patch.object(self.service, '_decrypt', side_effect=AssertionError('Não deve ler valores')):
            keys = self.service.list_metadata()
        self.assertEqual('NOTES_ACCESS_KEY', keys[0]['name'])
        self.assertNotIn('encrypted_value', keys[0])
        self.assertNotIn('value', keys[0])
        self.assertNotIn('demo-private-value', str(keys))

    def test_decrypts_unicode_and_reuses_local_key(self):
        self.service.create('FIRST', 'demonstração ç🔑')
        original_key = self.key_path.read_bytes()
        service = VaultService(self.factory, self.key_path)
        service.create('SECOND', 'outro valor')
        self.assertEqual(original_key, self.key_path.read_bytes())
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
        self.key_path.unlink()
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
        self.service.update_value_by_iris('TOKEN_NOTAS', 'issued-token')
        self.assertEqual('issued-token', self.service.get_value('TOKEN_NOTAS'))
        self.assertTrue(self.key_path.exists())

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

    def test_missing_key_file_is_not_replaced(self):
        self.service.create('FIXED', 'original')
        self.key_path.unlink()
        with self.assertRaisesRegex(ValueError, 'Restaure'):
            self.service.get_value('FIXED')
        with self.assertRaises(ValueError):
            self.service.create('SECOND', 'another')
        self.assertFalse(self.key_path.exists())
        self.assertEqual(1, len(self.service.list_metadata()))

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
        self.key_path.write_bytes(Fernet.generate_key())
        with self.assertRaisesRegex(ValueError, 'descriptografar') as caught:
            self.service.get_value('FIXED')
        self.assertNotIn(ciphertext, str(caught.exception))
        self.key_path.write_bytes(b'invalid-local-key')
        with self.assertRaisesRegex(ValueError, 'inválido') as caught:
            self.service.get_value('FIXED')
        self.assertNotIn('invalid-local-key', str(caught.exception))

    def test_concurrent_first_use_reuses_one_key(self):
        def create(index):
            VaultService(self.factory, self.key_path).create(f'KEY_{index}', f'value-{index}')
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(create, range(4)))
        for index in range(4):
            self.assertEqual(f'value-{index}', self.service.get_value(f'KEY_{index}'))
