# System Architecture

## Overview

The Government AI Multi-Agent Assistant is a locally-running, production-grade
multi-agent pipeline built around three frameworks:

- **Praison AI** — orchestration, cross-agent memory, negotiation loop
- **DeerFlow 2** — dynamic DAG workflow engine with runtime re-planning
- **Hermes Agent** — meta-reasoning, self-critique, audit narration

All inference runs locally via Ollama. No external API calls are made.

---

## Layered Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
│   FastAPI  ·  POST /api/v1/analyze/text  ·  /analyze/pdf        │
│   GET /health  ·  Swagger UI at /docs                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼──────────────────────────────────────┐
│              Praison AI Orchestration Layer                       │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ Cross-agent     │  │ Negotiation loop │  │ Confidence     │  │
│  │ memory (shared  │  │ Drafter ↔ Critic │  │ scoring        │  │
│  │ MemoryManager)  │  │ max 3 rounds     │  │ (4-factor)     │  │
│  └─────────────────┘  └──────────────────┘  └────────────────┘  │
└──────┬───────────────────────────────────────────────────────────┘
       │ agent calls
┌──────▼───────────────────────────────────────────────────────────┐
│                      Agent Layer                                  │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Planner  │ │ Analyst  │ │ Drafter  │ │ Critic   │           │
│  │ SubTask  │ │ GR enrich│ │ Official │ │ Compliance│           │
│  │ DAG      │ │ + memory │ │ format   │ │ verdict  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Hermes Agent (meta-reasoning)                           │   │
│  │  self_critique()  ·  few_shot_adapt()  ·  narrate_audit()│   │
│  └──────────────────────────────────────────────────────────┘   │
└──────┬───────────────────────────────────────────────────────────┘
       │ node execution
┌──────▼───────────────────────────────────────────────────────────┐
│              DeerFlow 2 — Workflow DAG Engine                     │
│                                                                  │
│  Topological sort  ·  Parallel execution (asyncio.gather)        │
│  Dynamic node insertion  ·  Conditional edges                    │
│  Exponential backoff retry  ·  WorkflowState (shared)           │
└──────┬───────────────────────────────────────────────────────────┘
       │ tool calls
┌──────▼───────────────────────────────────────────────────────────┐
│                      Tools Layer                                  │
│                                                                  │
│  GR Analyzer      — 2-pass: regex + LLM extraction              │
│  Compliance Engine — rule-based obligation/deadline checks       │
│  Doc Comparator   — contradiction detection across GRs          │
│  Doc Generator    — official Maharashtra GR template            │
│  Schema Validator — Pydantic v2 JSON schema enforcement         │
└──────┬───────────────────────────────────────────────────────────┘
       │ inference / storage
┌──────▼───────────────────────────────────────────────────────────┐
│                     Infrastructure                                │
│                                                                  │
│  Ollama          — local LLM inference server (port 11434)      │
│  mistral:latest  — primary reasoning model (7B, Q4)             │
│  nomic-embed-text — 768-dim embeddings                          │
│  ChromaDB        — persistent vector store (port 8001)          │
│  Redis           — task queue for async jobs (port 6379)        │
│  Docker Compose  — one-command infrastructure start             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### Why a custom DAG instead of LangGraph?

LangGraph is excellent but abstracts away state transitions. For a government
compliance system, explicit auditability of every state change is a hard
requirement. The DeerFlow implementation gives direct control over:

1. Conditional edge evaluation — crucial for compliance branching
2. Dynamic node insertion without pipeline restart
3. Full state inspection at every step for audit trail generation
4. Retry logic with configurable backoff per node

### Why Pydantic v2 for all I/O contracts?

Two reasons. First, `model_json_schema()` generates OpenAPI-compatible schemas
directly — the FastAPI Swagger UI is auto-generated from the same models.
Second, Pydantic field validators enforce domain invariants at the type level,
catching issues like circular task dependencies at plan-creation time rather
than at runtime mid-pipeline.

### Why SHA-256 for document deduplication?

Government circulars are frequently re-submitted through different channels
with minor OCR artifacts or formatting differences. Hashing the raw text lets
the system skip expensive LLM re-analysis of documents already processed. The
hash is the foreign key linking ChromaDB entries to past session data — a
lightweight deduplication mechanism with zero false positives on exact matches.

---

## Data Flow

```
Raw input (PDF / text)
        │
        ▼
GRAnalysis (Pydantic) ── clauses · obligations · deadlines · confidence
        │
        ▼
Draft (string) ── official Maharashtra government format
        │
        ▼
ComplianceReport (Pydantic) ── verdict · score · issues · counter-args
        │
        ▼
PipelineOutput (Pydantic) ── all of the above + audit_trail + confidence_score
```

---

## Extended Capabilities Map

| # | Capability | Component | Implementation |
|---|---|---|---|
| 1 | Dynamic re-planning | DeerFlow 2 | `_handle_replan()` on ambiguity signal |
| 2 | Hermes self-critique | Hermes Agent | `self_critique()` adversarial pass |
| 3 | Cross-agent memory | Praison AI + ChromaDB | `_persist_to_memory()` |
| 4 | Multi-round negotiation | Praison AI orchestrator | `_negotiation_loop()` |
| 5 | Automated audit trail | Hermes + AuditTrailGenerator | `narrate_audit_trail()` |

---

## Port Reference

| Service | Port | Purpose |
|---|---|---|
| FastAPI | 8000 | REST API + Swagger UI |
| Ollama | 11434 | Local LLM inference |
| ChromaDB | 8001 | Vector store |
| Redis | 6379 | Task queue |

---

## Component Diagram

See `diagrams/architecture.png` for the full visual diagram.
See `diagrams/agent_flow.png` for the agent interaction flow.
See `diagrams/deerflow_dag.png` for the DeerFlow DAG structure.