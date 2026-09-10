from database.db import SessionLocal
from repositories.general_settings_repository import GeneralSettingsRepository
from services.general_settings import GeneralSettings


class GeneralSettingsService:
    def load(self) -> GeneralSettings:
        db = SessionLocal()
        try:
            return GeneralSettingsRepository(db).get()
        finally:
            db.close()

    def save(self, settings: GeneralSettings) -> GeneralSettings:
        db = SessionLocal()
        try:
            return GeneralSettingsRepository(db).save(settings)
        finally:
            db.close()
