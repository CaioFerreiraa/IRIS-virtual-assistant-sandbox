import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import flet as ft
import ui.home as ui
from services.home_service import HomeService
from services.speech_service import SpeechEvent, SpeechEventKind
from services.speech_service_manager import SpeechServiceManager
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import PASTEL_DARK_PURPLE
from ui.theme.fonts import TITLE_FONT


LOGO_PATH = "assets/images/logo_transparent.png"
DROPDOWN_HEIGHT = 360


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
        self._argument_capability_cache: dict[int, bool] = {}
        self.controls: HomeViewControls | None = None
        self.dropdowns: ui.dropdowns.HomeDropdowns | None = None

    def build(self) -> ft.Container:
        # Monta a view e inicializa o gerenciador de dropdowns.
        callbacks = HomeViewCallbacks(
            on_send=self.send_request,
            on_command_change=self.refresh_module_suggestions,
            on_command_focus=self.show_module_suggestions_from_event,
            on_command_click=self.show_module_suggestions_from_event,
            on_command_tap_outside=self.hide_dropdowns,
            on_argument_submit=self.execute_argument_from_event,
            on_argument_change=self.show_argument_suggestions_from_event,
            on_argument_tap_outside=self.hide_dropdowns,
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
            dropdown_height=DROPDOWN_HEIGHT,
        )
        if self.speech_manager is not None:
            self.speech_manager.subscribe(self.on_speech_event)
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
        controls = self._controls()
        controls.command_input_field.value = ""
        controls.argument_input_field.value = ""
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
            self.is_voice_active = True
            ui.input.set_voice_hint_text(controls.voice_hint, "“Enviar” para concluir")
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
            self._apply_voice_text(event.text)
            if event.should_submit:
                self._submit_voice_command(event.text)
            return

        if event.kind in {SpeechEventKind.DEACTIVATED, SpeechEventKind.ERROR, SpeechEventKind.STOPPED}:
            self.is_voice_active = False
            self.is_basic_capture_active = False
            controls.voice_hint.visible = False
            ui.input.set_input_shell_voice_active(controls.input_shell, False)
            self.update_if_ready(controls.voice_hint)
            self.update_if_ready(controls.input_shell)
            if event.kind == SpeechEventKind.ERROR and self.toaster_handler:
                self.toaster_handler.show_error(event.message, title="Voz indisponível")

    def _apply_voice_text(self, text: str) -> None:
        controls = self._controls()
        controls.command_input_field.value = text
        self._dropdowns().clear_selected_module()
        self._set_module_icon(None)
        self.sync_clear_button_visibility()
        self.update_if_ready(controls.command_input_field)

        resolved = ui.dropdowns.resolve_voice_module_option(text, self.module_options)
        if resolved is None:
            self._dropdowns().show_module_suggestions(text)
            return
        if resolved.ambiguous or resolved.module_id is None:
            self._dropdowns().show_module_suggestions(text)
            return

        self._set_module_icon(resolved.module_id)

        if resolved.argument and self._module_has_arguments(resolved.module_id):
            self._dropdowns().open_argument_dropdown(
                resolved.module_id,
                resolved.path,
                load_suggestions=False,
            )
            controls.argument_input_field.value = resolved.argument
            self._request_argument_suggestions(resolved.argument)
            self.update_if_ready(controls.argument_input_field)
            return

        self._dropdowns().show_module_suggestions(resolved.path)

    def _submit_voice_command(self, text: str) -> None:
        resolved = ui.dropdowns.resolve_voice_module_option(text, self.module_options)
        if resolved is None:
            self.show_module_error("Não encontrei um módulo compatível com o comando falado.")
            return
        if resolved.ambiguous:
            self.show_module_error("O comando corresponde a mais de um módulo. Escolha um item da lista.")
            return
        if resolved.module_id is None:
            self.show_module_error("Não foi possível identificar o módulo selecionado.")
            return

        self._dropdowns().selected_module_id = resolved.module_id
        self._dropdowns().selected_module_path = resolved.path
        self._set_module_icon(resolved.module_id)
        self.send_request(argument=resolved.argument or None)

    def _module_has_arguments(self, module_id: int) -> bool:
        if module_id not in self._argument_capability_cache:
            self._argument_capability_cache[module_id] = self.home_service.module_has_arguments(module_id)
        return self._argument_capability_cache[module_id]

    def keep_dropdowns_open(self, e=None) -> None:
        # Mantem cliques internos dos dropdowns sem fechar nada.
        self._dropdowns().keep_open(e)

    def refresh_module_suggestions(self, e) -> None:
        # Atualiza o dropdown de modulos quando o texto principal muda.
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
        self._request_argument_suggestions(e.control.value or "")

    def _request_argument_suggestions(self, query: str) -> None:
        dropdowns = self._dropdowns()
        module_id = dropdowns.selected_module_id
        if module_id is None:
            return
        try:
            page = self._controls().root.page
        except RuntimeError:
            page = None
        if page is None:
            dropdowns.show_argument_suggestions(query)
            return
        page.run_thread(
            self._search_arguments_background,
            page,
            module_id,
            query,
        )

    def _search_arguments_background(
        self,
        page: ft.Page,
        module_id: int,
        query: str,
    ) -> None:
        arguments = self.home_service.search_module_arguments(module_id, query)
        page.run_task(
            self._apply_argument_suggestions,
            module_id,
            query,
            arguments,
        )

    async def _apply_argument_suggestions(
        self,
        module_id: int,
        query: str,
        arguments: Sequence[ui.argument_dropdown.ArgumentOption],
    ) -> None:
        dropdowns = self._dropdowns()
        if dropdowns.selected_module_id != module_id:
            return
        current_query = self._controls().argument_input_field.value or ""
        if current_query != query:
            return
        dropdowns.apply_argument_suggestions(arguments)

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

        if self.is_voice_active:
            resolved = ui.dropdowns.resolve_voice_module_option(
                controls.command_input_field.value or "",
                self.module_options,
            )
            if resolved is not None and resolved.ambiguous:
                self.show_module_error("O comando corresponde a mais de um módulo. Escolha um item da lista.")
                return
            if resolved is not None and resolved.module_id is not None:
                module_id = resolved.module_id
                module_path = resolved.path
                self._dropdowns().selected_module_id = module_id
                self._dropdowns().selected_module_path = module_path
                if argument is None and resolved.argument:
                    argument = resolved.argument

        try:
            if module_id is None or module_path is None:
                module_id, module_path = self.validate_module_request()
        except Exception as error:
            self.show_module_error(str(error))
            return

        if argument is None and self.home_service.module_requires_argument(module_id):
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
        if self.home_service.module_requires_argument(module_id):
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

        self.hide_dropdowns()
        self.send_request(argument=argument)

    def select_argument(self, argument: str) -> None:
        # Seleciona um argumento da lista e executa o modulo.
        controls = self._controls()
        controls.argument_input_field.value = argument
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
    on_command_tap_outside: Callable
    on_argument_submit: Callable
    on_argument_change: Callable
    on_argument_tap_outside: Callable
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
    module_suggestions_list = ft.ListView(spacing=4, padding=0, expand=True, auto_scroll=False)
    argument_suggestions_list = ft.ListView(spacing=4, padding=0, expand=True, auto_scroll=False)

    module_panel = ui.dropdowns.build_dropdown_panel(module_suggestions_list, on_click=callbacks.on_dropdown_click)
    argument_input_field = ui.input.build_argument_field(
        on_submit=callbacks.on_argument_submit,
        on_change=callbacks.on_argument_change,
        on_tap_outside=callbacks.on_argument_tap_outside,
    )
    argument_panel = ui.dropdowns.build_dropdown_panel(
        ui.argument_dropdown.build_argument_panel_content(argument_input_field, argument_suggestions_list),
        on_click=callbacks.on_dropdown_click,
    )
    dropdown_stack = ui.dropdowns.build_dropdown_stack(module_panel, argument_panel, DROPDOWN_HEIGHT)

    command_input_field = ui.input.build_command_field(
        on_submit=callbacks.on_send,
        on_change=callbacks.on_command_change,
        on_focus=callbacks.on_command_focus,
        on_click=callbacks.on_command_click,
        on_tap_outside=callbacks.on_command_tap_outside,
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
        build_input_title(),
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


def build_input_title() -> ft.Container:
    # Cria o titulo exibido acima do input principal.
    return ft.Container(
        padding=ft.Padding(left=10, bottom=10),
        alignment=ft.Alignment.CENTER_LEFT,
        content=ft.Text(
            "Escolha sua rota",
            size=18,
            weight=ft.FontWeight.W_800,
            color=PASTEL_DARK_PURPLE,
            font_family=TITLE_FONT,
        ),
    )


def build_background_logo() -> ft.Container:
    # Cria a logo translucida usada como imagem de fundo da home.
    return ft.Container(
        alignment=ft.Alignment.BOTTOM_CENTER,
        padding=ft.Padding(bottom=100),
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
                build_background_logo(),
                ft.Container(
                    alignment=ft.Alignment.TOP_CENTER,
                    padding=ft.Padding(left=24, top=18, right=24, bottom=24),
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
