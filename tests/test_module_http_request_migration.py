import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


REVISION = "d9f2a6c4e1b8"
PREVIOUS_REVISION = "b7e4a1c9d2f6"


class ModuleHttpRequestMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "migration.db"
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
        command.stamp(self.config, PREVIOUS_REVISION)

    def test_upgrade_creates_empty_http_request_table(self) -> None:
        command.upgrade(self.config, REVISION)

        engine = sa.create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            self.assertIn("module_http_requests", inspector.get_table_names())
            self.assertEqual(
                0,
                connection.execute(
                    sa.text("SELECT COUNT(*) FROM module_http_requests")
                ).scalar_one(),
            )
            foreign_keys = inspector.get_foreign_keys("module_http_requests")
            self.assertEqual(["module_id"], foreign_keys[0]["constrained_columns"])
            unique_constraints = inspector.get_unique_constraints(
                "module_http_requests"
            )
            self.assertTrue(
                any(
                    constraint["column_names"] == ["module_id"]
                    for constraint in unique_constraints
                )
            )

    def test_upgrade_downgrade_and_upgrade_again(self) -> None:
        command.upgrade(self.config, REVISION)
        command.downgrade(self.config, PREVIOUS_REVISION)

        engine = sa.create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            self.assertNotIn(
                "module_http_requests",
                sa.inspect(connection).get_table_names(),
            )

        command.upgrade(self.config, REVISION)
        with engine.connect() as connection:
            self.assertIn(
                "module_http_requests",
                sa.inspect(connection).get_table_names(),
            )


if __name__ == "__main__":
    unittest.main()
