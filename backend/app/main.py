from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings
from app.graph.nodes import GraphDependencies
from app.graph.workflow import build_graph
from app.services.llm import LLMService
from app.services.weather import WeatherService


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Weather-Advisory Support Bot", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    dependencies = GraphDependencies(WeatherService(settings.weather_timeout_seconds, event_type=settings.weather_event_type), LLMService(settings.groq_api_key, settings.groq_model), Path(__file__).with_name("policies.yaml"))
    app.state.graph = build_graph(dependencies)
    app.state.sessions = {}
    app.include_router(router)
    return app


app = create_app()
