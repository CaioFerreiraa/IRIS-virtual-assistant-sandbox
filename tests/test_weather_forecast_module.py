import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from services.module_loader import load_python_entrypoint


ENTRYPOINT = (
    Path(__file__).resolve().parents[1]
    / "modules"
    / "installed"
    / "weather_forecast"
    / "main.py"
)


def build_response(url: str, payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", url),
    )


def geocoding_payload() -> dict:
    return {
        "results": [
            {
                "name": "Campinas",
                "admin1": "São Paulo",
                "country": "Brasil",
                "latitude": -22.9056,
                "longitude": -47.0608,
                "timezone": "America/Sao_Paulo",
            }
        ]
    }


def forecast_payload() -> dict:
    return {
        "timezone": "America/Sao_Paulo",
        "current": {
            "temperature_2m": 24.3,
            "apparent_temperature": 25.1,
            "relative_humidity_2m": 68,
            "precipitation": 0,
            "weather_code": 2,
            "wind_speed_10m": 8.4,
        },
        "daily": {
            "time": ["2026-08-16", "2026-08-17"],
            "weather_code": [2, 61],
            "temperature_2m_max": [27.2, 25.4],
            "temperature_2m_min": [16.8, 17.1],
            "precipitation_probability_max": [20, 70],
        },
    }


class WeatherForecastModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_python_entrypoint(ENTRYPOINT, "weather.forecast")
        self.module._location_cache.clear()

    def test_requires_argument_or_default_location(self) -> None:
        self.assertTrue(
            self.module.should_request_argument(
                {"default_location": ""}
            )
        )
        self.assertFalse(
            self.module.should_request_argument(
                {"default_location": "Campinas"}
            )
        )
        with self.assertRaisesRegex(ValueError, "Local padrão"):
            self.module.execute(variables={"default_location": "", "forecast_days": "3"})

    def test_uses_default_location_and_returns_structured_forecast(self) -> None:
        responses = [
            build_response(self.module.GEOCODING_URL, geocoding_payload()),
            build_response(self.module.FORECAST_URL, forecast_payload()),
        ]
        with patch.object(self.module.httpx, "get", side_effect=responses) as mocked_get:
            result = self.module.execute(
                variables={"default_location": "Campinas", "forecast_days": "2"}
            )

        self.assertTrue(result["success"])
        self.assertIn("Campinas, São Paulo, Brasil", result["message"])
        self.assertIn("24,3 °C", result["message"])
        self.assertEqual("Campinas, São Paulo, Brasil", result["result"]["location"])
        self.assertEqual(2, mocked_get.call_count)
        self.assertEqual(
            2,
            mocked_get.call_args_list[1].kwargs["params"]["forecast_days"],
        )

    def test_argument_overrides_default_location(self) -> None:
        responses = [
            build_response(self.module.GEOCODING_URL, geocoding_payload()),
            build_response(self.module.FORECAST_URL, forecast_payload()),
        ]
        with patch.object(self.module.httpx, "get", side_effect=responses) as mocked_get:
            self.module.execute(
                argument="Campinas",
                variables={"default_location": "Recife", "forecast_days": "1"},
            )

        self.assertEqual(
            "Campinas",
            mocked_get.call_args_list[0].kwargs["params"]["name"],
        )

    def test_blank_argument_falls_back_to_default_location(self) -> None:
        responses = [
            build_response(self.module.GEOCODING_URL, geocoding_payload()),
            build_response(self.module.FORECAST_URL, forecast_payload()),
        ]
        with patch.object(self.module.httpx, "get", side_effect=responses) as mocked_get:
            self.module.execute(
                argument="   ",
                variables={"default_location": "Campinas", "forecast_days": "1"},
            )

        self.assertEqual(
            "Campinas",
            mocked_get.call_args_list[0].kwargs["params"]["name"],
        )

    def test_selected_suggestion_reuses_cached_coordinates(self) -> None:
        with patch.object(
            self.module.httpx,
            "get",
            return_value=build_response(self.module.GEOCODING_URL, geocoding_payload()),
        ):
            suggestions = self.module.search_arguments("Campinas")

        with patch.object(
            self.module.httpx,
            "get",
            return_value=build_response(self.module.FORECAST_URL, forecast_payload()),
        ) as mocked_get:
            result = self.module.execute(
                argument=suggestions[0]["value"],
                variables={"forecast_days": "2"},
            )

        self.assertTrue(result["success"])
        self.assertEqual(1, mocked_get.call_count)
        self.assertEqual(self.module.FORECAST_URL, mocked_get.call_args.args[0])

    def test_unknown_location_is_reported(self) -> None:
        with patch.object(
            self.module.httpx,
            "get",
            return_value=build_response(self.module.GEOCODING_URL, {"results": []}),
        ):
            with self.assertRaisesRegex(ValueError, "Nenhum local"):
                self.module.execute(
                    argument="Lugar inexistente",
                    variables={"forecast_days": "3"},
                )

    def test_invalid_forecast_days_is_reported_before_network(self) -> None:
        with patch.object(self.module.httpx, "get") as mocked_get:
            with self.assertRaisesRegex(ValueError, "entre 1 e 7"):
                self.module.execute(
                    argument="Campinas",
                    variables={"forecast_days": "10"},
                )
        mocked_get.assert_not_called()

    def test_timeout_has_friendly_message(self) -> None:
        with patch.object(
            self.module.httpx,
            "get",
            side_effect=httpx.ReadTimeout("timeout"),
        ):
            with self.assertRaisesRegex(RuntimeError, "demorou demais"):
                self.module.execute(
                    argument="Campinas",
                    variables={"forecast_days": "3"},
                )


if __name__ == "__main__":
    unittest.main()
