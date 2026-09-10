from sqlalchemy.orm import Session

from database.models import GeneralSetting
from services.general_settings import GeneralSettings


class GeneralSettingsRepository:
    SETTINGS_ID = 1

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> GeneralSettings:
        record = self.db.get(GeneralSetting, self.SETTINGS_ID)
        if record is None:
            return GeneralSettings()
        return GeneralSettings(
            background_execution_enabled=record.background_execution_enabled,
            listening_overlay_enabled=record.listening_overlay_enabled,
        )

    def save(self, settings: GeneralSettings) -> GeneralSettings:
        record = self.db.get(GeneralSetting, self.SETTINGS_ID)
        if record is None:
            record = GeneralSetting(id=self.SETTINGS_ID)
            self.db.add(record)

        record.background_execution_enabled = settings.background_execution_enabled
        record.listening_overlay_enabled = settings.listening_overlay_enabled
        try:
            self.db.commit()
            self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise
        return GeneralSettings(
            background_execution_enabled=record.background_execution_enabled,
            listening_overlay_enabled=record.listening_overlay_enabled,
        )
