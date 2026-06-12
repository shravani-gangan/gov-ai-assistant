"""
Hermes Meta-Reasoning Agent
----------------------------
Implements three advanced capabilities from the assignment:
  1. Self-critique with counter-argument generation
  2. Few-shot policy adaptation via in-context learning
  3. Automated audit trail narration

Uses Nous-Hermes-2 model which is specifically trained for:
  - Function calling and structured output
  - Meta-reasoning ("think about your thinking")
  - Chain-of-thought decomposition

Why Hermes for meta-reasoning?
  Nous-Hermes-2 was fine-tuned on synthetic reasoning datasets using
  Constitutional AI patterns. It naturally produces counter-arguments
  when prompted, making it ideal for the self-critique loop.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.core.config import get_config
from src.core.schemas import (
    AgentRole,
    AuditEvent,
    AuditTrail,
    ComplianceReport,
    ComplianceVerdict,
)
from src.agents.base import BaseAgent
from src.memory.manager import MemoryManager
from src.models.ollama_client import OllamaClient

logger = structlog.get_logger(__name__)

_SELF_CRITIQUE_PROMPT = """\
You are Hermes, an expert meta-reasoning system for government policy analysis.

A Compliance Agent has produced the following compliance assessment:
VERDICT: {verdict}
ISSUES FOUND:
{issues}

DRAFT REVIEWED:
{draft}

Your task is to perform ADVERSARIAL SELF-CRITIQUE:
1. Generate 2-3 counter-arguments challenging the compliance verdict.
2. Identify any biases or blind spots in the analysis.
3. Propose a refined verdict if warranted.

Respond in JSON:
{{
  "counter_arguments": ["<arg1>", "<arg2>", "..."],
  "blind_spots": ["<identified bias>", "..."],
  "refined_verdict": "<compliant|non_compliant|needs_revision|insufficient_data>",
  "confidence_adjustment": <float between -0.2 and 0.2>,
  "reasoning_chain": ["<step 1>", "<step 2>", "..."]
}}
Output ONLY the JSON.
"""

_FEW_SHOT_ADAPTATION_PROMPT = """\
You are Hermes. You are analyzing a new type of government circular.

Previous similar documents and their interpretations:
{few_shot_examples}

New document type detected: {doc_type}
Document excerpt:
{excerpt}

Using the patterns from past interpretations, infer:
1. How should this new circular type be processed?
2. What extraction rules apply?
3. What compliance checks are most relevant?

Respond in JSON:
{{
  "processing_strategy": "<description>",
  "applicable_extraction_rules": ["<rule1>", "..."],
  "priority_compliance_checks": ["<check1>", "..."],
  "confidence": <0.0-1.0>
}}
"""


class HermesAgent(BaseAgent):
    """
    Meta-reasoning agent responsible for:
    - Generating counter-arguments for compliance self-critique
    - Adapting to new circular types via few-shot in-context learning
    - Narrating the audit trail in human-readable format
    """

    role = AgentRole.HERMES

    def __init__(self, memory: MemoryManager) -> None:
        config = get_config()
        llm = OllamaClient(model=config.ollama.hermes_model)
        super().__init__(llm=llm, memory=memory)

    async def _run(self, task: str, **kwargs: Any) -> Any:
        """Route to the correct Hermes sub-capability."""
        dispatch = {
            "self_critique": self.self_critique,
            "few_shot_adapt": self.few_shot_adapt,
            "narrate_audit": self.narrate_audit_trail,
        }
        handler = dispatch.get(task)
        if handler is None:
            raise ValueError(f"Unknown Hermes task: '{task}'. Valid: {list(dispatch)}")
        return await handler(**kwargs)

    async def self_critique(
        self,
        compliance_report: ComplianceReport,
        draft: str,
    ) -> ComplianceReport:
        """
        Hermes-driven self-critique loop.
        Takes a ComplianceReport, generates counter-arguments,
        and returns an enriched report with refined verdict.
        """
        self._log.info("hermes.self_critique.start", verdict=compliance_report.verdict)

        issues_text = "\n".join(
            f"- [{i.severity}] {i.description}" for i in compliance_report.issues
        )
        prompt = _SELF_CRITIQUE_PROMPT.format(
            verdict=compliance_report.verdict.value,
            issues=issues_text or "None identified",
            draft=draft[:2000],
        )

        response = await self._llm.generate(prompt=prompt, temperature=0.2)
        parsed = self._parse_json_safe(response)

        # Enrich the compliance report with Hermes's meta-analysis
        enriched = compliance_report.model_copy(
            update={
                "counter_arguments": parsed.get("counter_arguments", []),
                "refinement_iterations": compliance_report.refinement_iterations + 1,
            }
        )

        # Apply confidence adjustment to overall score
        adjustment = parsed.get("confidence_adjustment", 0.0)
        new_score = max(0.0, min(100.0, enriched.overall_score + adjustment * 100))

        refined_verdict_str = parsed.get("refined_verdict", compliance_report.verdict.value)
        try:
            refined_verdict = ComplianceVerdict(refined_verdict_str)
        except ValueError:
            refined_verdict = compliance_report.verdict

        enriched = enriched.model_copy(
            update={"overall_score": new_score, "verdict": refined_verdict}
        )

        self._log.info(
            "hermes.self_critique.complete",
            original_verdict=compliance_report.verdict,
            refined_verdict=refined_verdict,
            counter_args=len(enriched.counter_arguments),
        )
        return enriched

    async def few_shot_adapt(
        self,
        doc_type: str,
        excerpt: str,
    ) -> dict[str, Any]:
        """
        Retrieves similar past documents from semantic memory and uses
        them as few-shot examples to adapt processing for new circular types.
        """
        self._log.info("hermes.few_shot_adapt.start", doc_type=doc_type)

        # Pull relevant past interpretations from long-term memory
        similar_docs = await self._memory.semantic_search(
            query=f"{doc_type} government circular interpretation",
            top_k=3,
        )
        few_shot_text = "\n---\n".join(
            f"Type: {d.get('doc_type', 'unknown')}\nStrategy: {d.get('strategy', '')}"
            for d in similar_docs
        ) or "No prior examples available."

        prompt = _FEW_SHOT_ADAPTATION_PROMPT.format(
            few_shot_examples=few_shot_text,
            doc_type=doc_type,
            excerpt=excerpt[:1500],
        )

        response = await self._llm.generate(prompt=prompt, temperature=0.1)
        return self._parse_json_safe(response)

    async def narrate_audit_trail(self, audit_trail: AuditTrail) -> str:
        """
        Converts the structured AuditTrail into a human-readable
        internal audit log formatted per government standards.
        """
        events_summary = "\n".join(
            f"{i+1}. [{e.agent.value.upper()}] {e.action}: {e.output_summary[:100]}"
            for i, e in enumerate(audit_trail.events)
        )

        narration_prompt = f"""
Convert this agent execution trace into an official internal audit log.

TRACE:
{events_summary}

Format as: 
- Use formal government language
- Number each decision point
- Note any escalations or re-plans
- Conclude with total processing stats

Total tokens: {audit_trail.total_tokens}
Total time: {audit_trail.total_latency_ms:.0f}ms
"""
        return await self._llm.generate(prompt=narration_prompt, temperature=0.1)

    def _parse_json_safe(self, response: str) -> dict[str, Any]:
        import json, re
        cleaned = re.sub(r"^```(?:json)?\n?", "", response.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            self._log.warning("hermes.json_parse_failed", snippet=response[:100])
            return {}