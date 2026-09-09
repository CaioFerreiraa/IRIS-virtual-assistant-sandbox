import unittest
from datetime import datetime, timezone

from services.routine_schedule_service import (
    MONTHLY,
    WEEKLY,
    RoutineScheduleService,
)


class RoutineScheduleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RoutineScheduleService(timezone.utc)

    def test_builds_weekly_cron_in_canonical_order(self) -> None:
        expression = self.service.build_cron(
            WEEKLY,
            ["fri", "mon", "wed"],
            "18:30",
        )
        self.assertEqual("30 18 * * mon,wed,fri", expression)

    def test_builds_monthly_cron_with_sorted_days(self) -> None:
        expression = self.service.build_cron(MONTHLY, [15, 1], "09:00")
        self.assertEqual("0 9 1,15 * *", expression)

    def test_parses_generated_weekly_and_monthly_expressions(self) -> None:
        weekly = self.service.parse_cron("0 8 * * mon,tue,wed,thu,fri")
        monthly = self.service.parse_cron("30 18 1,15,31 * *")
        self.assertEqual(WEEKLY, weekly.schedule_type)
        self.assertEqual("08:00", weekly.time)
        self.assertEqual(MONTHLY, monthly.schedule_type)
        self.assertEqual((1, 15, 31), monthly.days)

    def test_rejects_invalid_time(self) -> None:
        for invalid_time in ("8:00", "24:00", "10:60", "texto"):
            with self.subTest(invalid_time=invalid_time):
                with self.assertRaises(ValueError):
                    self.service.build_cron(WEEKLY, ["mon"], invalid_time)

    def test_rejects_empty_days_and_invalid_month_days(self) -> None:
        with self.assertRaisesRegex(ValueError, "ao menos um dia"):
            self.service.build_cron(WEEKLY, [], "08:00")
        for invalid_day in (0, 32):
            with self.subTest(invalid_day=invalid_day):
                with self.assertRaisesRegex(ValueError, "1 e 31"):
                    self.service.build_cron(MONTHLY, [invalid_day], "08:00")

    def test_builds_friendly_descriptions(self) -> None:
        self.assertEqual(
            "Todos os dias às 08:00",
            self.service.describe("0 8 * * mon,tue,wed,thu,fri,sat,sun"),
        )
        self.assertEqual(
            "Segunda-feira, quarta-feira e sexta-feira às 18:30",
            self.service.describe("30 18 * * mon,wed,fri"),
        )
        self.assertEqual(
            "Dias 1 e 15 do mês às 09:00",
            self.service.describe("0 9 1,15 * *"),
        )

    def test_next_run_skips_day_31_when_month_does_not_have_it(self) -> None:
        next_run = self.service.next_run(
            "0 9 31 * *",
            now=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(datetime(2026, 3, 31, 9, 0, tzinfo=timezone.utc), next_run)

    def test_invalid_cron_is_reported_without_raising_from_inspect(self) -> None:
        inspection = self.service.inspect("expressão inválida")
        self.assertFalse(inspection["valid"])
        self.assertIn("corrigido", inspection["error"])
        self.assertIsNone(inspection["next_run"])


if __name__ == "__main__":
    unittest.main()
