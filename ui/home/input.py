from collections.abc import Callable

import flet as ft

from ui.shared.components.material_icons import material_icon
from ui.theme.colors import BORDER, PASTEL_DARK_PURPLE, PASTEL_PURPLE, SURFACE, BLUE_GREY, TEXT_PRIMARY, TEXT_SECONDARY


INPUT_SHELL_HOVER_BG = "#F5F5F5"


def build_command_field(
    on_submit: Callable,
    on_change: Callable,
    on_focus: Callable,
    on_click: Callable,
    on_tap_outside: Callable,
) -> ft.TextField:
    # Cria o campo principal onde o usuario digita ou escolhe a rota.
    return ft.TextField(
        expand=True,
        hint_text="Fale ou escreva Iris...",
        hint_style=ft.TextStyle(color=TEXT_SECONDARY, size=16),
        text_style=ft.TextStyle(color=TEXT_PRIMARY, size=16),
        cursor_color=TEXT_PRIMARY,
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding.all(0),
        on_submit=on_submit,
        on_change=on_change,
        on_focus=on_focus,
        on_click=on_click,
        # on_tap_outside=on_tap_outside,
        bgcolor=ft.Colors.TRANSPARENT,
        hover_color=ft.Colors.TRANSPARENT,
        focused_bgcolor=ft.Colors.TRANSPARENT,
    )


def build_argument_field(on_submit: Callable, on_change: Callable, on_tap_outside: Callable) -> ft.TextField:
    # Cria o campo usado para filtrar argumentos do modulo selecionado.
    return ft.TextField(
        height=42,
        expand=True,
        hint_text="Buscar item da area de trabalho...",
        hint_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        text_style=ft.TextStyle(color=TEXT_PRIMARY, size=13),
        cursor_color=TEXT_PRIMARY,
        border=ft.InputBorder.NONE,
        content_padding=ft.Padding.only(left=12, right=12),
        on_submit=on_submit,
        on_change=on_change,
        on_tap_outside=on_tap_outside,
        bgcolor=BLUE_GREY,
        border_radius=12,
    )


def build_send_button(on_click: Callable) -> ft.Container:
    # Cria o botao que dispara a execucao da rota selecionada.
    return ft.Container(
        width=36,
        height=36,
        border_radius=18,
        alignment=ft.Alignment.CENTER,
        bgcolor=PASTEL_DARK_PURPLE,
        content=ft.Icon(icon=ft.Icons.ARROW_FORWARD_ROUNDED, color=ft.Colors.WHITE, size=18),
        on_click=on_click,
    )


def build_clear_button(on_click: Callable) -> ft.Container:
    # Cria o botao que limpa o campo principal.
    return ft.Container(
        visible=False,
        width=30,
        height=30,
        border_radius=15,
        alignment=ft.Alignment.CENTER,
        bgcolor=ft.Colors.TRANSPARENT,
        ink=True,
        ink_color=ft.Colors.with_opacity(0.08, TEXT_PRIMARY),
        tooltip="Limpar",
        content=ft.Icon(
            icon=ft.Icons.CLOSE_ROUNDED,
            color=TEXT_SECONDARY,
            size=18,
        ),
        on_click=on_click,
    )


def set_send_button_loading(send_button: ft.Container, is_loading: bool) -> None:
    # Alterna o botao de envio entre icone normal e loading.
    send_button.content = (
        ft.ProgressRing(width=18, height=18, stroke_width=2, color=ft.Colors.WHITE)
        if is_loading
        else ft.Icon(icon=ft.Icons.ARROW_FORWARD_ROUNDED, color=ft.Colors.WHITE, size=18)
    )


def set_input_shell_hovered(input_shell: ft.Container, is_hovered: bool) -> None:
    # Atualiza a aparencia do shell quando o mouse entra ou sai.
    if is_hovered:
        input_shell.bgcolor = INPUT_SHELL_HOVER_BG
        input_shell.border = ft.Border.all(1, TEXT_PRIMARY)
    else:
        input_shell.bgcolor = SURFACE
        input_shell.border = ft.Border.all(1, BORDER)


def set_input_shell_voice_active(input_shell: ft.Container, is_active: bool, *, pulse: bool = False) -> None:
    # Indica visualmente que o texto atual veio do comando de voz.
    if not is_active:
        input_shell.bgcolor = SURFACE
        input_shell.border = ft.Border.all(1, BORDER)
        input_shell.shadow = ft.BoxShadow(blur_radius=24, color="#16000000", offset=ft.Offset(0, 10))
        return

    input_shell.bgcolor = SURFACE
    input_shell.border = ft.Border.all(2 if pulse else 1.5, PASTEL_PURPLE)
    input_shell.shadow = ft.BoxShadow(
        spread_radius=3 if pulse else 1,
        blur_radius=42 if pulse else 26,
        color="#70C3A0DE" if pulse else "#45C3A0DE",
        offset=ft.Offset(0, 7),
    )


def build_command_input(
    command_input_field: ft.TextField,
    module_icon: ft.Text,
    clear_button: ft.Container,
    send_button: ft.Container,
    voice_hint: ft.Container | None = None,
) -> ft.Container:
    # Agrupa icone, campo principal e botao de envio.
    return ft.Container(
        height=56,
        border_radius=28,
        bgcolor=ft.Colors.TRANSPARENT,
        padding=ft.Padding.only(left=16, right=10),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                module_icon,
                command_input_field,
                clear_button,
                ft.Stack(
                    width=150,
                    height=56,
                    clip_behavior=ft.ClipBehavior.NONE,
                    controls=[
                        ft.Container(right=0, top=10, content=send_button),
                        voice_hint
                        or ft.Container(
                            visible=False,
                            right=0,
                            top=-20,
                        ),
                    ],
                ),
            ],
        ),
    )


def build_module_icon() -> ft.Text:
    return material_icon("explore", size=28, color=PASTEL_DARK_PURPLE)


def build_input_shell(command_input: ft.Container) -> ft.Container:
    # Cria o container arredondado que envolve o input principal.
    return ft.Container(
        width=800,
        padding=ft.Padding(left=12, top=7, right=12, bottom=7),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=28,
        shadow=ft.BoxShadow(blur_radius=24, color="#16000000", offset=ft.Offset(0, 10)),
        animate=ft.Animation(280, ft.AnimationCurve.EASE_OUT),
        content=command_input,
    )


def build_voice_hint() -> ft.Container:
    # Overlay absoluto acima do botão de envio, exibido somente durante voz.
    return ft.Container(
        visible=False,
        right=0,
        top=-20,
        padding=ft.Padding(left=10, top=5, right=10, bottom=5),
        bgcolor=PASTEL_DARK_PURPLE,
        border_radius=12,
        shadow=ft.BoxShadow(blur_radius=12, color="#28000000", offset=ft.Offset(0, 4)),
        content=ft.Text("“Enviar” para concluir", size=11, color=ft.Colors.WHITE, no_wrap=True),
    )
