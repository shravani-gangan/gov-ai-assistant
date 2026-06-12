"""
Abstract base class for all domain-specific tools.
Forces a consistent interface: every tool is async, typed, and observable.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: Any
    error: str | None = None
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    All tools inherit from this. Enforces:
    - Async execution
    - Automatic timing + structured logging
    - Consistent error envelope
    """

    name: str = "base_tool"
    description: str = "Abstract base tool"

    async def run(self, **kwargs: Any) -> ToolResult:
        """Public entry point — wraps _execute with timing and error handling."""
        start = time.perf_counter()
        log = logger.bind(tool=self.name, kwargs=list(kwargs.keys()))
        log.info("tool.start")

        try:
            data = await self._execute(**kwargs)
            latency = (time.perf_counter() - start) * 1000
            log.info("tool.success", latency_ms=round(latency, 2))
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=data,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            log.error("tool.failure", error=str(exc), latency_ms=round(latency, 2))
            return ToolResult(
                tool_name=self.name,
                success=False,
                data=None,
                error=str(exc),
                latency_ms=latency,
            )

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> Any:
        """Concrete tools implement their logic here."""
        ...