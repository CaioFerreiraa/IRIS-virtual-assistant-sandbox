from collections.abc import Callable

import flet as ft

from ui.theme.colors import BORDER, PASTEL_DARK_PURPLE, SURFACE, SURFACE_MUTED, TEXT_PRIMARY, TEXT_SECONDARY


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
        bgcolor=SURFACE_MUTED,
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


def build_command_input(
    command_input_field: ft.TextField,
    clear_button: ft.Container,
    send_button: ft.Container,
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
                ft.Icon(icon=ft.Icons.EXPLORE, color=PASTEL_DARK_PURPLE, size=28),
                command_input_field,
                clear_button,
                send_button,
            ],
        ),
    )


def build_input_shell(command_input: ft.Container) -> ft.Container:
    # Cria o container arredondado que envolve o input principal.
    return ft.Container(
        width=800,
        padding=ft.Padding(left=12, top=7, right=12, bottom=7),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=28,
        shadow=ft.BoxShadow(blur_radius=24, color="#16000000", offset=ft.Offset(0, 10)),
        content=command_input,
    )
