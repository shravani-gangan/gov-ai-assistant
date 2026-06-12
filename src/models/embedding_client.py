"""Embedding client using nomic-embed-text via Ollama."""
from __future__ import annotations

import httpx
import structlog

from src.core.config import get_config

logger = structlog.get_logger(__name__)


class EmbeddingClient:
    def __init__(self) -> None:
        self._config = get_config().ollama
        self._model  = self._config.embedding_model
        self._log    = logger.bind(model=self._model)

    async def embed(self, text: str) -> list[float]:
        # Sanitize model name
        model_name = self._model.split(":")[0] if ":" in self._model else self._model
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._config.base_url}/api/embeddings",
                json={"model": model_name, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])