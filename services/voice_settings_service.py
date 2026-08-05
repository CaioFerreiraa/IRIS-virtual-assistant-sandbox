from dataclasses import replace

from database.db import SessionLocal
from repositories.module_repository import ModuleRepository
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

    def load_for_runtime(self) -> VoiceSettings:
        """Carrega a configuração e acrescenta nomes de módulos somente ao prompt interno."""
        return self._with_module_context(self.load())

    def save(self, settings: VoiceSettings) -> VoiceSettings:
        db = SessionLocal()
        try:
            saved_settings = VoiceSettingsRepository(db).save(settings)
        finally:
            db.close()

        self.speech_manager.apply_settings(self._with_module_context(saved_settings))
        return saved_settings

    def _with_module_context(self, settings: VoiceSettings) -> VoiceSettings:
        db = SessionLocal()
        try:
            call_names = ModuleRepository(db).list_call_names()
        finally:
            db.close()

        if not call_names:
            return settings

        module_context = f"Comandos conhecidos pela IRIS: {', '.join(call_names)}."
        combined_context = " ".join(part for part in (settings.context.strip(), module_context) if part)
        return replace(settings, context=combined_context)
