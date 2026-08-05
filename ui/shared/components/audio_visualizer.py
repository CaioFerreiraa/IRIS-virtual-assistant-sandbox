from __future__ import annotations

import flet as ft

from ui.theme.colors import BLUE_GREY, BORDER, PASTEL_BLUE, PASTEL_PURPLE, TEXT_SECONDARY


BAR_WEIGHTS = (0.28, 0.42, 0.62, 0.82, 1.0, 0.76, 0.54, 0.88, 0.68, 0.46, 0.3)


class AudioVisualizer:
    """Visualização leve de um nível de áudio já calculado pelo serviço."""

    def __init__(self, label: str = "Nível do microfone"):
        self.bars = [
            ft.Container(
                width=7,
                height=5,
                border_radius=4,
                bgcolor=PASTEL_BLUE,
                animate=ft.Animation(90, ft.AnimationCurve.EASE_OUT),
            )
            for _ in BAR_WEIGHTS
        ]
        self.level_text = ft.Text("Sem sinal", size=12, color=TEXT_SECONDARY)
        self.root = ft.Container(
            padding=ft.Padding(left=14, top=10, right=14, bottom=10),
            bgcolor=BLUE_GREY,
            border=ft.Border.all(1, BORDER),
            border_radius=8,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        tight=True,
                        spacing=1,
                        controls=[ft.Text(label, size=13), self.level_text],
                    ),
                    ft.Container(
                        height=42,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=self.bars,
                        ),
                    ),
                ],
            ),
        )

    def build(self) -> ft.Container:
        return self.root

    def set_level(self, level: float) -> None:
        normalized = max(0.0, min(1.0, level))
        for bar, weight in zip(self.bars, BAR_WEIGHTS, strict=True):
            bar.height = 5 + (32 * normalized * weight)
            bar.bgcolor = PASTEL_PURPLE if normalized >= 0.55 else PASTEL_BLUE

        if normalized < 0.04:
            self.level_text.value = "Sem sinal"
        elif normalized < 0.25:
            self.level_text.value = "Sinal baixo"
        elif normalized < 0.75:
            self.level_text.value = "Microfone detectado"
        else:
            self.level_text.value = "Sinal forte"
