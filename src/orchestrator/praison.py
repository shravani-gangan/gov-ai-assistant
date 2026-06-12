"""
Praison AI Orchestration Layer
-------------------------------
Manages the full multi-agent pipeline including:
  - Cross-agent memory (Praison AI's key contribution)
  - Conversational orchestration
  - The drafting ↔ compliance negotiation loop

Why Praison AI patterns here?
  Praison AI's architecture treats agents as conversational participants
  with shared context. This maps perfectly to our negotiation loop where
  the Drafter and Critic must "argue" toward a compliant draft. Their
  shared memory (via MemoryManager) prevents re-analysis on each round.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from src.agents.analyst  import AnalystAgent
from src.agents.critic   import CriticAgent
from src.agents.drafter  import DrafterAgent
from src.agents.hermes   import HermesAgent
from src.agents.planner  import PlannerAgent
from src.audit.trail     import AuditTrailGenerator
from src.core.config     import get_config
from src.core.schemas    import (
    AuditTrail,
    ComplianceVerdict,
    DocumentType,
    ExecutionPlan,
    GRAnalysis,
    PipelineOutput,
    TaskStatus,
)
from src.memory.manager  import MemoryManager
from src.tools.gr_analyzer       import GRAnalyzerTool
from src.tools.compliance_engine import ComplianceEngineTool
from src.workflow.deerflow        import (
    DeerFlowEngine,
    WorkflowNode,
    WorkflowState,
    NodeType,
)

logger = structlog.get_logger(__name__)


def _make_fallback_gr_analysis(reason: str = "extraction_failed") -> GRAnalysis:
    """
    Returns a valid empty GRAnalysis when extraction fails or times out.
    Ensures PipelineOutput validation never fails due to missing GR data.
    """
    return GRAnalysis(
        document_type=DocumentType.UNKNOWN,
        title=f"Extraction unavailable — {reason}",
        issuing_authority=None,
        issue_date=None,
        reference_number=None,
        clauses=[],
        key_obligations=["Manual review required — automated extraction failed"],
        deadlines=[],
        applicability=[],
        ambiguities_detected=[f"GR extraction failed: {reason}"],
        raw_text_hash=f"fallback_{reason[:20]}",
    )


def _coerce_gr_analysis(raw: Any) -> GRAnalysis:
    """
    Safely coerces any value coming out of the workflow state into
    a valid GRAnalysis object. Handles: None, dict, GRAnalysis, fallback dict.
    """
    if raw is None:
        return _make_fallback_gr_analysis("no_result_returned")

    if isinstance(raw, GRAnalysis):
        return raw

    if isinstance(raw, dict):
        # Workflow state dicts injected by analysis_handler
        if raw.get("needs_replan") and not raw.get("document_type"):
            return _make_fallback_gr_analysis(
                raw.get("ambiguities", ["unknown_reason"])[0][:40]
            )
        # Try to reconstruct from model_dump output
        try:
            return GRAnalysis(**{
                k: v for k, v in raw.items()
                if k not in ("needs_replan", "ambiguities")
            })
        except Exception as exc:
            logger.warning(
                "praison.gr_coerce_failed",
                error=str(exc),
                keys=list(raw.keys()),
            )
            return _make_fallback_gr_analysis("dict_coerce_failed")

    return _make_fallback_gr_analysis("unexpected_type")


class PraisonOrchestrator:
    """
    Top-level orchestrator implementing the full government AI pipeline.

    Extended capabilities demonstrated:
    1. Dynamic workflow re-planning (DeerFlow 2)
    2. Hermes self-critique
    3. Cross-agent memory (Praison AI)
    4. Multi-round drafting ↔ compliance negotiation
    5. Automated audit trail
    """

    def __init__(self) -> None:
        self._config  = get_config()
        self._memory  = MemoryManager()

        # All agents share ONE MemoryManager instance
        # This is the Praison AI cross-agent memory pattern
        self._planner  = PlannerAgent(memory=self._memory)
        self._analyst  = AnalystAgent(memory=self._memory)
        self._drafter  = DrafterAgent(memory=self._memory)
        self._critic   = CriticAgent(memory=self._memory)
        self._hermes   = HermesAgent(memory=self._memory)

        # Tools
        self._gr_tool    = GRAnalyzerTool()
        self._compliance = ComplianceEngineTool()

        # Audit
        self._audit_gen = AuditTrailGenerator()

        self._log = logger.bind(component="praison_orchestrator")

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def process(
        self,
        *,
        user_request: str,
        document_text: str | None = None,
        pdf_path: str | None = None,
    ) -> PipelineOutput:
        """
        Main entry point. Orchestrates the full pipeline.
        Returns a complete PipelineOutput with all deliverables.
        """
        session_id  = str(uuid.uuid4())
        request_id  = str(uuid.uuid4())
        audit_events: list[Any] = []

        self._log.info(
            "orchestrator.process.start",
            session=session_id,
            request_preview=user_request[:100],
        )

        # ── Step 1: Planner decomposes the request ─────────────────────────
        plan, plan_event = await self._planner.run(
            request=user_request,
            has_document=bool(document_text or pdf_path),
        )
        audit_events.append(plan_event)
        self._log.info(
            "orchestrator.plan_ready",
            tasks=len(plan.tasks),
        )

        # ── Step 2: Build DeerFlow DAG from plan ───────────────────────────
        engine, state = self._build_workflow(
            plan=plan,
            session_id=session_id,
            user_request=user_request,
        )

        # Inject document context into workflow state
        state.node_results["__input__"] = {
            "request":       user_request,
            "document_text": document_text,
            "pdf_path":      pdf_path,
        }

        # ── Step 3: Execute workflow (with dynamic re-planning) ─────────────
        final_state = await engine.execute(state)
        audit_events.extend(final_state.audit_events)

        # ── Step 4: Safely extract GRAnalysis from workflow state ───────────
        gr_analysis_raw = (
            final_state.node_results.get("analysis_obj")
            or final_state.node_results.get("analysis")
        )
        gr_analysis = _coerce_gr_analysis(gr_analysis_raw)

        initial_draft = ""
        drafting_result = final_state.node_results.get("drafting")
        if isinstance(drafting_result, dict):
            initial_draft = drafting_result.get("draft", "")
        elif isinstance(drafting_result, str):
            initial_draft = drafting_result

        self._log.info(
            "orchestrator.extraction_complete",
            doc_type=gr_analysis.document_type,
            obligations=len(gr_analysis.key_obligations),
            draft_chars=len(initial_draft),
        )

        # ── Step 5: Negotiation loop (Praison AI multi-round) ──────────────
        final_draft, compliance_report, negotiation_rounds = (
            await self._negotiation_loop(
                gr_analysis=gr_analysis,
                initial_draft=initial_draft,
                user_request=user_request,
                audit_events=audit_events,
            )
        )

        # ── Step 6: Hermes self-critique ───────────────────────────────────
        enriched_compliance, hermes_event = await self._hermes.run(
            task="self_critique",
            compliance_report=compliance_report,
            draft=final_draft,
        )
        audit_events.append(hermes_event)

        # ── Step 7: Persist to cross-agent memory (Praison AI) ─────────────
        await self._persist_to_memory(
            session_id=session_id,
            gr_analysis=gr_analysis,
            compliance_report=enriched_compliance,
            draft=final_draft,
        )

        # ── Step 8: Generate audit trail (Hermes narration) ─────────────────
        raw_trail = self._audit_gen.compile(
            request_id=request_id,
            session_id=session_id,
            events=audit_events,
        )
        narrated_trail_text, narrate_event = await self._hermes.run(
            task="narrate_audit",
            audit_trail=raw_trail,
        )
        audit_events.append(narrate_event)

        # ── Step 9: Score confidence ────────────────────────────────────────
        confidence, breakdown = self._compute_confidence(
            gr_analysis=gr_analysis,
            compliance_report=enriched_compliance,
            negotiation_rounds=negotiation_rounds,
            replan_count=final_state.replan_count,
        )

        # ── Step 10: Build reasoning steps from execution log ───────────────
        reasoning_steps = final_state.execution_log or [
            "Planner decomposed request into subtasks",
            "GR Analyzer extracted document structure",
            "Drafter generated official response",
            "Critic validated compliance",
            "Hermes performed self-critique",
        ]

        self._log.info(
            "orchestrator.process.complete",
            confidence=confidence,
            negotiation_rounds=negotiation_rounds,
            replans=final_state.replan_count,
        )

        return PipelineOutput(
            request_id=request_id,
            session_id=session_id,
            human_readable_draft=final_draft or "Draft generation failed — please retry.",
            gr_analysis=gr_analysis,
            compliance_report=enriched_compliance,
            execution_plan=plan,
            confidence_score=confidence,
            confidence_breakdown=breakdown,
            reasoning_steps=reasoning_steps,
            negotiation_rounds=negotiation_rounds,
            audit_trail=raw_trail,
            models_used=self._get_models_used(),
            processing_time_ms=sum(
                e.latency_ms for e in audit_events
                if hasattr(e, "latency_ms")
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Negotiation loop
    # ─────────────────────────────────────────────────────────────────────────

    async def _negotiation_loop(
        self,
        gr_analysis: GRAnalysis,
        initial_draft: str,
        user_request: str,
        audit_events: list,
    ) -> tuple[str, Any, int]:
        """
        Praison AI-style conversational negotiation between Drafter and Critic.
        Converges on a policy-compliant draft within max_rounds iterations.

        Extended capability: Multi-round negotiation between agents.
        """
        config = self._config.agent
        draft  = initial_draft
        rounds = 0

        # If no initial draft, generate one before the loop
        if not draft.strip():
            self._log.info("negotiation.generating_initial_draft")
            draft_result, draft_event = await self._drafter.run(
                task="initial",
                gr_analysis=gr_analysis,
                request=user_request,
            )
            audit_events.append(draft_event)
            draft = draft_result.get("draft", "") if isinstance(draft_result, dict) else str(draft_result)

        for round_num in range(1, config.max_negotiation_rounds + 1):
            self._log.info("negotiation.round", round=round_num)

            # Critic evaluates current draft
            compliance_result, critic_event = await self._critic.run(
                draft=draft,
                gr_analysis=gr_analysis,
            )
            audit_events.append(critic_event)
            rounds = round_num

            verdict_score = compliance_result.overall_score
            self._log.info(
                "negotiation.critic_verdict",
                round=round_num,
                score=verdict_score,
                verdict=compliance_result.verdict,
            )

            # Converged: draft passes compliance threshold
            if (
                compliance_result.verdict in (
                    ComplianceVerdict.COMPLIANT,
                    ComplianceVerdict.INSUFFICIENT_DATA,
                )
                or verdict_score >= config.compliance_threshold
            ):
                self._log.info("negotiation.converged", round=round_num)
                return draft, compliance_result, rounds

            # Drafter revises based on critic's issues
            if round_num < config.max_negotiation_rounds:
                revised_result, drafter_event = await self._drafter.run(
                    task="revise",
                    current_draft=draft,
                    compliance_issues=compliance_result.issues,
                    gr_analysis=gr_analysis,
                )
                audit_events.append(drafter_event)
                if isinstance(revised_result, dict):
                    draft = revised_result.get("draft", draft)

        # Max rounds reached — return best effort
        self._log.warning("negotiation.max_rounds_reached", rounds=rounds)
        final_compliance, _ = await self._critic.run(
            draft=draft,
            gr_analysis=gr_analysis,
        )
        return draft, final_compliance, rounds

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_workflow(
        self,
        plan: ExecutionPlan,
        session_id: str,
        user_request: str,
    ) -> tuple[DeerFlowEngine, WorkflowState]:
        """
        Converts an ExecutionPlan into a DeerFlow DAG.
        Extended capability: Dynamic workflow re-planning triggered by
        ambiguity signals from the analysis node.
        """
        engine = DeerFlowEngine()
        state  = WorkflowState(
            session_id=session_id,
            original_request=user_request,
        )

        # ── Analysis node ──────────────────────────────────────────────────
        async def analysis_handler(s: WorkflowState) -> Any:
            inp = s.node_results.get("__input__", {})
            tool_result = await self._gr_tool.run(
                text=inp.get("document_text"),
                pdf_path=inp.get("pdf_path"),
            )

            result, event = await self._analyst.run(
                gr_tool_result=tool_result,
                request=s.original_request,
            )
            s.audit_events.append(event)

            if result is None:
                s.execution_log.append(
                    "[ANALYSIS] GR extraction returned no result — triggering replan"
                )
                return {
                    "needs_replan": True,
                    "ambiguities": ["Document analysis returned no result"],
                }

            # Store the typed object separately for downstream safe access
            s.node_results["analysis_obj"] = result
            s.execution_log.append(
                f"[ANALYSIS] Extracted {len(result.clauses)} clauses, "
                f"{len(result.key_obligations)} obligations, "
                f"{len(result.deadlines)} deadlines"
            )

            needs_replan = bool(result.ambiguities_detected)
            if needs_replan:
                s.execution_log.append(
                    f"[REPLAN SIGNAL] {len(result.ambiguities_detected)} ambiguities detected"
                )

            return {
                **result.model_dump(),
                "needs_replan": needs_replan,
                "ambiguities":  result.ambiguities_detected,
            }

        engine.add_node(WorkflowNode(
            node_id="analysis",
            node_type=NodeType.AGENT_CALL,
            name="GR Analysis",
            handler=analysis_handler,
            dependencies=[],
        ))

        # ── Drafting node ──────────────────────────────────────────────────
        async def drafting_handler(s: WorkflowState) -> Any:
            # Use typed object if available, else fall back to dict
            analysis = (
                s.node_results.get("analysis_obj")
                or s.node_results.get("analysis")
            )
            result, event = await self._drafter.run(
                task="initial",
                gr_analysis=analysis,
                request=s.original_request,
            )
            s.audit_events.append(event)
            s.execution_log.append(
                f"[DRAFTING] Generated initial draft "
                f"({len(result.get('draft', '')) if isinstance(result, dict) else 0} chars)"
            )
            return result

        engine.add_node(WorkflowNode(
            node_id="drafting",
            node_type=NodeType.AGENT_CALL,
            name="Draft Generation",
            handler=drafting_handler,
            dependencies=["analysis"],
        ))

        engine.add_edge("analysis", "drafting")
        return engine, state

    # ─────────────────────────────────────────────────────────────────────────
    # Memory persistence
    # ─────────────────────────────────────────────────────────────────────────

    async def _persist_to_memory(
        self,
        session_id: str,
        gr_analysis: GRAnalysis,
        compliance_report: Any,
        draft: str,
    ) -> None:
        """
        Praison AI cross-agent memory persistence.
        Stores GR interpretation for future few-shot adaptation by Hermes.
        Extended capability: Cross-agent long-term episodic memory.
        """
        raw_hash = gr_analysis.raw_text_hash
        if not raw_hash or raw_hash.startswith("fallback"):
            self._log.info("orchestrator.memory_skip", reason="fallback_hash")
            return

        doc_type = str(gr_analysis.document_type)
        obligations = gr_analysis.key_obligations[:3]

        verdict = "unknown"
        if compliance_report:
            verdict = (
                compliance_report.verdict.value
                if hasattr(compliance_report.verdict, "value")
                else str(compliance_report.verdict)
            )

        try:
            await self._memory.store(
                key=f"gr:{raw_hash}",
                value={
                    "doc_type":           doc_type,
                    "strategy":           f"Analyzed {len(gr_analysis.clauses)} clauses",
                    "obligations":        str(obligations),
                    "compliance_verdict": verdict,
                    "session_id":         session_id,
                },
                embed_text=(
                    f"{doc_type} "
                    + " ".join(str(o) for o in obligations[:5])
                ),
            )
            self._log.info(
                "orchestrator.memory_persisted",
                hash=raw_hash[:8],
            )
        except Exception as exc:
            self._log.warning(
                "orchestrator.memory_persist_failed",
                error=str(exc),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Confidence scoring
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_confidence(
        self,
        gr_analysis: GRAnalysis,
        compliance_report: Any,
        negotiation_rounds: int,
        replan_count: int,
    ) -> tuple[float, dict[str, float]]:
        """
        Multi-factor confidence scoring.
        Penalizes replanning (ambiguity) and long negotiation (non-compliance).
        """
        breakdown: dict[str, float] = {}

        # ── Extraction confidence ─────────────────────────────────────────
        clauses = gr_analysis.clauses if gr_analysis else []
        if clauses:
            confidences = [
                c.confidence if hasattr(c,"confidence")
                else float(c.get("confidence",0.7))
                for c in clauses
            ]
            breakdown["extraction"] = sum(confidences)/len(confidences)
        else:
            # Fallback GRAnalysis - low but non zero confidence
            breakdown["extraction"] = 0.3

        # Compliance Confidence
        if compliance_report:
            breakdown["compliance"] = compliance_report.overall_score / 100.0
        else:
            breakdown["compliance"] = 0.5

        # Stability - penealize replanning
        breakdown["stability"] = max(0.3, 1.0 - replan_count*0.2)

        # Negotiation efficiency
        breakdown["negotiation"] = max(0.4, 1.0 - (negotiation_rounds-1)*0.15)

        overall = sum(breakdown.values())/len(breakdown)
        return round(overall, 3),{k:round(v,3) for k, v in breakdown.items()}
    
    # Helpers
    def _get_models_used(self)-> list[str]:
        """Returns deduplicated list of all models used in this pipeline run"""
        config = self._config.ollama
        return list(dict.fromkeys([
            config.planner_model,
            config.analyst_model,
            config.drafter_model,
            config.critic_model,
            config.hermes_model,
        ]))
