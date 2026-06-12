"""
Semantic memory — persistent ChromaDB vector store.
Separated from manager.py for single-responsibility principle.
"""
from __future__ import annotations

from typing import Any

import chromadb
import structlog

from src.core.config import get_config
from src.models.embedding_client import EmbeddingClient

logger = structlog.get_logger(__name__)


class SemanticMemory:
    def __init__(self) -> None:
        config = get_config()
        self._log = logger.bind(component="semantic_memory")
        self._embedder = EmbeddingClient()
        self._top_k = config.chroma.top_k_results

        client = chromadb.PersistentClient(
            path=str(config.chroma.persist_directory)
        )
        self._col = client.get_or_create_collection(
            name=config.chroma.collection_name,
            metadata={"hnsw:space": config.chroma.distance_metric},
        )

    async def store(
        self, key: str, value: dict[str, Any], embed_text: str
    ) -> None:
        embedding = await self._embedder.embed(embed_text)
        self._col.upsert(
            ids=[key],
            embeddings=[embedding],
            documents=[embed_text],
            metadatas=[{k: str(v) for k, v in value.items()}],
        )
        self._log.info("semantic.stored", key=key[:30])

    async def search(
        self, query: str, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        embedding = await self._embedder.embed(query)
        k = top_k or self._top_k
        try:
            results = self._col.query(
                query_embeddings=[embedding], n_results=k
            )
            return results.get("metadatas", [[]])[0]
        except Exception as exc:
            self._log.warning("semantic.search_failed", error=str(exc))
            return []