import flet as ft

from ui.flet_app import main
from database.db import init_db

if __name__ == "__main__":
    init_db()
    ft.app(target=main)
