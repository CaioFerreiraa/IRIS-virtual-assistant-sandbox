from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.db import Base


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    call_name = Column(String(100), nullable=False)
    custom_call_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    request_method = Column(String(10), nullable=True)
    request_url = Column(String(255), nullable=True)
    is_executable = Column(Boolean, default=False)

    parent_module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    edited_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent_module = relationship(
        "Module",
        remote_side=[id],
        back_populates="child_modules",
    )
    child_modules = relationship(
        "Module",
        back_populates="parent_module",
        cascade="all, delete-orphan",
    )
    logs = relationship("Log", back_populates="module")
    routine_actions = relationship("RoutineAction", back_populates="module")


class Routine(Base):
    __tablename__ = "routine"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    cron_expression = Column(String(100), nullable=True)

    active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    routine_actions = relationship("RoutineAction", back_populates="routine")
    logs = relationship("Log", back_populates="routine")


class RoutineAction(Base):
    __tablename__ = "routine_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    routine_id = Column(Integer, ForeignKey("routine.id"), nullable=False)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)

    execution_order = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, default=True)

    routine = relationship("Routine", back_populates="routine_actions")
    module = relationship("Module", back_populates="routine_actions")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)
    routine_id = Column(Integer, ForeignKey("routine.id"), nullable=True)

    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    module = relationship("Module", back_populates="logs")
    routine = relationship("Routine", back_populates="logs")


class VoiceSetting(Base):
    __tablename__ = "voice_settings"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=False)
    mode = Column(String(20), nullable=False, default="basic")
    language = Column(String(10), nullable=False, default="pt")
    model_size = Column(String(100), nullable=False, default="small")
    realtime_model_size = Column(String(100), nullable=False, default="tiny")
    device = Column(String(20), nullable=False, default="cpu")
    compute_type = Column(String(30), nullable=False, default="int8")
    input_device_index = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=False, default=16000)
    audio_threshold = Column(Float, nullable=False, default=0.025)
    silence_duration = Column(Float, nullable=False, default=1.2)
    min_recording_duration = Column(Float, nullable=False, default=0.5)
    realtime_processing_pause = Column(Float, nullable=False, default=0.3)
    beam_size = Column(Integer, nullable=False, default=5)
    realtime_beam_size = Column(Integer, nullable=False, default=3)
    batch_size = Column(Integer, nullable=False, default=0)
    realtime_batch_size = Column(Integer, nullable=False, default=0)
    vad_filter = Column(Boolean, nullable=False, default=True)
    silero_sensitivity = Column(Float, nullable=False, default=0.4)
    webrtc_sensitivity = Column(Integer, nullable=False, default=3)
    proper_names = Column(Text, nullable=False, default="")
    context = Column(Text, nullable=False, default="")
    hotwords = Column(Text, nullable=False, default="")
    condition_on_previous_text = Column(Boolean, nullable=False, default=True)
    temperature = Column(Float, nullable=False, default=0.0)
