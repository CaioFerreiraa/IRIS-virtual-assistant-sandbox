import sys
from pathlib import Path

import flet as ft

from core.fatal_error_handler import FatalErrorHandler
from core.routes import MODULE_ROUTE_PATTERN, build_route_content

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import SessionLocal
from repositories.module_repository import ModuleRepository
from services.speech_service_manager import SpeechServiceManager
from services.module_registry_state import get_module_registry_state
from services.module_runtime_service import module_runtime_manager
from services.voice_settings_service import VoiceSettingsService
from ui.shared.components.header import VOICE_ACTIVE_ROUTES, build_header
from ui.shared.components.sidebar import (
    DEFAULT_SIDEBAR_WIDTH,
    SidebarViewState,
    build_sidebar,
)
from ui.shared.components.toaster_handler import ToasterHandler
from ui.shared.components.window_resize import build_window_resize_handles
from ui.theme.colors import APP_BACKGROUND
from ui.theme.fonts import DEFAULT_FONT, FONT_ASSETS


def main(page: ft.Page):
    try:
        get_default_page(page)
    except Exception as error:
        toaster_handler = ToasterHandler(page)
        toaster_handler.mount()
        fatal_error_handler = FatalErrorHandler(page, toaster_handler)
        fatal_error_handler.install()
        fatal_error_handler.handle(error)


def get_default_page(page: ft.Page):
    page.title = "IRIS Virtual Assistant"
    page.bgcolor = APP_BACKGROUND
    page.padding = 0
    page.spacing = 0

    page.window.bgcolor = APP_BACKGROUND

    page.window.frameless = True
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.window.resizable = True
    page.window.shadow = True
    page.window.icon = "assets/images/logo_transparent.png"

    page.window.width = 1400
    page.window.height = 900
    page.window.min_width = 1000
    page.window.min_height = 650

    page.fonts = FONT_ASSETS
    page.theme = ft.Theme(font_family=DEFAULT_FONT)

    toaster_handler = ToasterHandler(page)
    toaster_handler.mount()
    fatal_error_handler = FatalErrorHandler(page, toaster_handler)
    fatal_error_handler.install()
    speech_manager = SpeechServiceManager()

    app_container = fatal_error_handler.guard_call(
        get_app_container,
        page,
        fatal_error_handler,
        toaster_handler,
        speech_manager,
        fallback=ft.Container(expand=True, bgcolor=APP_BACKGROUND),
    )
    fatal_error_handler.guard_call(page.add, app_container)
    def shutdown_services(event=None) -> None:
        speech_manager.shutdown()
        module_runtime_manager.shutdown()

    page.on_disconnect = shutdown_services
    page.on_close = shutdown_services
    fatal_error_handler.guard_call(
        speech_manager.prepare,
        VoiceSettingsService(speech_manager).load_for_runtime(),
    )
    fatal_error_handler.guard_call(
        page.run_thread,
        module_runtime_manager.start_enabled_backends,
    )
    return page


def get_app_container(
    page: ft.Page,
    fatal_error_handler: FatalErrorHandler,
    toaster_handler: ToasterHandler,
    speech_manager: SpeechServiceManager,
):
    header_slot = ft.Container()
    sidebar_slot = ft.Container()
    route_slot = ft.Container(expand=True)
    sidebar_width = DEFAULT_SIDEBAR_WIDTH
    sidebar_view_state = SidebarViewState()
    expanded_module_ids: set[int] = set()
    collapsed_module_ids: set[int] = set()

    def load_module_options(
        *,
        available_only: bool,
    ) -> list[dict[str, object]]:
        db = SessionLocal()
        try:
            return ModuleRepository(db).list_module_options(
                available_only=available_only,
            )
        finally:
            db.close()

    def remember_sidebar_width(width: float) -> None:
        nonlocal sidebar_width
        sidebar_width = width

    def navigate(route: str):
        page.go(route)

    def select_module(module_id: int, module_name: str):
        del module_name
        page.go(f"/modules/{module_id}")

    def active_module_id(route: str) -> int | None:
        match = MODULE_ROUTE_PATTERN.fullmatch(route)
        if match is None or not match.group(1).isdigit():
            return None
        return int(match.group(1))

    def render_layout(e=None):
        current_route = page.route or "/"
        sidebar_module_options = load_module_options(available_only=False)
        module_options = [
            option
            for option in sidebar_module_options
            if bool(option.get("is_available"))
        ]
        registry_state = get_module_registry_state()
        registered_public_keys = {
            str(option.get("module_public_key"))
            for option in sidebar_module_options
            if option.get("module_public_key")
        }
        unregistered_invalid_modules = tuple(
            invalid_module
            for invalid_module in registry_state.invalid_modules
            if (
                not invalid_module.module_public_key
                or invalid_module.module_public_key not in registered_public_keys
            )
        )
        for option in sidebar_module_options:
            module_id = option.get("module_id")
            if type(module_id) is int:
                option["runtime_status"] = registry_state.runtime_statuses.get(
                    module_id,
                    "offline",
                )
                option["readme_content"] = registry_state.readme_contents.get(
                    module_id,
                    "",
                )
        speech_manager.clear_subscribers()
        speech_manager.set_command_enabled(current_route in VOICE_ACTIVE_ROUTES)
        header_slot.content = build_header(
            current_route=current_route,
            on_navigate=fatal_error_handler.guard_callback(navigate),
            speech_manager=speech_manager,
        )
        sidebar = build_sidebar(
            active_module_id=active_module_id(current_route),
            on_select=fatal_error_handler.guard_callback(select_module),
            modules=sidebar_module_options,
            invalid_modules=unregistered_invalid_modules,
            width=sidebar_width,
            on_width_change=remember_sidebar_width,
            expanded_module_ids=expanded_module_ids,
            collapsed_module_ids=collapsed_module_ids,
            view_state=sidebar_view_state,
        )
        if sidebar_slot.content is not sidebar:
            sidebar_slot.content = sidebar
        route_slot.content = build_route_content(
            current_route,
            module_options=module_options,
            toaster_handler=toaster_handler,
            speech_manager=speech_manager,
        )

        if page.controls:
            page.update()

    page.on_route_change = fatal_error_handler.guard_callback(render_layout)
    fatal_error_handler.guard_call(render_layout)

    layout = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            ft.WindowDragArea(content=header_slot),
            ft.Row(
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    sidebar_slot,
                    route_slot,
                ],
            ),
        ],
    )
    return ft.Container(
        expand=True,
        bgcolor=APP_BACKGROUND,
        content=ft.Stack(
            expand=True,
            controls=[layout, *build_window_resize_handles(page)],
        ),
    )
