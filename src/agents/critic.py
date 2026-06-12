"""Critic/Compliance Agent — validates drafts against policy constraints."""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from src.agents.base import BaseAgent
from src.core.config import get_config
from src.core.schemas import (
    AgentRole,
    ComplianceIssue,
    ComplianceReport,
    ComplianceVerdict,
    GRAnalysis,
)
from src.memory.manager import MemoryManager
from src.models.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)

_CRITIC_SYSTEM = """\
You are a strict government compliance officer. Evaluate drafts against
policy documents with zero tolerance for omissions or misstatements.
"""

_CRITIC_PROMPT = """\
Evaluate this draft for policy compliance.

POLICY ANALYSIS (source of truth):
Obligations: {obligations}
Deadlines: {deadlines}

DRAFT TO REVIEW:
{draft}

Return ONLY JSON:
{{
  "verdict": "<compliant|non_compliant|needs_revision|insufficient_data>",
  "overall_score": <0-100>,
  "issues": [
    {{
      "severity": "<critical|major|minor|advisory>",
      "clause_violated": "<clause text>",
      "description": "<what is wrong>",
      "suggested_fix": "<how to fix>",
      "confidence": <0.0-1.0>
    }}
  ]
}}
"""


class CriticAgent(BaseAgent):
    role = AgentRole.CRITIC

    def __init__(self, memory: MemoryManager) -> None:
        config = get_config()
        llm = OllamaClient(model=config.ollama.critic_model)
        super().__init__(llm=llm, memory=memory)

    async def _run(
        self,
        draft: str,
        gr_analysis: GRAnalysis | dict | None = None,
    ) -> ComplianceReport:
        if not gr_analysis:
            return ComplianceReport(
                verdict=ComplianceVerdict.INSUFFICIENT_DATA,
                overall_score=50.0,
                issues=[],
            )

        analysis = gr_analysis if isinstance(gr_analysis, dict) else gr_analysis.model_dump()
        prompt = _CRITIC_PROMPT.format(
            obligations="\n".join(analysis.get("key_obligations", [])),
            deadlines="\n".join(analysis.get("deadlines", [])),
            draft=draft[:3000],
        )
        response = await self._llm.generate(
            prompt=prompt, system=_CRITIC_SYSTEM, temperature=0.0
        )

        cleaned = re.sub(r"^```(?:json)?\n?", "", response.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            self._log.warning("critic.json_parse_failed")
            return ComplianceReport(
                verdict=ComplianceVerdict.NEEDS_REVISION,
                overall_score=40.0,
                issues=[],
            )

        issues = [
            ComplianceIssue(
                severity=i.get("severity", "minor"),
                clause_violated=i.get("clause_violated", ""),
                description=i.get("description", ""),
                suggested_fix=i.get("suggested_fix", ""),
                confidence=float(i.get("confidence", 0.7)),
            )
            for i in parsed.get("issues", [])
        ]

        try:
            verdict = ComplianceVerdict(parsed.get("verdict", "needs_revision"))
        except ValueError:
            verdict = ComplianceVerdict.NEEDS_REVISION

        return ComplianceReport(
            verdict=verdict,
            overall_score=float(parsed.get("overall_score", 50.0)),
            issues=issues,
        )