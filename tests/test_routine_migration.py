import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


REVISION = "a1f6d8c3b9e2"
PREVIOUS_REVISION = "e4b7c2d9a6f1"


class RoutineMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "migration.db"
        self.database_url = f"sqlite:///{database_path}"
        project_root = Path(__file__).resolve().parents[1]
        self.config = Config(str(project_root / "alembic.ini"))
        self.config.set_main_option("sqlalchemy.url", self.database_url)

    def test_upgrade_head_on_empty_database_creates_routine_fields(self) -> None:
        self._create_previous_schema()
        command.stamp(self.config, PREVIOUS_REVISION)
        command.upgrade(self.config, REVISION)

        engine = sa.create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            routine_columns = {
                column["name"] for column in inspector.get_columns("routine")
            }
            action_columns = {
                column["name"]
                for column in inspector.get_columns("routine_actions")
            }
            self.assertIn("stop_on_failure", routine_columns)
            self.assertIn("deleted_at", routine_columns)
            self.assertIn("argument", action_columns)

    def test_existing_routines_receive_safe_default(self) -> None:
        self._create_previous_schema()
        command.stamp(self.config, PREVIOUS_REVISION)
        engine = sa.create_engine(self.database_url)
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO routine (name, cron_expression, active, created_at) "
                    "VALUES ('Legada', '0 8 * * mon', 1, CURRENT_TIMESTAMP)"
                )
            )

        command.upgrade(self.config, REVISION)

        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT stop_on_failure, deleted_at FROM routine "
                    "WHERE name = 'Legada'"
                )
            ).one()
            self.assertEqual(1, row.stop_on_failure)
            self.assertIsNone(row.deleted_at)

    def _create_previous_schema(self) -> None:
        engine = sa.create_engine(self.database_url)
        try:
            metadata = sa.MetaData()
            sa.Table(
                "routine",
                metadata,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("name", sa.String(100), nullable=False),
                sa.Column("cron_expression", sa.String(100), nullable=True),
                sa.Column("active", sa.Boolean(), nullable=True),
                sa.Column("last_run_at", sa.DateTime(), nullable=True),
                sa.Column("created_at", sa.DateTime(), nullable=True),
            )
            sa.Table(
                "routine_actions",
                metadata,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("routine_id", sa.Integer(), nullable=False),
                sa.Column("module_id", sa.Integer(), nullable=False),
                sa.Column("execution_order", sa.Integer(), nullable=False),
                sa.Column("active", sa.Boolean(), nullable=True),
            )
            metadata.create_all(engine)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
