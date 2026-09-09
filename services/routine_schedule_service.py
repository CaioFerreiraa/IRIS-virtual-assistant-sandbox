from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo
import re
from typing import Iterable

from apscheduler.triggers.cron import CronTrigger


WEEKLY = "weekly"
MONTHLY = "monthly"
WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_LABELS = {
    "mon": "segunda-feira",
    "tue": "terça-feira",
    "wed": "quarta-feira",
    "thu": "quinta-feira",
    "fri": "sexta-feira",
    "sat": "sábado",
    "sun": "domingo",
}
WEEKDAY_ALIASES = {
    "monday": "mon",
    "segunda": "mon",
    "segunda-feira": "mon",
    "tuesday": "tue",
    "terca": "tue",
    "terça": "tue",
    "terca-feira": "tue",
    "terça-feira": "tue",
    "wednesday": "wed",
    "quarta": "wed",
    "quarta-feira": "wed",
    "thursday": "thu",
    "quinta": "thu",
    "quinta-feira": "thu",
    "friday": "fri",
    "sexta": "fri",
    "sexta-feira": "fri",
    "saturday": "sat",
    "sabado": "sat",
    "sábado": "sat",
    "sunday": "sun",
    "domingo": "sun",
}
TIME_PATTERN = re.compile(r"^(?P<hour>\d{2}):(?P<minute>\d{2})$")


@dataclass(frozen=True)
class RoutineSchedule:
    schedule_type: str
    days: tuple[str | int, ...]
    time: str
    cron_expression: str


