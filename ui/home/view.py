import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import flet as ft
import ui.home as ui
from services.home_service import HomeService, ModuleArgumentContext
from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from services.voice_submission_service import (
    ArgumentSource,
    VoiceSubmissionReason,
    VoiceSubmissionService,
    VoiceSubmissionState,
)
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import PASTEL_DARK_PURPLE
from ui.theme.fonts import TITLE_FONT


LOGO_PATH = "assets/images/logo_transparent.png"
MAX_DROPDOWN_HEIGHT = 360
VOICE_SUBMIT_DELAY_SECONDS = 2.0
HOME_ROUTES = {"", "/", "/home"}


def build_home_view(
    module_options: Sequence[ui.dropdowns.ModuleOption] | None = None,
    toaster_handler: ToasterHandler | None = None,
    speech_manager: SpeechServiceManager | None = None,
) -> ft.Container:
    # Cria a tela home conectando view, dropdowns e servico.
    return HomeViewState(module_options, toaster_handler, speech_manager).build()


class HomeViewState:
    def __init__(
        self,
        module_options: Sequence[ui.dropdowns.ModuleOption] | None = None,
        toaster_handler: ToasterHandler | None = None,
        speech_manager: SpeechServiceManager | None = None,
    ):
        # Guarda dependencias gerais da home.
        self.module_options = tuple(ui.dropdowns.sort_modules(module_options or ()))
        self.executable_lookup = ui.dropdowns.module_executable_lookup(self.module_options)
        self.home_service = HomeService()
        self.toaster_handler = toaster_handler
        self.speech_manager = speech_manager
        self.is_loading = False
        self.is_voice_active = False
        self.is_basic_capture_active = False
        self.active_voice_session_id = ""
        self.command_revision = 0
        self._voice_submit_task = None
        self.argument_source = ArgumentSource.EMPTY
        self.requires_explicit_confirmation = False
        self.argument_match_count: int | None = None
        self._argument_context_cache: dict[int, ModuleArgumentContext] = {}
        self.controls: HomeViewControls | None = None
        self.dropdowns: ui.dropdowns.HomeDropdowns | None = None

    def build(self) -> ft.Container:
        # Monta a view e inicializa o gerenciador de dropdowns.
        callbacks = HomeViewCallbacks(
            on_send=self.attempt_explicit_submit,
            on_command_change=self.refresh_module_suggestions,
            on_command_focus=self.show_module_suggestions_from_event,
            on_command_click=self.show_module_suggestions_from_event,
            on_argument_submit=self.execute_argument_from_event,
            on_argument_change=self.show_argument_suggestions_from_event,
            on_dropdown_click=self.keep_dropdowns_open,
            on_background_click=self.hide_dropdowns,
            on_input_shell_click=self.show_module_suggestions_from_shell,
            on_input_shell_hover=self.on_input_shell_hover,
            on_clear_command=self.clear_command_input,
        )
        self.controls = build_home_controls(callbacks)
        self.dropdowns = ui.dropdowns.HomeDropdowns(
            module_options=self.module_options,
            executable_lookup=self.executable_lookup,
            controls=self.controls,
            search_arguments=self.home_service.search_module_arguments,
            on_select_module=self.select_module,
            on_select_argument=self.select_argument,
            update_control=self.update_if_ready,
            dropdown_height=MAX_DROPDOWN_HEIGHT,
        )
        if self.speech_manager is not None:
            self.speech_manager.subscribe(self.on_speech_event, persistent=True)
        return self.controls.root

    def _controls(self) -> "HomeViewControls":
        # Retorna os controles da tela depois que a view foi montada.
        if self.controls is None:
            raise RuntimeError("HomeViewState ainda nao foi construido.")
        return self.controls

    def _dropdowns(self) -> ui.dropdowns.HomeDropdowns:
        # Retorna o gerenciador dos dropdowns depois da montagem.
        if self.dropdowns is None:
            raise RuntimeError("HomeDropdowns ainda nao foi construido.")
        return self.dropdowns

    def update_if_ready(self, control: ft.Control) -> None:
        # Atualiza um controle apenas quando ele ja esta conectado a uma page.
        try:
            page = control.page
        except RuntimeError:
            return

        if page:
            control.update()

    def hide_dropdowns(self, e=None) -> None:
        # Fecha todos os dropdowns.
        self._dropdowns().hide_all(e)

    def clear_command_input(self, e=None) -> None:
        # Limpa texto, argumento e selecao atual do modulo.
        self._cancel_voice_submit()
        controls = self._controls()
        controls.command_input_field.value = ""
        controls.argument_input_field.value = ""
        self.argument_source = ArgumentSource.EMPTY
        self.requires_explicit_confirmation = False
        self.argument_match_count = None
        self._dropdowns().clear_selected_module()
        self._set_module_icon(None)
        self.sync_clear_button_visibility()
        self.hide_dropdowns()
        self.update_if_ready(controls.command_input_field)
        self.update_if_ready(controls.argument_input_field)
        if self.speech_manager is not None:
            self.speech_manager.deactivate_command()

    def on_speech_event(self, event: SpeechEvent) -> None:
        controls = self._controls()
        try:
            page = controls.root.page
        except RuntimeError:
            return
        if page is not None:
            page.run_task(self._apply_speech_event, event)

    async def _apply_speech_event(self, event: SpeechEvent) -> None:
        controls = self._controls()
        if event.kind == SpeechEventKind.CAPTURE_STARTED:
            self._cancel_voice_submit()
            self.is_basic_capture_active = True
            if not self.is_voice_active:
                ui.input.set_voice_hint_text(controls.voice_hint, "Ouvindo...")
                controls.voice_hint.visible = True
                ui.input.set_input_shell_voice_active(controls.input_shell, True, pulse=True)
                self.update_if_ready(controls.voice_hint)
                self.update_if_ready(controls.input_shell)
            return

        if event.kind == SpeechEventKind.CAPTURE_FINISHED:
            self.is_basic_capture_active = False
            if not self.is_voice_active:
                controls.voice_hint.visible = False
                ui.input.set_input_shell_voice_active(controls.input_shell, False)
                self.update_if_ready(controls.voice_hint)
                self.update_if_ready(controls.input_shell)
            return

        if event.kind == SpeechEventKind.ACTIVATED:
            self._cancel_voice_submit()
            self.is_voice_active = True
            self.active_voice_session_id = event.session_id
            ui.input.set_voice_hint_text(controls.voice_hint, "IRIS ativada")
            controls.voice_hint.visible = True
            ui.input.set_input_shell_voice_active(controls.input_shell, True, pulse=True)
            self.update_if_ready(controls.input_shell)
            self.update_if_ready(controls.voice_hint)
            await controls.command_input_field.focus()
            await asyncio.sleep(0.35)
            if self.is_voice_active:
                ui.input.set_input_shell_voice_active(controls.input_shell, True)
                self.update_if_ready(controls.input_shell)
            return

        if event.kind in {SpeechEventKind.PARTIAL, SpeechEventKind.FINAL}:
            self._cancel_voice_submit()
            self._apply_voice_text(event.text)
            if event.should_submit:
                self.attempt_explicit_submit()
            elif event.kind == SpeechEventKind.FINAL:
                self._schedule_voice_submit()
            return

        if event.kind in {SpeechEventKind.DEACTIVATED, SpeechEventKind.ERROR, SpeechEventKind.STOPPED}:
            self._cancel_voice_submit()
            self.is_voice_active = False
            self.is_basic_capture_active = False
            self.active_voice_session_id = ""
            controls.voice_hint.visible = False
            ui.input.set_input_shell_voice_active(controls.input_shell, False)
            self.update_if_ready(controls.voice_hint)
            self.update_if_ready(controls.input_shell)
            if event.kind == SpeechEventKind.ERROR and self.toaster_handler:
                self.toaster_handler.show_error(event.message, title="Voz indisponível")

    def _apply_voice_text(
        self,
        text: str,
        argument_source: ArgumentSource = ArgumentSource.VOICE,
    ) -> None:
        controls = self._controls()
        controls.command_input_field.value = text
        self.sync_clear_button_visibility()
        self.update_if_ready(controls.command_input_field)

        resolved = ui.dropdowns.resolve_voice_module_option(text, self.module_options)
        if resolved is None:
            self._clear_transient_selection()
            self._dropdowns().show_module_suggestions(text)
            return
        if resolved.ambiguous or resolved.module_id is None:
            self._clear_transient_selection()
            self._dropdowns().show_module_suggestions(text)
            return

        previous_module_id = self._dropdowns().selected_module_id
        if previous_module_id != resolved.module_id:
            self._clear_transient_selection()
        self._dropdowns().selected_module_id = resolved.module_id
        self._dropdowns().selected_module_path = resolved.path
        self._set_module_icon(resolved.module_id)
        context = self._module_argument_context(resolved.module_id)
        self.requires_explicit_confirmation = context.saved_default is not None

        if resolved.argument:
            self.argument_source = argument_source
            self._open_argument_dropdown(resolved.module_id, resolved.path)
            controls.argument_input_field.value = resolved.argument
            self.update_if_ready(controls.argument_input_field)
            if context.supports_search:
                self._request_argument_suggestions(resolved.argument)
            else:
                self.argument_match_count = 0
            return

        if context.saved_default is not None:
            self.argument_source = ArgumentSource.SAVED_DEFAULT
            self._open_argument_dropdown(resolved.module_id, resolved.path)
            controls.argument_input_field.value = context.saved_default
            self.update_if_ready(controls.argument_input_field)
            if context.supports_search:
                self._request_argument_suggestions(context.saved_default)
            else:
                self.argument_match_count = 0
            return

        if context.required:
            self.argument_source = ArgumentSource.EMPTY
            self._open_argument_dropdown(resolved.module_id, resolved.path)
            self._request_argument_suggestions("")
            return

        self.argument_match_count = 0
        self._dropdowns().show_module_suggestions(resolved.path)

    def _open_argument_dropdown(self, module_id: int, module_path: str) -> None:
        self._dropdowns().open_argument_dropdown(
            module_id,
            module_path,
            load_suggestions=False,
        )

    def _clear_transient_selection(self) -> None:
        controls = self._controls()
        controls.argument_input_field.value = ""
        self.argument_source = ArgumentSource.EMPTY
        self.requires_explicit_confirmation = False
        self.argument_match_count = None
        self._dropdowns().clear_selected_module()
        self._dropdowns().hide_argument_suggestions()
        self._set_module_icon(None)
        self.update_if_ready(controls.argument_input_field)

    def _module_argument_context(self, module_id: int) -> ModuleArgumentContext:
        if module_id not in self._argument_context_cache:
            self._argument_context_cache[module_id] = (
                self.home_service.get_module_argument_context(module_id)
            )
        return self._argument_context_cache[module_id]

    def _module_has_arguments(self, module_id: int) -> bool:
        return self._module_argument_context(module_id).supports_search

    def _submit_voice_command(self, text: str) -> None:
        self._apply_voice_text(text)
        self.attempt_explicit_submit()

    def keep_dropdowns_open(self, e=None) -> None:
        # Mantem cliques internos dos dropdowns sem fechar nada.
        self._dropdowns().keep_open(e)

    def refresh_module_suggestions(self, e) -> None:
        # Atualiza o dropdown de modulos quando o texto principal muda.
        self._cancel_voice_submit()
        if self.speech_manager is not None:
            self.speech_manager.replace_active_command(e.control.value or "")
        if self.is_voice_active:
            self._apply_voice_text(
                e.control.value or "",
                argument_source=ArgumentSource.MANUAL,
            )
            self._schedule_voice_submit()
            return
        self.argument_source = ArgumentSource.EMPTY
        self.requires_explicit_confirmation = False
        self.argument_match_count = None
        self.sync_clear_button_visibility()
        self._set_module_icon(None)
        self._dropdowns().refresh_module_suggestions(e)

    def show_module_suggestions_from_event(self, e) -> None:
        # Abre sugestoes de modulos a partir do evento do input.
        self._dropdowns().show_module_suggestions_from_event(e)

    def show_module_suggestions_from_shell(self, e=None) -> None:
        # Abre sugestoes de modulos quando o shell e clicado.
        self._dropdowns().show_module_suggestions_from_shell(e)

    def show_argument_suggestions_from_event(self, e) -> None:
        # Atualiza sugestoes de argumentos a partir do input secundario.
        self._cancel_voice_submit()
        argument = (e.control.value or "").strip()
        self.argument_source = ArgumentSource.MANUAL if argument else ArgumentSource.EMPTY
        if self.is_voice_active and self.speech_manager is not None:
            module_path = self._dropdowns().selected_module_path or ""
            command = self._voice_command_with_argument(module_path, argument)
            self.speech_manager.replace_active_command(command)
        self._request_argument_suggestions(argument)
        if self.is_voice_active:
            self._schedule_voice_submit()

    def _request_argument_suggestions(self, query: str) -> None:
        dropdowns = self._dropdowns()
        module_id = dropdowns.selected_module_id
        if module_id is None:
            return
        self.argument_match_count = None
        try:
            page = self._controls().root.page
        except RuntimeError:
            page = None
        if page is None:
            arguments = self.home_service.search_module_arguments(module_id, query)
            self._apply_argument_suggestion_results(
                module_id,
                query,
                self.command_revision,
                self.active_voice_session_id,
                arguments,
            )
            return
        page.run_thread(
            self._search_arguments_background,
            page,
            module_id,
            query,
            self.command_revision,
            self.active_voice_session_id,
        )

    def _search_arguments_background(
        self,
        page: ft.Page,
        module_id: int,
        query: str,
        request_revision: int,
        request_session_id: str,
    ) -> None:
        arguments = self.home_service.search_module_arguments(module_id, query)
        page.run_task(
            self._apply_argument_suggestions,
            module_id,
            query,
            request_revision,
            request_session_id,
            arguments,
        )

    async def _apply_argument_suggestions(
        self,
        module_id: int,
        query: str,
        request_revision: int,
        request_session_id: str,
        arguments: Sequence[ui.argument_dropdown.ArgumentOption],
    ) -> None:
        was_applied = self._apply_argument_suggestion_results(
            module_id,
            query,
            request_revision,
            request_session_id,
            arguments,
        )
        if was_applied and self.is_voice_active:
            self._schedule_voice_submit()

    def _apply_argument_suggestion_results(
        self,
        module_id: int,
        query: str,
        request_revision: int,
        request_session_id: str,
        arguments: Sequence[ui.argument_dropdown.ArgumentOption],
    ) -> bool:
        dropdowns = self._dropdowns()
        if (
            request_revision != self.command_revision
            or request_session_id != self.active_voice_session_id
            or dropdowns.selected_module_id != module_id
        ):
            return False
        current_query = self._controls().argument_input_field.value or ""
        if current_query != query:
            return False
        self.argument_match_count = len(arguments)
        dropdowns.apply_argument_suggestions(arguments)
        if self.is_voice_active and len(arguments) == 1:
            argument = ui.argument_dropdown.argument_value(arguments[0])
            self._controls().argument_input_field.value = argument
            self.update_if_ready(self._controls().argument_input_field)
            if (
                self.speech_manager is not None
                and self.argument_source != ArgumentSource.SAVED_DEFAULT
            ):
                command = self._voice_command_with_argument(
                    dropdowns.selected_module_path or "",
                    argument,
                )
                self.speech_manager.replace_active_command(command)
        return True

    def _cancel_voice_submit(self) -> None:
        self.command_revision += 1
        task = self._voice_submit_task
        self._voice_submit_task = None
        if task is not None and not task.done():
            task.cancel()

    def _schedule_voice_submit(self) -> None:
        if not self.is_voice_active:
            return
        try:
            page = self._controls().root.page
        except RuntimeError:
            return
        if page is None:
            return

        state = self._build_voice_submission_state(page)
        if not VoiceSubmissionService.evaluate_silence(state).can_submit:
            return

        self._cancel_voice_submit()
        revision = self.command_revision
        session_id = self.active_voice_session_id
        self._voice_submit_task = page.run_task(
            self._submit_voice_command_after_silence,
            page,
            revision,
            session_id,
        )

    async def _submit_voice_command_after_silence(
        self,
        page: ft.Page,
        revision: int,
        session_id: str,
    ) -> None:
        try:
            await asyncio.sleep(VOICE_SUBMIT_DELAY_SECONDS)
        except asyncio.CancelledError:
            return
        if revision != self.command_revision:
            return
        if not self.is_voice_active or session_id != self.active_voice_session_id:
            return
        self._voice_submit_task = None
        self.attempt_silence_submit(page=page)

    def _build_voice_submission_state(self, page: ft.Page | None = None) -> VoiceSubmissionState:
        controls = self._controls()
        resolved = ui.dropdowns.resolve_voice_module_option(
            controls.command_input_field.value or "",
            self.module_options,
        )
        dropdowns = self._dropdowns()
        module_id = resolved.module_id if resolved is not None else None
        module_path = resolved.path if resolved is not None else ""
        is_ambiguous = bool(resolved and resolved.ambiguous)
        is_preselected = bool(
            module_id is not None
            and dropdowns.selected_module_id == module_id
            and dropdowns.selected_module_path == module_path
        )
        if not is_preselected:
            module_id = None
            module_path = ""
        context = (
            self._module_argument_context(module_id)
            if module_id is not None
            else ModuleArgumentContext(False, False, None)
        )
        argument = (controls.argument_input_field.value or "").strip()
        if page is None:
            try:
                page = controls.root.page
            except RuntimeError:
                page = None
        return VoiceSubmissionState(
            session_id=self.active_voice_session_id,
            command_revision=self.command_revision,
            module_id=module_id,
            module_path=module_path,
            is_executable=bool(module_path and self.executable_lookup.get(module_path, False)),
            is_ambiguous=is_ambiguous,
            argument=argument,
            argument_source=self.argument_source,
            argument_required=context.required,
            argument_match_count=(
                self.argument_match_count if context.supports_search else 0
            ),
            requires_explicit_confirmation=self.requires_explicit_confirmation,
            is_home_active=bool(page is not None and (page.route or "/") in HOME_ROUTES),
            is_executing=self.is_loading,
        )

    def attempt_silence_submit(self, page: ft.Page | None = None) -> None:
        state = self._build_voice_submission_state(page)
        if not VoiceSubmissionService.evaluate_silence(state).can_submit:
            return
        self.send_request(
            argument=state.argument or None,
            module_id=state.module_id,
            module_path=state.module_path,
        )

    def attempt_explicit_submit(self, e: ft.ControlEvent | None = None) -> None:
        self._ensure_current_module_preselected()
        state = self._build_voice_submission_state()
        decision = VoiceSubmissionService.evaluate_explicit(state)
        if not decision.can_submit:
            self._show_submission_decision_error(decision.reason)
            return
        self._cancel_voice_submit()
        self.send_request(
            argument=state.argument or None,
            module_id=state.module_id,
            module_path=state.module_path,
        )

    def _ensure_current_module_preselected(self) -> None:
        controls = self._controls()
        resolved = ui.dropdowns.resolve_voice_module_option(
            controls.command_input_field.value or "",
            self.module_options,
        )
        if resolved is None or resolved.ambiguous or resolved.module_id is None:
            return
        dropdowns = self._dropdowns()
        if (
            dropdowns.selected_module_id == resolved.module_id
            and dropdowns.selected_module_path == resolved.path
        ):
            return
        self._apply_voice_text(
            controls.command_input_field.value or "",
            argument_source=ArgumentSource.MANUAL,
        )

    def _show_submission_decision_error(self, reason: VoiceSubmissionReason) -> None:
        messages = {
            VoiceSubmissionReason.MODULE_NOT_FOUND: "Escolha um módulo válido na lista de sugestões.",
            VoiceSubmissionReason.AMBIGUOUS_MODULE: (
                "O comando corresponde a mais de um módulo. Escolha um item da lista."
            ),
            VoiceSubmissionReason.MODULE_NOT_EXECUTABLE: (
                "O módulo selecionado não possui execução configurada."
            ),
            VoiceSubmissionReason.REQUIRED_ARGUMENT_EMPTY: (
                "Informe o argumento antes de executar o módulo."
            ),
        }
        if reason in messages:
            self.show_module_error(messages[reason])

    @staticmethod
    def _voice_command_with_argument(module_path: str, argument: str) -> str:
        command_path = " ".join(module_path.replace("/", " ").split())
        return " ".join((command_path, argument.strip())).strip()

    def validate_module_request(self) -> tuple[int, str]:
        # Garante que existe um modulo digitado ou selecionado.
        selected_module_id = self._dropdowns().selected_module_id
        selected_module_path = self._dropdowns().selected_module_path
        if selected_module_id is not None and selected_module_path:
            return selected_module_id, selected_module_path

        command = (self._controls().command_input_field.value or "").strip()
        if not command:
            raise ValueError("Informe um módulo para executar.")
        resolved = ui.dropdowns.resolve_typed_module(command, self.module_options)
        if resolved is None:
            raise ValueError("Escolha um módulo válido na lista de sugestões.")
        if resolved.ambiguous:
            raise ValueError("O comando corresponde a mais de um módulo. Escolha um item da lista.")
        if resolved.module_id is None:
            raise ValueError("Não foi possível identificar o módulo selecionado.")
        return resolved.module_id, resolved.path

    def send_request(
        self,
        e=None,
        argument: str | None = None,
        module_id: int | None = None,
        module_path: str | None = None,
    ) -> None:
        # Executa a rota atual ou abre a busca de argumentos quando necessario.
        controls = self._controls()
        if self.is_loading:
            return

        try:
            if module_id is None or module_path is None:
                module_id, module_path = self.validate_module_request()
        except Exception as error:
            self.show_module_error(str(error))
            return

        if argument is None and self._module_argument_context(module_id).required:
            self._dropdowns().open_argument_dropdown(
                module_id,
                module_path,
                load_suggestions=False,
            )
            self._request_argument_suggestions("")
            return

        self.is_loading = True
        ui.input.set_send_button_loading(controls.send_button, self.is_loading)
        self.update_if_ready(controls.send_button)

        try:
            page = controls.root.page
        except RuntimeError:
            page = None
        if page is None:
            try:
                result = self.home_service.execute_module(module_id, argument)
                self._apply_request_result(result, None)
            except Exception as error:
                self._apply_request_result(None, error)
            return
        page.run_thread(self._execute_request, page, module_id, argument)

    def _execute_request(
        self,
        page: ft.Page,
        module_id: int,
        argument: str | None,
    ) -> None:
        try:
            result = self.home_service.execute_module(module_id, argument)
            page.run_task(self._finish_request, result, None)
        except Exception as error:
            page.run_task(self._finish_request, None, error)

    async def _finish_request(
        self,
        result: dict | None,
        error: Exception | None,
    ) -> None:
        self._apply_request_result(result, error)

    def _apply_request_result(
        self,
        result: dict | None,
        error: Exception | None,
    ) -> None:
        controls = self._controls()
        if error is not None:
            self.show_module_error(str(error))
        elif result is not None and result.get("success", True):
            self.show_module_success(result)
            controls.command_input_field.value = ""
            controls.argument_input_field.value = ""
            self.argument_source = ArgumentSource.EMPTY
            self.requires_explicit_confirmation = False
            self.argument_match_count = None
            self._dropdowns().clear_selected_module()
            self._set_module_icon(None)
            self.sync_clear_button_visibility()
            self.update_if_ready(controls.command_input_field)
            self.update_if_ready(controls.argument_input_field)
        elif result is not None:
            self.show_module_error(self.result_message(result) or "O módulo retornou erro.")

        self.is_loading = False
        ui.input.set_send_button_loading(controls.send_button, self.is_loading)
        self.update_if_ready(controls.send_button)
        if self.speech_manager is not None:
            self.speech_manager.deactivate_command()

    def show_module_success(self, result: dict) -> None:
        if self.toaster_handler is None:
            return

        self.toaster_handler.show_success(
            message=self.result_message(result) or "Módulo executado com sucesso.",
            title="Módulo executado",
        )

    def show_module_error(self, message: str) -> None:
        if self.toaster_handler is None:
            return

        self.toaster_handler.show_error(
            message=message or "Não foi possível executar o módulo.",
            title="Erro no módulo",
        )

    def result_message(self, result: dict) -> str:
        if "message" in result:
            return str(result["message"])
        if "result" in result:
            return str(result["result"])
        if "opened" in result:
            return f"URL aberta: {result['opened']}"
        return ""

    def select_module(self, module_id: int, module_path: str) -> None:
        # Seleciona um modulo e decide se executa direto ou pede argumento.
        controls = self._controls()
        controls.command_input_field.value = module_path
        self.sync_clear_button_visibility()
        self.update_if_ready(controls.command_input_field)

        self._dropdowns().selected_module_id = module_id
        self._dropdowns().selected_module_path = module_path
        self._set_module_icon(module_id)
        context = self._module_argument_context(module_id)
        self.requires_explicit_confirmation = context.saved_default is not None
        self.argument_source = ArgumentSource.EMPTY
        self.argument_match_count = None
        if context.saved_default is not None:
            self._open_argument_dropdown(module_id, module_path)
            controls.argument_input_field.value = context.saved_default
            self.argument_source = ArgumentSource.SAVED_DEFAULT
            self.update_if_ready(controls.argument_input_field)
            if context.supports_search:
                self._request_argument_suggestions(context.saved_default)
            return
        if context.required:
            self._dropdowns().open_argument_dropdown(
                module_id,
                module_path,
                load_suggestions=False,
            )
            self._request_argument_suggestions("")
            return

        self.hide_dropdowns()
        self.send_request(argument=None, module_id=module_id, module_path=module_path)

    def execute_argument_from_event(self, e) -> None:
        # Executa o argumento digitado no input secundario.
        self.execute_selected_argument(e.control.value or "")

    def execute_selected_argument(self, argument: str) -> None:
        # Executa o modulo selecionado usando o argumento informado.
        if not argument:
            return

        self.argument_source = ArgumentSource.MANUAL
        self.hide_dropdowns()
        self.attempt_explicit_submit()

    def select_argument(self, argument: str) -> None:
        # Seleciona um argumento da lista e executa o modulo.
        controls = self._controls()
        controls.argument_input_field.value = argument
        self.argument_source = ArgumentSource.MANUAL
        self.update_if_ready(controls.argument_input_field)
        self.execute_selected_argument(argument)

    def on_input_shell_hover(self, e) -> None:
        # Atualiza o visual do shell quando o mouse entra ou sai.
        controls = self._controls()
        if not self.is_voice_active and not self.is_basic_capture_active:
            ui.input.set_input_shell_hovered(controls.input_shell, str(e.data).lower() == "true")
        self.update_if_ready(controls.input_shell)

    def sync_clear_button_visibility(self) -> None:
        controls = self._controls()
        has_command = bool((controls.command_input_field.value or "").strip())
        has_selected_module = bool(self.dropdowns and self.dropdowns.selected_module_path)
        controls.clear_button.visible = has_command or has_selected_module
        self.update_if_ready(controls.clear_button)

    def _set_module_icon(self, module_id: int | None) -> None:
        controls = self._controls()
        icon_name = "explore"
        if module_id is not None:
            for option in self.module_options:
                if ui.dropdowns.option_module_id(option) == module_id:
                    icon_name = ui.dropdowns.option_icon(option)
                    break
        controls.module_icon.value = icon_name
        self.update_if_ready(controls.module_icon)


