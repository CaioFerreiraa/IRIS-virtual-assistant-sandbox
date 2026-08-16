import unittest

import flet as ft

from ui.shared.components.route_content_container import (
    build_route_content_container,
)


class RouteContentContainerTests(unittest.TestCase):
    def test_content_is_the_only_required_argument(self) -> None:
        content = ft.Text("Conteúdo")
        route_container = build_route_content_container(content)

        column = route_container.content
        self.assertIsInstance(column, ft.Column)
        self.assertEqual(1, len(column.controls))
        self.assertIs(content, column.controls[0].content)

    def test_optional_header_uses_standard_structure(self) -> None:
        trailing = ft.Text("Ação")
        route_container = build_route_content_container(
            ft.Text("Conteúdo"),
            icon=ft.Icons.HOME_ROUNDED,
            title="Início",
            subtitle="Escolha uma rota.",
            trailing=trailing,
        )

        header = route_container.content.controls[0]
        self.assertIsInstance(header, ft.Row)
        self.assertEqual(3, len(header.controls))
        self.assertIs(trailing, header.controls[-1])
        texts = _collect_text_values(header)
        self.assertIn("Início", texts)
        self.assertIn("Escolha uma rota.", texts)

    def test_shell_spacing_is_standardized(self) -> None:
        route_container = build_route_content_container(ft.Text("Conteúdo"))

        self.assertEqual(16, route_container.margin.left)
        self.assertEqual(28, route_container.margin.top)
        self.assertEqual(22, route_container.margin.right)
        self.assertEqual(25, route_container.margin.bottom)
        self.assertEqual(12, route_container.border_radius)

    def test_non_expanded_variant_keeps_the_same_visual_shell(self) -> None:
        route_container = build_route_content_container(
            ft.Text("Conteúdo modal"),
            expand=False,
        )

        self.assertFalse(route_container.expand)
        self.assertFalse(route_container.content.expand)
        self.assertTrue(route_container.content.tight)
        self.assertEqual(12, route_container.border_radius)


def _collect_text_values(control: ft.Control) -> list[str]:
    values: list[str] = []
    if isinstance(control, ft.Text):
        values.append(str(control.value))
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        values.extend(_collect_text_values(content))
    for child in getattr(control, "controls", ()) or ():
        if isinstance(child, ft.Control):
            values.extend(_collect_text_values(child))
    return values


if __name__ == "__main__":
    unittest.main()
