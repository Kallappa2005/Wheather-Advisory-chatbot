from pathlib import Path
from typing import Any

from app.graph.state import AdvisoryState
from app.policy_engine.loader import PolicyLoader
from app.policy_engine.matcher import PolicyMatcher
from app.policy_engine.resolver import select_policy
from app.services.llm import LLMService
from app.services.weather import WeatherService, WeatherUnavailable


class GraphDependencies:
    def __init__(self, weather: WeatherService, llm: LLMService, policy_path: str | Path):
        self.weather = weather
        self.llm = llm
        self.policy_path = policy_path


def parse_request(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    return {"request": deps.llm.extract_request(state["message"], state.get("history", []))}


def resolve_location(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    name = state.get("request", {}).get("location")
    if not name:
        return {"location_error": "Please include a city or location so I can retrieve live weather."}
    try:
        return {"location": deps.weather.resolve_location(name)}
    except WeatherUnavailable as exc:
        return {"location_error": str(exc)}


def fetch_weather(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    if state.get("location_error") or state.get("weather_error"):
        return {}
    location = state["location"]
    try:
        request = state.get("request", {})
        weather = deps.weather.current(location["latitude"], location["longitude"], request.get("time"), request.get("day_offset", 0))
        return {"weather": weather}
    except WeatherUnavailable as exc:
        return {"weather_error": str(exc)}


def match_sops(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    policies = PolicyLoader(deps.policy_path).load()
    matcher = PolicyMatcher(policies)
    if state.get("weather", {}).get("period_status", "").endswith("_passed"):
        return {"matches": [], "policy_candidates": []}
    return {"matches": matcher.match(state["request"], state["weather"]), "policy_candidates": matcher.candidates(state["request"])}


def select_applicable_policy(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    return {"selected_policy": select_policy(state.get("matches", []))}


def generate_response(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    return {"answer": deps.llm.compose(state["selected_policy"], state["weather"], state["location"])}


def handle_no_policy(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    activity = state.get("request", {}).get("activity", "that activity")
    weather = state.get("weather", {})
    if weather.get("period_status", "").endswith("_passed"):
        period = weather.get("requested_period") or state.get("request", {}).get("time") or "requested"
        article = "an" if period[0].lower() in "aeiou" else "a"
        return {"answer": f"Today's {period} period has passed. I cannot provide {article} {period}-specific recommendation for {_activity_label(activity)}. Current weather at {weather.get('time')} is {weather.get('temperature')}°C, wind {weather.get('wind_speed')} km/h, rain probability {weather.get('precipitation_probability')}%, and UV {weather.get('uv_index')}. Ask for tomorrow's {period} forecast if you want a forecast."}
    if not state.get("policy_candidates"):
        return {"answer": f"I don't have an SOP for {_activity_label(activity)} under the current policy set, so I can't provide a safety recommendation."}
    return {"answer": deps.llm.compose_no_policy(_activity_label(activity), weather, state["location"])}


def handle_weather_failure(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    return {"answer": "I couldn't retrieve current weather data for this location, so I can't provide weather-based guidance right now.", "error": "WEATHER_UNAVAILABLE"}


def handle_location_failure(state: AdvisoryState, deps: GraphDependencies) -> dict[str, Any]:
    return {"answer": state.get("location_error", "Please include a city or location so I can retrieve live weather."), "error": "LOCATION_UNAVAILABLE"}


def _activity_label(activity: str) -> str:
    return {"outdoor_play": "outdoor play", "two_wheeler": "two-wheeler travel", "pet_walk": "walking a pet", "kite_flying": "kite flying"}.get(activity, activity.replace("_", " "))
