from __future__ import annotations

import flet as ft

from ui.modules.components.card import build_card
from ui.theme.colors import BORDER, GREY_100, TEXT_PRIMARY


class ModuleAboutTabMixin:
    def _build_about_tab(self) -> ft.Column:
        controls: list[ft.Control] = [
            ft.Text(
                str(self.detail["description"])
                or "Este módulo não possui descrição.",
                size=14,
                color=TEXT_PRIMARY,
                selectable=True,
            ),
        ]
        readme_content = str(self.detail["readme_content"])
        if readme_content:
            controls.append(
                build_card(
                    "README",
                    ft.Markdown(
                        readme_content,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        code_theme=ft.MarkdownCodeTheme.A11Y_LIGHT,
                        auto_follow_links=False,
                    ),
                )
            )

        manifest_content = str(self.detail["manifest_content"])
        if manifest_content:
            controls.append(
                build_card(
                    "module.json",
                    ft.Container(
                        bgcolor=GREY_100,
                        border=ft.Border.all(1, BORDER),
                        border_radius=8,
                        padding=16,
                        content=ft.Text(
                            manifest_content,
                            size=12,
                            color=TEXT_PRIMARY,
                            font_family="Consolas",
                            selectable=True,
                        ),
                    ),
                )
            )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
            controls=controls,
        )
