from sqlalchemy.orm import Session

from database.models import VoiceSetting
from services.voice_settings import VoiceSettings


class VoiceSettingsRepository:
    SETTINGS_ID = 1

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> VoiceSettings:
        record = self.db.get(VoiceSetting, self.SETTINGS_ID)
        if record is None:
            return VoiceSettings()
        return self._to_settings(record)

    def save(self, settings: VoiceSettings) -> VoiceSettings:
        settings.validate()
        record = self.db.get(VoiceSetting, self.SETTINGS_ID)
        if record is None:
            record = VoiceSetting(id=self.SETTINGS_ID)
            self.db.add(record)

        for field_name in VoiceSettings.__dataclass_fields__:
            setattr(record, field_name, getattr(settings, field_name))

        try:
            self.db.commit()
            self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise
        return self._to_settings(record)

    def _to_settings(self, record: VoiceSetting) -> VoiceSettings:
        return VoiceSettings(
            **{
                field_name: getattr(record, field_name)
                for field_name in VoiceSettings.__dataclass_fields__
            }
        )
