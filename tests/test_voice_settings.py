import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
import database.models  # noqa: F401
from repositories.voice_settings_repository import VoiceSettingsRepository
from services.voice_settings import VoiceSettings


class VoiceSettingsTests(unittest.TestCase):
    def test_default_settings_are_lightweight_and_disabled(self) -> None:
        settings = VoiceSettings()
        self.assertFalse(settings.enabled)
        self.assertEqual("basic", settings.mode)
        self.assertEqual("cpu", settings.device)
        self.assertEqual("int8", settings.compute_type)

    def test_rejects_invalid_realtime_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, "intervalo em tempo real"):
            VoiceSettings(realtime_processing_pause=0.01).validate()

    def test_repository_round_trip(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            repository = VoiceSettingsRepository(db)
            saved = repository.save(
                VoiceSettings(enabled=True, mode="realtime", proper_names="Caio")
            )
            loaded = repository.get()
        finally:
            db.close()

        self.assertEqual(saved, loaded)
        self.assertTrue(loaded.enabled)
        self.assertEqual("realtime", loaded.mode)
        self.assertEqual("Caio", loaded.proper_names)


if __name__ == "__main__":
    unittest.main()
