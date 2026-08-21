from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import re
import textwrap

import flet as ft

from services.module_registry_state import InvalidModuleInfo
from services.module_service import module_has_problem
from ui.shared.components.material_icons import material_icon
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    CANCEL,
    GREY_100,
    GREY_200,
    GREY_300,
    GREY_400,
    GREY_500,
    PASTEL_DARK_GREEN,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.theme.fonts import TITLE_FONT

DEFAULT_SIDEBAR_WIDTH = 272.0
MIN_SIDEBAR_WIDTH = 240.0
MAX_SIDEBAR_WIDTH = 460.0
MODULE_ITEM_HEIGHT = 55.0
STATUS_DOT_SIZE = 7.0
TOOLTIP_LINE_WIDTH = 44
TOOLTIP_README_LINES = 3
CHILD_BACKGROUNDS = (
    GREY_100,
    GREY_200,
    GREY_300,
    GREY_400,
    GREY_500,
)
PARENT_SHADOW_COLOR = ft.Colors.with_opacity(0.16, PASTEL_DARK_PURPLE)


@dataclass
class _ModuleNode:
    data: Mapping[str, object]
    children: list["_ModuleNode"] = field(default_factory=list)


# Dados da árvore

def _build_module_tree(
    modules: Sequence[Mapping[str, object]],
) -> list[_ModuleNode]:
    nodes: dict[int, _ModuleNode] = {}
    ordered_ids: list[int] = []

    for module in modules:
        module_id = module.get("module_id")
        if type(module_id) is not int or module_id in nodes:
            continue
        nodes[module_id] = _ModuleNode(module)
        ordered_ids.append(module_id)

    roots: list[_ModuleNode] = []
    for module_id in ordered_ids:
        node = nodes[module_id]
        parent_id = node.data.get("parent_module_id")
        parent = nodes.get(parent_id) if type(parent_id) is int else None

        if parent is None or parent is node:
            roots.append(node)
            continue
        parent.children.append(node)

    return roots


def _contains_active_module(
    node: _ModuleNode,
    active_module_id: int | None,
) -> bool:
    if node.data.get("module_id") == active_module_id:
        return True
    for child in node.children:
        if _contains_active_module(child, active_module_id):
            return True
    return False


def _module_background(depth: int) -> str:
    if depth == 0:
        return SURFACE
    child_index = min(depth - 1, len(CHILD_BACKGROUNDS) - 1)
    return CHILD_BACKGROUNDS[child_index]


# Texto e status do item

def _build_tooltip_message(name: str, readme_content: str) -> str:
    plain_text = _markdown_to_plain_text(readme_content)
    if plain_text.casefold().startswith(name.casefold()):
        plain_text = plain_text[len(name) :].lstrip(" -:\n")
    if not plain_text:
        plain_text = "Sem descrição disponível."

    lines = textwrap.wrap(
        plain_text,
        width=TOOLTIP_LINE_WIDTH,
        break_long_words=False,
        break_on_hyphens=False,
    )
    preview = lines[:TOOLTIP_README_LINES]
    if len(lines) > TOOLTIP_README_LINES:
        preview[-1] = f"{preview[-1].rstrip(' .')}..."
    return "\n".join([name, *preview])


def _markdown_to_plain_text(content: str) -> str:
    text = re.sub(r"```.*?```", " ", content, flags=re.DOTALL)
    text = re.sub(r"!\[([^]]*)]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", text)

    lines: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"^\s*(?:#{1,6}|[-+*>]|\d+[.)])\s*", "", line)
        cleaned = re.sub(r"[*_`~]", "", cleaned).strip()
        if cleaned:
            lines.append(cleaned)
    return " ".join(lines)


def _build_status_dot(module: Mapping[str, object]) -> ft.Container | None:
    if module_has_problem(module):
        color = CANCEL
        tooltip = "Módulo com problema"
    elif bool(module.get("is_executable")):
        color = PASTEL_DARK_GREEN
        tooltip = "Módulo executável"
    else:
        return None

    return ft.Container(
        width=STATUS_DOT_SIZE,
        height=STATUS_DOT_SIZE,
        border_radius=STATUS_DOT_SIZE / 2,
        bgcolor=color,
        border=ft.Border.all(1, BORDER),
        tooltip=tooltip,
    )


