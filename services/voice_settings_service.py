from database.db import SessionLocal
from repositories.voice_settings_repository import VoiceSettingsRepository
from services.speech_service_manager import SpeechServiceManager
from services.voice_settings import VoiceSettings


class VoiceSettingsService:
    def __init__(self, speech_manager: SpeechServiceManager):
        self.speech_manager = speech_manager

    def load(self) -> VoiceSettings:
        db = SessionLocal()
        try:
            return VoiceSettingsRepository(db).get()
        finally:
            db.close()

    def save(self, settings: VoiceSettings) -> VoiceSettings:
        db = SessionLocal()
        try:
            saved_settings = VoiceSettingsRepository(db).save(settings)
        finally:
            db.close()

        self.speech_manager.apply_settings(saved_settings)
        return saved_settings
