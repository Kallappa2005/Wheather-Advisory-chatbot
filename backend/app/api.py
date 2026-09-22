from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.graph.state import AdvisoryState

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    sop_id: str | None = None
    sop_name: str | None = None
    severity: str | None = None
    considered_sops: list[dict[str, str]] = Field(default_factory=list)
    weather: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    error: str | None = None


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "Weather-Advisory Support Bot", "status": "running", "docs": "/docs"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    sessions: dict[str, list[dict[str, Any]]] = request.app.state.sessions
    history = sessions.setdefault(payload.session_id, [])
    state: AdvisoryState = request.app.state.graph.invoke({"session_id": payload.session_id, "message": payload.message, "history": history})
    policy = state.get("selected_policy") or {}
    considered = [{"id": item["id"], "name": item["name"], "severity": item.get("severity", "")} for item in state.get("policy_candidates", [])]
    response = ChatResponse(answer=state["answer"], sop_id=policy.get("id"), sop_name=policy.get("name"), severity=policy.get("severity"), considered_sops=considered, weather=state.get("weather"), location=state.get("location"), error=state.get("error"))
    history.append({"role": "user", "content": payload.message, "request": state.get("request", {})})
    history.append({"role": "assistant", "content": response.answer})
    return response
