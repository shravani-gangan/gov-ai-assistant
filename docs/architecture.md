<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Gov AI Assistant — Architecture Diagrams</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; }

  .page { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
  h1 { text-align: center; font-size: 28px; color: #60a5fa; margin-bottom: 8px; }
  .subtitle { text-align: center; color: #94a3b8; margin-bottom: 48px; font-size: 14px; }

  h2 { font-size: 18px; color: #93c5fd; margin-bottom: 20px; border-left: 3px solid #3b82f6; padding-left: 12px; }

  .diagram-section { margin-bottom: 60px; }

  /* ── System Architecture ── */
  .arch-grid {
    display: grid;
    grid-template-rows: auto auto auto auto auto;
    gap: 0;
    position: relative;
  }

  .layer {
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 4px;
    position: relative;
  }

  .layer-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 10px;
  }

  .layer-api    { background: #1e293b; border-color: #3b82f6; }
  .layer-orch   { background: #1a1f2e; border-color: #8b5cf6; }
  .layer-agents { background: #1a2230; border-color: #10b981; }
  .layer-dag    { background: #1a2520; border-color: #f59e0b; }
  .layer-tools  { background: #1a1a2e; border-color: #ec4899; }
  .layer-infra  { background: #1f1a2e; border-color: #6366f1; }

  .layer-api    .layer-label { color: #60a5fa; }
  .layer-orch   .layer-label { color: #a78bfa; }
  .layer-agents .layer-label { color: #34d399; }
  .layer-dag    .layer-label { color: #fbbf24; }
  .layer-tools  .layer-label { color: #f472b6; }
  .layer-infra  .layer-label { color: #818cf8; }

  .boxes { display: flex; gap: 10px; flex-wrap: wrap; }

  .box {
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid transparent;
  }

  .box-blue   { background: #1d4ed8; border-color: #3b82f6; color: #bfdbfe; }
  .box-purple { background: #6d28d9; border-color: #8b5cf6; color: #ede9fe; }
  .box-green  { background: #065f46; border-color: #10b981; color: #a7f3d0; }
  .box-yellow { background: #78350f; border-color: #f59e0b; color: #fde68a; }
  .box-pink   { background: #831843; border-color: #ec4899; color: #fbcfe8; }
  .box-indigo { background: #312e81; border-color: #6366f1; color: #c7d2fe; }
  .box-red    { background: #7f1d1d; border-color: #ef4444; color: #fecaca; }
  .box-teal   { background: #134e4a; border-color: #14b8a6; color: #99f6e4; }
  .box-orange { background: #7c2d12; border-color: #f97316; color: #fed7aa; }

  .arrow-down {
    text-align: center;
    color: #475569;
    font-size: 20px;
    line-height: 1;
    margin: 2px 0;
  }

  /* ── Agent Flow ── */
  .flow-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
  }

  .flow-node {
    width: 340px;
    padding: 14px 20px;
    border-radius: 10px;
    text-align: center;
    border: 1px solid;
    position: relative;
  }

  .flow-node .title { font-weight: 700; font-size: 14px; margin-bottom: 4px; }
  .flow-node .desc  { font-size: 11px; opacity: 0.75; }

  .flow-arrow {
    width: 2px;
    height: 28px;
    background: #334155;
    margin: 0 auto;
    position: relative;
  }
  .flow-arrow::after {
    content: '▼';
    position: absolute;
    bottom: -14px;
    left: 50%;
    transform: translateX(-50%);
    color: #475569;
    font-size: 12px;
  }

  .flow-split {
    display: flex;
    align-items: flex-start;
    gap: 20px;
    margin: 8px 0;
  }
  .flow-branch { display: flex; flex-direction: column; align-items: center; }
  .branch-label {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
    margin-bottom: 6px;
    font-weight: 600;
  }
  .branch-yes { background: #14532d; color: #86efac; }
  .branch-no  { background: #7f1d1d; color: #fca5a5; }

  .loop-indicator {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: #1e293b;
    border: 1px dashed #475569;
    border-radius: 8px;
    font-size: 12px;
    color: #94a3b8;
    margin: 8px 0;
  }

  /* ── Extended Capabilities ── */
  .caps-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .cap-card {
    background: #1e293b;
    border-radius: 10px;
    padding: 20px;
    border: 1px solid #334155;
  }

  .cap-number {
    font-size: 28px;
    font-weight: 900;
    opacity: 0.15;
    float: right;
    line-height: 1;
  }

  .cap-tag {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }

  .cap-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
  .cap-desc  { font-size: 12px; color: #94a3b8; line-height: 1.5; }
  .cap-file  { font-size: 11px; color: #64748b; margin-top: 8px; font-family: monospace; }

  /* ── Data Flow ── */
  .data-flow {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .data-node {
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
    border: 1px solid;
    min-width: 110px;
  }

  .data-arrow {
    color: #475569;
    font-size: 18px;
  }

  /* separator */
  .sep { border: none; border-top: 1px solid #1e293b; margin: 40px 0; }
</style>
</head>
<body>
<div class="page">
  <h1>🏛️ Government AI Multi-Agent Assistant</h1>
  <p class="subtitle">Architecture Diagrams — v1.0.0</p>

  <!-- ─── DIAGRAM 1: System Architecture ────────────────────────────────── -->
  <div class="diagram-section">
    <h2>1 · System Architecture (Layered)</h2>
    <div class="arch-grid">

      <div class="layer layer-api">
        <div class="layer-label">API Layer</div>
        <div class="boxes">
          <div class="box box-blue">FastAPI REST</div>
          <div class="box box-blue">POST /analyze/text</div>
          <div class="box box-blue">POST /analyze/pdf</div>
          <div class="box box-blue">GET /health</div>
          <div class="box box-blue">OpenAPI / Swagger</div>
        </div>
      </div>

      <div class="arrow-down">↕</div>

      <div class="layer layer-orch">
        <div class="layer-label">Praison AI Orchestration</div>
        <div class="boxes">
          <div class="box box-purple">PraisonOrchestrator</div>
          <div class="box box-purple">Cross-Agent Memory</div>
          <div class="box box-purple">Negotiation Loop (3 rounds)</div>
          <div class="box box-purple">Confidence Scoring</div>
          <div class="box box-purple">Audit Trail Compilation</div>
        </div>
      </div>

      <div class="arrow-down">↕</div>

      <div class="layer layer-agents">
        <div class="layer-label">Agent Layer (5 Agents)</div>
        <div class="boxes">
          <div class="box box-green">🗂 Planner</div>
          <div class="box box-green">🔍 Analyst</div>
          <div class="box box-green">✍️ Drafter</div>
          <div class="box box-green">⚖️ Critic</div>
          <div class="box box-red">🧠 Hermes (Meta-Reasoning)</div>
        </div>
      </div>

      <div class="arrow-down">↕</div>

      <div class="layer layer-dag">
        <div class="layer-label">DeerFlow 2 — Workflow DAG Engine</div>
        <div class="boxes">
          <div class="box box-yellow">Topological Sort</div>
          <div class="box box-yellow">Parallel Execution</div>
          <div class="box box-yellow">Dynamic Re-planning</div>
          <div class="box box-yellow">Conditional Edges</div>
          <div class="box box-yellow">Retry + Backoff</div>
          <div class="box box-yellow">WorkflowState</div>
        </div>
      </div>

      <div class="arrow-down">↕</div>

      <div class="layer layer-tools">
        <div class="layer-label">Tools Layer (5 Domain Tools)</div>
        <div class="boxes">
          <div class="box box-pink">GR Analyzer (2-pass)</div>
          <div class="box box-pink">Compliance Engine</div>
          <div class="box box-pink">Doc Comparator</div>
          <div class="box box-pink">Doc Generator</div>
          <div class="box box-pink">Schema Validator</div>
        </div>
      </div>

      <div class="arrow-down">↕</div>

      <div class="layer layer-infra">
        <div class="layer-label">Infrastructure</div>
        <div class="boxes">
          <div class="box box-indigo">Ollama (mistral:latest)</div>
          <div class="box box-indigo">nomic-embed-text</div>
          <div class="box box-teal">ChromaDB (Vector Store)</div>
          <div class="box box-teal">Episodic Memory (dict)</div>
          <div class="box box-orange">Redis (Task Queue)</div>
          <div class="box box-orange">Docker Compose</div>
        </div>
      </div>
    </div>
  </div>

  <hr class="sep">

  <!-- ─── DIAGRAM 2: Agent Interaction Flow ─────────────────────────────── -->
  <div class="diagram-section">
    <h2>2 · Agent Interaction Flow</h2>
    <div class="flow-container">

      <div class="flow-node" style="background:#1e3a5f;border-color:#3b82f6;color:#bfdbfe;width:400px">
        <div class="title">👤 Government Officer Request</div>
        <div class="desc">Text or PDF input + natural language request</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#2d1b69;border-color:#8b5cf6;color:#ddd6fe">
        <div class="title">🗂 Planner Agent</div>
        <div class="desc">Decomposes request → ExecutionPlan (SubTask DAG)</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#78350f;border-color:#f59e0b;color:#fde68a">
        <div class="title">⚡ DeerFlow 2 Engine</div>
        <div class="desc">Builds and executes topological DAG</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#831843;border-color:#ec4899;color:#fbcfe8">
        <div class="title">🔧 GR Analyzer Tool</div>
        <div class="desc">Pass 1: Regex (dates, refs) → Pass 2: LLM (semantic)</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#064e3b;border-color:#10b981;color:#a7f3d0">
        <div class="title">🔍 Analyst Agent</div>
        <div class="desc">Enriches extraction + checks semantic memory for similar GRs</div>
      </div>

      <!-- Replan split -->
      <div class="flow-split" style="margin:12px 0">
        <div class="flow-branch">
          <div class="branch-label branch-yes">✓ Clear GR</div>
          <div class="flow-node" style="background:#1a2530;border-color:#334155;color:#94a3b8;width:180px;font-size:12px">
            <div class="title">Continue</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;color:#475569;font-size:24px;padding-top:28px">⟷</div>
        <div class="flow-branch">
          <div class="branch-label branch-no">⚠ Ambiguity</div>
          <div class="flow-node" style="background:#7f1d1d;border-color:#ef4444;color:#fecaca;width:180px;font-size:12px">
            <div class="title">DeerFlow Re-plan</div>
            <div class="desc">Insert clarification node</div>
          </div>
        </div>
      </div>

      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#1e3a5f;border-color:#3b82f6;color:#bfdbfe">
        <div class="title">✍️ Drafter Agent</div>
        <div class="desc">Generates official-format government document</div>
      </div>

      <!-- Negotiation loop -->
      <div class="loop-indicator" style="width:340px">
        <span style="font-size:20px">🔄</span>
        <span><strong style="color:#60a5fa">Negotiation Loop</strong> (max 3 rounds)<br>
        Drafter ↔ Critic converge on compliant draft</span>
      </div>

      <div class="flow-node" style="background:#2d1b69;border-color:#8b5cf6;color:#ddd6fe">
        <div class="title">⚖️ Critic Agent</div>
        <div class="desc">Validates draft against GR obligations, deadlines, authority</div>
      </div>

      <div class="flow-split" style="margin:12px 0">
        <div class="flow-branch">
          <div class="branch-label branch-yes">✓ Score ≥ 75</div>
          <div class="flow-node" style="background:#064e3b;border-color:#10b981;color:#a7f3d0;width:180px;font-size:12px">
            <div class="title">Converged ✓</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;color:#475569;font-size:24px;padding-top:28px">⟷</div>
        <div class="flow-branch">
          <div class="branch-label branch-no">✗ Score &lt; 75</div>
          <div class="flow-node" style="background:#7f1d1d;border-color:#ef4444;color:#fecaca;width:180px;font-size:12px">
            <div class="title">Revise Draft</div>
            <div class="desc">Back to Drafter</div>
          </div>
        </div>
      </div>

      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#7f1d1d;border-color:#ef4444;color:#fecaca">
        <div class="title">🧠 Hermes Agent — Self-Critique</div>
        <div class="desc">Generates counter-arguments · Refines verdict · Identifies blind spots</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#134e4a;border-color:#14b8a6;color:#99f6e4">
        <div class="title">💾 Memory Persistence</div>
        <div class="desc">ChromaDB stores GR interpretation for future few-shot adaptation</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#7f1d1d;border-color:#ef4444;color:#fecaca">
        <div class="title">🧠 Hermes Agent — Audit Narration</div>
        <div class="desc">Converts AuditTrail to official government audit log language</div>
      </div>
      <div class="flow-arrow"></div>

      <div class="flow-node" style="background:#1e3a5f;border-color:#3b82f6;color:#bfdbfe;width:400px">
        <div class="title">📄 PipelineOutput</div>
        <div class="desc">Draft · GR Analysis · Compliance Report · Confidence · Audit Trail</div>
      </div>
    </div>
  </div>

  <hr class="sep">

  <!-- ─── DIAGRAM 3: Extended Capabilities ──────────────────────────────── -->
  <div class="diagram-section">
    <h2>3 · Extended Capabilities (All 5 Demonstrated)</h2>
    <div class="caps-grid">

      <div class="cap-card">
        <div class="cap-number">1</div>
        <div class="cap-tag" style="background:#78350f;color:#fde68a">DeerFlow 2</div>
        <div class="cap-title">Dynamic Workflow Re-planning</div>
        <div class="cap-desc">When the Analysis node detects ambiguities, it emits <code>needs_replan: True</code>. DeerFlow intercepts this signal, logs the replan event, and dynamically inserts clarification nodes into the live DAG without restarting execution.</div>
        <div class="cap-file">src/workflow/deerflow.py → _handle_replan()</div>
      </div>

      <div class="cap-card">
        <div class="cap-number">2</div>
        <div class="cap-tag" style="background:#7f1d1d;color:#fecaca">Hermes Agent</div>
        <div class="cap-title">Hermes-Driven Self-Critique</div>
        <div class="cap-desc">After Critic produces a verdict, Hermes runs an adversarial second pass — generating 3 counter-arguments that challenge the assessment. In the demo, Hermes correctly refined COMPLIANT → NEEDS_REVISION by identifying missed deadline references.</div>
        <div class="cap-file">src/agents/hermes.py → self_critique()</div>
      </div>

      <div class="cap-card">
        <div class="cap-number">3</div>
        <div class="cap-tag" style="background:#312e81;color:#c7d2fe">Praison AI</div>
        <div class="cap-title">Cross-Agent Long-Term Memory</div>
        <div class="cap-desc">All 5 agents share a single MemoryManager (injected via constructor). Past GR analyses are stored in ChromaDB with SHA-256 deduplication. Future sessions retrieve similar analyses as few-shot examples, improving consistency without retraining.</div>
        <div class="cap-file">src/memory/manager.py · src/orchestrator/praison.py → _persist_to_memory()</div>
      </div>

      <div class="cap-card">
        <div class="cap-number">4</div>
        <div class="cap-tag" style="background:#312e81;color:#c7d2fe">Praison AI</div>
        <div class="cap-title">Multi-Round Negotiation Loop</div>
        <div class="cap-desc">Drafter and Critic engage in structured negotiation (max 3 rounds). Critic identifies issues; Drafter revises. Loop converges when compliance score ≥ 75/100. Each round's state is accessible to both agents via shared memory.</div>
        <div class="cap-file">src/orchestrator/praison.py → _negotiation_loop()</div>
      </div>

      <div class="cap-card" style="grid-column: 1 / -1">
        <div class="cap-number">5</div>
        <div class="cap-tag" style="background:#7f1d1d;color:#fecaca">Hermes + DeerFlow</div>
        <div class="cap-title">Automated Audit Trail Generation</div>
        <div class="cap-desc">Every agent action, tool call, input/output summary, token usage, and latency is captured as a structured AuditEvent. DeerFlow's WorkflowState accumulates events across the DAG. Hermes narrates the full trace into official government audit log language — formatted as an internal memorandum.</div>
        <div class="cap-file">src/audit/trail.py · src/agents/hermes.py → narrate_audit_trail()</div>
      </div>
    </div>
  </div>

  <hr class="sep">

  <!-- ─── DIAGRAM 4: Data Flow ───────────────────────────────────────────── -->
  <div class="diagram-section">
    <h2>4 · Pipeline Data Flow</h2>
    <div class="data-flow">
      <div class="data-node" style="background:#1e3a5f;border-color:#3b82f6;color:#bfdbfe">
        📄 Raw Input<br><small>PDF / Text</small>
      </div>
      <div class="data-arrow">→</div>
      <div class="data-node" style="background:#831843;border-color:#ec4899;color:#fbcfe8">
        🔧 GRAnalysis<br><small>Pydantic model</small>
      </div>
      <div class="data-arrow">→</div>
      <div class="data-node" style="background:#064e3b;border-color:#10b981;color:#a7f3d0">
        ✍️ Draft<br><small>string</small>
      </div>
      <div class="data-arrow">→</div>
      <div class="data-node" style="background:#2d1b69;border-color:#8b5cf6;color:#ddd6fe">
        ⚖️ Compliance<br><small>Report</small>
      </div>
      <div class="data-arrow">→</div>
      <div class="data-node" style="background:#7f1d1d;border-color:#ef4444;color:#fecaca">
        🧠 Hermes<br><small>Enriched Report</small>
      </div>
      <div class="data-arrow">→</div>
      <div class="data-node" style="background:#134e4a;border-color:#14b8a6;color:#99f6e4">
        📊 Pipeline<br><small>Output JSON</small>
      </div>
    </div>

    <div style="margin-top:32px;background:#1e293b;border-radius:10px;padding:20px;border:1px solid #334155">
      <div style="font-size:13px;color:#94a3b8;font-weight:600;margin-bottom:12px">PipelineOutput — Final Envelope</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;font-size:12px">
        <div style="background:#0f172a;padding:10px;border-radius:6px;border-left:3px solid #3b82f6">
          <div style="color:#60a5fa;font-weight:700">human_readable_draft</div>
          <div style="color:#64748b;margin-top:4px">Official format document</div>
        </div>
        <div style="background:#0f172a;padding:10px;border-radius:6px;border-left:3px solid #ec4899">
          <div style="color:#f472b6;font-weight:700">gr_analysis</div>
          <div style="color:#64748b;margin-top:4px">Clauses · Obligations · Deadlines</div>
        </div>
        <div style="background:#0f172a;padding:10px;border-radius:6px;border-left:3px solid #8b5cf6">
          <div style="color:#a78bfa;font-weight:700">compliance_report</div>
          <div style="color:#64748b;margin-top:4px">Verdict · Score · Issues · Counter-args</div>
        </div>
        <div style="background:#0f172a;padding:10px;border-radius:6px;border-left:3px solid #10b981">
          <div style="color:#34d399;font-weight:700">confidence_score</div>
          <div style="color:#64748b;margin-top:4px">Multi-factor 0.0–1.0</div>
        </div>
        <div style="background:#0f172a;padding:10px;border-radius:6px;border-left:3px solid #f59e0b">
          <div style="color:#fbbf24;font-weight:700">audit_trail</div>
          <div style="color:#64748b;margin-top:4px">Full agent decision trace</div>
        </div>
        <div style="background:#0f172a;padding:10px;border-radius:6px;border-left:3px solid #14b8a6">
          <div style="color:#2dd4bf;font-weight:700">reasoning_steps</div>
          <div style="color:#64748b;margin-top:4px">Step-by-step execution log</div>
        </div>
      </div>
    </div>
  </div>

  <hr class="sep">
  <div style="text-align:center;color:#475569;font-size:12px;padding-bottom:20px">
    Government AI Multi-Agent Assistant · Architecture v1.0.0 · June 2026
  </div>
</div>
</body>
</html>