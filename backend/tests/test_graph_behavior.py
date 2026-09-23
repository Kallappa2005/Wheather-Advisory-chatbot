from pathlib import Path

from app.graph.nodes import GraphDependencies
from app.graph.workflow import build_graph
from app.services.llm import LLMService
from app.services.weather import WeatherUnavailable


class FakeWeather:
    def resolve_location(self, name):
        return {"name": name, "latitude": 0.0, "longitude": 0.0}

    def current(self, latitude, longitude, time_period=None, day_offset=0):
        return {"time": time_period or "now", "temperature": 28.0, "wind_speed": 10.0, "precipitation": 0.0, "precipitation_probability": 0.0, "uv_index": 0.0}


class BrokenWeather(FakeWeather):
    def current(self, latitude, longitude, time_period=None, day_offset=0):
        raise WeatherUnavailable("outage")


class PassedEveningWeather(FakeWeather):
    def current(self, latitude, longitude, time_period=None, day_offset=0):
        period = time_period or "evening"
        return {"time": "2026-09-22T23:00", "temperature": 25.0, "wind_speed": 10.0, "precipitation": 0.0, "precipitation_probability": 20.0, "uv_index": 0.0, "period_status": f"{period}_passed", "requested_period": period}


class SevereWeather(FakeWeather):
    def current(self, latitude, longitude, time_period=None, day_offset=0):
        return {"time": "fixture", "temperature": 30.0, "wind_speed": 20.0, "precipitation": 2.0, "precipitation_probability": 80.0, "uv_index": 3.0, "weather_event": {"active": True, "type": "heavy_rain_system", "source": "fixture"}}


class StrongWindWeather(FakeWeather):
    def current(self, latitude, longitude, time_period=None, day_offset=0):
        return {"time": "fixture", "temperature": 28.0, "wind_speed": 45.0, "precipitation": 0.0, "precipitation_probability": 0.0, "uv_index": 0.0}


def test_location_parser_stops_at_sentence_words():
    request = LLMService(None, "unused").extract_request("Would riding my bicycle to work in Mumbai be suitable today?", [])
    assert request["location"] == "Mumbai"


def test_location_parser_stops_at_weather_condition_phrases():
    service = LLMService(None, "unused")
    assert service.extract_request("Is it safe to cycle in Delhi when the wind is strong?", [])["location"] == "Delhi"
    assert service.extract_request("Can I run in Mumbai if rain is expected?", [])["location"] == "Mumbai"
    assert service.extract_request("Can I commute by scooter in Delhi during strong winds?", [])["location"] == "Delhi"


def test_tomorrow_is_preserved_as_explicit_date_offset():
    request = LLMService(None, "unused").extract_request("Can I travel by bike in Bengaluru tomorrow evening?", [])
    assert request["day_offset"] == 1
    assert request["time"] == "evening"


def make_graph(weather):
    return build_graph(GraphDependencies(weather, LLMService(None, "unused"), Path(__file__).parents[1] / "app" / "policies.yaml"))


def test_missing_location_stops_before_weather_and_does_not_reuse_stale_weather():
    result = make_graph(FakeWeather()).invoke({"session_id": "test", "message": "Is it safe to go cycling today?", "history": []})
    assert result["error"] == "LOCATION_UNAVAILABLE"
    assert "include a city" in result["answer"]
    assert "weather" not in result


def test_known_activity_but_untriggered_policy_is_explained():
    result = make_graph(FakeWeather()).invoke({"session_id": "test", "message": "Should I take my child to the park in Jaipur today?", "history": []})
    assert result.get("selected_policy") is None
    assert "none of the current safety thresholds are triggered" in result["answer"]
    assert "Jaipur" in result["answer"]
    assert "Policies checked" not in result["answer"]


def test_scooter_is_classified_as_two_wheeler():
    result = make_graph(FakeWeather()).invoke({"session_id": "test", "message": "Can I commute by scooter in Kolkata today?", "history": []})
    assert result["request"]["activity"] == "two_wheeler"


def test_strong_wind_selects_activity_specific_sop():
    bicycle = make_graph(StrongWindWeather()).invoke({"session_id": "test", "message": "Can I ride my bicycle in Delhi?", "history": []})
    scooter = make_graph(StrongWindWeather()).invoke({"session_id": "test", "message": "Can I commute by scooter in Delhi?", "history": []})
    assert bicycle["selected_policy"]["id"] == "SOP-002"
    assert scooter["selected_policy"]["id"] == "SOP-006"


def test_travel_by_bike_is_classified_as_two_wheeler():
    result = make_graph(FakeWeather()).invoke({"session_id": "test", "message": "Can I travel by bike in Bengaluru this evening?", "history": []})
    assert result["request"]["activity"] == "two_wheeler"
    assert result["request"]["time"] == "evening"


def test_picnic_does_not_include_elderly_policy_without_elderly_group():
    result = make_graph(FakeWeather()).invoke({"session_id": "test", "message": "Does the weather look good for an outdoor lunch in Mumbai?", "history": []})
    assert "SOP-009" not in [policy["id"] for policy in result.get("policy_candidates", [])]


def test_weather_failure_does_not_enter_policy_matching():
    result = make_graph(BrokenWeather()).invoke({"session_id": "test", "message": "Is it safe to cycle in Delhi today?", "history": []})
    assert result["error"] == "WEATHER_UNAVAILABLE"
    assert "matches" not in result


def test_evening_after_window_does_not_switch_to_tomorrow():
    result = make_graph(PassedEveningWeather()).invoke({"session_id": "test", "message": "Can I travel by bike in Bengaluru this evening?", "history": []})
    assert "Today's evening period has passed" in result["answer"]
    assert "tomorrow's evening forecast" in result["answer"]
    assert result["weather"]["time"] == "2026-09-22T23:00"


def test_passed_afternoon_uses_same_honest_response():
    result = make_graph(PassedEveningWeather()).invoke({"session_id": "test", "message": "Could I walk in Bengaluru this afternoon?", "history": []})
    assert "Today's afternoon period has passed" in result["answer"]
    assert "tomorrow's afternoon forecast" in result["answer"]


def test_active_severe_event_overrides_numeric_conditions():
    result = make_graph(SevereWeather()).invoke({"session_id": "test", "message": "Is it safe to cycle in Bhopal today?", "history": []})
    assert result["selected_policy"]["id"] == "SOP-012"