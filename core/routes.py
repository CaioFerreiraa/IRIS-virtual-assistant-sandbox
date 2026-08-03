import flet as ft
import ui.history as history_ui
import ui.home as ui
import ui.settings as settings_ui

from services.speech_service_manager import SpeechServiceManager
from ui.shared.components.toaster_handler import ToasterHandler

from ui.theme.colors import SURFACE, BORDER, TEXT_PRIMARY, TEXT_SECONDARY

DEFAULT_ROUTES = {
    "/home": "Início",
    "/community": "Comunidade",
    "/routines": "Rotinas",
    "/history": "Histórico",
    "/settings": "Configurações",
}

def build_route_content(
    route: str,
    module_options: list[str | dict[str, str | bool]] | tuple[str | dict[str, str | bool], ...] | None = None,
    toaster_handler=None,
    speech_manager: SpeechServiceManager | None = None,
) -> ft.Control:
    if route in ("", "/", "/home"):
        return ui.view.build_home_view(
            module_options=module_options,
            toaster_handler=toaster_handler,
            speech_manager=speech_manager,
        )

    if route == "/history":
        return history_ui.view.build_history_view()

    if route == "/settings" and speech_manager is not None and isinstance(toaster_handler, ToasterHandler):
        return settings_ui.build_settings_view(speech_manager, toaster_handler)

    title = DEFAULT_ROUTES.get(route, "IRIS")

    return ft.Container(
        expand=True,
        padding=ft.Padding(left=28, top=28, right=28, bottom=28),
        content=ft.Container(
            expand=True,
            padding=ft.Padding(left=24, top=24, right=24, bottom=24),
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                spacing=7,
                controls=[
                    ft.Text(
                        title,
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Text(
                        f"Rota atual: {route}",
                        size=14,
                        color=TEXT_SECONDARY,
                    ),
                ],
            ),
        ),
    )
