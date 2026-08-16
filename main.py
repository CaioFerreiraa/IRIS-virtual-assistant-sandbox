import flet as ft

from ui.flet_app import main
from database.db import init_db
from services.module_registry_service import initialize_module_registry

if __name__ == "__main__":
    init_db()
    initialize_module_registry()
    ft.app(target=main)
