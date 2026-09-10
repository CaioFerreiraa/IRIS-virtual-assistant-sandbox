from dataclasses import dataclass


@dataclass(frozen=True)
class GeneralSettings:
    background_execution_enabled: bool = True
    listening_overlay_enabled: bool = True
