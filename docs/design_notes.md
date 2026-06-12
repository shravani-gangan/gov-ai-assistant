# Design Notes — Government AI Multi-Agent Assistant



---

## 1. Model Selection Rationale

### Primary Model: `mistral:latest` (Mistral-7B-Instruct)

**Why Mistral-7B over larger models?**

Government document analysis is fundamentally a **structured extraction and structured generation** task, not a general knowledge task. Mistral-7B excels here because:

- **Instruction following:** The instruct fine-tune reliably produces JSON when explicitly asked, critical for our two-pass GR extraction pipeline
- **Latency:** At Q4 quantization, it fits in 6-8GB VRAM (or runs on CPU) while producing coherent government-format prose
- **Determinism:** At `temperature=0.1` with a fixed seed, outputs are reproducible — essential for audit compliance
- **Context window:** 32K tokens handles the longest Indian government circulars without chunking

**Why not GPT-4 / Claude / Gemini?**
The assignment explicitly requires local inference. No external APIs. All data stays on-premise — a hard requirement for government systems handling potentially sensitive policy documents.

### Embedding Model: `nomic-embed-text`

- Produces 768-dimensional embeddings — sufficient for semantic similarity on policy text
- Runs in ~200MB RAM — negligible overhead
- Ollama-native: same inference server, no additional process

### Model Upgrade Path (Production)
```
Current (demo):     mistral:latest (7B, Q4)
Production Tier 1:  mistral:7b-instruct-v0.3 (Q8, higher quality)
Production Tier 2:  mixtral:8x7b-instruct (MoE, near-GPT-4 quality)
Production Tier 3:  llama3:70b (highest quality, needs A100)
```

---

## 2. Memory Architecture

### Two-Tier Design

```
┌─────────────────────────────────────────────────────────┐
│                  MemoryManager                          │
│                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │   Episodic Memory    │  │    Semantic Memory       │ │
│  │   (EpisodicMemory)   │  │    (ChromaDB)            │ │
│  │                      │  │                          │ │
│  │  • In-process dict   │  │  • Persistent on disk    │ │
│  │  • Session-scoped    │  │  • Cross-session recall  │ │
│  │  • O(1) access       │  │  • Vector similarity     │ │
│  │  • LRU eviction      │  │  • Top-k retrieval       │ │
│  │  • ~500 entry cap    │  │  • nomic-embed-text       │ │
│  └──────────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Episodic Memory (Short-term)
Used for within-session state sharing between agents. For example, the Analyst stores `past_analyses` (results from ChromaDB similarity search) in episodic memory so the Drafter can reference them without re-querying.

**Implementation:** `collections.OrderedDict` with LRU eviction at 500 entries. O(1) read/write.

### Semantic Memory (Long-term)
Every completed GR analysis is persisted to ChromaDB with:
- **Key:** `gr:{sha256_hash}` — prevents duplicate storage of re-submitted documents
- **Embedding:** `{doc_type} {obligations[:5]}` — captures the semantic essence
- **Metadata:** doc_type, clause count, compliance verdict, session_id

**Purpose:** When a new GR arrives, the Analyst queries semantic memory for the top-5 most similar past analyses. These become few-shot examples for the Hermes adaptation capability, improving consistency across similar document types without retraining.

### Why SHA-256 as document key?
Government circulars are frequently re-submitted with minor OCR artifacts or formatting differences. Hashing the raw text lets us skip expensive LLM re-analysis of documents we've already processed. The hash is the foreign key linking ChromaDB entries to past session data.

---

## 3. How Hermes Agent, DeerFlow 2, and Praison AI Are Combined

### Integration Architecture

```
                    ┌─────────────────────┐
                    │   User Request      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Praison AI Layer   │◄──── Cross-agent memory
                    │  (Orchestrator)     │      Negotiation loop
                    └──────────┬──────────┘      Confidence scoring
                               │
              ┌────────────────▼────────────────┐
              │      DeerFlow 2 Engine          │◄── Dynamic re-planning
              │      (DAG Execution)            │    Conditional edges
              └────────────────┬────────────────┘    Retry with backoff
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    ┌────▼────┐           ┌────▼────┐           ┌────▼────┐
    │Analysis │           │Drafting │           │  More   │
    │  Node   │           │  Node   │           │ Nodes   │
    └─────────┘           └─────────┘           └─────────┘
         │
         │ (after DAG completes)
         │
    ┌────▼────────────────────────────────────────────┐
    │              Hermes Agent                       │◄── Meta-reasoning
    │   self_critique() → few_shot_adapt()            │    Counter-arguments
    │   narrate_audit()                               │    Audit narration
    └─────────────────────────────────────────────────┘
