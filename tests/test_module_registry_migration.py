import importlib
import tempfile
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION = importlib.import_module(
    "migrations.versions.f8c1d4a7b2e9_add_module_registry"
)


class ModuleRegistryMigrationTests(unittest.TestCase):
    def test_alembic_command_upgrades_an_existing_unstamped_schema(self) -> None:
        engine = self._build_previous_head_database(with_module=True)
        database_url = str(engine.url)
        engine.dispose()

        project_root = Path(__file__).resolve().parents[1]
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.stamp(config, "e5f7a9c2d4b1")
        command.upgrade(config, "head")

        migrated_engine = sa.create_engine(database_url)
        self.addCleanup(migrated_engine.dispose)
        with migrated_engine.connect() as connection:
            revision = connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            self.assertEqual("f8c1d4a7b2e9", revision)
            self.assertEqual([], connection.execute(sa.text("PRAGMA foreign_key_check")).fetchall())

    def test_upgrade_previous_head_with_existing_module(self) -> None:
        engine = self._build_previous_head_database(with_module=True)
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            self._run_upgrade(connection)
            row = connection.execute(
                sa.text(
                    "SELECT module_public_key, is_available FROM modules WHERE id = 1"
                )
            ).one()
            self.assertEqual("legacy.module-1", row.module_public_key)
            self.assertEqual(1, row.is_available)
            tables = set(sa.inspect(connection).get_table_names())
            self.assertIn("module_variable_definitions", tables)
            self.assertIn("module_variable_values", tables)

    def test_upgrade_previous_head_with_empty_module_table(self) -> None:
        engine = self._build_previous_head_database(with_module=False)
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            self._run_upgrade(connection)
            columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns("modules")
            }
            self.assertIn("module_public_key", columns)
            self.assertIn("auto_start_enabled", columns)

    def test_upgrade_recovers_from_leftover_batch_table(self) -> None:
        engine = self._build_previous_head_database(with_module=True)
        self.addCleanup(engine.dispose)
        metadata = sa.MetaData()
        with engine.begin() as connection:
            metadata.reflect(connection)
            modules = metadata.tables["modules"]
            modules.to_metadata(sa.MetaData(), name="_alembic_tmp_modules").create(connection)
            self._create_variable_tables(connection)

            self._run_upgrade(connection)

            inspector = sa.inspect(connection)
            self.assertNotIn("_alembic_tmp_modules", inspector.get_table_names())
            self.assertIn("module_public_key", {
                column["name"] for column in inspector.get_columns("modules")
            })

    def _build_previous_head_database(self, *, with_module: bool):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        database_path = Path(temporary_directory.name) / "migration.db"
        engine = sa.create_engine(f"sqlite:///{database_path}")
        metadata = sa.MetaData()
        modules = sa.Table(
            "modules",
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("call_name", sa.String(100), nullable=False),
            sa.Column("custom_call_name", sa.String(100)),
            sa.Column("description", sa.Text()),
            sa.Column("request_method", sa.String(10)),
            sa.Column("request_url", sa.String(255)),
            sa.Column("is_executable", sa.Boolean()),
            sa.Column(
                "parent_module_id",
                sa.Integer(),
                sa.ForeignKey(
                    "modules.id",
                ),
            ),
            sa.Column("created_date", sa.DateTime()),
            sa.Column("edited_date", sa.DateTime()),
        )
        metadata.create_all(engine)
        if with_module:
            with engine.begin() as connection:
                connection.execute(
                    modules.insert().values(
                        id=1,
                        name="Legado",
                        call_name="legado",
                    )
                )
        return engine

    def _run_upgrade(self, connection) -> None:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            MIGRATION.upgrade()

    def _create_variable_tables(self, connection) -> None:
        metadata = sa.MetaData()
        sa.Table(
            "module_variable_definitions",
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("module_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(100), nullable=False),
            sa.Column("label", sa.String(150), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("type", sa.String(30), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False),
            sa.Column("is_user_editable", sa.Boolean(), nullable=False),
            sa.Column("default_value", sa.Text()),
            sa.Column("display_order", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
        )
        sa.Table(
            "module_variable_values",
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("variable_definition_id", sa.Integer(), nullable=False),
            sa.Column("value_text", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        metadata.create_all(connection)


if __name__ == "__main__":
    unittest.main()
