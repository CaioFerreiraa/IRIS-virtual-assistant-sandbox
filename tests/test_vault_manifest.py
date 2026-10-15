import json
from pathlib import Path
import tempfile
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from database.models import Module, VaultKey
from services.module_manifest import ManifestValidationError, parse_module_manifest
from services.module_registry_service import ModuleRegistryService
from services.module_validation import validate_module_folder, ModuleFolderValidationError
from tests.module_test_utils import build_manifest, build_http_request, create_module_folder


class VaultManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_optional_declaration_is_backwards_compatible(self):
        data = build_manifest()
        folder = create_module_folder(self.root, 'example', data)
        self.assertEqual((), parse_module_manifest(data, folder).vault_keys)
        data['vault_keys'] = ['NOTES_ACCESS_KEY', '_SECOND2']
        self.assertEqual(('NOTES_ACCESS_KEY', '_SECOND2'), parse_module_manifest(data, folder).vault_keys)

    def test_invalid_names_types_and_duplicates_are_rejected_by_shared_validation(self):
        for names in (None, 'KEY', [1], [{}], ['lowercase'], ['1KEY'], ['A-B'], [''], ['KEY', 'KEY']):
            with self.subTest(names=names):
                data = build_manifest()
                data['vault_keys'] = names
                folder = create_module_folder(self.root, 'example', data)
                with self.assertRaises(ManifestValidationError):
                    parse_module_manifest(data, folder)
                with self.assertRaises(ModuleFolderValidationError):
                    validate_module_folder(folder)

    def test_registry_syncs_names_without_creating_keys_and_can_remove_declaration(self):
        engine = create_engine(f"sqlite:///{self.root / 'registry.db'}")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        installed = self.root / 'installed'
        data = build_manifest()
        data['vault_keys'] = ['NOTES_ACCESS_KEY']
        folder = create_module_folder(installed, 'example', data)
        registry = ModuleRegistryService(installed, factory)
        self.assertEqual((), registry.sync().invalid_modules)
        with factory() as db:
            self.assertEqual(['NOTES_ACCESS_KEY'], json.loads(db.query(Module).one().vault_keys_json))
            self.assertEqual(0, db.query(VaultKey).count())
        del data['vault_keys']
        (folder / 'module.json').write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual((), registry.sync().invalid_modules)
        with factory() as db:
            self.assertEqual('[]', db.query(Module).one().vault_keys_json)

    def test_sensitive_http_fields_accept_references_but_reject_literals(self):
        for body in ({'mode': 'raw_json', 'content': '{"token":"{{vk.NOTES_ACCESS_KEY}}"}'},
                     {'mode': 'raw_text', 'content': 'token={{vk.NOTES_ACCESS_KEY}}'}):
            data = build_manifest(runtime=None, http_request=build_http_request(
                url='https://example.com/?token={{vk.NOTES_ACCESS_KEY}}',
                headers=[{'key': 'Authorization', 'value': '{{vk.NOTES_ACCESS_KEY}}', 'description': '', 'enabled': True}],
                body=body))
            data['vault_keys'] = ['NOTES_ACCESS_KEY']
            folder = create_module_folder(self.root, 'example', data)
            self.assertIsNotNone(parse_module_manifest(data, folder).http_request)
            data['http_request']['headers'][0]['value'] = 'literal-demo-value'
            with self.assertRaises(ManifestValidationError):
                parse_module_manifest(data, folder)

    def test_full_url_reference_is_valid_without_accessing_vault(self):
        data = build_manifest(runtime=None, http_request=build_http_request(url="{{vk.SERVICE_URL}}/items"))
        data["vault_keys"] = ["SERVICE_URL"]
        folder = create_module_folder(self.root, "example", data)
        self.assertEqual("{{vk.SERVICE_URL}}/items", parse_module_manifest(data, folder).http_request.url)

    def test_http_response_vault_must_be_declared_and_have_simple_json_path(self):
        data = build_manifest(runtime=None, http_request=build_http_request())
        data['vault_keys'] = ['TOKEN_NOTAS']
        data['http_request']['response_vault'] = {
            'key': 'TOKEN_NOTAS', 'path': 'data.token',
        }
        folder = create_module_folder(self.root, 'example', data)
        mapping = parse_module_manifest(data, folder).http_request.response_vault
        self.assertEqual(('TOKEN_NOTAS', 'data.token'), (mapping.key, mapping.path))
        data['http_request']['response_vault']['key'] = 'UNDECLARED'
        with self.assertRaisesRegex(ManifestValidationError, 'declarada'):
            parse_module_manifest(data, folder)
        data['http_request']['response_vault'] = {
            'key': 'TOKEN_NOTAS', 'path': 'data[0].token',
        }
        with self.assertRaisesRegex(ManifestValidationError, 'caminho JSON'):
            parse_module_manifest(data, folder)

    def test_argument_is_not_allowed_as_a_secret_reference(self):
        data = build_manifest(runtime=None, http_request=build_http_request(
            body={"mode": "raw_json", "content": '{"token":"{{argument}}"}'}))
        folder = create_module_folder(self.root, "example", data)
        with self.assertRaises(ManifestValidationError):
            parse_module_manifest(data, folder)
