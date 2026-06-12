"""
Central Pydantic v2 schema definitions for all agent I/O contracts.
Defines the structured output envelope that the entire pipeline produces.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class AgentRole(str, Enum):
    PLANNER    = "planner"
    ANALYST    = "analyst"
    DRAFTER    = "drafter"
    CRITIC     = "critic"
    HERMES     = "hermes"
    ORCHESTRATOR = "orchestrator"


class TaskStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    SKIPPED    = "skipped"


class ComplianceVerdict(str, Enum):
    COMPLIANT        = "compliant"
    NON_COMPLIANT    = "non_compliant"
    NEEDS_REVISION   = "needs_revision"
    INSUFFICIENT_DATA = "insufficient_data"


class DocumentType(str, Enum):
    GOVERNMENT_RESOLUTION = "government_resolution"
    CIRCULAR              = "circular"
    OFFICE_MEMORANDUM     = "office_memorandum"
    NOTIFICATION          = "notification"
    UNKNOWN               = "unknown"


# ─────────────────────────────────────────────
# GR Analysis Schemas
# ─────────────────────────────────────────────

class PolicyClause(BaseModel):
    clause_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    clause_text: str
    clause_type: str  # "obligation", "deadline", "authority", "applicability", "penalty"
    authority_referenced: str | None = None
    deadline: str | None = None
    applicability_scope: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class GRAnalysis(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_type: DocumentType
    title: str | None = None
    issuing_authority: str | None = None
    issue_date: str | None = None
    reference_number: str | None = None
    clauses: list[PolicyClause]
    key_obligations: list[str]
    deadlines: list[str]
    applicability: list[str]
    ambiguities_detected: list[str] = Field(default_factory=list)
    raw_text_hash: str  # SHA-256 for deduplication


# ─────────────────────────────────────────────
# Compliance Schemas
# ─────────────────────────────────────────────

class ComplianceIssue(BaseModel):
    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    severity: str  # "critical", "major", "minor", "advisory"
    clause_violated: str
    description: str
    suggested_fix: str
    confidence: float = Field(ge=0.0, le=1.0)


class ComplianceReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verdict: ComplianceVerdict
    overall_score: float = Field(ge=0.0, le=100.0)
    issues: list[ComplianceIssue]
    counter_arguments: list[str] = Field(
        default_factory=list,
        description="Hermes-generated counter-arguments for self-critique"
    )
    refinement_iterations: int = 0
    checked_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# Planning Schemas
# ─────────────────────────────────────────────

class SubTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str
    assigned_agent: AgentRole
    dependencies: list[str] = Field(default_factory=list)  # task_ids
    status: TaskStatus = TaskStatus.PENDING
    priority: int = Field(ge=1, le=5, default=3)
    estimated_tokens: int = 500
    retry_count: int = 0
    max_retries: int = 2


class ExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_request: str
    tasks: list[SubTask]
    estimated_total_tokens: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revision_count: int = 0
    ambiguities_detected: list[str] = Field(default_factory=list)

    @field_validator("tasks")
    @classmethod
    def validate_dag(cls, tasks: list[SubTask]) -> list[SubTask]:
        """Ensure no circular dependencies exist in the task graph."""
        task_ids = {t.task_id for t in tasks}
        for task in tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    raise ValueError(
                        f"Task '{task.task_id}' has unknown dependency '{dep}'"
                    )
        return tasks


# ─────────────────────────────────────────────
# Audit Trail
# ─────────────────────────────────────────────

class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: AgentRole
    action: str
    tool_called: str | None = None
    input_summary: str
    output_summary: str
    token_usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditTrail(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    events: list[AuditEvent]
    total_tokens: int
    total_latency_ms: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# Final Pipeline Output
# ─────────────────────────────────────────────

class PipelineOutput(BaseModel):
    """
    The canonical output envelope returned by the full pipeline.
    Every field here maps directly to an 'Evaluation Criteria' item.
    """
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str

    # Core deliverables
    human_readable_draft: str
    gr_analysis: GRAnalysis
    compliance_report: ComplianceReport
    execution_plan: ExecutionPlan

    # Scoring
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)

    # Reasoning transparency
    reasoning_steps: list[str]
    negotiation_rounds: int = 0

    # Audit
    audit_trail: AuditTrail

    # Metadata
    models_used: list[str]
    processing_time_ms: float
    created_at: datetime = Field(default_factory=datetime.utcnow)