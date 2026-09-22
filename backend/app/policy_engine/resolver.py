from typing import Any


def select_policy(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    return matches[0] if matches else None