@dataclass
class HomeViewCallbacks:
    on_send: Callable
    on_command_change: Callable
    on_command_focus: Callable
    on_command_click: Callable
    on_argument_submit: Callable
    on_argument_change: Callable
    on_dropdown_click: Callable
    on_background_click: Callable
    on_input_shell_click: Callable
    on_input_shell_hover: Callable
    on_clear_command: Callable


@dataclass
class HomeViewControls:
    root: ft.Container
    command_input_field: ft.TextField
    module_icon: ft.Text
    argument_input_field: ft.TextField
    send_button: ft.Container
    clear_button: ft.Container
    input_shell: ft.Container
    voice_hint: ft.Container
    module_panel: ft.Container
    argument_panel: ft.Container
    dropdown_stack: ft.Stack
    module_suggestions_list: ft.ListView
    argument_suggestions_list: ft.ListView


def build_home_controls(callbacks: HomeViewCallbacks) -> HomeViewControls:
    # Monta a tela home e devolve referencias dos controles atualizaveis.
    module_suggestions_list = ft.ListView(
        spacing=ui.dropdowns.DROPDOWN_LIST_SPACING,
        padding=0,
        expand=True,
        auto_scroll=False,
    )
    argument_suggestions_list = ft.ListView(
        spacing=ui.dropdowns.DROPDOWN_LIST_SPACING,
        padding=0,
        expand=True,
        auto_scroll=False,
    )

    module_panel = ui.dropdowns.build_dropdown_panel(module_suggestions_list, on_click=callbacks.on_dropdown_click)
    argument_input_field = ui.input.build_argument_field(
        on_submit=callbacks.on_argument_submit,
        on_change=callbacks.on_argument_change,
    )
    argument_panel = ui.dropdowns.build_dropdown_panel(
        ui.argument_dropdown.build_argument_panel_content(argument_input_field, argument_suggestions_list),
        on_click=callbacks.on_dropdown_click,
    )
    dropdown_stack = ui.dropdowns.build_dropdown_stack(
        module_panel,
        argument_panel,
        MAX_DROPDOWN_HEIGHT,
    )

    command_input_field = ui.input.build_command_field(
        on_submit=callbacks.on_send,
        on_change=callbacks.on_command_change,
        on_focus=callbacks.on_command_focus,
        on_click=callbacks.on_command_click,
    )
    module_icon = ui.input.build_module_icon()
    send_button = ui.input.build_send_button(callbacks.on_send)
    voice_hint = ui.input.build_voice_hint()
    clear_button = ui.input.build_clear_button(callbacks.on_clear_command)
    command_input = ui.input.build_command_input(
        command_input_field,
        module_icon,
        clear_button,
        send_button,
        voice_hint,
    )
    input_shell = ui.input.build_input_shell(command_input)
    input_shell.on_click = callbacks.on_input_shell_click
    input_shell.on_hover = callbacks.on_input_shell_hover

    root = build_home_content(
        build_input_title(on_click=callbacks.on_background_click),
        input_shell,
        dropdown_stack,
        on_background_click=callbacks.on_background_click,
    )

    return HomeViewControls(
        root=root,
        command_input_field=command_input_field,
        module_icon=module_icon,
        argument_input_field=argument_input_field,
        send_button=send_button,
        clear_button=clear_button,
        input_shell=input_shell,
        voice_hint=voice_hint,
        module_panel=module_panel,
        argument_panel=argument_panel,
        dropdown_stack=dropdown_stack,
        module_suggestions_list=module_suggestions_list,
        argument_suggestions_list=argument_suggestions_list,
    )


