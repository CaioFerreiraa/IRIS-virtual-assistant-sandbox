import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


PREVIOUS_REVISION = "d9f2a6c4e1b8"
REVISION = "e4b7c2d9a6f1"


class ModuleHttpCustomizationMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "customization.db"
        self.database_url = f"sqlite:///{database_path}"
        project_root = Path(__file__).resolve().parents[1]
        self.config = Config(str(project_root / "alembic.ini"))
        self.config.set_main_option("sqlalchemy.url", self.database_url)

        engine = sa.create_engine(self.database_url)
        try:
            metadata = sa.MetaData()
            sa.Table(
                "modules",
                metadata,
                sa.Column("id", sa.Integer(), primary_key=True),
            )
            metadata.create_all(engine)
        finally:
            engine.dispose()
        command.stamp(self.config, "b7e4a1c9d2f6")
        command.upgrade(self.config, PREVIOUS_REVISION)

    def test_upgrade_adds_false_customization_flag_to_existing_rows(self) -> None:
        engine = sa.create_engine(self.database_url)
        try:
            with engine.begin() as connection:
                connection.execute(sa.text("INSERT INTO modules (id) VALUES (1)"))
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO module_http_requests (
                            module_id, method, url, argument_enabled,
                            params_json, authorization_json, headers_json,
                            body_json, scripts_json, created_at, updated_at
                        ) VALUES (
                            1, 'GET', 'https://example.com', 0,
                            '[]', '{"type":"none"}', '[]',
                            '{"mode":"none","content":""}',
                            '{"pre_request":"","post_response":""}',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
        finally:
            engine.dispose()

        command.upgrade(self.config, REVISION)

        engine = sa.create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "module_http_requests"
                )
            }
            self.assertIn("is_customized", columns)
            self.assertEqual(
                0,
                connection.execute(
                    sa.text("SELECT is_customized FROM module_http_requests")
                ).scalar_one(),
            )

    def test_upgrade_downgrade_and_upgrade_again(self) -> None:
        command.upgrade(self.config, REVISION)
        command.downgrade(self.config, PREVIOUS_REVISION)

        engine = sa.create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "module_http_requests"
                )
            }
            self.assertNotIn("is_customized", columns)

        command.upgrade(self.config, REVISION)
        with engine.connect() as connection:
            columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "module_http_requests"
                )
            }
            self.assertIn("is_customized", columns)


if __name__ == "__main__":
    unittest.main()
