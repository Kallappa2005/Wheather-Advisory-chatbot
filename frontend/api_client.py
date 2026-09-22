import os

import requests
from dotenv import load_dotenv

load_dotenv()


class BackendError(Exception):
    pass


def send_message(session_id: str, message: str) -> dict:
    base_url = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    try:
        response = requests.post(f"{base_url}/chat", json={"session_id": session_id, "message": message}, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise BackendError(f"Backend unavailable: {exc}") from exc
