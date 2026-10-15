import asyncio

import flet as ft

from services.vault_service import VaultService
from ui.shared.components.custom_dialog import show_custom_dialog
from ui.shared.components.form_controls import (
    build_primary_button, build_secondary_button, build_text_field,
)
from ui.shared.components.table import TableColumn, build_responsive_table
from ui.shared.components.table_search import (
    build_table_search_bar, build_table_search_input, normalize_search_text,
)
from ui.shared.components.toaster_handler import ToasterHandler
from ui.theme.colors import (
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


VAULT_COLUMNS = (
    TableColumn("name", "Nome", 2),
    TableColumn("description", "Descrição", 2),
    TableColumn("value", "Valor"),
    TableColumn("modules", "Módulos que usam", 3),
    TableColumn("allow_iris_update", "IRIS pode alterar", 2),
    TableColumn("actions", "Ações", 2),
)
MASKED_VALUE_MARKER = "••••••••"


class VaultKeysTab(ft.Column):
    def __init__(self, toaster_handler: ToasterHandler | None,
                 vault_service: VaultService | None = None) -> None:
        self.toaster_handler = toaster_handler
        self.vault_service = vault_service or VaultService()
        self.keys: list[dict[str, object]] = []
        self.search_input = build_table_search_input(
            "Pesquisar nas Vault Keys...", self.on_search_change,
        )
        self.table_slot = ft.Container(expand=True, content=ft.Text("Carregando Vault Keys..."))
        super().__init__(expand=True, spacing=20, controls=[
            ft.Row(controls=[
                ft.Text("Vault Keys", size=24, weight=ft.FontWeight.W_700,
                        color=TEXT_PRIMARY, expand=True),
                build_secondary_button("Atualizar", self.on_refresh),
                build_primary_button("Cadastrar chave", self.on_create),
            ]),
            ft.Text("Variáveis globais com criptografia. "
                    "Os valores são entregues somente durante a execução dos módulos.",
                    color=TEXT_SECONDARY),
            build_table_search_bar(self.search_input, self.clear_search),
            self.table_slot,
        ])

    def did_mount(self) -> None:
        self.page.run_task(self.refresh)

    async def on_refresh(self, event: ft.ControlEvent) -> None:
        await self.refresh()

    async def refresh(self) -> None:
        self.table_slot.content = ft.Text("Carregando Vault Keys...")
        self._update_if_mounted()
        try:
            self.keys = await asyncio.to_thread(self.vault_service.list_metadata)
            self._render_table()
        except Exception:
            message = "Não foi possível carregar as Vault Keys. Tente atualizar a lista."
            self.table_slot.content = ft.Text(message, color=TEXT_SECONDARY)
            self._show_error(message)
        self._update_if_mounted()

    def on_search_change(self, event: ft.ControlEvent) -> None:
        self._render_table()
        self._update_if_mounted()

    def clear_search(self, event: ft.ControlEvent) -> None:
        self.search_input.value = ""
        self._render_table()
        self._update_if_mounted()

    def _render_table(self) -> None:
        tokens = normalize_search_text(self.search_input.value or "").split()
        keys = [
            key for key in self.keys
            if all(token in self._key_search_text(key) for token in tokens)
        ]
        self.table_slot.content = build_responsive_table(
            VAULT_COLUMNS, [self._build_row(key) for key in keys],
            "Nenhuma Vault Key encontrada." if tokens else "Nenhuma Vault Key cadastrada.",
            row_height=64,
        )

    @staticmethod
    def _key_search_text(key: dict[str, object]) -> str:
        modules = " ".join(str(module["name"]) for module in key["modules"])
        return normalize_search_text(" ".join((
            str(key["name"]),
            str(key["description"] or ""),
            modules,
            "sim" if key["allow_iris_update"] else "não",
        )))

    def _build_row(self, key: dict[str, object]) -> dict[str, object]:
        async def on_delete(event: ft.ControlEvent) -> None:
            await self.on_delete(event, key)

        return {
            "name": key["name"], "description": key["description"] or "—",
            "value": MASKED_VALUE_MARKER if key.get("has_value") else "—",
            "modules": ", ".join(str(module["name"]) for module in key["modules"]) or "Nenhum módulo",
            "allow_iris_update": "Sim" if key["allow_iris_update"] else "Não",
            "actions": ft.Row(spacing=0, controls=[
                ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Editar chave",
                              on_click=lambda event: self._open_form(event.page, key)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, tooltip="Excluir chave",
                              on_click=on_delete),
            ]),
        }

    def on_create(self, event: ft.ControlEvent) -> None:
        self._open_form(event.page)

    def _open_form(self, page: ft.Page, key: dict[str, object] | None = None) -> ft.AlertDialog:
        name = build_text_field("Nome", str(key["name"]) if key else "", expand=True,
                                disabled=key is not None,
                                helper="O nome não pode ser alterado depois do cadastro.")
        name.read_only = key is not None
        name.autofocus = key is None
        description = build_text_field("Descrição", str(key["description"] or "") if key else "",
                                       multiline=True, expand=True)
        description.min_lines = 7
        description.max_lines = 7
        description.hint_text = "Explique para que esta chave será usada."
        value = build_text_field(
            "Novo valor (opcional)" if key else "Valor (opcional)",
            MASKED_VALUE_MARKER if key and key.get("has_value") else "",
            expand=True,
            helper=(
                "O valor atual está oculto. Mantenha o marcador para preservá-lo, "
                "apague para limpar ou digite outro valor."
                if key and key.get("has_value")
                else "Em branco, a chave ficará sem valor."
            ),
        )
        value.password = True
        value.can_reveal_password = key is None
        value.obscuring_character = "•"
        value.prefix_icon = ft.Icon(
            ft.Icons.LOCK_OUTLINE_ROUNDED, color=PASTEL_DARK_PURPLE,
        )
        value.hint_text = "Cole ou digite um valor, se necessário."
        allow_update = ft.Switch(
            label=ft.Column(
                tight=True,
                spacing=2,
                controls=[
                    ft.Text(
                        "Permitir que a IRIS atualize o valor",
                        size=13,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Text(
                        "Deixe desativado para impedir alterações automáticas por módulos.",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                ],
            ),
            value=bool(key["allow_iris_update"]) if key else False,
            active_color=PASTEL_DARK_PURPLE,
            active_track_color=PASTEL_PURPLE,
            tooltip="O valor é criptografado antes de ser salvo e não será exibido novamente.",
        )

        def close(event=None) -> None:
            value.value = ""
            dialog.open = False
            page.update()

        async def save(event: ft.ControlEvent) -> None:
            save_button.disabled = True
            page.update()
            try:
                if key:
                    await asyncio.to_thread(self.vault_service.update, int(key["id"]),
                                            description=description.value or "",
                                            new_value=value.value or None,
                                            keep_existing_value=(
                                                bool(key.get("has_value"))
                                                and value.value == MASKED_VALUE_MARKER
                                            ),
                                            allow_iris_update=bool(allow_update.value))
                else:
                    await asyncio.to_thread(self.vault_service.create, name.value or "",
                                            value.value or None, description.value or "",
                                            bool(allow_update.value))
            except ValueError as error:
                self._show_error(str(error))
            except Exception:
                self._show_error("Não foi possível salvar a Vault Key. Tente novamente.")
            else:
                close()
                if self.toaster_handler:
                    self.toaster_handler.show_success("Vault Key salva.")
                await self.refresh()
            finally:
                save_button.disabled = False
                page.update()

        save_button = build_primary_button(
            "Salvar alterações" if key else "Cadastrar chave",
            save,
        )
        page_width = getattr(page, "width", None)
        content_width = (
            min(840, max(320, page_width - 96))
            if isinstance(page_width, (int, float)) else 840
        )
        dialog = show_custom_dialog(
            page, "Editar Vault Key" if key else "Cadastrar Vault Key",
            modal=True, alignment=ft.Alignment.CENTER,
            inset_padding=ft.Padding.all(24),
            content=ft.Container(
                width=content_width,
                height=500 if content_width < 768 else 280,
                content=ft.ResponsiveRow(
                    spacing=16,
                    run_spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            col={"sm": 12, "md": 6},
                            controls=[name, value, allow_update],
                        ),
                        ft.Column(
                            col={"sm": 12, "md": 6},
                            controls=[description],
                        ),
                    ],
                ),
            ),
            actions=[build_secondary_button("Cancelar", close), save_button],
            on_close=close,
            on_dismiss=close,
        )
        return dialog

    async def on_delete(self, event: ft.ControlEvent, key: dict[str, object]) -> None:
        try:
            modules = await asyncio.to_thread(self.vault_service.modules_using, str(key["name"]))
        except Exception:
            self._show_error("Não foi possível verificar os módulos que usam a chave.")
            return
        page = event.page
        affected = ", ".join(str(module["name"]) for module in modules)
        message = f"Excluir a Vault Key {key['name']}?"
        if affected:
            message += f" Módulos afetados: {affected}. A chave ficará indisponível na próxima execução."

        def close(event=None) -> None:
            dialog.open = False
            page.update()

        async def confirm(event: ft.ControlEvent) -> None:
            delete_button.disabled = True
            page.update()
            try:
                await asyncio.to_thread(self.vault_service.delete, int(key["id"]))
            except ValueError as error:
                self._show_error(str(error))
            except Exception:
                self._show_error("Não foi possível excluir a Vault Key. Tente novamente.")
            else:
                close()
                if self.toaster_handler:
                    self.toaster_handler.show_success("Vault Key excluída.")
                await self.refresh()
            finally:
                delete_button.disabled = False
                page.update()

        delete_button = build_primary_button("Excluir", confirm)
        dialog = show_custom_dialog(page, "Excluir Vault Key", message, kind="warning", modal=True,
                                    alignment=ft.Alignment.CENTER, inset_padding=ft.Padding.all(24),
                                    actions=[build_secondary_button("Cancelar", close), delete_button])

    def _show_error(self, message: str) -> None:
        if self.toaster_handler:
            self.toaster_handler.show_error(message, title="Vault Keys")

    def _update_if_mounted(self) -> None:
        try:
            if self.page:
                self.update()
        except RuntimeError:
            pass
