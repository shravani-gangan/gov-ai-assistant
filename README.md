# 🏛️ Government AI Multi-Agent Assistant

> A locally-running, production-grade multi-agent AI system that assists Government Officers in analyzing circulars, drafting compliant responses, and validating policy adherence — with zero external API dependencies.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Extended Capabilities](#extended-capabilities)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the System](#running-the-system)
- [API Reference](#api-reference)
- [Demo](#demo)
- [Design Notes](#design-notes)
- [Evaluation Criteria Coverage](#evaluation-criteria-coverage)

---

## Overview

This system simulates an intelligent internal assistant for Government Officers, capable of:

- **Analyzing** Government Resolutions (GRs) and Circulars from PDF or text
- **Extracting** obligations, deadlines, authorities, and applicability clauses
- **Drafting** official-format responses and internal notes
- **Validating** compliance against source policy documents
- **Negotiating** between drafting and compliance agents iteratively
- **Generating** a full audit trail of every agent decision

All inference runs locally via **Ollama** — no external API calls, no data leaves your machine.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI REST Layer                          │
│              POST /api/v1/analyze/text  |  /analyze/pdf         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│              Praison AI Orchestrator (praison.py)               │
│   Cross-agent memory │ Negotiation loop │ Confidence scoring    │
└──────┬──────────┬──────────┬──────────┬────────────┬────────────┘
       │          │          │          │            │
  ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌────▼────┐
  │Planner │ │Analyst │ │Drafter │ │ Critic │ │ Hermes  │
  │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │ │  Agent  │
  └────┬───┘ └───┬────┘ └───┬────┘ └───┬────┘ └────┬────┘
       │         │          │          │            │
       └─────────┴──────────┴──────────┴────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│              DeerFlow 2 DAG Engine (deerflow.py)                 │
│   Topological execution │ Retry logic │ Dynamic re-planning     │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼───────────────────────────────────────────────────────────┐
│                     Tools Layer                                   │
│  GRAnalyzer │ ComplianceEngine │ DocComparator │ DocGenerator    │
│  SchemaValidator                                                  │
└──────┬───────────────────────────────────────────────────────────┘
       │
┌──────▼───────────────────────────────────────────────────────────┐
│                   Infrastructure                                  │
│  Ollama (local LLM) │ ChromaDB (vector memory) │ Redis (queue)  │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Interaction Flow

```
User Request
    │
    ▼
[Planner] ──── Decomposes into SubTask DAG
    │
    ▼
[DeerFlow Engine] ──── Executes DAG (topological order)
    │
    ├──► [GR Analyzer Tool] ──── Two-pass extraction (regex + LLM)
    │         │
    ▼         ▼
[Analyst Agent] ──── Enriches extraction, checks memory for similar GRs
    │
    ▼
[Drafter Agent] ──── Generates official-format draft
    │
    ▼ ◄──────────────────────────────────────────┐
[Critic Agent] ──── Validates against policy     │
    │                                            │
    ├── COMPLIANT ──► Continue                   │
    │                                            │
    └── NON-COMPLIANT ──► [Drafter revises] ─────┘
              (max 3 negotiation rounds)
    │
    ▼
[Hermes Agent] ──── Self-critique + counter-arguments
    │
    ▼
[Hermes Agent] ──── Narrates audit trail
    │
    ▼
[Memory Manager] ──── Persists to ChromaDB for future sessions
    │
    ▼
PipelineOutput (JSON + human-readable draft + audit trail)
```

---

## Extended Capabilities

All 5 extended capabilities are implemented and demonstrated:

### 1. 🔄 Dynamic Workflow Re-planning (DeerFlow 2)
When the analysis node detects ambiguities in a GR, it emits a `needs_replan: True` signal. The DeerFlow engine intercepts this, logs a replan event, and adjusts downstream node execution accordingly — without restarting the pipeline.

**Code:** `src/workflow/deerflow.py` → `_handle_replan()`

### 2. 🧠 Hermes-Driven Self-Critique
After the Critic produces a compliance verdict, the Hermes Agent runs an adversarial second pass — generating counter-arguments that challenge the verdict, identifying blind spots, and producing a refined verdict. In the demo run, Hermes correctly refined `COMPLIANT → NEEDS_REVISION`.

**Code:** `src/agents/hermes.py` → `self_critique()`

### 3. 💾 Praison AI Cross-Agent Memory
All 5 agents share a single `MemoryManager` instance (injected via constructor). Past GR interpretations are stored in ChromaDB with embeddings, enabling future sessions to retrieve similar analyses as few-shot examples for the Hermes adaptation capability.

**Code:** `src/memory/manager.py`, `src/orchestrator/praison.py` → `_persist_to_memory()`

### 4. 🤝 Multi-Round Negotiation Between Agents
The Drafter and Critic engage in a structured negotiation loop (up to 3 rounds). The Critic identifies compliance issues; the Drafter revises the draft to address them. The loop converges when the compliance score exceeds the threshold (default: 75/100).

**Code:** `src/orchestrator/praison.py` → `_negotiation_loop()`

### 5. 📋 Automated Audit Trail Generation
Every agent action, tool call, input summary, output summary, and latency is captured as a structured `AuditEvent`. Hermes narrates this trace into a human-readable official internal audit log.

**Code:** `src/audit/trail.py`, `src/agents/hermes.py` → `narrate_audit_trail()`

---

## Tech Stack

| Component | Technology | Rationale |
|---|---|---|
| Local LLM Runtime | Ollama | OpenAI-compatible API, GGUF support |
| Primary Model | `mistral:latest` | Best instruction-following at 7B scale |
| Embeddings | `nomic-embed-text` | 768-dim local embeddings, fast |
| Vector Store | ChromaDB | Persistent local vector DB, no server needed |
| Agent Framework | Custom (Praison AI patterns) | Full control over state and audit |
| Workflow Engine | Custom DAG (DeerFlow 2 patterns) | Explicit re-planning support |
| Schema Validation | Pydantic v2 | Runtime type safety + JSON schema generation |
| API Layer | FastAPI | Async, auto-docs via OpenAPI |
| Document Parsing | pdfplumber + PyMuPDF | Accurate text extraction with layout |
| Logging | structlog | Structured JSON logs for observability |
| Containerization | Docker Compose | One-command infrastructure setup |

---

## Project Structure

```
gov-ai-assistant/
├── src/
│   ├── core/           # Config, schemas, logging, exceptions
│   ├── models/         # Ollama + embedding clients
│   ├── memory/         # Episodic + semantic memory (Praison AI)
│   ├── tools/          # GR analyzer, compliance engine, doc tools
│   ├── agents/         # Planner, Analyst, Drafter, Critic, Hermes
│   ├── workflow/       # DeerFlow DAG engine + re-planner
│   ├── orchestrator/   # Praison orchestrator + negotiation loop
│   ├── audit/          # Audit trail compiler
│   └── api/            # FastAPI app + routes
├── scripts/
│   ├── run_demo.py     # End-to-end demo
│   └── setup_models.sh # Ollama model pull
├── tests/
│   ├── unit/           # Tool + agent unit tests
│   └── integration/    # Pipeline integration tests
├── docs/               # Architecture + design notes
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Setup & Installation

### Prerequisites

| Requirement | Version | Install |
|---|---|---|
| Python | ≥ 3.11 | [python.org](https://python.org) |
| Ollama | Latest | [ollama.com/download](https://ollama.com/download) |
| Git | Any | [git-scm.com](https://git-scm.com) |

### Step 1 — Clone the repository

```bash
git clone https://github.com/<your-username>/gov-ai-assistant.git
cd gov-ai-assistant
```

### Step 2 — Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install fastapi==0.111.0 uvicorn[standard]==0.29.0 pydantic==2.7.0 \
  pydantic-settings==2.3.0 httpx==0.27.0 chromadb==0.5.3 \
  pdfplumber==0.11.0 PyMuPDF==1.24.0 structlog==24.2.0 \
  python-multipart==0.0.9 pytest==8.2.0 pytest-asyncio==0.23.6

pip install -e . --no-deps
```

### Step 4 — Pull Ollama models

```bash
# Start Ollama server (keep this terminal open)
ollama serve

# In a new terminal, pull models
ollama pull mistral
ollama pull nomic-embed-text
ollama pull phi3:mini        # optional — for long-context compliance
ollama pull nous-hermes2     # optional — for enhanced meta-reasoning
```

### Step 5 — Configure environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box with mistral
```

`.env.example`:
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_PLANNER_MODEL=mistral
OLLAMA_ANALYST_MODEL=mistral
OLLAMA_DRAFTER_MODEL=mistral
OLLAMA_CRITIC_MODEL=mistral
OLLAMA_HERMES_MODEL=mistral
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_TIMEOUT_SECONDS=300
OLLAMA_MAX_RETRIES=2
AGENT_TEMPERATURE=0.1
AGENT_SEED=42
AGENT_MAX_NEGOTIATION_ROUNDS=3
AGENT_COMPLIANCE_THRESHOLD=75.0
```

---

## Running the System

### Option A — Demo Script (Recommended for evaluation)

```bash
python scripts/run_demo.py
```

Runs the full pipeline with a real Maharashtra GR (Jal Jeevan Mission).
Output saved to `demo_output.json`.

### Option B — API Server

```bash
uvicorn src.api.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for interactive Swagger UI.

### Option C — Docker Compose

```bash
docker-compose up -d
```

Starts Ollama, ChromaDB, Redis, and the API server together.

---

## API Reference

### `POST /api/v1/analyze/text`

Analyze a GR from raw text input.

**Request:**
```json
{
  "request": "I am the District Collector of Pune. Analyze this GR and draft my response.",
  "document_text": "Government of Maharashtra\nNo. GR/2024/CR-123\n..."
}
```

**Response:** Full `PipelineOutput` including:
- `human_readable_draft` — Official formatted document
- `gr_analysis` — Structured extraction (clauses, obligations, deadlines)
- `compliance_report` — Verdict, score, issues, Hermes counter-arguments
- `confidence_score` — Multi-factor confidence (0.0–1.0)
- `reasoning_steps` — Step-by-step execution log
- `audit_trail` — Full agent decision trace
- `negotiation_rounds` — Number of draft↔compliance iterations

### `POST /api/v1/analyze/pdf`

Same as above but accepts a PDF file upload via multipart form.

```bash
curl -X POST http://localhost:8000/api/v1/analyze/pdf \
  -F "request=Analyze this GR and extract all obligations" \
  -F "file=@path/to/circular.pdf"
```

### `GET /health`

Returns system health + model configuration.

---

## Demo

The demo script (`scripts/run_demo.py`) processes a real Government of Maharashtra GR for the Jal Jeevan Mission Phase II, demonstrating all 5 extended capabilities in a single run.

**Expected output:**
```
✅ PIPELINE COMPLETE

📊 Confidence Score:     0.75
🔄 Negotiation Rounds:   1
⏱  Processing Time:      ~800,000ms (CPU inference)
🤖 Models Used:          mistral:latest
📝 Compliance Verdict:   COMPLIANT → NEEDS_REVISION (Hermes refinement)
🎯 Compliance Score:     100.0/100

EXTRACTED OBLIGATIONS:
  1. All District Collectors must implement DPI by 31 March 2025
  2. CEOs of Zilla Parishads must prepare action plans within 30 days
  ...

HERMES COUNTER-ARGUMENTS:
  ↔ The draft does not address the penalty clause under Section 56
  ↔ Water Quality Testing Labs deadline (30 June 2024) not referenced
  ↔ Budget allocation (Rs. 2,500 Crores) should be cited in the draft
```

---

## Design Notes

See [`docs/design_notes.md`](docs/design_notes.md) for full rationale covering:
- Model selection
- Memory architecture
- Framework integration strategy
- Failure handling
- Scalability roadmap

---

## Evaluation Criteria Coverage

| Criterion | Implementation | Location |
|---|---|---|
| Architecture depth | 5-agent DAG with typed schemas | `src/agents/`, `src/workflow/` |
| Agentic orchestration | Praison negotiation loop | `src/orchestrator/praison.py` |
| Tool integration | 5 domain tools | `src/tools/` |
| Extended capability ≥3 | All 5 demonstrated | See above |
| Robustness | Fallback GRAnalysis, retry logic, graceful degradation | `praison.py`, `ollama_client.py` |
| Code quality | Type hints, structlog, Pydantic v2, PEP 8 | Throughout |
| Government applicability | Maharashtra GR format, official templates | `src/tools/doc_generator.py` |

---

## Running Tests

```bash
pytest tests/ -v --tb=short
```