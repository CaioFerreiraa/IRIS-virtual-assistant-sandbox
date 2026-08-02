from collections.abc import Callable, Sequence
from dataclasses import dataclass

import flet as ft
import ui.home as ui
from services.home_service import HomeService
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import BORDER, PASTEL_DARK_PURPLE, SURFACE
from ui.theme.fonts import TITLE_FONT


LOGO_PATH = "assets/images/logo_transparent.png"
DROPDOWN_HEIGHT = 360


def build_home_view(
    module_options: Sequence[ui.dropdowns.ModuleOption] | None = None,
    toaster_handler: ToasterHandler | None = None,
) -> ft.Container:
    # Cria a tela home conectando view, dropdowns e servico.
    return HomeViewState(module_options, toaster_handler).build()


class HomeViewState:
    def __init__(
        self,
        module_options: Sequence[ui.dropdowns.ModuleOption] | None = None,
        toaster_handler: ToasterHandler | None = None,
    ):
        # Guarda dependencias gerais da home.
        self.module_options = tuple(ui.dropdowns.sort_modules(module_options or ()))
        self.executable_lookup = ui.dropdowns.module_executable_lookup(self.module_options)
        self.home_service = HomeService()
        self.toaster_handler = toaster_handler
        self.is_loading = False
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
        self.sync_clear_button_visibility()
        self.hide_dropdowns()
        self.update_if_ready(controls.command_input_field)
        self.update_if_ready(controls.argument_input_field)

    def keep_dropdowns_open(self, e=None) -> None:
        # Mantem cliques internos dos dropdowns sem fechar nada.
        self._dropdowns().keep_open(e)

    def refresh_module_suggestions(self, e) -> None:
        # Atualiza o dropdown de modulos quando o texto principal muda.
        self.sync_clear_button_visibility()
        self._dropdowns().refresh_module_suggestions(e)

    def show_module_suggestions_from_event(self, e) -> None:
        # Abre sugestoes de modulos a partir do evento do input.
        self._dropdowns().show_module_suggestions_from_event(e)

    def show_module_suggestions_from_shell(self, e=None) -> None:
        # Abre sugestoes de modulos quando o shell e clicado.
        self._dropdowns().show_module_suggestions_from_shell(e)

    def show_argument_suggestions_from_event(self, e) -> None:
        # Atualiza sugestoes de argumentos a partir do input secundario.
        self._dropdowns().show_argument_suggestions_from_event(e)

    def validate_module_request(self) -> str:
        # Garante que existe um modulo digitado ou selecionado.
        selected_module_path = self._dropdowns().selected_module_path
        command = selected_module_path or (self._controls().command_input_field.value or "").strip()
        if not command:
            raise ValueError("Informe um modulo para executar.")
        return command

    def send_request(self, e=None, argument: str | None = None) -> None:
        # Executa a rota atual ou abre a busca de argumentos quando necessario.
        controls = self._controls()
        if self.is_loading:
            return

        try:
            module_path = self.validate_module_request()
        except Exception as error:
            self.show_module_error(str(error))
            return

        if argument is None and self.home_service.module_has_arguments(module_path):
            self._dropdowns().open_argument_dropdown(module_path)
            return

        self.is_loading = True
        ui.input.set_send_button_loading(controls.send_button, self.is_loading)
        self.update_if_ready(controls.send_button)

        try:
            result = self.home_service.execute_module(module_path, argument)
            if result.get("success", True):
                self.show_module_success(result)
                controls.command_input_field.value = ""
                controls.argument_input_field.value = ""
                self.sync_clear_button_visibility()
                self.update_if_ready(controls.command_input_field)
                self.update_if_ready(controls.argument_input_field)
            else:
                self.show_module_error(self.result_message(result) or "O modulo retornou erro.")
        except Exception as error:
            self.show_module_error(str(error))
            print(error)
        finally:
            self.is_loading = False
            ui.input.set_send_button_loading(controls.send_button, self.is_loading)
            self.update_if_ready(controls.send_button)

    def show_module_success(self, result: dict) -> None:
        if self.toaster_handler is None:
            return

        self.toaster_handler.show_success(
            message=self.result_message(result) or "Modulo executado com sucesso.",
            title="Modulo executado",
        )

    def show_module_error(self, message: str) -> None:
        if self.toaster_handler is None:
            return

        self.toaster_handler.show_error(
            message=message or "Nao foi possivel executar o modulo.",
            title="Erro no modulo",
        )

    def result_message(self, result: dict) -> str:
        if "message" in result:
            return str(result["message"])
        if "result" in result:
            return str(result["result"])
        if "opened" in result:
            return f"URL aberta: {result['opened']}"
        return ""

    def select_module(self, module_path: str) -> None:
        # Seleciona um modulo e decide se executa direto ou pede argumento.
        controls = self._controls()
        controls.command_input_field.value = module_path
        self.sync_clear_button_visibility()
        self.update_if_ready(controls.command_input_field)

        if self.home_service.module_has_arguments(module_path):
            self._dropdowns().open_argument_dropdown(module_path)
            return

        self._dropdowns().clear_selected_module()
        self.hide_dropdowns()
        self.send_request(argument=None)

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
        ui.input.set_input_shell_hovered(controls.input_shell, str(e.data).lower() == "true")
        self.update_if_ready(controls.input_shell)

    def sync_clear_button_visibility(self) -> None:
        controls = self._controls()
        has_command = bool((controls.command_input_field.value or "").strip())
        has_selected_module = bool(self.dropdowns and self.dropdowns.selected_module_path)
        controls.clear_button.visible = has_command or has_selected_module
        self.update_if_ready(controls.clear_button)


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
    argument_input_field: ft.TextField
    send_button: ft.Container
    clear_button: ft.Container
    input_shell: ft.Container
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
    send_button = ui.input.build_send_button(callbacks.on_send)
    clear_button = ui.input.build_clear_button(callbacks.on_clear_command)
    command_input = ui.input.build_command_input(command_input_field, clear_button, send_button)
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
        argument_input_field=argument_input_field,
        send_button=send_button,
        clear_button=clear_button,
        input_shell=input_shell,
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


def build_home_content( input_title: ft.Container, input_shell: ft.Container, dropdown_stack: ft.Stack,
                        on_background_click: Callable | None = None, ) -> ft.Container:
    # Cria a estrutura visual da home com fundo, titulo, input e dropdowns.
    return ft.Container(
        expand=True,
        padding=ft.Padding(left=28, top=28, right=28, bottom=28),
        content=ft.Container(
            expand=True,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Stack(
                expand=True,
                fit=ft.StackFit.EXPAND,
                controls=[
                    build_background_logo(),
                    ft.Container(
                        alignment=ft.Alignment.TOP_CENTER,
                        padding=ft.Padding(left=24, top=34, right=24, bottom=24),
                        content=ft.Column(
                            width=800,
                            tight=True,
                            spacing=0,
                            controls=[input_title, input_shell, dropdown_stack],
                        ),
                    ),
                ],
            ),
        ),
    )
