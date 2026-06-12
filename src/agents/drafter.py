"""Drafting Agent — generates and revises official government documents."""
from __future__ import annotations

from typing import Any

import structlog

from src.agents.base import BaseAgent
from src.core.config import get_config
from src.core.schemas import AgentRole, ComplianceIssue, GRAnalysis
from src.memory.manager import MemoryManager
from src.models.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)

_DRAFT_SYSTEM = """\
You are an expert government officer drafting official documents.
Use formal government language. Follow standard Maharashtra GR format.
"""

_INITIAL_DRAFT_PROMPT = """\
Draft an official government response based on:

ANALYSIS:
Obligations: {obligations}
Deadlines: {deadlines}
Applicability: {applicability}
Document Type: {doc_type}

OFFICER REQUEST: {request}

Write a complete official note/response in proper government format.
Include: Subject, Reference, Body, Action Required, Signature block.
"""

_REVISION_PROMPT = """\
Revise the following draft to address compliance issues:

CURRENT DRAFT:
{draft}

COMPLIANCE ISSUES TO FIX:
{issues}

Return the revised draft only. Maintain official government format.
"""


class DrafterAgent(BaseAgent):
    role = AgentRole.DRAFTER

    def __init__(self, memory: MemoryManager) -> None:
        config = get_config()
        llm = OllamaClient(model=config.ollama.drafter_model)
        super().__init__(llm=llm, memory=memory)

    async def _run(
        self,
        task: str = "initial",
        gr_analysis: Any = None,
        request: str = "",
        current_draft: str = "",
        compliance_issues: list[ComplianceIssue] | None = None,
    ) -> dict[str, Any]:
        if task == "initial":
            return await self._initial_draft(gr_analysis, request)
        elif task == "revise":
            return await self._revise_draft(current_draft, compliance_issues or [])
        else:
            raise ValueError(f"Unknown drafter task: {task}")

    async def _initial_draft(self, gr_analysis: Any, request: str) -> dict[str, Any]:
        if gr_analysis is None:
            prompt = f"Draft an official government note for: {request}"
        else:
            analysis_dict = gr_analysis if isinstance(gr_analysis, dict) else gr_analysis.model_dump()
            prompt = _INITIAL_DRAFT_PROMPT.format(
                obligations="\n".join(analysis_dict.get("key_obligations", [])),
                deadlines="\n".join(analysis_dict.get("deadlines", [])),
                applicability="\n".join(analysis_dict.get("applicability", [])),
                doc_type=analysis_dict.get("document_type", "unknown"),
                request=request,
            )
        draft = await self._llm.generate(prompt=prompt, system=_DRAFT_SYSTEM, temperature=0.2)
        return {"draft": draft, "task": "initial"}

    async def _revise_draft(
        self, current_draft: str, issues: list[ComplianceIssue]
    ) -> dict[str, Any]:
        issues_text = "\n".join(
            f"[{i.severity.upper()}] {i.description} → Fix: {i.suggested_fix}"
            for i in issues
        )
        prompt = _REVISION_PROMPT.format(draft=current_draft, issues=issues_text)
        revised = await self._llm.generate(prompt=prompt, system=_DRAFT_SYSTEM, temperature=0.15)
        return {"draft": revised, "task": "revision"}