```

### What Each Framework Contributes

**Praison AI (Orchestration Layer)**
- Provides the "conversational agent" paradigm: agents communicate through shared state (MemoryManager) rather than direct method calls
- The negotiation loop (`_negotiation_loop`) mirrors Praison AI's multi-turn conversation pattern: each round is a "turn" where Critic and Drafter exchange structured messages
- Cross-agent memory means the Drafter in round 2 has access to what the Critic said in round 1 without re-analysis

**DeerFlow 2 (Workflow Engine)**
- Implements the visual flow DAG as a topological execution graph
- The key differentiator: `insert_node()` allows runtime modification of the DAG when ambiguities are detected, implementing "visual flow re-ordering" without restarting
- Parallel execution of independent nodes via `asyncio.gather` (used when DAG has parallel branches)
- Conditional edges via `node.condition` callable — the compliance check node only runs if a draft exists

**Hermes Agent (Meta-Reasoning)**
- Nous-Hermes-2 is specifically fine-tuned for Constitutional AI patterns (self-critique, adversarial reasoning)
- `self_critique()`: Takes the Critic's output and generates 3 counter-arguments — identifying what the Critic may have missed or gotten wrong
- `few_shot_adapt()`: Queries semantic memory for similar past documents and uses them as in-context examples to infer processing strategy for new circular types
- `narrate_audit()`: Converts the raw structured AuditTrail into formal government language — the "official internal audit log" required by the assignment

### Additional Behaviors Enabled by Combining All Three

1. **Adaptive compliance thresholds:** DeerFlow's conditional branching + Hermes's confidence adjustment = dynamic threshold adaptation based on document complexity
2. **Self-improving few-shot examples:** Praison's memory persistence + Hermes's few-shot adaptation = the system gets better at new GR types with each session, without retraining
3. **Audit-driven re-planning:** Hermes's audit narration feeds back into DeerFlow's re-planner — ambiguities surfaced in the audit can trigger additional analysis passes in subsequent requests

---

## 4. Failure Case Handling

### Case 1: LLM Timeout (CPU inference slowness)
**Trigger:** Ollama takes >300s to respond (common on CPU-only machines)  
**Handling:**
- `OllamaClient.generate()` catches `httpx.ReadTimeout` and returns `""` (empty string) after exhausting retries
- Each agent handles empty LLM responses by returning a graceful fallback (e.g., PlannerAgent returns a minimal plan, DrafterAgent returns a canned template)
- Pipeline continues — output quality degrades but the system never crashes

### Case 2: GR Extraction Failure
**Trigger:** LLM returns invalid JSON or times out during GR analysis  
**Handling:**
- `GRAnalyzerTool._parse_llm_json()` catches `JSONDecodeError` and returns `{}`
- `_coerce_gr_analysis()` in the orchestrator converts any unexpected value to a valid `GRAnalysis` with `document_type=UNKNOWN` and `raw_text_hash="fallback_*"`
- The pipeline continues with fallback data — Critic detects `INSUFFICIENT_DATA` and sets verdict accordingly

### Case 3: Ambiguous/Contradictory GR Input
**Trigger:** GR contains internally contradictory clauses (e.g., two different deadlines for the same obligation)  
**Handling:**
- GR Analyzer's LLM pass detects contradictions and populates `ambiguities_detected`
- DeerFlow engine receives `needs_replan: True` signal and logs a replan event
- Hermes's `self_critique()` surfaces these contradictions as counter-arguments
- Final output explicitly lists ambiguities in `gr_analysis.ambiguities_detected`

### Case 4: Partial Document Input (Missing Pages)
**Trigger:** PDF is incomplete or OCR extraction misses pages  
**Handling:**
- Two-pass extraction in `GRAnalyzerTool`: regex pass always succeeds on whatever text exists; LLM pass extracts what it can
- Fields that cannot be determined are `null` (not fabricated)
- `confidence` scores on each `PolicyClause` reflect extraction certainty — missing data → low confidence scores → low overall `confidence_score` in `PipelineOutput`

### Case 5: ChromaDB Connection Failure
**Trigger:** ChromaDB process not running or disk full  
**Handling:**
- `MemoryManager.store()` and `semantic_search()` wrap all ChromaDB calls in try/except
- On failure: warning logged, operation skipped
- Pipeline continues without memory persistence — stateless degradation

### Case 6: Compliance Negotiation Doesn't Converge
**Trigger:** Draft fails compliance after 3 negotiation rounds  
**Handling:**
- Loop exits with best-effort draft + final compliance score
- `compliance_report.verdict` reflects actual state (`NEEDS_REVISION` or `NON_COMPLIANT`)
- `confidence_score` is penalized via `negotiation` component of breakdown
- Hermes's counter-arguments provide specific guidance for human reviewer

---

## 5. Future Scalability Considerations

### Horizontal Scaling

**Current:** Single-process, synchronous agent chain  
**Scale path:**
```
Phase 1: Celery + Redis task queue
  → Each agent call becomes an async Celery task
  → Multiple pipeline requests processed in parallel
  → Redis stores intermediate state between tasks

Phase 2: Agent microservices
  → Each agent as a FastAPI microservice
  → Kubernetes deployment with HPA
  → Shared ChromaDB becomes a ChromaDB cluster

Phase 3: Model serving
  → vLLM or TGI for batched inference
  → GPU node pool for model serving
  → CPU nodes for orchestration only
```

### Model Quality Scaling
```
Current:  mistral:7b (demo quality)
Phase 1:  mixtral:8x7b (production quality, 48GB RAM)
Phase 2:  llama3:70b (enterprise quality, A100 GPU)
Phase 3:  Fine-tuned model on Indian government circular corpus
```

### Memory Scaling
```
Current:  Local ChromaDB (single node)
Phase 1:  ChromaDB with replication
Phase 2:  Qdrant cluster (better performance at scale)
Phase 3:  Hybrid: ChromaDB (recent) + Elasticsearch (historical) + Graph DB (policy relationships)
```

### Multi-Tenancy (Multiple Departments)
- Each department gets isolated ChromaDB collection (namespace isolation)
- Per-department compliance rule sets loaded via YAML config
- Role-based access control on the FastAPI layer
- Audit trails partitioned by department + officer ID

### Observability (Production)
```
Current:  structlog to stdout
Phase 1:  OpenTelemetry traces → Jaeger
Phase 2:  Prometheus metrics → Grafana
Phase 3:  Full LLM observability (Langfuse or Helicone self-hosted)
```

### Document Volume
- Current: Single document per request
- Phase 1: Batch processing via background tasks
- Phase 2: Document streaming for large PDFs (>50 pages)
- Phase 3: Distributed document processing pipeline (Apache Spark for corpus-level analysis)