class RoutineScheduleService:
    def __init__(self, local_timezone: tzinfo | None = None) -> None:
        self.local_timezone = local_timezone or datetime.now().astimezone().tzinfo

    def build_cron(
        self,
        schedule_type: str,
        days: Iterable[str | int],
        time_value: str,
    ) -> str:
        hour, minute, normalized_time = self._parse_time(time_value)
        if schedule_type == WEEKLY:
            normalized_days = self._normalize_weekdays(days)
            return f"{minute} {hour} * * {','.join(normalized_days)}"
        if schedule_type == MONTHLY:
            normalized_days = self._normalize_month_days(days)
            return f"{minute} {hour} {','.join(str(day) for day in normalized_days)} * *"
        raise ValueError("Selecione um tipo de repetição válido.")

    def parse_cron(self, cron_expression: str | None) -> RoutineSchedule:
        expression = str(cron_expression or "").strip()
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError("O agendamento salvo é inválido e precisa ser corrigido.")

        minute_text, hour_text, month_day, month, week_day = fields
        if not minute_text.isdigit() or not hour_text.isdigit() or month != "*":
            raise ValueError("O agendamento salvo é inválido e precisa ser corrigido.")
        minute = int(minute_text)
        hour = int(hour_text)
        if minute > 59 or hour > 23:
            raise ValueError("O agendamento salvo é inválido e precisa ser corrigido.")
        time_value = f"{hour:02d}:{minute:02d}"

        if month_day == "*" and week_day != "*":
            days = self._normalize_weekdays(week_day.split(","))
            schedule_type = WEEKLY
        elif month_day == "*" and week_day == "*":
            days = WEEKDAY_KEYS
            schedule_type = WEEKLY
        elif month_day != "*" and week_day == "*":
            days = self._normalize_month_days(month_day.split(","))
            schedule_type = MONTHLY
        else:
            raise ValueError("O agendamento salvo é inválido e precisa ser corrigido.")

        canonical_expression = self.build_cron(schedule_type, days, time_value)
        return RoutineSchedule(
            schedule_type=schedule_type,
            days=tuple(days),
            time=time_value,
            cron_expression=canonical_expression,
        )

    def describe(self, cron_expression: str | None) -> str:
        schedule = self.parse_cron(cron_expression)
        if schedule.schedule_type == WEEKLY:
            weekday_keys = tuple(str(day) for day in schedule.days)
            if weekday_keys == WEEKDAY_KEYS:
                return f"Todos os dias às {schedule.time}"
            labels = [WEEKDAY_LABELS[key] for key in weekday_keys]
            return f"{_join_labels(labels).capitalize()} às {schedule.time}"

        month_days = [str(day) for day in schedule.days]
        prefix = "Dia" if len(month_days) == 1 else "Dias"
        return f"{prefix} {_join_labels(month_days)} do mês às {schedule.time}"

    def next_run(
        self,
        cron_expression: str | None,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        schedule = self.parse_cron(cron_expression)
        trigger = CronTrigger.from_crontab(
            schedule.cron_expression,
            timezone=self.local_timezone,
        )
        reference = now or datetime.now(self.local_timezone)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=self.local_timezone)
        else:
            reference = reference.astimezone(self.local_timezone)
        return trigger.get_next_fire_time(None, reference)

    def inspect(self, cron_expression: str | None) -> dict[str, object]:
        try:
            schedule = self.parse_cron(cron_expression)
            return {
                "valid": True,
                "schedule_type": schedule.schedule_type,
                "days": list(schedule.days),
                "time": schedule.time,
                "cron_expression": schedule.cron_expression,
                "description": self.describe(schedule.cron_expression),
                "next_run": self.next_run(schedule.cron_expression),
                "error": "",
            }
        except (TypeError, ValueError) as error:
            return {
                "valid": False,
                "schedule_type": None,
                "days": [],
                "time": "",
                "cron_expression": str(cron_expression or ""),
                "description": "Agendamento inválido — corrija antes de ativar.",
                "next_run": None,
                "error": str(error),
            }

    def build_trigger(self, cron_expression: str | None) -> CronTrigger:
        schedule = self.parse_cron(cron_expression)
        return CronTrigger.from_crontab(
            schedule.cron_expression,
            timezone=self.local_timezone,
        )

    def _parse_time(self, time_value: str) -> tuple[int, int, str]:
        if not isinstance(time_value, str):
            raise ValueError("Informe o horário no formato HH:mm.")
        match = TIME_PATTERN.fullmatch(time_value.strip())
        if match is None:
            raise ValueError("Informe o horário no formato HH:mm.")
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        if hour > 23 or minute > 59:
            raise ValueError("Informe um horário válido no formato HH:mm.")
        return hour, minute, f"{hour:02d}:{minute:02d}"

    def _normalize_weekdays(
        self,
        days: Iterable[str | int],
    ) -> tuple[str, ...]:
        normalized: set[str] = set()
        for day in days:
            if isinstance(day, bool):
                raise ValueError("Selecione dias da semana válidos.")
            if isinstance(day, int):
                if day < 0 or day > 6:
                    raise ValueError("Selecione dias da semana válidos.")
                normalized.add(WEEKDAY_KEYS[day])
                continue
            key = str(day).strip().lower()
            key = WEEKDAY_ALIASES.get(key, key)
            if key not in WEEKDAY_KEYS:
                raise ValueError("Selecione dias da semana válidos.")
            normalized.add(key)
        if not normalized:
            raise ValueError("Selecione ao menos um dia.")
        return tuple(day for day in WEEKDAY_KEYS if day in normalized)

    def _normalize_month_days(
        self,
        days: Iterable[str | int],
    ) -> tuple[int, ...]:
        normalized: set[int] = set()
        for day in days:
            if isinstance(day, bool):
                raise ValueError("Os dias do mês devem estar entre 1 e 31.")
            try:
                value = int(str(day).strip())
            except (TypeError, ValueError) as error:
                raise ValueError("Os dias do mês devem estar entre 1 e 31.") from error
            if value < 1 or value > 31:
                raise ValueError("Os dias do mês devem estar entre 1 e 31.")
            normalized.add(value)
        if not normalized:
            raise ValueError("Selecione ao menos um dia.")
        return tuple(sorted(normalized))


def _join_labels(labels: list[str]) -> str:
    if len(labels) < 2:
        return "".join(labels)
    return f"{', '.join(labels[:-1])} e {labels[-1]}"
