from dataclasses import dataclass
from enum import StrEnum


class ArgumentSource(StrEnum):
    EMPTY = "empty"
    VOICE = "voice"
    MANUAL = "manual"
    SAVED_DEFAULT = "saved_default"


class VoiceSubmissionReason(StrEnum):
    READY = "ready"
    HOME_INACTIVE = "home_inactive"
    EXPLICIT_CONFIRMATION_REQUIRED = "explicit_confirmation_required"
    ARGUMENT_SEARCH_PENDING = "argument_search_pending"
    MULTIPLE_ARGUMENT_MATCHES = "multiple_argument_matches"
    MODULE_NOT_FOUND = "module_not_found"
    AMBIGUOUS_MODULE = "ambiguous_module"
    MODULE_NOT_EXECUTABLE = "module_not_executable"
    EXECUTION_IN_PROGRESS = "execution_in_progress"
    REQUIRED_ARGUMENT_EMPTY = "required_argument_empty"


@dataclass(frozen=True)
class VoiceSubmissionState:
    session_id: str
    command_revision: int
    module_id: int | None
    module_path: str
    is_executable: bool
    is_ambiguous: bool
    argument: str
    argument_source: ArgumentSource
    argument_required: bool
    argument_match_count: int | None
    requires_explicit_confirmation: bool
    is_home_active: bool
    is_executing: bool


@dataclass(frozen=True)
class VoiceSubmissionDecision:
    can_submit: bool
    reason: VoiceSubmissionReason


class VoiceSubmissionService:
    @staticmethod
    def evaluate_silence(state: VoiceSubmissionState) -> VoiceSubmissionDecision:
        invalid = VoiceSubmissionService._evaluate_common(state)
        if invalid is not None:
            return invalid
        if state.requires_explicit_confirmation:
            return VoiceSubmissionDecision(
                False,
                VoiceSubmissionReason.EXPLICIT_CONFIRMATION_REQUIRED,
            )
        if state.argument and state.argument_match_count is None:
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.ARGUMENT_SEARCH_PENDING)
        if state.argument_match_count is not None and state.argument_match_count > 1:
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.MULTIPLE_ARGUMENT_MATCHES)
        return VoiceSubmissionDecision(True, VoiceSubmissionReason.READY)

    @staticmethod
    def evaluate_explicit(state: VoiceSubmissionState) -> VoiceSubmissionDecision:
        invalid = VoiceSubmissionService._evaluate_common(state)
        if invalid is not None:
            return invalid
        return VoiceSubmissionDecision(True, VoiceSubmissionReason.READY)

    @staticmethod
    def _evaluate_common(state: VoiceSubmissionState) -> VoiceSubmissionDecision | None:
        if state.is_ambiguous:
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.AMBIGUOUS_MODULE)
        if state.module_id is None or not state.module_path:
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.MODULE_NOT_FOUND)
        if not state.is_executable:
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.MODULE_NOT_EXECUTABLE)
        if state.is_executing:
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.EXECUTION_IN_PROGRESS)
        if state.argument_required and not state.argument.strip():
            return VoiceSubmissionDecision(False, VoiceSubmissionReason.REQUIRED_ARGUMENT_EMPTY)
        return None
