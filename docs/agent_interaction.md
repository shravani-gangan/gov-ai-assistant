# Agent Interaction Diagram

## Agent Roster

| Agent | Model | Role | Key Output |
|---|---|---|---|
| Planner | mistral:latest | Decomposes user request into SubTask DAG | `ExecutionPlan` |
| Analyst | mistral:latest | Enriches GR extraction, queries memory | `GRAnalysis` (enriched) |
| Drafter | mistral:latest | Generates official-format government document | `str` (draft) |
| Critic | mistral:latest | Validates draft against policy constraints | `ComplianceReport` |
| Hermes | mistral:latest | Meta-reasoning, self-critique, audit narration | enriched `ComplianceReport` + audit log |

All agents share one `MemoryManager` instance injected at construction time.
This is the Praison AI cross-agent memory pattern.

---

## Full Interaction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   Government Officer                            │
│   "Analyze this GR and draft my response as District           │
│    Collector of Pune."  +  [PDF or text input]                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. PLANNER AGENT                                               │
│                                                                 │
│  Input:  user request + has_document flag                       │
│  Action: LLM decomposes into 4-5 SubTasks with dependencies    │
│  Output: ExecutionPlan (typed, DAG-validated by Pydantic)       │
│                                                                 │
│  Example tasks generated:                                       │
│    task_1: Analyze GR document      → assigned: analyst        │
│    task_2: Extract obligations      → assigned: analyst        │
│    task_3: Draft official response  → assigned: drafter        │
│    task_4: Validate compliance      → assigned: critic         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ ExecutionPlan
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. DEERFLOW 2 ENGINE — builds and executes DAG                 │
│                                                                 │
│  Nodes:   analysis → drafting                                   │
│  Edges:   analysis must complete before drafting starts         │
│  State:   WorkflowState shared across all nodes                 │
└──────────┬──────────────────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────────────┐
     │  NODE: analysis                                        │
     │                                                        │
     │  Step A: GR ANALYZER TOOL (2-pass extraction)         │
     │    Pass 1 — Regex: dates, ref numbers, authorities    │
     │    Pass 2 — LLM:   clauses, obligations, applicability│
     │    Output: GRAnalysis with SHA-256 hash               │
     │                                                        │
     │  Step B: ANALYST AGENT                                │
     │    Queries ChromaDB for top-5 similar past GRs        │
     │    Enriches obligations and detects implicit deadlines │
     │    Flags ambiguities → sets needs_replan signal       │
     └──────────────────────────┬─────────────────────────────┘
                                │
                   ┌────────────▼────────────────────────┐
                   │  ambiguities detected?               │
                   └──────┬───────────────┬──────────────┘
                          │ YES           │ NO
                          ▼               ▼
                   ┌──────────────┐  ┌──────────────┐
                   │ DEERFLOW     │  │ Continue to  │
                   │ REPLAN #1    │  │ next node    │
                   │ [CAP #1]     │  │              │
                   └──────┬───────┘  └──────┬───────┘
                          └────────┬─────────┘
                                   │
     ┌─────────────────────────────▼──────────────────────────┐
     │  NODE: drafting                                        │
     │                                                        │
     │  DRAFTER AGENT                                        │
     │    Input: GRAnalysis + officer request                │
     │    Generates official Maharashtra government format:  │
     │      - Letterhead + reference number                  │
     │      - Subject + reference note                       │
     │      - Body addressing all obligations                │
     │      - Action required section                        │
     │      - Signatory block + copy-to list                 │
     │    Output: draft string (500-1500 chars typical)      │
     └─────────────────────────────┬──────────────────────────┘
                                   │ DAG complete
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. PRAISON AI NEGOTIATION LOOP  [CAPABILITY #4]                │
│                                                                 │
│  Round 1:                                                       │
│    CRITIC AGENT evaluates draft                                 │
│      - Rule checks: obligations covered? deadlines mentioned?   │
│      - Authority referenced? Reference number present?          │
│      - LLM semantic check against policy clauses               │
│      - Output: ComplianceReport (verdict + score 0-100)        │
│                                                                 │
│    If score ≥ 75 → CONVERGED, exit loop                        │
│    If score < 75 → DRAFTER revises based on issues list        │
│                                                                 │
│  Round 2 (if needed):                                           │
│    Same Critic evaluation on revised draft                      │
│    Drafter has access to round-1 issues via shared memory      │
│                                                                 │
│  Round 3 (max, if needed):                                      │
│    Final Critic evaluation, exit regardless of score           │
│                                                                 │
│  Demo result: Converged in round 1, score 100/100              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ final draft + ComplianceReport
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. HERMES AGENT — SELF-CRITIQUE  [CAPABILITY #2]               │
│                                                                 │
│  Input:  ComplianceReport + final draft                         │
│  Method: Adversarial prompt — Hermes is told to DISAGREE       │
│                                                                 │
│  Generates:                                                     │
│    counter_arguments[0]: "Draft omits deadline for Water Labs" │
│    counter_arguments[1]: "Penalty clause not cited"            │
│    counter_arguments[2]: "Budget allocation not referenced"    │
│                                                                 │
│  Adjusts:                                                       │
│    confidence_adjustment: -0.1 (score penalized)               │
│    refined_verdict: COMPLIANT → NEEDS_REVISION                 │
│                                                                 │
│  Demo result: 3 counter-args generated, verdict refined        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ enriched ComplianceReport
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. MEMORY PERSISTENCE  [CAPABILITY #3]                         │
│                                                                 │
│  MemoryManager.store():                                         │
│    key:        gr:{sha256_hash}                                 │
│    embedding:  "{doc_type} {obligations[:5]}"                  │
│    metadata:   doc_type, clause_count, verdict, session_id     │
│                                                                 │
│  Future sessions: Analyst queries ChromaDB for top-5 similar   │
│  GRs → Hermes uses them as few-shot examples for new types     │
│                                                                 │
│  Skipped if: hash starts with "fallback" (extraction failed)   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. HERMES AGENT — AUDIT NARRATION  [CAPABILITY #5]             │
│                                                                 │
│  Input:  AuditTrail (all AuditEvent objects from pipeline)      │
│  Action: Converts structured trace to official government text  │
│                                                                 │
│  Each AuditEvent contains:                                      │
│    agent, action, tool_called, input_summary, output_summary,  │
│    token_usage, latency_ms, timestamp                          │
│                                                                 │
│  Output: Human-readable internal audit memorandum              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. PIPELINE OUTPUT — final envelope                            │
│                                                                 │
│  human_readable_draft   — official format document             │
│  gr_analysis            — typed GRAnalysis (clauses, etc.)     │
│  compliance_report      — verdict + score + counter_arguments  │
│  execution_plan         — SubTask DAG from Planner             │
│  confidence_score       — multi-factor float 0.0–1.0           │
│  confidence_breakdown   — per-component scores                 │
│  reasoning_steps        — execution log from WorkflowState     │
│  negotiation_rounds     — how many rounds to converge          │
│  audit_trail            — all AuditEvents + narration          │
│  models_used            — deduplicated model list              │
│  processing_time_ms     — total pipeline latency               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Inter-Agent Communication Protocol

Agents never call each other directly. All communication flows through:

1. **WorkflowState.node_results** — typed results stored by node ID, read by
   downstream nodes. Ensures strict dependency ordering enforced by DeerFlow.

2. **MemoryManager** — shared instance injected into every agent constructor.
   Episodic (session dict) and semantic (ChromaDB) tiers. Analyst writes
   past analyses; Hermes reads them as few-shot examples.

3. **PraisonOrchestrator** — collects `(result, AuditEvent)` tuples from
   every `agent.run()` call, building the audit trail and passing results
   to the next stage.

---

## Timing Profile (CPU inference, mistral:latest)

| Stage | Typical latency |
|---|---|
| Planner | 60–120 seconds |
| GR Analyzer (regex pass) | < 1 second |
| GR Analyzer (LLM pass) | 120–180 seconds |
| Analyst enrichment | 60–90 seconds |
| Drafter initial draft | 60–120 seconds |
| Critic validation | 15–30 seconds |
| Hermes self-critique | 60–120 seconds |
| Hermes audit narration | 60–120 seconds |
| ChromaDB store/query | < 2 seconds |
| **Total (1 negotiation round)** | **~8–15 minutes on CPU** |

> GPU inference (NVIDIA RTX 3080+) reduces total time to 60–90 seconds.