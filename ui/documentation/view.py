from __future__ import annotations

import flet as ft

from services.documentation_service import (
    DocumentationDocument,
    DocumentationSearchResult,
    DocumentationService,
    INITIAL_DOCUMENT,
    resolve_document_link,
)
from ui.shared.components.custom_dialog import custom_dialog
from ui.shared.components.route_content_container import build_route_content_container
from ui.theme.colors import (
    BORDER,
    PASTEL_BLUE,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    BLUE_GREY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.theme.fonts import TITLE_FONT


SEARCH_DIALOG_WIDTH = 720


def build_documentation_view() -> ft.Container:
    return DocumentationViewState().build()


class DocumentationViewState:
    def __init__(self, service: DocumentationService | None = None):
        self.service = service or DocumentationService()
        self.documents = self.service.list_documents()
        self.active_document = self._initial_document()
        self.document_list = ft.ListView(spacing=6, padding=0, expand=True)
        self.markdown_container = ft.Container(expand=True)
        self.title_text = ft.Text()
        self.subtitle_text = ft.Text()
        self.search_results_list = ft.ListView(spacing=6, padding=0, height=420)
        self.search_input: ft.TextField | None = None
        self.search_dialog: ft.AlertDialog | None = None

    def build(self) -> ft.Container:
        self._render_document_list()
        self._render_active_document()

        return build_route_content_container(
            icon=ft.Icons.MENU_BOOK_ROUNDED,
            title="Documentação",
            subtitle=f"{len(self.documents)} documentos encontrados",
            trailing=self._build_search_button(),
            content=ft.Row(
                expand=True,
                spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    self._build_sidebar(),
                    ft.Container(
                        expand=4,
                        height=None,
                        content=self.markdown_container,
                    ),
                ],
            ),
        )

    def _initial_document(self) -> DocumentationDocument | None:
        if not self.documents:
            return None

        for document in self.documents:
            if document.filename == INITIAL_DOCUMENT:
                return document
        return self.documents[0]

    def _build_search_button(self) -> ft.Container:
        return ft.Container(
            height=42,
            width=300,
            padding=ft.Padding(left=14, top=0, right=12, bottom=0),
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            bgcolor=BLUE_GREY,
            ink=True,
            ink_color=ft.Colors.with_opacity(0.08, PASTEL_PURPLE),
            tooltip="Pesquisar na documentação",
            on_click=self.open_search_dialog,
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SEARCH_ROUNDED, size=18, color=PASTEL_DARK_PURPLE),
                    ft.Text(
                        "Pesquisar documentação",
                        size=13,
                        color=TEXT_SECONDARY,
                        expand=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        no_wrap=True,
                    ),
                ],
            ),
        )

    def _build_sidebar(self) -> ft.Container:
        return ft.Container(
            expand=1,
            padding=ft.Padding(left=14, top=14, right=14, bottom=14),
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Column(
                expand=True,
                spacing=12,
                controls=[
                    ft.Text(
                        "Arquivos",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_SECONDARY,
                    ),
                    self.document_list,
                ],
            ),
        )

    def _render_document_list(self) -> None:
        if not self.documents:
            self.document_list.controls = [
                ft.Text(
                    "Nenhum arquivo Markdown encontrado.",
                    size=13,
                    color=TEXT_SECONDARY,
                )
            ]
            return

        self.document_list.controls = [
            self._build_document_item(document)
            for document in self.documents
        ]

    def _build_document_item(self, document: DocumentationDocument) -> ft.Container:
        is_active = self.active_document is not None and document.filename == self.active_document.filename
        return ft.Container(
            height=58,
            padding=ft.Padding(left=12, top=8, right=10, bottom=8),
            border_radius=8,
            border=ft.Border.all(1, PASTEL_PURPLE if is_active else BORDER),
            bgcolor=SURFACE if is_active else ft.Colors.TRANSPARENT,
            ink=True,
            ink_color=PASTEL_BLUE,
            on_click=lambda _, selected=document.filename: self.select_document(selected),
            content=ft.Row(
                spacing=9,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        icon=ft.Icons.ARTICLE_OUTLINED,
                        size=18,
                        color=PASTEL_DARK_PURPLE if is_active else TEXT_SECONDARY,
                    ),
                    ft.Column(
                        expand=True,
                        tight=True,
                        spacing=1,
                        controls=[
                            ft.Text(
                                document.title,
                                size=13,
                                weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                                color=TEXT_PRIMARY if is_active else TEXT_SECONDARY,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                no_wrap=True,
                                tooltip=document.title,
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _render_active_document(self) -> None:
        if self.active_document is None:
            self.markdown_container.content = self._build_empty_state()
            return

        self.title_text = ft.Text(
            self.active_document.title,
            size=22,
            weight=ft.FontWeight.BOLD,
            color=TEXT_PRIMARY,
            font_family=TITLE_FONT,
        )
        self.subtitle_text = ft.Text(
            self.active_document.filename,
            size=13,
            color=TEXT_SECONDARY,
        )

        markdown = ft.Markdown(
            self.active_document.content,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.A11Y_LIGHT,
            auto_follow_links=False,
            on_tap_link=self.on_tap_markdown_link,
        )

        self.markdown_container.content = ft.Column(
            expand=True,
            spacing=14,
            controls=[
                ft.Row(
                    spacing=10,
                    # vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[self.title_text, self.subtitle_text]
                ),
                ft.Divider(height=1, color=BORDER),
                ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Container(
                            padding=ft.Padding(left=4, top=2, right=16, bottom=24),
                            content=markdown,
                        )
                    ],
                ),
            ],
        )

    def _build_empty_state(self) -> ft.Container:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                "Nenhum arquivo de documentação foi encontrado.",
                size=14,
                color=TEXT_SECONDARY,
            ),
        )

    def select_document(self, filename: str) -> None:
        document = self.service.get_document(filename)
        if document is None:
            return

        self.active_document = document
        self._render_document_list()
        self._render_active_document()
        self._update_if_mounted(self.document_list)
        self._update_if_mounted(self.markdown_container)

    def open_search_dialog(self, event: ft.ControlEvent) -> None:
        self.search_input = ft.TextField(
            autofocus=True,
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            hint_text="Buscar em todos os documentos...",
            text_style=ft.TextStyle(size=13, color=TEXT_PRIMARY),
            hint_style=ft.TextStyle(size=13, color=TEXT_SECONDARY),
            border_radius=8,
            border_color=BORDER,
            focused_border_color=PASTEL_PURPLE,
            cursor_color=PASTEL_DARK_PURPLE,
            on_change=self.on_search_change,
            on_submit=self.select_first_search_result,
        )
        self.search_results_list.controls = self._build_search_result_controls("")

        content = ft.Container(
            width=SEARCH_DIALOG_WIDTH,
            content=ft.Column(
                tight=True,
                spacing=14,
                controls=[
                    self.search_input,
                    ft.Container(
                        height=420,
                        padding=ft.Padding(left=4, top=0, right=4, bottom=0),
                        content=self.search_results_list,
                    ),
                ],
            ),
        )
        close_button = ft.TextButton(
            content="Fechar",
            style=ft.ButtonStyle(color=PASTEL_DARK_PURPLE),
            on_click=self.close_search_dialog,
        )

        self.search_dialog = custom_dialog(
            title="Buscar na documentação",
            content=content,
            actions=[close_button],
            width=SEARCH_DIALOG_WIDTH,
            inset_padding=ft.Padding(left=24, top=90, right=24, bottom=24),
            icon=ft.Icons.SEARCH_ROUNDED,
        )
        event.page.overlay.append(self.search_dialog)
        self.search_dialog.open = True
        event.page.update()

    def on_search_change(self, event: ft.ControlEvent) -> None:
        self.search_results_list.controls = self._build_search_result_controls(event.control.value or "")
        self._update_if_mounted(self.search_results_list)

    def select_first_search_result(self, event: ft.ControlEvent) -> None:
        results = self.service.search(event.control.value or "", self.documents, limit=1)
        if results:
            self.open_search_result(results[0].filename, event)

    def _build_search_result_controls(self, query: str) -> list[ft.Control]:
        results = self.service.search(query, self.documents)
        if not results:
            return [
                ft.Container(
                    height=110,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        "Nenhum resultado encontrado.",
                        size=14,
                        color=TEXT_SECONDARY,
                    ),
                )
            ]

        return [
            self._build_search_result_item(result)
            for result in results
        ]

    def _build_search_result_item(self, result: DocumentationSearchResult) -> ft.Container:
        return ft.Container(
            height=92,
            padding=ft.Padding(left=12, top=10, right=12, bottom=10),
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            bgcolor=SURFACE,
            ink=True,
            ink_color=PASTEL_BLUE,
            on_click=lambda event, selected=result.filename: self.open_search_result(selected, event),
            content=ft.Column(
                tight=True,
                spacing=4,
                controls=[
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=16, color=PASTEL_DARK_PURPLE),
                            ft.Text(
                                result.title,
                                size=14,
                                weight=ft.FontWeight.W_700,
                                color=TEXT_PRIMARY,
                                expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                no_wrap=True,
                                tooltip=result.title,
                            ),
                        ],
                    ),
                    ft.Text(
                        result.subtitle,
                        size=12,
                        color=TEXT_SECONDARY,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        no_wrap=True,
                    ),
                    ft.Text(
                        result.excerpt,
                        size=12,
                        color=TEXT_SECONDARY,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
        )

    def open_search_result(self, filename: str, event: ft.ControlEvent) -> None:
        self.select_document(filename)
        self.close_search_dialog(event)

    def close_search_dialog(self, event: ft.ControlEvent) -> None:
        if self.search_dialog is not None:
            self.search_dialog.open = False
        event.page.update()

    def on_tap_markdown_link(self, event: ft.ControlEvent) -> None:
        if self.active_document is None:
            return

        link_target = str(event.data or "")
        filename = resolve_document_link(self.active_document.filename, link_target)
        if filename is not None:
            self.select_document(filename)
            return

        if link_target:
            event.page.launch_url(link_target)

    def _update_if_mounted(self, control: ft.Control) -> None:
        try:
            if control.page is not None:
                control.update()
        except RuntimeError:
            return
