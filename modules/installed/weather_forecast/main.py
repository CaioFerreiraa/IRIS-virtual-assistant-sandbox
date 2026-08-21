from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_ARGUMENT_RESULTS = 8


@dataclass(frozen=True)
class Location:
    label: str
    name: str
    country: str
    admin1: str
    latitude: float
    longitude: float
    timezone: str


_location_cache: dict[str, Location] = {}


def should_request_argument(
    variables: dict[str, str] | None = None,
) -> bool:
    return not bool((variables or {}).get("default_location", "").strip())


def search_arguments(query: str = "") -> list[dict[str, str]]:
    normalized_query = query.strip()
    if len(normalized_query) < 2:
        return []

    locations = _search_locations(normalized_query, MAX_ARGUMENT_RESULTS)
    results: list[dict[str, str]] = []
    for location in locations:
        _location_cache[location.label.casefold()] = location
        description_parts = [
            part
            for part in (
                location.admin1,
                location.country,
                f"{location.latitude:.4f}, {location.longitude:.4f}",
            )
            if part
        ]
        results.append(
            {
                "label": location.label,
                "value": location.label,
                "description": " · ".join(description_parts),
            }
        )
    return results


def execute(
    argument: str | None = None,
    variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    settings = variables or {}
    argument_location = (argument or "").strip()
    default_location = settings.get("default_location", "").strip()
    requested_location = argument_location or default_location
    if not requested_location:
        raise ValueError(
            "Informe o local da previsão ou configure o campo 'Local padrão' na rota do módulo."
        )

    forecast_days = _parse_forecast_days(settings.get("forecast_days", "3"))
    location = _resolve_location(requested_location)
    forecast = _fetch_forecast(location, forecast_days)

    return {
        "success": True,
        "message": _format_forecast_message(location, forecast),
        "result": {
            "location": location.label,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": forecast.get("timezone", location.timezone),
            "current": forecast.get("current", {}),
            "daily": forecast.get("daily", {}),
        },
    }


def _parse_forecast_days(value: str) -> int:
    try:
        days = int(value.strip())
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("O campo 'Dias da previsão' deve ser um número inteiro entre 1 e 7.") from error
    if not 1 <= days <= 7:
        raise ValueError("O campo 'Dias da previsão' deve ficar entre 1 e 7.")
    return days


def _resolve_location(query: str) -> Location:
    cached_location = _location_cache.get(query.casefold())
    if cached_location is not None:
        return cached_location

    locations = _search_locations(query, 1)
    if not locations:
        raise ValueError(
            f"Nenhum local foi encontrado para '{query}'. Informe uma cidade ou código postal mais específico."
        )
    location = locations[0]
    _location_cache[query.casefold()] = location
    _location_cache[location.label.casefold()] = location
    return location


def _search_locations(query: str, count: int) -> list[Location]:
    payload = _request_json(
        GEOCODING_URL,
        {
            "name": query,
            "count": count,
            "language": "pt",
            "format": "json",
        },
        "localização",
    )
    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        raise RuntimeError("O Open-Meteo retornou uma lista de localizações inválida.")

    locations: list[Location] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            name = str(item["name"]).strip()
            latitude = float(item["latitude"])
            longitude = float(item["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        country = str(item.get("country", "")).strip()
        admin1 = str(item.get("admin1", "")).strip()
        timezone = str(item.get("timezone", "auto")).strip() or "auto"
        label = _build_location_label(name, admin1, country)
        locations.append(
            Location(
                label=label,
                name=name,
                country=country,
                admin1=admin1,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
            )
        )
    return locations


def _build_location_label(name: str, admin1: str, country: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for part in (name, admin1, country):
        normalized_part = part.casefold()
        if part and normalized_part not in seen:
            seen.add(normalized_part)
            parts.append(part)
    return ", ".join(parts)


def _fetch_forecast(location: Location, forecast_days: int) -> dict[str, Any]:
    return _request_json(
        FORECAST_URL,
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "precipitation,weather_code,wind_speed_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
            "forecast_days": forecast_days,
        },
        "previsão do tempo",
    )


def _request_json(
    url: str,
    params: dict[str, object],
    operation: str,
) -> dict[str, Any]:
    try:
        response = httpx.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as error:
        raise RuntimeError(
            f"O Open-Meteo demorou demais para responder à consulta de {operation}."
        ) from error
    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"O Open-Meteo recusou a consulta de {operation} com status {error.response.status_code}."
        ) from error
    except httpx.RequestError as error:
        raise RuntimeError(
            f"Não foi possível conectar ao Open-Meteo para consultar {operation}."
        ) from error
    except ValueError as error:
        raise RuntimeError(
            f"O Open-Meteo retornou dados inválidos para a consulta de {operation}."
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(f"O Open-Meteo retornou uma resposta inválida para {operation}.")
    if payload.get("error"):
        reason = str(payload.get("reason", "erro não detalhado"))
        raise RuntimeError(f"O Open-Meteo não concluiu a consulta de {operation}: {reason}")
    return payload


def _format_forecast_message(location: Location, forecast: dict[str, Any]) -> str:
    current = forecast.get("current", {})
    daily = forecast.get("daily", {})
    if not isinstance(current, dict) or not isinstance(daily, dict):
        raise RuntimeError("A previsão retornada pelo Open-Meteo está incompleta.")

    temperature = _format_number(current.get("temperature_2m"), "°C")
    apparent_temperature = _format_number(current.get("apparent_temperature"), "°C")
    humidity = _format_number(current.get("relative_humidity_2m"), "%", decimals=0)
    wind_speed = _format_number(current.get("wind_speed_10m"), "km/h")
    weather = _weather_description(current.get("weather_code"))
    daily_summaries = _format_daily_summaries(daily)

    message = (
        f"Previsão para {location.label}: agora {temperature}, {weather}, "
        f"sensação de {apparent_temperature}, umidade de {humidity} e vento de {wind_speed}."
    )
    if daily_summaries:
        message = f"{message} Próximos dias: {'; '.join(daily_summaries)}."
    return message


def _format_daily_summaries(daily: dict[str, Any]) -> list[str]:
    times = daily.get("time", [])
    minimums = daily.get("temperature_2m_min", [])
    maximums = daily.get("temperature_2m_max", [])
    precipitation = daily.get("precipitation_probability_max", [])
    weather_codes = daily.get("weather_code", [])
    if not all(isinstance(values, list) for values in (times, minimums, maximums, precipitation, weather_codes)):
        return []

    summaries: list[str] = []
    item_count = min(len(times), len(minimums), len(maximums), len(precipitation), len(weather_codes))
    for index in range(item_count):
        day_label = _format_date(times[index])
        minimum = _format_number(minimums[index], "°C")
        maximum = _format_number(maximums[index], "°C")
        rain_chance = _format_number(precipitation[index], "%", decimals=0)
        weather = _weather_description(weather_codes[index])
        summaries.append(
            f"{day_label}, {weather}, mínima {minimum}, máxima {maximum}, chuva {rain_chance}"
        )
    return summaries


def _format_date(value: object) -> str:
    try:
        return date.fromisoformat(str(value)).strftime("%d/%m")
    except ValueError:
        return str(value)


def _format_number(value: object, unit: str, decimals: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"indisponível {unit}".strip()
    formatted = f"{number:.{decimals}f}".replace(".", ",")
    return f"{formatted} {unit}".strip()


def _weather_description(value: object) -> str:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return "condição não informada"

    descriptions = {
        0: "céu limpo",
        1: "predominantemente limpo",
        2: "parcialmente nublado",
        3: "nublado",
        45: "neblina",
        48: "neblina com geada",
        51: "garoa fraca",
        53: "garoa moderada",
        55: "garoa forte",
        56: "garoa congelante fraca",
        57: "garoa congelante forte",
        61: "chuva fraca",
        63: "chuva moderada",
        65: "chuva forte",
        66: "chuva congelante fraca",
        67: "chuva congelante forte",
        71: "neve fraca",
        73: "neve moderada",
        75: "neve forte",
        77: "grãos de neve",
        80: "pancadas de chuva fracas",
        81: "pancadas de chuva moderadas",
        82: "pancadas de chuva fortes",
        85: "pancadas de neve fracas",
        86: "pancadas de neve fortes",
        95: "trovoada",
        96: "trovoada com granizo fraco",
        99: "trovoada com granizo forte",
    }
    return descriptions.get(code, f"condição meteorológica {code}")
