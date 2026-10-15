from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
import database.db as database


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'e3a6c9f1d2b4'
HTTP_RESPONSE_REVISION = 'a9d7c4b2e6f1'
VAULT_REVISION = 'c8a2f6d4e9b1'
PREVIOUS_HEAD = 'b4e6f8a0c2d3'


class VaultMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = sa.create_engine(f"sqlite:///{Path(self.temp.name) / 'migration.db'}")
        self.addCleanup(self.engine.dispose)
        self.config = Config(str(PROJECT_ROOT / 'alembic.ini'))
        self.config.set_main_option('sqlalchemy.url', str(self.engine.url))

    def assert_vault_schema(self):
        inspector = sa.inspect(self.engine)
        self.assertEqual({'id', 'name', 'description', 'encrypted_value', 'allow_iris_update', 'created_date', 'edited_date'},
                         {column['name'] for column in inspector.get_columns('vault_keys')})
        self.assertTrue(next(column['nullable'] for column in inspector.get_columns('vault_keys')
                             if column['name'] == 'encrypted_value'))
        self.assertIn('vault_keys_json', {column['name'] for column in inspector.get_columns('modules')})
        self.assertIn('response_vault_json', {
            column['name'] for column in inspector.get_columns('module_http_requests')
        })
        self.assertEqual(['name'], inspector.get_unique_constraints('vault_keys')[0]['column_names'])
        with self.engine.connect() as connection:
            self.assertEqual(REVISION, connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one())
            self.assertEqual(0, connection.execute(sa.text('SELECT COUNT(*) FROM vault_keys')).scalar_one())
            self.assertEqual([], connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall())

    def test_upgrade_new_database_and_single_head(self):
        self.assertEqual([REVISION], ScriptDirectory.from_config(self.config).get_heads())
        command.upgrade(self.config, 'head')
        self.assert_vault_schema()
        command.upgrade(self.config, 'head')
        self.assert_vault_schema()

    def prepare_existing_database(self):
        command.upgrade(self.config, 'head')
        command.downgrade(self.config, PREVIOUS_HEAD)
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        with self.engine.begin() as connection:
            connection.execute(metadata.tables['modules'].insert().values(
                id=1, module_public_key='legacy.example', name='Legado', call_name='legado',
                call_aliases_json='["alias"]', icon='extension', is_executable=True, is_available=True,
                supports_auto_start=False, auto_start_enabled=False))
            connection.execute(metadata.tables['logs'].insert().values(id=1, module_id=1, status='success', message='Histórico preservado'))

    def test_upgrade_existing_database_preserves_modules_and_history(self):
        self.prepare_existing_database()
        command.upgrade(self.config, 'head')
        self.assert_vault_schema()
        with self.engine.connect() as connection:
            row = connection.execute(sa.text('SELECT name, call_aliases_json, vault_keys_json FROM modules WHERE id=1')).one()
            self.assertEqual(('Legado', '["alias"]', '[]'), tuple(row))
            self.assertEqual('Histórico preservado', connection.execute(sa.text('SELECT message FROM logs')).scalar_one())
        command.downgrade(self.config, PREVIOUS_HEAD)
        self.assertNotIn('vault_keys', sa.inspect(self.engine).get_table_names())
        command.upgrade(self.config, 'head')
        self.assert_vault_schema()

    def test_http_response_vault_upgrade_preserves_existing_request(self):
        command.upgrade(self.config, 'head')
        command.downgrade(self.config, VAULT_REVISION)
        with self.engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO modules (id, module_public_key, name, call_name, "
                "call_aliases_json, vault_keys_json, icon, is_executable, "
                "is_available, supports_auto_start, auto_start_enabled) "
                "VALUES (1, 'example.http', 'HTTP', 'http', '[]', '[]', "
                "'extension', 1, 1, 0, 0)"
            ))
            connection.execute(sa.text(
                "INSERT INTO module_http_requests "
                "(module_id, method, url, argument_enabled, params_json, "
                "authorization_json, headers_json, body_json, scripts_json, "
                "is_customized, created_at, updated_at) "
                "VALUES (1, 'POST', 'https://example.com', 0, '[]', "
                "'{\"type\":\"none\"}', '[]', '{\"mode\":\"none\",\"content\":\"\"}', "
                "'{\"pre_request\":\"\",\"post_response\":\"\"}', 0, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
        command.upgrade(self.config, 'head')
        with self.engine.connect() as connection:
            self.assertEqual(
                ('POST', 'https://example.com', 'null'),
                tuple(connection.execute(sa.text(
                    "SELECT method, url, response_vault_json FROM module_http_requests"
                )).one()),
            )

    def test_nullable_value_upgrade_preserves_existing_ciphertext(self):
        command.upgrade(self.config, 'head')
        command.downgrade(self.config, HTTP_RESPONSE_REVISION)
        with self.engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO vault_keys "
                "(name, encrypted_value, allow_iris_update, created_date, edited_date) "
                "VALUES ('EXISTING', 'ciphertext-fixture', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
        command.upgrade(self.config, 'head')
        self.assertTrue(next(column['nullable'] for column in sa.inspect(self.engine).get_columns('vault_keys')
                             if column['name'] == 'encrypted_value'))
        with self.engine.begin() as connection:
            self.assertEqual(
                'ciphertext-fixture',
                connection.execute(sa.text(
                    "SELECT encrypted_value FROM vault_keys WHERE name='EXISTING'"
                )).scalar_one(),
            )
            connection.execute(sa.text(
                "INSERT INTO vault_keys "
                "(name, encrypted_value, allow_iris_update, created_date, edited_date) "
                "VALUES ('EMPTY', NULL, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
        with self.assertRaisesRegex(RuntimeError, 'Vault Keys sem valor'):
            command.downgrade(self.config, HTTP_RESPONSE_REVISION)

    def test_init_db_upgrades_existing_unstamped_current_schema(self):
        self.prepare_existing_database()
        with self.engine.begin() as connection:
            connection.exec_driver_sql('DROP TABLE alembic_version')
        with patch.object(database, 'engine', self.engine), patch.object(database, 'SessionLocal', sessionmaker(bind=self.engine)):
            database.init_db()
        self.assert_vault_schema()

    def test_init_db_creates_empty_database_and_is_idempotent(self):
        with patch.object(database, 'engine', self.engine), patch.object(database, 'SessionLocal', sessionmaker(bind=self.engine)):
            database.init_db()
            database.init_db()
        self.assert_vault_schema()
