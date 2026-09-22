from typing import Any, TypedDict


class WeatherData(TypedDict, total=False):
    time: str
    temperature: float
    wind_speed: float
    precipitation: float
    precipitation_probability: float
    uv_index: float
    period_status: str
    requested_period: str
    weather_event: dict[str, Any]


class AdvisoryState(TypedDict, total=False):
    session_id: str
    message: str
    history: list[dict[str, str]]
    request: dict[str, Any]
    location: dict[str, Any]
    weather: WeatherData
    weather_error: str
    location_error: str
    matches: list[dict[str, Any]]
    policy_candidates: list[dict[str, Any]]
    selected_policy: dict[str, Any]
    answer: str
    error: str
