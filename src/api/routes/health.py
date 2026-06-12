"""Health check route."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.core.config import get_config

router = APIRouter()


@router.get("")          # matches /health
@router.get("/")         # matches /health/
async def health_check() -> JSONResponse:
    config = get_config()
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": config.version,
            "ollama_url": config.ollama.base_url,
            "models": {
                "planner":   config.ollama.planner_model,
                "analyst":   config.ollama.analyst_model,
                "drafter":   config.ollama.drafter_model,
                "critic":    config.ollama.critic_model,
                "hermes":    config.ollama.hermes_model,
                "embedding": config.ollama.embedding_model,
            },
        },
    )