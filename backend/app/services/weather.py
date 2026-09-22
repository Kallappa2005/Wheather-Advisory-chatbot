from datetime import datetime, timedelta
from typing import Any

import httpx


class WeatherUnavailable(Exception):
    pass


class WeatherService:
    def __init__(self, timeout: float = 10.0, client: httpx.Client | None = None, event_type: str | None = None):
        self.timeout = timeout
        self.client = client
        self.event_type = event_type

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            if self.client:
                response = self.client.get(url, params=params)
            else:
                response = httpx.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherUnavailable(str(exc)) from exc
        if not isinstance(data, dict):
            raise WeatherUnavailable("Weather service returned an invalid payload")
        return data

    def resolve_location(self, name: str) -> dict[str, Any]:
        data = self._get(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": name, "count": 1, "language": "en", "format": "json"},
        )
        results = data.get("results") or []
        if not results:
            raise WeatherUnavailable(f"Could not resolve location: {name}")
        result = results[0]
        return {
            "name": result.get("name", name),
            "country": result.get("country"),
            "latitude": float(result["latitude"]),
            "longitude": float(result["longitude"]),
        }

    def current(self, latitude: float, longitude: float, time_period: str | None = None, day_offset: int = 0) -> dict[str, Any]:
        if time_period in {"morning", "afternoon", "evening"}:
            return self._period(latitude, longitude, time_period, day_offset)
        data = self._get(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m,precipitation,precipitation_probability,uv_index",
                "timezone": "auto",
            },
        )
        current = data.get("current")
        if not isinstance(current, dict):
            raise WeatherUnavailable("Weather service returned no current values")
        fields = {
            "time": current.get("time", ""),
            "temperature": current.get("temperature_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "precipitation": current.get("precipitation"),
            "precipitation_probability": current.get("precipitation_probability"),
            "uv_index": current.get("uv_index"),
        }
        if any(value is None for value in fields.values() if value != fields["time"]):
            raise WeatherUnavailable("Weather response was missing required values")
        return self._add_event(fields)

    def _period(self, latitude: float, longitude: float, period: str, day_offset: int) -> dict[str, Any]:
        data = self._get(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m,precipitation,precipitation_probability,uv_index",
                "hourly": "temperature_2m,wind_speed_10m,precipitation,precipitation_probability,uv_index",
                "forecast_days": 2,
                "timezone": "auto",
            },
        )
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            raise WeatherUnavailable("Weather service returned no hourly values")
        current = data.get("current") or {}
        current_time = current.get("time")
        if not current_time:
            raise WeatherUnavailable("Weather service returned no current time")
        current_datetime = datetime.fromisoformat(current_time)
        target_date = current_datetime.date() + timedelta(days=day_offset)
        windows = {"morning": range(6, 12), "afternoon": range(12, 18), "evening": range(18, 21)}
        index = next(
            (
                i
                for i, value in enumerate(times)
                if datetime.fromisoformat(value) >= current_datetime
                and datetime.fromisoformat(value).date() == target_date
                and datetime.fromisoformat(value).hour in windows[period]
            ),
            None,
        )
        if index is None and day_offset == 0:
            return self._add_event({
                "time": current_time,
                "temperature": current.get("temperature_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "precipitation": current.get("precipitation"),
                "precipitation_probability": current.get("precipitation_probability"),
                "uv_index": current.get("uv_index"),
                "period_status": f"{period}_passed",
                "requested_period": period,
            })
        if index is None:
            raise WeatherUnavailable(f"No {period} forecast was available for the requested date")
        fields = {
            "time": times[index],
            "temperature": hourly.get("temperature_2m", [])[index],
            "wind_speed": hourly.get("wind_speed_10m", [])[index],
            "precipitation": hourly.get("precipitation", [])[index],
            "precipitation_probability": hourly.get("precipitation_probability", [])[index],
            "uv_index": hourly.get("uv_index", [])[index],
            "period_status": f"{period}_forecast",
            "requested_period": period,
        }
        if any(value is None for value in fields.values()):
            raise WeatherUnavailable("Hourly weather response was missing required values")
        return self._add_event(fields)

    def _add_event(self, weather: dict[str, Any]) -> dict[str, Any]:
        if self.event_type:
            weather["weather_event"] = {"active": True, "type": self.event_type, "source": "configured alert input"}
        return weather
