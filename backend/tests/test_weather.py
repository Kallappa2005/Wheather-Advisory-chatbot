import pytest

from app.services.weather import WeatherService, WeatherUnavailable


def test_weather_requires_current_fields():
    class IncompleteResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"current": {"temperature_2m": 20}}

    class IncompleteClient:
        def get(self, url, params):
            return IncompleteResponse()

    service = WeatherService(client=IncompleteClient())
    with pytest.raises(WeatherUnavailable):
        service.current(0, 0)


def test_evening_after_window_returns_current_weather_with_status():
    class ForecastResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "current": {"time": "2026-09-22T22:00", "temperature_2m": 28},
                "hourly": {
                    "time": ["2026-09-22T18:00", "2026-09-23T18:00"],
                    "temperature_2m": [25, 26], "wind_speed_10m": [8, 9],
                    "precipitation": [0, 0], "precipitation_probability": [5, 10], "uv_index": [0, 0],
                },
            }

    class ForecastClient:
        def get(self, url, params):
            return ForecastResponse()

    service = WeatherService(client=ForecastClient())
    weather = service.current(0, 0, "evening")
    assert weather["time"] == "2026-09-22T22:00"
    assert weather["period_status"] == "evening_passed"


def test_tomorrow_evening_selects_tomorrow_hourly_value():
    class ForecastResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "current": {"time": "2026-09-22T10:00", "temperature_2m": 28, "wind_speed_10m": 5, "precipitation": 0, "precipitation_probability": 0, "uv_index": 2},
                "hourly": {
                    "time": ["2026-09-22T18:00", "2026-09-23T18:00"],
                    "temperature_2m": [25, 26], "wind_speed_10m": [8, 9],
                    "precipitation": [0, 0], "precipitation_probability": [5, 10], "uv_index": [0, 0],
                },
            }

    class ForecastClient:
        def get(self, url, params):
            return ForecastResponse()

    weather = WeatherService(client=ForecastClient()).current(0, 0, "evening", 1)
    assert weather["time"] == "2026-09-23T18:00"
    assert weather["period_status"] == "evening_forecast"
