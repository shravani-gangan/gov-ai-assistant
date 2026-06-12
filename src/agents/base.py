"""
Abstract BaseAgent — the contract every agent must fulfill.

Key design decisions:
1. Agents are stateless between calls — all state lives in memory manager
2. Every agent call is wrapped in timing + audit event emission
3. Agents communicate via typed Pydantic schemas, never raw strings
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.core.schemas import AgentRole, AuditEvent
from src.memory.manager import MemoryManager
from src.models.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    role: AgentRole
    system_prompt: str = ""

    def __init__(self, llm: OllamaClient, memory: MemoryManager) -> None:
        self._llm = llm
        self._memory = memory
        self._log = logger.bind(agent=self.role.value)

    async def run(self, **kwargs: Any) -> tuple[Any, AuditEvent]:
        """
        Public entry: runs the agent, emits an AuditEvent.
        Returns (result, audit_event) for the orchestrator to collect.
        """
        start = time.perf_counter()
        event_id = str(uuid.uuid4())
        self._log.info("agent.start", event_id=event_id)

        try:
            result = await self._run(**kwargs)
            latency = (time.perf_counter() - start) * 1000

            event = AuditEvent(
                event_id=event_id,
                agent=self.role,
                action=self.__class__.__name__,
                input_summary=self._summarize_input(kwargs),
                output_summary=self._summarize_output(result),
                latency_ms=latency,
            )
            self._log.info("agent.success", latency_ms=round(latency, 2))
            return result, event

        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            self._log.error("agent.failure", error=str(exc), latency_ms=round(latency, 2))
            raise

    @abstractmethod
    async def _run(self, **kwargs: Any) -> Any:
        """Agent-specific logic — implemented by each concrete agent."""
        ...

    def _summarize_input(self, kwargs: dict) -> str:
        """Truncate large inputs for audit log readability."""
        summary = {k: str(v)[:200] for k, v in kwargs.items()}
        return str(summary)

    def _summarize_output(self, result: Any) -> str:
        if hasattr(result, "model_dump"):
            return str(result.model_dump())[:500]
        return str(result)[:500]