def build_input_title(on_click: Callable | None = None) -> ft.Container:
    # Cria o titulo exibido acima do input principal.
    return ft.Container(
        padding=ft.Padding(left=10, bottom=10),
        alignment=ft.Alignment.CENTER_LEFT,
        on_click=on_click,
        content=ft.Text(
            "Escolha sua rota",
            size=18,
            weight=ft.FontWeight.W_800,
            color=PASTEL_DARK_PURPLE,
            font_family=TITLE_FONT,
        ),
    )


def build_background_logo(on_click: Callable | None = None) -> ft.Container:
    # Cria a logo translucida usada como imagem de fundo da home.
    return ft.Container(
        expand=True,
        alignment=ft.Alignment.BOTTOM_CENTER,
        padding=ft.Padding(bottom=100),
        on_click=on_click,
        content=ft.Image(src=LOGO_PATH, width=530, height=530, opacity=0.1, fit=ft.BoxFit.CONTAIN),
    )


def build_home_content(
    input_title: ft.Container,
    input_shell: ft.Container,
    dropdown_stack: ft.Stack,
    on_background_click: Callable | None = None,
) -> ft.Container:
    # Cria a estrutura visual da home com fundo, titulo, input e dropdowns.
    return build_route_content_container(
        content=ft.Stack(
            expand=True,
            fit=ft.StackFit.EXPAND,
            controls=[
                build_background_logo(on_click=on_background_click),
                ft.Container(
                    alignment=ft.Alignment.TOP_CENTER,
                    padding=ft.Padding(left=24, top=18, right=24, bottom=24),
                    on_click=on_background_click,
                    content=ft.Column(
                        width=800,
                        tight=True,
                        spacing=0,
                        controls=[input_title, input_shell, dropdown_stack],
                    ),
                ),
            ],
        ),
    )
