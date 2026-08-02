import sys
from pathlib import Path

import flet as ft

from core.fatal_error_handler import FatalErrorHandler
from core.routes import build_route_content

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import SessionLocal
from repositories.module_repository import ModuleRepository
from ui.shared.components.header import build_header
from ui.shared.components.sidebar import build_sidebar
from ui.shared.components.toaster_handler import ToasterHandler
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
    page.window.icon = "assets/icons/favicon.ico"

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

    app_container = fatal_error_handler.guard_call(
        get_app_container,
        page,
        fatal_error_handler,
        toaster_handler,
        fallback=ft.Container(expand=True, bgcolor=APP_BACKGROUND),
    )
    fatal_error_handler.guard_call(page.add, app_container)
    return page


def get_app_container(
    page: ft.Page,
    fatal_error_handler: FatalErrorHandler,
    toaster_handler: ToasterHandler,
):
    header_slot = ft.Container()
    sidebar_slot = ft.Container()
    route_slot = ft.Container(expand=True)
    active_module = {"name": "Assistente"}

    def load_module_options() -> list[dict[str, str | bool]]:
        db = SessionLocal()
        try:
            return ModuleRepository(db).list_module_options()
        finally:
            db.close()

    def navigate(route: str):
        page.go(route)

    def select_module(module_name: str):
        active_module["name"] = module_name
        render_layout()

    def render_layout(e=None):
        current_route = page.route or "/"
        module_options = load_module_options()
        header_slot.content = build_header(
            current_route=current_route,
            on_navigate=fatal_error_handler.guard_callback(navigate),
        )
        sidebar_slot.content = build_sidebar(
            active_module=active_module["name"],
            on_select=fatal_error_handler.guard_callback(select_module),
            modules=[str(module_option["path"]) for module_option in module_options],
        )
        route_slot.content = build_route_content(
            current_route,
            module_options=module_options,
            toaster_handler=toaster_handler,
        )

        if page.controls:
            page.update()

    page.on_route_change = fatal_error_handler.guard_callback(render_layout)
    fatal_error_handler.guard_call(render_layout)

    return ft.Container(
        expand=True,
        bgcolor=APP_BACKGROUND,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.WindowDragArea(content=header_slot),
                ft.Row(
                    expand=True,
                    spacing=0,
                    controls=[
                        sidebar_slot,
                        route_slot,
                    ],
                ),
            ],
        ),
    )
