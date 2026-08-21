from __future__ import annotations

import flet as ft

from ui.theme.colors import CANCEL, PASTEL_DARK_PURPLE, TEXT_PRIMARY, TEXT_SECONDARY


class ModuleErrorTabMixin:
    def _build_error_tab(self) -> ft.Column:
        cards: list[ft.Control] = []
        for error in self.technical_errors:
            is_submodule = bool(error.get("is_submodule"))
            module_name = str(error.get("module_name") or "Módulo")
            title = (
                f"Problema no submódulo {module_name}"
                if is_submodule
                else f"Problema no módulo {module_name}"
            )
            details: list[ft.Control] = [
                ft.Text(
                    str(error.get("message") or "O módulo apresentou um problema técnico."),
                    size=13,
                    color=TEXT_PRIMARY,
                    selectable=True,
                )
            ]
            log_path = str(error.get("log_path") or "")
            if log_path:
                details.extend(
                    [
                        ft.Text(
                            "Log técnico",
                            size=11,
                            weight=ft.FontWeight.W_700,
                            color=TEXT_SECONDARY,
                        ),
                        ft.Text(
                            log_path,
                            size=12,
                            color=TEXT_PRIMARY,
                            font_family="Consolas",
                            selectable=True,
                        ),
                    ]
                )
            cards.append(
                ft.Container(
                    padding=16,
                    bgcolor=ft.Colors.with_opacity(0.35, CANCEL),
                    border=ft.Border.all(1, CANCEL),
                    border_radius=8,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(
                                        ft.Icons.ERROR_OUTLINE_ROUNDED,
                                        size=20,
                                        color=PASTEL_DARK_PURPLE,
                                    ),
                                    ft.Text(
                                        title,
                                        size=15,
                                        weight=ft.FontWeight.W_700,
                                        color=TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            *details,
                        ],
                    ),
                )
            )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=cards,
        )
