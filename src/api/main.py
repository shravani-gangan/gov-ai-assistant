"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"]     = "False"

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import get_config
from src.core.logging import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(get_config().log_level)
    logger.info("app.startup", version=get_config().version)
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    config = get_config()

    app = FastAPI(
        title=config.app_name,
        version=config.version,
        description="Multi-agent AI system for Government Officer Assistance",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Root ──────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse({
            "service":   config.app_name,
            "version":   config.version,
            "status":    "running",
            "docs":      "/docs",
            "health":    "/health",
            "endpoints": {
                "analyze_text": "POST /api/v1/analyze/text",
                "analyze_pdf":  "POST /api/v1/analyze/pdf",
            },
        })

    # ── Routers ───────────────────────────────────────────────────────────
    from src.api.routes.health  import router as health_router
    from src.api.routes.analyze import router as analyze_router

    app.include_router(health_router,  prefix="/health", tags=["Health"])
    app.include_router(analyze_router, prefix="/api/v1", tags=["Analysis"])

    return app


app = create_app()