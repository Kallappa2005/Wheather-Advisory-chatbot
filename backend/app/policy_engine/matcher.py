from typing import Any


class PolicyMatcher:
    def __init__(self, policies: list[dict[str, Any]]):
        self.policies = policies

    def match(self, request: dict[str, Any], weather: dict[str, Any]) -> list[dict[str, Any]]:
        matches = []
        for policy in self.policies:
            conditions = policy.get("conditions", {})
            weather_conditions = dict(conditions.get("weather", {}))
            if "weather_event" in conditions:
                weather_conditions["weather_event"] = conditions["weather_event"]
            if self._matches_intent(conditions.get("activities"), request.get("activity")) and self._matches_group(conditions.get("groups"), request.get("group")) and self._matches_weather(weather_conditions, weather):
                matches.append(policy)
        return sorted(matches, key=lambda item: (-self._severity_score(item.get("severity")), -item.get("priority", 0), item.get("id", "")))

    def candidates(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            policy
            for policy in self.policies
            if self._matches_intent(policy.get("conditions", {}).get("activities"), request.get("activity"))
            and self._matches_group(policy.get("conditions", {}).get("groups"), request.get("group"))
        ]

    @staticmethod
    def _matches_intent(values: list[str] | None, actual: str | None) -> bool:
        return not values or actual in values

    @staticmethod
    def _matches_group(values: list[str] | None, actual: str | None) -> bool:
        return not values or actual in values

    def _matches_weather(self, conditions: dict[str, Any], weather: dict[str, Any]) -> bool:
        if not conditions:
            return True
        checks = []
        for metric, rule in conditions.items():
            if metric == "mode":
                continue
            if metric == "weather_event":
                event = weather.get("weather_event") or {}
                active = event.get("active") is True and event.get("type") in rule.get("types", [])
                checks.append(active)
                continue
            value = weather.get(metric)
            if value is None:
                checks.append(False)
                continue
            checks.append(self._compare(value, rule.get("operator", ">="), rule.get("value")))
        mode = conditions.get("mode", "all")
        return any(checks) if mode == "any" else all(checks)

    @staticmethod
    def _compare(actual: float, operator: str, expected: float) -> bool:
        return {">": actual > expected, ">=": actual >= expected, "<": actual < expected, "<=": actual <= expected, "==": actual == expected}.get(operator, False)

    @staticmethod
    def _severity_score(severity: str | None) -> int:
        return {"low": 1, "moderate": 2, "high": 3, "critical": 4}.get(severity or "low", 0)