def _build_module_labels(
    module: Mapping[str, object],
    name: str,
    custom_call_name: str,
    is_active: bool,
) -> ft.Row:
    custom_call_span = (
        ft.TextSpan(
            text=f" ({custom_call_name})",
            style=ft.TextStyle(
                size=10,
                color=TEXT_SECONDARY,
                italic=True,
            ),
        )
        if custom_call_name
        else None
    )
    underline = ft.Container(
        height=2,
        border_radius=1,
        bgcolor=PASTEL_PURPLE if is_active else None,
        visible=is_active,
    )

    def on_label_size_change(event: ft.LayoutSizeChangeEvent) -> None:
        if underline.width == event.width:
            return
        underline.width = event.width
        _update_if_mounted(underline)

    label = ft.Column(
        expand=True,
        tight=True,
        spacing=3,
        controls=[
            ft.Text(
                name,
                size=12,
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_600,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                spans=[custom_call_span] if custom_call_span is not None else None,
                on_size_change=on_label_size_change if is_active else None,
            ),
            underline,
        ],
    )

    controls: list[ft.Control] = []
    status_dot = _build_status_dot(module)
    if status_dot is not None:
        controls.append(status_dot)
    controls.append(label)

    return ft.Row(
        expand=True,
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=controls,
    )


def _build_module_icons(module: Mapping[str, object]) -> ft.Container:
    return ft.Container(
        width=26,
        height=26,
        border_radius=8,
        alignment=ft.Alignment.CENTER,
        bgcolor=BLUE_GREY,
        content=material_icon(
            str(module.get("icon") or "extension"),
            size=20,
            color=PASTEL_DARK_PURPLE,
            weight=ft.FontWeight.W_500,
        ),
    )

# Controles da árvore

def _build_module_item(
    module: Mapping[str, object],
    depth: int,
    is_active: bool,
    on_click: Callable[[ft.ControlEvent], None],
    trailing: ft.Control | None = None,
    parent_shadow_color: str | None = None,
) -> ft.Container:
    name = str(module.get("name") or module.get("path") or "Módulo")
    custom_call_name = str(module.get("custom_call_name") or "").strip()
    readme_content = str(
        module.get("readme_content")
        or module.get("description")
        or ""
    )

    row_controls: list[ft.Control] = [
        _build_module_icons(module),
        _build_module_labels(module, name, custom_call_name, is_active),
    ]
    if trailing is not None:
        row_controls.append(trailing)

    return ft.Container(
        height=MODULE_ITEM_HEIGHT,
        padding=ft.Padding(
            left=12,
            top=8,
            right=8,
            bottom=8,
        ),
        alignment=ft.Alignment.CENTER_LEFT,
        border=ft.Border.only(bottom=ft.BorderSide(0.5, BORDER)),
        bgcolor=_module_background(depth),
        border_radius=0,
        shadow=(
            ft.BoxShadow(
                blur_radius=5,
                color=parent_shadow_color,
                offset=ft.Offset(0, -4),
            )
            if parent_shadow_color is not None
            else None
        ),
        ink=True,
        ink_color=ft.Colors.with_opacity(0.06, PASTEL_DARK_PURPLE),
        tooltip=ft.Tooltip(
            message=_build_tooltip_message(name, readme_content),
            padding=ft.Padding(left=12, top=9, right=12, bottom=9),
            bgcolor=PASTEL_DARK_PURPLE,
            text_style=ft.TextStyle(size=12, color=SURFACE, height=1.35),
            wait_duration=350,
            size_constraints=ft.BoxConstraints(max_width=340),
        ),
        on_click=on_click,
        content=ft.Row(
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=row_controls,
        ),
    )


