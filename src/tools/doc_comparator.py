"""
Multi-document Comparison Tool
--------------------------------
Detects contradictions and superseding clauses across multiple GRs.
Critical for real government workflows where newer circulars
override older ones without explicit revocation.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.core.schemas import GRAnalysis
from src.models.ollama_client import OllamaClient
from src.tools.base import BaseTool
from src.core.config import get_config

logger = structlog.get_logger(__name__)

_COMPARE_PROMPT = """\
You are a government policy analyst. Compare these two policy documents
and identify contradictions, superseding clauses, or conflicts.

DOCUMENT A ({ref_a}):
Obligations: {obligations_a}
Deadlines: {deadlines_a}

DOCUMENT B ({ref_b}):
Obligations: {obligations_b}
Deadlines: {deadlines_b}

Return ONLY JSON:
{{
  "contradictions": [
    {{
      "aspect": "<what contradicts>",
      "doc_a_position": "<what A says>",
      "doc_b_position": "<what B says>",
      "severity": "<critical|major|minor>"
    }}
  ],
  "superseding_clauses": ["<description of what B overrides from A>"],
  "compatible_clauses": ["<aspects that are aligned>"],
  "recommendation": "<which document takes precedence and why>"
}}
"""


class DocComparatorTool(BaseTool):
    name = "doc_comparator"
    description = (
        "Compares two GR/Circular analyses to detect contradictions, "
        "superseding clauses, and policy conflicts."
    )

    def __init__(self) -> None:
        self._llm = OllamaClient(model=get_config().ollama.analyst_model)
        self._log = logger.bind(tool=self.name)

    async def _execute(
        self,
        *,
        doc_a: GRAnalysis,
        doc_b: GRAnalysis,
    ) -> dict[str, Any]:
        import json, re

        prompt = _COMPARE_PROMPT.format(
            ref_a=doc_a.reference_number or "Document A",
            ref_b=doc_b.reference_number or "Document B",
            obligations_a="\n".join(doc_a.key_obligations),
            deadlines_a="\n".join(doc_a.deadlines),
            obligations_b="\n".join(doc_b.key_obligations),
            deadlines_b="\n".join(doc_b.deadlines),
        )

        response = await self._llm.generate(prompt=prompt, temperature=0.0)
        cleaned = re.sub(r"^```(?:json)?\n?", "", response.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            self._log.warning("doc_comparator.parse_failed")
            result = {
                "contradictions": [],
                "superseding_clauses": [],
                "compatible_clauses": [],
                "recommendation": "Could not determine — manual review required.",
            }

        self._log.info(
            "doc_comparator.complete",
            contradictions=len(result.get("contradictions", [])),
        )
        return result