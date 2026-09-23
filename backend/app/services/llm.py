import json
import re
from typing import Any

from groq import Groq


class LLMService:
    def __init__(self, api_key: str | None, model: str):
        self.client = Groq(api_key=api_key) if api_key else None
        self.model = model

    def extract_request(self, message: str, history: list[dict[str, str]]) -> dict[str, Any]:
        deterministic = self._inherit_context(self._infer_from_text(message), message, history)
        if deterministic.get("activity") != "unknown" and deterministic.get("location"):
            return deterministic
        if not self.client:
            return deterministic
        prompt = (
            "Extract a weather advisory request as JSON only. Keys: location (string or null), "
            "activity (one of cycling, two_wheeler, running, walking, picnic, travel, outdoor_play, pet_walk, "
            "kite_flying, unknown), group (one of child, elderly, pet, none), time (morning, afternoon, evening, or null), "
            "day_offset (0 for today, 1 for tomorrow, or null). "
            "Use prior turns for omitted context. Never provide advice.\n"
            f"Prior turns: {json.dumps(history[-6:])}\nUser: {message}"
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": prompt}],
            )
            data = json.loads(completion.choices[0].message.content or "{}")
            return self._normalize_request(data, message, history)
        except Exception:
            return self._heuristic_request(message, history)

    def compose(self, policy: dict[str, Any], weather: dict[str, Any], location: dict[str, Any]) -> str:
        if not self.client:
            return self._fallback_answer(policy, weather, location)
        facts = json.dumps({"decision": "policy_matched", "policy": policy, "weather": weather, "location": location})
        prompt = (
            "You are composing the final response for a policy-first weather assistant. "
            "Use only the supplied deterministic decision, SOP, location, and measured weather. "
            "Format the response with a short 'Current conditions' section, then explain which SOP applies, "
            "the measured value that triggered it, and bullet points containing only the recommendations written "
            "in that SOP. Never invent advice, weather facts, or a safety approval.\n"
            f"Facts: {facts}"
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[{"role": "system", "content": prompt}],
            )
            return completion.choices[0].message.content or self._fallback_answer(policy, weather, location)
        except Exception:
            return self._fallback_answer(policy, weather, location)

    def compose_no_policy(self, activity: str, weather: dict[str, Any], location: dict[str, Any], candidates: list[dict[str, Any]] | None = None) -> str:
        if not self.client:
            return self._fallback_no_policy_answer(activity, weather, location)
        facts = json.dumps({"decision": "no_policy_threshold_matched", "activity": activity, "weather": weather, "location": location, "considered_policies": candidates or []})
        prompt = (
            "You are composing the final response for a policy-first weather assistant. "
            "The deterministic matcher found no applicable SOP threshold. Explain that clearly, "
            "start with a short 'Current conditions' section, mention the activity and location, and say that "
            "the system cannot confirm safety without an applicable SOP. Do not say conditions are generally safe. "
            "Do not invent advice, alerts, or facts. Do not expose internal candidate-policy lists or IDs.\n"
            f"Facts: {facts}"
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[{"role": "system", "content": prompt}],
            )
            return completion.choices[0].message.content or self._fallback_no_policy_answer(activity, weather, location)
        except Exception:
            return self._fallback_no_policy_answer(activity, weather, location)

    def _normalize_request(self, data: dict[str, Any], message: str, history: list[dict[str, str]]) -> dict[str, Any]:
        request = {"location": data.get("location"), "activity": data.get("activity", "unknown"), "group": data.get("group", "none"), "time": data.get("time"), "day_offset": data.get("day_offset")}
        request = self._inherit_context(request, message, history)
        inferred = self._infer_from_text(message)
        for key in ("activity", "group", "location", "time", "day_offset"):
            if inferred.get(key) not in {None, "unknown", "none"}:
                request[key] = inferred[key]
        return request

    def _heuristic_request(self, message: str, history: list[dict[str, str]]) -> dict[str, Any]:
        return self._inherit_context(self._infer_from_text(message), message, history)

    @staticmethod
    def _infer_from_text(message: str) -> dict[str, Any]:
        text = message.lower()
        is_travel_request = any(term in text for term in ["travel", "commute", "journey", "go to work", "to work"])
        if any(term in text for term in ["scooter", "motorcycle", "motorbike", "two-wheeler"]) or (is_travel_request and any(term in text for term in ["bike", "bicycle", "cycle"])):
            activity = "two_wheeler"
        elif any(term in text for term in ["cycl", "bike", "bicycle"]):
            activity = "cycling"
        elif any(term in text for term in ["run", "jog"]):
            activity = "running"
        elif "picnic" in text or "outdoor lunch" in text:
            activity = "picnic"
        elif any(term in text for term in ["park", "play outside", "playground"]):
            activity = "outdoor_play"
        elif any(term in text for term in ["pet", "dog", "cat"]):
            activity = "pet_walk"
        elif "kite" in text:
            activity = "kite_flying"
        elif is_travel_request:
            activity = "travel"
        elif any(term in text for term in ["walk", "stroll"]):
            activity = "walking"
        else:
            activity = "unknown"
        group = "child" if any(term in text for term in ["kid", "child", "son", "daughter"]) else "elderly" if any(term in text for term in ["elderly", "old parents", "senior"]) else "pet" if any(term in text for term in ["pet", "dog", "cat"]) else "none"
        time_period = next((period for period in ("morning", "afternoon", "evening") if period in text), None)
        if "tonight" in text:
            time_period = "evening"
        day_offset = 1 if "tomorrow" in text else 0 if "today" in text or "this " in text else None
        return {"location": LLMService._find_location(text), "activity": activity, "group": group, "time": time_period, "day_offset": day_offset}

    def _inherit_context(self, request: dict[str, Any], message: str, history: list[dict[str, str]]) -> dict[str, Any]:
        previous = next((item.get("request") for item in reversed(history) if item.get("request")), {})
        for key in ("location", "activity", "group", "day_offset"):
            if not request.get(key) or request[key] in {"unknown", "none"}:
                request[key] = previous.get(key, request[key])
        return request

    @staticmethod
    def _find_location(text: str) -> str | None:
        match = re.search(
            r"(?:\s|^)(?:in|at|near)\s+([a-z][a-z ]*?)"
            r"(?=\s+(?:today|tonight|tomorrow|this|that|be|should|can|could|is|would|for|and|"
            r"if|when|while|during|with|because|before|after|where)\b|[?.!,]|$)",
            text,
        )
        if match:
            return match.group(1).strip().title()
        return None

    @staticmethod
    def _fallback_answer(policy: dict[str, Any], weather: dict[str, Any], location: dict[str, Any]) -> str:
        recommendations = "\n".join(f"- {item}" for item in policy.get("advice", {}).get("recommendations", []))
        return (
            f"Current conditions in {location['name']}:\n"
            f"- Temperature: {weather['temperature']}°C\n"
            f"- Wind: {weather['wind_speed']} km/h\n"
            f"- Rain: {weather['precipitation']} mm ({weather['precipitation_probability']}% probability)\n"
            f"- UV index: {weather['uv_index']}\n\n"
            f"{policy['id']} ({policy['name']}) applies because the measured conditions meet its written rule.\n\n"
            f"Recommendations:\n{recommendations}"
        )

    @staticmethod
    def _fallback_no_policy_answer(activity: str, weather: dict[str, Any], location: dict[str, Any]) -> str:
        label = activity.replace("_", " ")
        return (
            f"Current conditions in {location['name']}:\n"
            f"- Temperature: {weather['temperature']}°C\n"
            f"- Wind: {weather['wind_speed']} km/h\n"
            f"- Rain: {weather['precipitation']} mm ({weather['precipitation_probability']}% probability)\n"
            f"- UV index: {weather['uv_index']}\n\n"
            f"No current SOP threshold is triggered for {label}. The available policies do not define "
            "guidance for these conditions, so I cannot confirm that the activity is safe."
        )