def _build_module_branch(
    node: _ModuleNode,
    active_module_id: int | None,
    on_select: Callable[[int, str], None],
    expanded_module_ids: set[int],
    collapsed_module_ids: set[int],
    visited_ids: set[int],
    depth: int = 0,
    parent_shadow_color: str | None = None,
) -> ft.Control:
    module_id = int(node.data["module_id"])
    if module_id in visited_ids:
        return ft.Container()

    branch_visited_ids = {*visited_ids, module_id}
    is_active = module_id == active_module_id
    name = str(node.data.get("name") or node.data.get("path") or "Módulo")

    if not node.children:
        return _build_module_item(
            node.data,
            depth,
            is_active,
            lambda _: on_select(module_id, name),
            parent_shadow_color=parent_shadow_color,
        )

    starts_expanded = (
        module_id not in collapsed_module_ids
        and (
            module_id in expanded_module_ids
            or _contains_active_module(node, active_module_id)
        )
    )
    if starts_expanded:
        expanded_module_ids.add(module_id)

    children = ft.Column(
        visible=starts_expanded,
        spacing=0,
        controls=[
            _build_module_branch(
                child,
                active_module_id,
                on_select,
                expanded_module_ids,
                collapsed_module_ids,
                branch_visited_ids,
                depth + 1,
                PARENT_SHADOW_COLOR if child_index == 0 else None,
            )
            for child_index, child in enumerate(node.children)
        ],
    )
    toggle_button = ft.IconButton(
        icon=(
            ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            if starts_expanded
            else ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED
        ),
        icon_size=18,
        icon_color=TEXT_SECONDARY,
        width=28,
        height=28,
        padding=0,
        tooltip="Recolher submódulos" if starts_expanded else "Mostrar submódulos",
    )

    def set_expanded(expanded: bool) -> None:
        children.visible = expanded
        if expanded:
            expanded_module_ids.add(module_id)
            collapsed_module_ids.discard(module_id)
            toggle_button.icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            toggle_button.tooltip = "Recolher submódulos"
        else:
            expanded_module_ids.discard(module_id)
            collapsed_module_ids.add(module_id)
            toggle_button.icon = ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED
            toggle_button.tooltip = "Mostrar submódulos"
        _update_if_mounted(toggle_button)
        _update_if_mounted(children)

    def on_toggle(_: ft.ControlEvent) -> None:
        set_expanded(not children.visible)

    def on_parent_click(_: ft.ControlEvent) -> None:
        set_expanded(not children.visible)
        on_select(module_id, name)

    toggle_button.on_click = on_toggle
    return ft.Column(
        spacing=0,
        controls=[
            _build_module_item(
                node.data,
                depth,
                is_active,
                on_parent_click,
                toggle_button,
                parent_shadow_color,
            ),
            children,
        ],
    )


def _update_if_mounted(control: ft.Control) -> None:
    try:
        control.update()
    except RuntimeError:
        pass


# Diagnóstico e títulos

def _build_invalid_module_item(module: InvalidModuleInfo) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(left=14, top=10, right=10, bottom=10),
        bgcolor=GREY_100,
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
        border_radius=0,
        tooltip=f"Log técnico: {module.log_path}",
        content=ft.Row(
            spacing=9,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Container(
                    width=STATUS_DOT_SIZE,
                    height=STATUS_DOT_SIZE,
                    margin=ft.Margin(top=3),
                    border_radius=STATUS_DOT_SIZE / 2,
                    bgcolor=CANCEL,
                    border=ft.Border.all(1, BORDER),
                    tooltip="Módulo com problema",
                ),
                ft.Column(
                    expand=True,
                    tight=True,
                    spacing=2,
                    controls=[
                        ft.Text(
                            module.folder_name,
                            size=12,
                            weight=ft.FontWeight.W_700,
                            color=TEXT_PRIMARY,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            no_wrap=True,
                        ),
                        ft.Text(
                            module.message,
                            size=11,
                            color=TEXT_SECONDARY,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            module.log_path,
                            size=10,
                            color=TEXT_SECONDARY,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            no_wrap=True,
                        ),
                    ],
                ),
            ],
        ),
    )


def _build_section_title(label: str, icon: ft.IconData, count: int) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(left=16, top=28, right=14, bottom=16),
        #bgcolor=GREY_100,
        #border=ft.Border.only(bottom=ft.BorderSide(0.3, PASTEL_PURPLE)),
        content=ft.Row(
            spacing=7,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=17, color=PASTEL_DARK_PURPLE),
                ft.Text(
                    label,
                    expand=True,
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=TEXT_PRIMARY,
                    font_family=TITLE_FONT
                ),
                ft.Container(
                    width=24,
                    height=22,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=SURFACE,
                    border_radius=11,
                    content=ft.Text(
                        str(count),
                        size=10,
                        weight=ft.FontWeight.W_700,
                        color=TEXT_SECONDARY,
                    ),
                ),
            ],
        ),
    )


# Sidebar e redimensionamento

