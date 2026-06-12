"""
Unified Memory Manager — Praison AI cross-agent memory.

Two memory tiers:
  - Episodic: In-process dict for current session (fast, ephemeral)
  - Semantic: ChromaDB vector store for long-term recall (persistent)

All agents share ONE MemoryManager instance, injected via constructor.
This is the Praison AI "cross-agent shared memory" pattern.
"""
from __future__ import annotations

from typing import Any

import chromadb
import structlog

from src.core.config import get_config
from src.models.embedding_client import EmbeddingClient

logger = structlog.get_logger(__name__)


class MemoryManager:
    def __init__(self) -> None:
        config = get_config()
        self._log = logger.bind(component="memory")

        # Episodic (session-scoped)
        self._episodic: dict[str, Any] = {}

        # Semantic (persistent ChromaDB)
        self._chroma = chromadb.PersistentClient(
            path=str(config.chroma.persist_directory)
        )
        self._collection = self._chroma.get_or_create_collection(
            name=config.chroma.collection_name,
            metadata={"hnsw:space": config.chroma.distance_metric},
        )
        self._embedder = EmbeddingClient()
        self._top_k = config.chroma.top_k_results

    # ── Episodic ─────────────────────────────────────────────────────────────

    def set_episodic(self, key: str, value: Any) -> None:
        self._episodic[key] = value
        self._log.debug("memory.episodic.set", key=key)

    def get_episodic(self, key: str, default: Any = None) -> Any:
        return self._episodic.get(key, default)

    # ── Semantic ──────────────────────────────────────────────────────────────

    async def store(self, key: str, value: dict[str, Any], embed_text: str) -> None:
        """Store a document with its embedding in ChromaDB."""
        embedding = await self._embedder.embed(embed_text)
        self._collection.upsert(
            ids=[key],
            embeddings=[embedding],
            documents=[embed_text],
            metadatas=[{k: str(v) for k, v in value.items()}],
        )
        self._log.info("memory.semantic.stored", key=key)

    async def semantic_search(
        self, query: str, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        """Return top-k most semantically similar stored documents."""
        embedding = await self._embedder.embed(query)
        k = top_k or self._top_k
        try:
            results = self._collection.query(
                query_embeddings=[embedding], n_results=k
            )
            metadatas = results.get("metadatas", [[]])[0]
            self._log.debug("memory.semantic.search", query=query[:50], hits=len(metadatas))
            return metadatas
        except Exception as exc:
            self._log.warning("memory.semantic.search_failed", error=str(exc))
            return []