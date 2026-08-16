import re

import flet as ft
import ui.documentation as documentation_ui
import ui.history as history_ui
import ui.home as ui
import ui.modules as modules_ui
import ui.settings as settings_ui

from database.db import SessionLocal
from services.speech_service_manager import SpeechServiceManager
from ui.shared.components.route_content_container import build_route_content_container
from ui.shared.components.toaster_handler import ToasterHandler

DEFAULT_ROUTES = {
    "/community": (
        "Comunidade",
        "Descubra recursos compartilhados pela comunidade IRIS.",
        ft.Icons.GROUP_ROUNDED,
    ),
    "/routines": (
        "Rotinas",
        "Organize sequências de ações para executar depois.",
        ft.Icons.AUTORENEW_ROUNDED,
    ),
    "/settings": (
        "Configurações",
        "Personalize o comportamento da IRIS.",
        ft.Icons.SETTINGS_ROUNDED,
    ),
}

MODULE_ROUTE_PATTERN = re.compile(r"^/modules/([^/]+)$")


def build_route_content(
    route: str,
    module_options: (
        list[str | dict[str, str | bool]]
        | tuple[str | dict[str, str | bool], ...]
        | None
    ) = None,
    toaster_handler=None,
    speech_manager: SpeechServiceManager | None = None,
    module_session_factory=SessionLocal,
) -> ft.Control:
    if route in ("", "/", "/home"):
        return ui.view.build_home_view(
            module_options=module_options,
            toaster_handler=toaster_handler,
            speech_manager=speech_manager,
        )

    if route == "/history":
        return history_ui.view.build_history_view()

    module_route_match = MODULE_ROUTE_PATTERN.fullmatch(route)
    if module_route_match is not None:
        raw_module_id = module_route_match.group(1)
        if not raw_module_id.isdigit():
            return modules_ui.build_module_not_found_view()
        return modules_ui.build_module_view(
            int(raw_module_id),
            toaster_handler=toaster_handler,
            session_factory=module_session_factory,
        )

    if route == "/documentation":
        return documentation_ui.view.build_documentation_view()

    if (
        route == "/settings/voice_checking"
        and speech_manager is not None
        and isinstance(toaster_handler, ToasterHandler)
    ):
        return settings_ui.build_voice_checking_view(speech_manager, toaster_handler)

    if (
        route == "/settings"
        and speech_manager is not None
        and isinstance(toaster_handler, ToasterHandler)
    ):
        return settings_ui.build_settings_view(speech_manager, toaster_handler)

    title, subtitle, icon = DEFAULT_ROUTES.get(
        route,
        ("IRIS", f"Rota atual: {route}", ft.Icons.ROUTE_ROUNDED),
    )
    return build_route_content_container(
        icon=icon,
        title=title,
        subtitle=subtitle,
        content=ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Text("Conteúdo em desenvolvimento.", size=14),
        ),
    )
