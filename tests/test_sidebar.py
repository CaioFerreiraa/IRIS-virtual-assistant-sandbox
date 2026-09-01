import unittest

import flet as ft

from ui.shared.components.sidebar import (
    MAX_SIDEBAR_WIDTH,
    MIN_SIDEBAR_WIDTH,
    MODULE_ITEM_HEIGHT,
    SidebarViewState,
    STATUS_DOT_SIZE,
    _build_module_icons,
    _build_module_tree,
    _build_tooltip_message,
    _module_background,
    build_sidebar,
)
from services.module_registry_state import InvalidModuleInfo
from ui.theme.colors import (
    BLUE_GREY,
    BORDER,
    CANCEL,
    GREY_100,
    GREY_200,
    GREY_300,
    GREY_400,
    GREY_500,
    GREY_900,
    PASTEL_DARK_PURPLE,
    PASTEL_PURPLE,
    SURFACE,
)


class SidebarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.modules = [
            {
                "module_id": 1,
                "name": "Abrir",
                "path": "Abrir",
                "parent_module_id": None,
                "custom_call_name": "iniciar",
                "description": "Abre recursos locais.",
            },
            {
                "module_id": 2,
                "name": "Web",
                "path": "Abrir / Web",
                "parent_module_id": 1,
                "custom_call_name": None,
                "description": "Agrupa ações da web.",
            },
            {
                "module_id": 3,
                "name": "Verde",
                "path": "Abrir / Web / Verde",
                "parent_module_id": 2,
                "custom_call_name": "site verde",
                "is_executable": True,
                "readme_content": "# Verde\nAbre o site verde configurado pelo módulo.",
            },
        ]

    def test_submodules_are_nested_under_their_parent(self) -> None:
        roots = _build_module_tree(self.modules)

        self.assertEqual(["Abrir"], [root.data["name"] for root in roots])
        self.assertEqual("Web", roots[0].children[0].data["name"])
        self.assertEqual("Verde", roots[0].children[0].children[0].data["name"])

    def test_tooltip_has_name_and_at_most_three_readme_lines(self) -> None:
        tooltip = _build_tooltip_message(
            "Clima",
            "# Clima\n" + " ".join(["previsão detalhada"] * 20),
        )

        lines = tooltip.splitlines()
        self.assertEqual("Clima", lines[0])
        self.assertEqual(4, len(lines))
        self.assertTrue(lines[-1].endswith("..."))

    def test_custom_call_name_is_rendered_as_secondary_text(self) -> None:
        sidebar = build_sidebar(None, lambda *_: None, modules=self.modules)
        texts = [control for control in _walk_controls(sidebar) if isinstance(control, ft.Text)]

        module_text = next(control for control in texts if control.value == "Abrir")
        custom_span = next(span for span in module_text.spans or () if span.text == " (iniciar)")

        self.assertTrue(custom_span.style.italic)
        self.assertEqual(10, custom_span.style.size)
        self.assertEqual("Abrir", module_text.value)

    def test_active_child_expands_its_ancestor_branches(self) -> None:
        expanded_ids: set[int] = set()
        build_sidebar(
            3,
            lambda *_: None,
            modules=self.modules,
            expanded_module_ids=expanded_ids,
        )

        self.assertEqual({1, 2}, expanded_ids)

    def test_manually_collapsed_parent_stays_closed_when_active(self) -> None:
        expanded_ids: set[int] = set()
        collapsed_ids = {1}
        build_sidebar(
            3,
            lambda *_: None,
            modules=self.modules,
            expanded_module_ids=expanded_ids,
            collapsed_module_ids=collapsed_ids,
        )

        self.assertNotIn(1, expanded_ids)

    def test_clicking_parent_toggles_children_and_selects_parent(self) -> None:
        expanded_ids: set[int] = set()
        collapsed_ids: set[int] = set()
        selected_ids: list[int] = []
        sidebar = build_sidebar(
            None,
            lambda module_id, _: selected_ids.append(module_id),
            modules=self.modules,
            expanded_module_ids=expanded_ids,
            collapsed_module_ids=collapsed_ids,
        )
        root_branch = _module_list(sidebar).controls[0]
        parent_item = root_branch.controls[0]

        parent_item.on_click(None)
        self.assertIn(1, expanded_ids)
        self.assertNotIn(1, collapsed_ids)
        self.assertEqual([1], selected_ids)

        parent_item.on_click(None)
        self.assertNotIn(1, expanded_ids)
        self.assertIn(1, collapsed_ids)
        self.assertEqual([1, 1], selected_ids)

    def test_sidebar_width_is_clamped_to_safe_limits(self) -> None:
        narrow = build_sidebar(None, lambda *_: None, width=1)
        wide = build_sidebar(None, lambda *_: None, width=9999)

        self.assertEqual(MIN_SIDEBAR_WIDTH, narrow.width)
        self.assertEqual(MAX_SIDEBAR_WIDTH, wide.width)

    def test_status_dots_are_small_and_rendered_before_the_label(self) -> None:
        sidebar = build_sidebar(None, lambda *_: None, modules=self.modules)
        root_branch = _module_list(sidebar).controls[0]
        child_branch = root_branch.controls[1].controls[0]
        grandchild_item = child_branch.controls[1].controls[0]
        labels = grandchild_item.content.controls[1]
        dot = labels.controls[0]
        label_column = labels.controls[1]

        self.assertEqual(STATUS_DOT_SIZE, dot.width)
        self.assertEqual(STATUS_DOT_SIZE, dot.height)
        self.assertEqual(GREY_900, dot.bgcolor)
        self.assertEqual("Módulo offline", dot.tooltip)
        self.assertEqual("Verde", label_column.controls[0].value)

    def test_organizational_module_does_not_have_status_dot(self) -> None:
        sidebar = build_sidebar(None, lambda *_: None, modules=self.modules)
        root_branch = _module_list(sidebar).controls[0]
        parent_item = root_branch.controls[0]
        labels = parent_item.content.controls[1]

        self.assertEqual(1, len(labels.controls))

    def test_problem_module_has_red_status_dot(self) -> None:
        modules = [
            {
                "module_id": 1,
                "name": "Quebrado",
                "validation_error": "Manifesto inválido.",
            }
        ]
        sidebar = build_sidebar(None, lambda *_: None, modules=modules)
        dots = [
            control
            for control in _walk_controls(sidebar)
            if isinstance(control, ft.Container)
            and control.width == STATUS_DOT_SIZE
            and control.height == STATUS_DOT_SIZE
        ]

        self.assertTrue(any(dot.bgcolor == CANCEL for dot in dots))

    def test_invalid_module_has_red_status_dot(self) -> None:
        sidebar = build_sidebar(
            None,
            lambda *_: None,
            modules=self.modules,
            invalid_modules=[
                InvalidModuleInfo(
                    folder_name="quebrado",
                    message="Manifesto inválido.",
                    log_path="modules/quebrado/module.log",
                )
            ],
        )
        dots = [
            control
            for control in _walk_controls(sidebar)
            if isinstance(control, ft.Container)
            and control.width == STATUS_DOT_SIZE
            and control.height == STATUS_DOT_SIZE
        ]

        self.assertTrue(any(dot.bgcolor == CANCEL for dot in dots))

    def test_module_icon_colors_do_not_change_with_status(self) -> None:
        problem_icon = _build_module_icons(
            {
                "icon": "warning",
                "validation_error": "Falha ao validar o módulo.",
            }
        )
        executable_icon = _build_module_icons(
            {
                "icon": "play_arrow",
                "is_executable": True,
            }
        )

        for icon in (problem_icon, executable_icon):
            self.assertEqual(BLUE_GREY, icon.bgcolor)
            self.assertIsInstance(icon.content, ft.Text)
            self.assertEqual(PASTEL_DARK_PURPLE, icon.content.color)

    def test_parent_and_children_follow_grey_depth_scale(self) -> None:
        self.assertEqual(SURFACE, _module_background(0))
        self.assertEqual(GREY_100, _module_background(1))
        self.assertEqual(GREY_200, _module_background(2))
        self.assertEqual(GREY_300, _module_background(3))
        self.assertEqual(GREY_400, _module_background(4))
        self.assertEqual(GREY_500, _module_background(5))
        self.assertEqual(GREY_500, _module_background(20))

    def test_module_list_fills_available_surface_area(self) -> None:
        sidebar = build_sidebar(None, lambda *_: None, modules=self.modules)
        sidebar_panel = sidebar.content.controls[0]
        list_shell = sidebar_panel.content.controls[1]
        module_list = _module_list(sidebar)

        self.assertEqual(0, sidebar_panel.padding)
        self.assertTrue(sidebar_panel.content.expand)
        self.assertTrue(list_shell.expand)
        self.assertEqual(SURFACE, list_shell.bgcolor)
        self.assertTrue(module_list.expand)
        self.assertEqual(0, module_list.padding)

    def test_reuses_sidebar_tree_when_the_active_route_changes(self) -> None:
        view_state = SidebarViewState()
        first_sidebar = build_sidebar(
            None,
            lambda *_: None,
            modules=self.modules,
            view_state=view_state,
        )
        first_module_list = _module_list(first_sidebar)

        second_sidebar = build_sidebar(
            3,
            lambda *_: None,
            modules=self.modules,
            view_state=view_state,
        )

        self.assertIs(first_sidebar, second_sidebar)
        self.assertIs(first_module_list, _module_list(second_sidebar))

    def test_module_items_keep_fixed_height(self) -> None:
        expanded_ids = {1, 2}
        sidebar = build_sidebar(
            None,
            lambda *_: None,
            modules=self.modules,
            expanded_module_ids=expanded_ids,
        )
        root_branch = _module_list(sidebar).controls[0]
        parent_item = root_branch.controls[0]
        child_branch = root_branch.controls[1].controls[0]
        child_item = child_branch.controls[0]
        grandchild_item = child_branch.controls[1].controls[0]

        self.assertEqual(MODULE_ITEM_HEIGHT, parent_item.height)
        self.assertEqual(MODULE_ITEM_HEIGHT, child_item.height)
        self.assertEqual(MODULE_ITEM_HEIGHT, grandchild_item.height)

    def test_module_name_uses_fixed_item_multiline_text(self) -> None:
        sidebar = build_sidebar(None, lambda *_: None, modules=self.modules)
        name = next(
            control
            for control in _walk_controls(sidebar)
            if isinstance(control, ft.Text) and control.value == "Abrir"
        )

        self.assertEqual(2, name.max_lines)
        self.assertEqual(ft.TextOverflow.ELLIPSIS, name.overflow)

    def test_active_module_has_underline_without_changing_item_border(self) -> None:
        sidebar = build_sidebar(1, lambda *_: None, modules=self.modules)
        root_branch = _module_list(sidebar).controls[0]
        parent_item = root_branch.controls[0]
        labels = parent_item.content.controls[1]
        label_column = labels.controls[-1]
        underline = label_column.controls[1]

        self.assertEqual(BORDER, parent_item.border.bottom.color)
        self.assertEqual(0, parent_item.border.top.width)
        self.assertTrue(underline.visible)
        self.assertEqual(PASTEL_PURPLE, underline.bgcolor)
        self.assertEqual(2, underline.height)

        label_text = label_column.controls[0]
        label_text.on_size_change(type("SizeEvent", (), {"width": 64.0})())
        self.assertEqual(64.0, underline.width)

    def test_nested_items_keep_the_same_padding(self) -> None:
        sidebar = build_sidebar(
            None,
            lambda *_: None,
            modules=self.modules,
            expanded_module_ids={1, 2},
        )
        root_branch = _module_list(sidebar).controls[0]
        parent_item = root_branch.controls[0]
        child_branch = root_branch.controls[1].controls[0]
        child_item = child_branch.controls[0]
        grandchild_item = child_branch.controls[1].controls[0]

        self.assertEqual(12, parent_item.padding.left)
        self.assertEqual(12, child_item.padding.left)
        self.assertEqual(12, grandchild_item.padding.left)

    def test_first_child_uses_parent_background_as_shadow(self) -> None:
        sidebar = build_sidebar(
            None,
            lambda *_: None,
            modules=self.modules,
            expanded_module_ids={1, 2},
        )
        root_branch = _module_list(sidebar).controls[0]
        parent_item = root_branch.controls[0]
        child_branch = root_branch.controls[1].controls[0]
        child_item = child_branch.controls[0]
        grandchild_item = child_branch.controls[1].controls[0]

        self.assertIsNone(parent_item.shadow)
        self.assertEqual(SURFACE, child_item.shadow.color)
        self.assertEqual(GREY_100, grandchild_item.shadow.color)


def _module_list(sidebar: ft.Container) -> ft.ListView:
    sidebar_panel = sidebar.content.controls[0]
    return sidebar_panel.content.controls[1].content


def _walk_controls(control: ft.Control):
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from _walk_controls(content)
    for child in getattr(control, "controls", ()) or ():
        if isinstance(child, ft.Control):
            yield from _walk_controls(child)


if __name__ == "__main__":
    unittest.main()
