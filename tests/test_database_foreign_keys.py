import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.db import Base, enable_sqlite_foreign_keys
from database.models import Module


class DatabaseForeignKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "foreign-keys.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        self.addCleanup(self.engine.dispose)
        enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def test_sqlite_foreign_keys_are_enabled_for_each_connection(self) -> None:
        with self.engine.connect() as connection:
            enabled = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        self.assertEqual(1, enabled)

    def test_missing_parent_is_rejected_by_database(self) -> None:
        db = self.session_factory()
        try:
            db.add(
                Module(
                    module_public_key="orphan",
                    name="Órfão",
                    call_name="orfao",
                    parent_module_id=999,
                )
            )
            with self.assertRaises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    unittest.main()
