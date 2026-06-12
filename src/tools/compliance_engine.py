"""
Compliance Validation Engine
------------------------------
Two-stage validation:
  Stage 1 — Rule-based deterministic checks (obligation coverage, deadline mentions)
  Stage 2 — Semantic checks via keyword matching

Design rationale: Rule-based first because it's fast, deterministic, and
auditable. LLM-based compliance check lives in CriticAgent. This tool
provides the raw signal; the agent provides the judgment.
"""
from __future__ import annotations

from typing import Any

import structlog

from src.core.schemas import ComplianceReport, ComplianceVerdict, ComplianceIssue, GRAnalysis
from src.tools.base import BaseTool

logger = structlog.get_logger(__name__)


class ComplianceEngineTool(BaseTool):
    """
    Rule-based compliance validator.
    Checks whether a draft document addresses all obligations and
    deadlines extracted from the source GR/Circular.
    """

    name = "compliance_engine"
    description = (
        "Validates a draft document against extracted GR policy constraints "
        "using deterministic rule-based checks."
    )

    def __init__(self) -> None:
        self._log = logger.bind(tool=self.name)

    async def _execute(
        self,
        *,
        draft: str,
        gr_analysis: GRAnalysis | None = None,
    ) -> dict[str, Any]:
        """
        Args:
            draft: The drafted government document text
            gr_analysis: Structured GR analysis to validate against

        Returns:
            dict with verdict, score, and list of issues
        """
        if not gr_analysis:
            self._log.warning("compliance_engine.no_analysis")
            return {
                "verdict": ComplianceVerdict.INSUFFICIENT_DATA.value,
                "score": 50.0,
                "issues": [],
                "checks_run": 0,
            }

        issues: list[dict[str, str]] = []
        score = 100.0
        checks_run = 0
        draft_lower = draft.lower()

        # ── Check 1: Obligations coverage ─────────────────────────────────
        for obligation in gr_analysis.key_obligations:
            checks_run += 1
            # Use first 4 significant words as signal tokens
            key_terms = [
                w for w in obligation.lower().split()
                if len(w) > 3  # skip stopwords
            ][:4]

            if key_terms and not any(term in draft_lower for term in key_terms):
                score -= 15.0
                issues.append({
                    "severity": "major",
                    "clause_violated": obligation[:100],
                    "description": f"Obligation not addressed in draft: '{obligation[:80]}'",
                    "suggested_fix": f"Add a section explicitly addressing: {obligation[:80]}",
                    "confidence": "0.85",
                })
                self._log.debug(
                    "compliance_engine.obligation_missing",
                    obligation=obligation[:60],
                )

        # ── Check 2: Deadlines mentioned ──────────────────────────────────
        for deadline in gr_analysis.deadlines:
            if not deadline:
                continue
            checks_run += 1
            # Check for date substring or year mention
            date_tokens = deadline.replace("/", " ").replace("-", " ").split()
            found = any(token in draft for token in date_tokens if len(token) >= 4)
            if not found:
                score -= 10.0
                issues.append({
                    "severity": "major",
                    "clause_violated": deadline,
                    "description": f"Deadline not explicitly mentioned in draft: '{deadline}'",
                    "suggested_fix": f"Include the deadline '{deadline}' in the action section.",
                    "confidence": "0.9",
                })

        # ── Check 3: Issuing authority acknowledged ────────────────────────
        if gr_analysis.issuing_authority:
            checks_run += 1
            authority_tokens = [
                w for w in gr_analysis.issuing_authority.lower().split()
                if len(w) > 4
            ][:2]
            if authority_tokens and not any(t in draft_lower for t in authority_tokens):
                score -= 5.0
                issues.append({
                    "severity": "minor",
                    "clause_violated": gr_analysis.issuing_authority,
                    "description": "Issuing authority not referenced in draft.",
                    "suggested_fix": f"Reference '{gr_analysis.issuing_authority}' in the subject or preamble.",
                    "confidence": "0.75",
                })

        # ── Check 4: Reference number present ─────────────────────────────
        if gr_analysis.reference_number:
            checks_run += 1
            if gr_analysis.reference_number not in draft:
                score -= 5.0
                issues.append({
                    "severity": "minor",
                    "clause_violated": gr_analysis.reference_number,
                    "description": "Source GR reference number missing from draft.",
                    "suggested_fix": f"Add 'Ref: {gr_analysis.reference_number}' in the header.",
                    "confidence": "0.95",
                })

        final_score = max(0.0, round(score, 2))

        if final_score >= 85.0:
            verdict = ComplianceVerdict.COMPLIANT.value
        elif final_score >= 60.0:
            verdict = ComplianceVerdict.NEEDS_REVISION.value
        else:
            verdict = ComplianceVerdict.NON_COMPLIANT.value

        self._log.info(
            "compliance_engine.complete",
            score=final_score,
            verdict=verdict,
            issues=len(issues),
            checks=checks_run,
        )

        return {
            "verdict": verdict,
            "score": final_score,
            "issues": issues,
            "checks_run": checks_run,
        }