def build_sidebar(
    active_module_id: int | None,
    on_select: Callable[[int, str], None],
    modules: Sequence[Mapping[str, object]] | None = None,
    invalid_modules: Sequence[InvalidModuleInfo] | None = None,
    width: float = DEFAULT_SIDEBAR_WIDTH,
    on_width_change: Callable[[float], None] | None = None,
    expanded_module_ids: set[int] | None = None,
    collapsed_module_ids: set[int] | None = None,
) -> ft.Container:
    module_data = tuple(modules or ())
    expanded_ids = expanded_module_ids if expanded_module_ids is not None else set()
    collapsed_ids = collapsed_module_ids if collapsed_module_ids is not None else set()
    roots = _build_module_tree(module_data)

    module_items = [
        _build_module_branch(
            node,
            active_module_id,
            on_select,
            expanded_ids,
            collapsed_ids,
            set(),
        )
        for node in roots
    ]
    if not module_items:
        module_items = [
            ft.Container(
                padding=ft.Padding(left=16, top=12, right=14, bottom=12),
                alignment=ft.Alignment.CENTER,
                content=ft.Text(
                    "Nenhum módulo disponível.",
                    size=12,
                    color=TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
            )
        ]

    panel_controls: list[ft.Control] = [
        _build_section_title("Módulos", ft.Icons.WIDGETS_OUTLINED, len(module_data)),
        ft.Container(
            expand=True,
            border_radius=0,
            bgcolor=SURFACE,
            content=ft.ListView(
                spacing=0,
                padding=0,
                expand=True,
                controls=module_items,
            ),
        )
    ]

    invalid_items = [
        _build_invalid_module_item(module)
        for module in invalid_modules or ()
    ]
    if invalid_items:
        panel_controls.extend(
            [
                ft.Divider(height=1, color=BORDER),
                _build_section_title(
                    "Diagnóstico",
                    ft.Icons.HEALTH_AND_SAFETY_OUTLINED,
                    len(invalid_items),
                ),
                ft.ListView(
                    spacing=0,
                    padding=0,
                    height=min(220, len(invalid_items) * 96),
                    controls=invalid_items,
                ),
            ]
        )

    sidebar_panel = ft.Container(
        left=0,
        top=0,
        right=8,
        bottom=0,
        margin=ft.Margin(left=18, top=28, right=4, bottom=25),
        padding=0,
        bgcolor=BLUE_GREY,
        border=ft.Border.all(1, BORDER),
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=ft.BoxShadow(
            blur_radius=18,
            color=ft.Colors.with_opacity(0.06, PASTEL_DARK_PURPLE),
            offset=ft.Offset(0, 5),
        ),
        content=ft.Column(
            expand=True,
            spacing=20,
            controls=panel_controls,
        ),
    )

    root = ft.Container(
        width=_clamp_sidebar_width(width),
        expand=True,
    )
    resize_handle = _build_resize_handle(root, width, on_width_change)
    root.content = ft.Stack(
        expand=True,
        controls=[sidebar_panel, resize_handle],
    )
    return root


def _clamp_sidebar_width(width: float) -> float:
    return max(MIN_SIDEBAR_WIDTH, min(MAX_SIDEBAR_WIDTH, float(width)))


def _build_resize_handle(
    root: ft.Container,
    fallback_width: float,
    on_width_change: Callable[[float], None] | None,
) -> ft.GestureDetector:
    resize_line = ft.Container(
        width=3,
        height=54,
        border_radius=2,
        bgcolor=BORDER,
    )

    def set_highlighted(highlighted: bool) -> None:
        resize_line.bgcolor = PASTEL_DARK_PURPLE if highlighted else BORDER
        resize_line.width = 4 if highlighted else 3
        _update_if_mounted(resize_line)

    def on_drag_update(event: ft.DragUpdateEvent) -> None:
        delta = event.primary_delta
        if delta is None and event.local_delta is not None:
            delta = event.local_delta.x
        if delta is None:
            return

        current_width = float(root.width or fallback_width)
        new_width = _clamp_sidebar_width(current_width + float(delta))
        if new_width == root.width:
            return

        root.width = new_width
        if on_width_change is not None:
            on_width_change(new_width)
        _update_if_mounted(root)

    return ft.GestureDetector(
        right=0,
        top=20,
        bottom=20,
        width=10,
        mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
        tooltip="Arraste para redimensionar o menu",
        on_enter=lambda _: set_highlighted(True),
        on_exit=lambda _: set_highlighted(False),
        on_horizontal_drag_start=lambda _: set_highlighted(True),
        on_horizontal_drag_update=on_drag_update,
        on_horizontal_drag_end=lambda _: set_highlighted(False),
        content=ft.Container(
            alignment=ft.Alignment.CENTER,
            content=resize_line,
        ),
    )
