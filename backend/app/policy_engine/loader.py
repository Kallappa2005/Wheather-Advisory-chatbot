from pathlib import Path
from typing import Any

import yaml


class PolicyLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> list[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return data.get("policies", [])
