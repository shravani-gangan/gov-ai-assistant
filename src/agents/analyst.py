"""Analysis Agent — interprets GR tool output and enriches it with context."""
from __future__ import annotations

from typing import Any

import structlog

from src.agents.base import BaseAgent
from src.core.config import get_config
from src.core.schemas import AgentRole, GRAnalysis
from src.memory.manager import MemoryManager
from src.models.ollama_client import OllamaClient
from src.tools.base import ToolResult

logger = structlog.get_logger(__name__)

_ANALYST_SYSTEM = "You are a senior government policy analyst specializing in Maharashtra state circulars."

_ANALYST_PROMPT = """\
A GR/Circular has been parsed. Review the extraction and provide enrichment.

EXTRACTION RESULT:
{extraction}

OFFICER REQUEST: {request}

Identify:
1. Any missed obligations
2. Implicit deadlines
3. Ambiguities requiring clarification
4. Applicable precedents or related circulars

Return JSON:
{{
  "enriched_obligations": ["<obligation>"],
  "implicit_deadlines": ["<deadline>"],
  "additional_ambiguities": ["<ambiguity>"],
  "precedent_notes": ["<note>"]
}}
"""


class AnalystAgent(BaseAgent):
    role = AgentRole.ANALYST

    def __init__(self, memory: MemoryManager) -> None:
        config = get_config()
        llm = OllamaClient(model=config.ollama.analyst_model)
        super().__init__(llm=llm, memory=memory)

    async def _run(
        self,
        gr_tool_result: ToolResult,
        request: str,
    ) -> GRAnalysis | None:
        if not gr_tool_result.success or not gr_tool_result.data:
            self._log.warning("analyst.no_data", error=gr_tool_result.error)
            return None

        gr_analysis: GRAnalysis = gr_tool_result.data

        # Check semantic memory for similar past analyses
        past = await self._memory.semantic_search(
            query=f"{gr_analysis.document_type} {' '.join(gr_analysis.key_obligations[:3])}"
        )
        if past:
            self._log.info("analyst.memory_hit", hits=len(past))
            self._memory.set_episodic("past_analyses", past)

        # Enrich via LLM
        import json
        prompt = _ANALYST_PROMPT.format(
            extraction=json.dumps(gr_analysis.model_dump(), indent=2)[:3000],
            request=request,
        )
        response = await self._llm.generate(
            prompt=prompt, system=_ANALYST_SYSTEM, temperature=0.1
        )

        try:
            import re
            cleaned = re.sub(r"^```(?:json)?\n?", "", response.strip())
            cleaned = re.sub(r"\n?```$", "", cleaned)
            enrichment = json.loads(cleaned)
        except json.JSONDecodeError:
            enrichment = {}

        # Merge enrichment back into GRAnalysis
        enriched = gr_analysis.model_copy(update={
            "key_obligations": gr_analysis.key_obligations + enrichment.get("enriched_obligations", []),
            "deadlines": gr_analysis.deadlines + enrichment.get("implicit_deadlines", []),
            "ambiguities_detected": gr_analysis.ambiguities_detected + enrichment.get("additional_ambiguities", []),
        })
        return enriched