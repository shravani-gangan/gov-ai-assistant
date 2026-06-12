"""Audit Trail Generator — compiles agent events into structured audit logs."""
from __future__ import annotations

from src.core.schemas import AuditEvent, AuditTrail


class AuditTrailGenerator:
    def compile(
        self,
        request_id: str,
        session_id: str,
        events: list[AuditEvent],
    ) -> AuditTrail:
        valid = [e for e in events if isinstance(e, AuditEvent)]
        return AuditTrail(
            request_id=request_id,
            session_id=session_id,
            events=valid,
            total_tokens=sum(
                sum(e.token_usage.values()) for e in valid
            ),
            total_latency_ms=sum(e.latency_ms for e in valid),
        )