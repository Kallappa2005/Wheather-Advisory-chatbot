from app.policy_engine.matcher import PolicyMatcher


def test_policy_matching_is_deterministic_and_severity_first():
    policies = [
        {"id": "low", "severity": "low", "priority": 100, "conditions": {"activities": ["cycling"], "weather": {"wind_speed": {"operator": ">", "value": 20}}}},
        {"id": "high", "severity": "high", "priority": 1, "conditions": {"activities": ["cycling"], "weather": {"wind_speed": {"operator": ">", "value": 20}}}},
    ]
    matches = PolicyMatcher(policies).match({"activity": "cycling", "group": "none"}, {"wind_speed": 45})
    assert [policy["id"] for policy in matches] == ["high", "low"]


def test_policy_mode_is_not_a_weather_metric():
    policy = {"id": "picnic", "severity": "moderate", "conditions": {"activities": ["picnic"], "weather": {"mode": "any", "wind_speed": {"operator": ">", "value": 30}, "uv_index": {"operator": ">=", "value": 8}}}}
    assert PolicyMatcher([policy]).match({"activity": "picnic", "group": "none"}, {"wind_speed": 35, "uv_index": 2})


def test_policy_candidates_distinguish_known_activity_from_no_policy():
    policies = [{"id": "child-heat", "conditions": {"activities": ["outdoor_play"], "groups": ["child"], "weather": {"temperature": {"operator": ">=", "value": 35}}}}]
    matcher = PolicyMatcher(policies)
    assert matcher.candidates({"activity": "outdoor_play", "group": "child"})
    assert not matcher.candidates({"activity": "kite_flying", "group": "none"})


def test_severe_weather_event_matches_critical_policy():
    policy = {"id": "SOP-012", "severity": "critical", "conditions": {"weather_event": {"active": True, "types": ["heavy_rain_system"]}}}
    matches = PolicyMatcher([policy]).match({"activity": "cycling", "group": "none"}, {"weather_event": {"active": True, "type": "heavy_rain_system"}})
    assert matches[0]["id"] == "SOP-012"
