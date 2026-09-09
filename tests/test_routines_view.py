import unittest
from types import SimpleNamespace

import flet as ft

from services.routine_schedule_service import MONTHLY, RoutineScheduleService
from ui.routines.view import RoutineFormState, RoutinesViewState


class FakeRoutineService:
    def __init__(self, *, fail_load: bool = False) -> None:
        self.fail_load = fail_load
        self.schedule_service = RoutineScheduleService()
        self.created = []
        self.updated = []

    def list_routines(self):
        if self.fail_load:
            raise RuntimeError("Falha controlada")
        return []

    def create_routine(self, **values):
        self.created.append(values)
        return {"id": 1, **values}

    def update_routine(self, routine_id, **values):
        self.updated.append((routine_id, values))
        return {"id": routine_id, **values}


class RoutinesViewTests(unittest.TestCase):
    def test_execute_captures_page_before_replacing_clicked_button(self) -> None:
        state = RoutinesViewState(
            routine_service=FakeRoutineService(),
            toaster_handler=None,
        )
        calls: list[str] = []
        page = SimpleNamespace(run_thread=lambda worker: calls.append("thread"))

        class GuardedEvent:
            @property
            def page(self):
                calls.append("page")
                return page

        def refresh() -> None:
            calls.append("refresh")
            if "page" not in calls:
                raise RuntimeError("O controle foi removido antes de capturar a página.")

        state.refresh = refresh
        state.execute_now(GuardedEvent(), 1)

        self.assertEqual(["page", "refresh", "thread"], calls)

    def test_empty_table_and_route_header_replace_placeholder(self) -> None:
        state = RoutinesViewState(
            routine_service=FakeRoutineService(),
            toaster_handler=None,
        )
        view = state.build()
        texts = _collect_text_values(view)
        self.assertIn("Rotinas", texts)
        self.assertIn("Nova rotina", texts)
        self.assertIn("Nenhuma rotina cadastrada.", texts)
        self.assertNotIn("Conteúdo em desenvolvimento.", texts)

    def test_form_contains_required_fields_and_only_available_options(self) -> None:
        parent = RoutinesViewState(
            routine_service=FakeRoutineService(),
            toaster_handler=None,
        )
        form = RoutineFormState(
            parent=parent,
            routine=None,
            modules=[
                {
                    "module_id": 1,
                    "path": "Disponível / Executar",
                    "is_available": True,
                    "accepts_argument": True,
                    "requires_argument": True,
                },
                {
                    "module_id": 2,
                    "path": "Indisponível / Executar",
                    "is_available": False,
                    "accepts_argument": False,
                    "requires_argument": False,
                },
            ],
        )
        dialog = form.build_dialog()
        texts = _collect_text_values(dialog)
        option_keys = [str(option.key) for option in form.module_dropdown.options]

        self.assertIn("Nome da rotina", texts)
        self.assertIn("Tipo de repetição", texts)
        self.assertIn("Parar se alguma requisição falhar", texts)
        self.assertIn("Módulos da rotina", texts)
        self.assertIn("Geral", texts)
        self.assertIn("Agendamento", texts)
        self.assertIn("Módulos", texts)
        self.assertIn("Adicionar dia da semana", texts)
        self.assertIn("Todos os dias", texts)
        self.assertIn("Nenhum dia selecionado.", texts)
        self.assertEqual(["1"], option_keys)
        self.assertTrue(form.active_switch.value)
        self.assertTrue(form.save_button.disabled)
        self.assertNotEqual(
            form.save_button.style.bgcolor[ft.ControlState.DISABLED],
            form.save_button.style.bgcolor[ft.ControlState.DEFAULT],
        )
        self.assertEqual(340, form.day_dropdown.width)

        form.saved_days.add("mon")
        form._render_days()
        self.assertIn("Segunda-feira", _collect_text_values(form.day_controls))
        form.remove_day(SimpleNamespace(), "mon")
        self.assertEqual([], form._selected_days())

    def test_month_days_use_validated_integer_input_and_warning(self) -> None:
        parent = RoutinesViewState(
            routine_service=FakeRoutineService(),
            toaster_handler=None,
        )
        form = RoutineFormState(parent=parent, routine=None, modules=[])
        form.build_dialog()
        form.schedule_type_field.value = MONTHLY
        form.on_schedule_type_change(SimpleNamespace())

        self.assertIsNone(form.day_dropdown)
        self.assertIsNotNone(form.month_day_field)

        form.month_day_draft = "-1"
        form.add_month_day(SimpleNamespace())
        self.assertIn("inteiro", str(form.month_day_field.error))

        form.month_day_draft = "32"
        form.add_month_day(SimpleNamespace())
        self.assertIn("maior que 31", str(form.month_day_field.error))

        form.month_day_field.value = "29"
        form.on_month_day_change(SimpleNamespace(control=form.month_day_field))
        self.assertIn("não existir", str(form.month_day_field.helper))
        form.add_month_day(SimpleNamespace())
        self.assertEqual([29], form._selected_days())

        form.month_day_draft = "29"
        form.add_month_day(SimpleNamespace())
        self.assertIn("já foi adicionado", str(form.month_day_field.error))

    def test_save_button_tracks_all_required_values(self) -> None:
        service = FakeRoutineService()
        parent = RoutinesViewState(routine_service=service, toaster_handler=None)
        form = RoutineFormState(
            parent=parent,
            routine=None,
            modules=[
                {
                    "module_id": 1,
                    "path": "Módulo simples",
                    "is_available": True,
                    "accepts_argument": False,
                    "requires_argument": False,
                }
            ],
        )
        form.build_dialog()
        self.assertTrue(form.save_button.disabled)

        form.name_field.value = "Rotina válida"
        form.on_form_value_change(SimpleNamespace())
        form.on_day_selected(SimpleNamespace(control=SimpleNamespace(value="mon")))
        form.module_dropdown.value = "1"
        form.add_module(SimpleNamespace())
        self.assertFalse(form.save_button.disabled)

        form.time_field.value = "25:00"
        form.on_schedule_value_change(SimpleNamespace())
        self.assertTrue(form.save_button.disabled)

    def test_add_reorder_remove_and_submit_update_form_state(self) -> None:
        service = FakeRoutineService()
        parent = RoutinesViewState(routine_service=service, toaster_handler=None)
        modules = [
            {
                "module_id": 1,
                "path": "Primeiro",
                "is_available": True,
                "accepts_argument": False,
                "requires_argument": False,
            },
            {
                "module_id": 2,
                "path": "Segundo",
                "is_available": True,
                "accepts_argument": False,
                "requires_argument": False,
            },
        ]
        form = RoutineFormState(parent=parent, routine=None, modules=modules)
        form.build_dialog()
        form.module_dropdown.value = "1"
        form.add_module(SimpleNamespace())
        form.module_dropdown.value = "2"
        form.add_module(SimpleNamespace())
        form.move_step(SimpleNamespace(), 1, -1)
        self.assertEqual([2, 1], [step["module_id"] for step in form.steps])
        form.remove_step(SimpleNamespace(), 1)
        self.assertEqual([2], [step["module_id"] for step in form.steps])

        form.name_field.value = "Rotina visual"
        form.saved_days.add("mon")
        form.submit(SimpleNamespace(page=SimpleNamespace(update=lambda: None)))
        self.assertEqual(1, len(service.created))
        self.assertEqual([{"action_id": None, "module_id": 2, "active": True, "argument": None}], service.created[0]["actions"])

    def test_load_failure_renders_controlled_error_state(self) -> None:
        state = RoutinesViewState(
            routine_service=FakeRoutineService(fail_load=True),
            toaster_handler=None,
        )
        view = state.build()
        texts = _collect_text_values(view)
        self.assertIn("Não foi possível carregar as rotinas.", texts)
        self.assertIn("Falha controlada", texts)


def _collect_text_values(control: ft.Control) -> list[str]:
    values: list[str] = []
    if isinstance(control, ft.Text):
        values.append(str(control.value))
    label = getattr(control, "label", None)
    if isinstance(label, str):
        values.append(label)
    elif isinstance(label, ft.Control):
        values.extend(_collect_text_values(label))
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        values.extend(_collect_text_values(content))
    title = getattr(control, "title", None)
    if isinstance(title, ft.Control):
        values.extend(_collect_text_values(title))
    for child in getattr(control, "controls", ()) or ():
        if isinstance(child, ft.Control):
            values.extend(_collect_text_values(child))
    for child in getattr(control, "actions", ()) or ():
        if isinstance(child, ft.Control):
            values.extend(_collect_text_values(child))
    for child in getattr(control, "tabs", ()) or ():
        if isinstance(child, ft.Control):
            values.extend(_collect_text_values(child))
    return values


if __name__ == "__main__":
    unittest.main()
