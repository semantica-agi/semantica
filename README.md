<div align="center">

<img src="Semantica Logo.png" alt="Semantica Logo" width="420"/>

**The Accountability and Context Layer for AI · Context Graphs · Decision Intelligence · Full Provenance**

[![Website](https://img.shields.io/badge/Website-getsemantica.ai-0066CC?logo=googlechrome&logoColor=white)](https://getsemantica.ai/)
[![Docs](https://img.shields.io/badge/Docs-docs.getsemantica.ai-0099FF?logo=readthedocs&logoColor=white)](https://docs.getsemantica.ai/)
[![PyPI](https://img.shields.io/pypi/v/semantica.svg)](https://pypi.org/project/semantica/)
[![Version](https://img.shields.io/badge/version-0.5.0-brightgreen.svg)](https://github.com/Hawksight-AI/semantica/releases/tag/v0.5.0)
[![Total Downloads](https://static.pepy.tech/badge/semantica)](https://pepy.tech/project/semantica)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/Hawksight-AI/semantica/workflows/CI/badge.svg)](https://github.com/Hawksight-AI/semantica/actions)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2?logo=discord&logoColor=white)](https://discord.gg/sV34vps5hH)
[![X](https://img.shields.io/badge/X-Follow%20Semantica-black?logo=x&logoColor=white)](https://x.com/BuildSemantica)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Plugin-FF3B30?logo=github&logoColor=white)](https://openclaw.ai)

**[Website](https://getsemantica.ai/)** · **[Docs](https://docs.getsemantica.ai/)** · **[Discord](https://discord.gg/sV34vps5hH)** · **[Changelog](CHANGELOG.md)**


⭐ **Star us if this solves your problem** · 🍴 Fork us · 💬 [Join our Discord](https://discord.gg/sV34vps5hH) · 🐦 [Follow on X](https://x.com/BuildSemantica)

> **Most AI agents act without a trail. Semantica adds the layer your stack is missing: structured context graphs, auditable decision records, and full provenance from every output back to its source — so your AI isn't just powerful, it's accountable.**

🌍 [🇺🇸 English](https://readme-i18n.com/Hawksight-AI/semantica?lang=en) · [🇩🇪 Deutsch](https://readme-i18n.com/Hawksight-AI/semantica?lang=de) · [🇫🇷 Français](https://readme-i18n.com/Hawksight-AI/semantica?lang=fr) · [🇪🇸 Español](https://readme-i18n.com/Hawksight-AI/semantica?lang=es) · [🇮🇹 Italiano](https://readme-i18n.com/Hawksight-AI/semantica?lang=it) · [🇵🇹 Português](https://readme-i18n.com/Hawksight-AI/semantica?lang=pt) · [🇸🇦 العربية](https://readme-i18n.com/Hawksight-AI/semantica?lang=ar) · [🇵🇰 اردو](https://readme-i18n.com/Hawksight-AI/semantica?lang=ur) · [🇮🇳 हिन्दी](https://readme-i18n.com/Hawksight-AI/semantica?lang=hi) · [🇨🇳 中文](https://readme-i18n.com/Hawksight-AI/semantica?lang=zh) · [🇯🇵 日本語](https://readme-i18n.com/Hawksight-AI/semantica?lang=ja) · [🇰🇷 한국어](https://readme-i18n.com/Hawksight-AI/semantica?lang=ko)

</div>

---

## The Problem

AI agents today are powerful but not trustworthy:

- ❌ **No memory structure** — agents store embeddings, not meaning. There's no way to ask *why* something was recalled.
- ❌ **No decision trail** — agents act continuously but record nothing. When something breaks, there's no history to audit.
- ❌ **No provenance** — outputs can't be traced back to source facts. In regulated industries, this is a hard compliance blocker.
- ❌ **No reasoning transparency** — black-box answers with zero explanation of how a conclusion was reached.
- ❌ **No conflict detection** — contradictory facts silently coexist in vector stores, producing unpredictable outputs.

## The Solution

Semantica is the **context and intelligence layer** you add on top of your existing AI stack:

- ✅ **Context Graphs** — structured, queryable graph of everything your agent knows, decides, and reasons about
- ✅ **Decision Intelligence** — every decision tracked as a first-class object with causal links, precedent search, and impact analysis
- ✅ **Full Provenance** — every fact links back to its source. W3C PROV-O compliant.
- ✅ **Reasoning Engines** — forward chaining, Rete, deductive, abductive, SPARQL. Explainable paths, not black boxes.
- ✅ **Quality & Deduplication** — conflict detection, entity resolution, and pipeline validation built in

> Works alongside **Agno** and any LLM. LangChain, LangGraph, CrewAI, and more coming soon.

```bash
pip install semantica
```

---

## 🚀 Quick Start

```python
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)

# Every decision is a first-class, queryable object
loan_id = graph.record_decision(
    category="loan_approval",
    scenario="Mortgage — 780 credit score, 28% DTI",
    reasoning="Strong credit history, stable 8-year income, low DTI",
    outcome="approved",
    confidence=0.95,
)
rate_id = graph.record_decision(
    category="interest_rate",
    scenario="Set rate for approved mortgage",
    outcome="rate_set_6.2pct",
    confidence=0.98,
)

# Build an auditable causal chain
graph.add_causal_relationship(loan_id, rate_id, relationship_type="enables")

# Answer "why did this happen?" instantly
chain      = graph.trace_decision_chain(loan_id)
similar    = graph.find_similar_decisions("mortgage approval", max_results=5)
impact     = graph.analyze_decision_impact(loan_id)
compliance = graph.check_decision_rules({"category": "loan_approval", "confidence": 0.95})
```

---

## 🆕 What's New in v0.5.0

**Released May 11, 2026** · [Full Release Notes](RELEASE_NOTES.md) · [Changelog](CHANGELOG.md)

### 📐 Distance Intelligence

- **10x+ embedding cache** — per-session revision-based caching with thread-safe invalidation
- **Distance Matrix API** — N×N semantic distance calculations (upper-triangle mirrored, capped at 200 nodes)
- **Semantic Neighborhood Search** — `get_neighbors()` blends graph proximity with semantic score
- **5 new API endpoints** — `/distance-matrix`, `/semantic-neighborhood`, `/causal-distance`, `/temporal/distance-history`, `/export/distance-enriched`
- **Explorer UI** — Ego Mode with BFS depth-of-field fading (depth slider 1–8), Structural/Semantic overlays, Heatmap (green→red by hop), Path inspector with distance band chips
- **Bidirectional path finding** — `directed=false` on BFS and Dijkstra; `PathResponse` gains `hop_count` and `distance_band` (direct/near/mid-range/distant)

### 🔷 Complete Ontology Hub Suite

- **Alignments Tab** — cross-ontology alignment authoring; ML confidence scoring (0.4×label + 0.6×TF-IDF); one-click accept
- **Health Dashboard** — 5-dimension quality scoring (Completeness, Consistency, SHACL, Alignment, Documentation); downloadable JSON report
- **SHACL Studio** — interactive shape authoring with Monaco editor and custom Turtle syntax highlighting
- **Visual Ontology Editor** — drag-and-drop canvas; context menus for rename, add super/subclass, SKOS metadata; edits staged as diffs — nothing commits until published
- **Versions & Proposals Tab** — version timeline, proposal review, SHACL pre-validation, side-by-side diff
- **Ontology Registry** — full CRUD with status/format badges, live search, filter pills (All/OWL/SKOS/Internal/External)
- **Ontology Loader** — URL import with preview, file upload (`.ttl/.rdf/.owl/.nt/.jsonld/.n3`), create from scratch/data/text
- **Entity Search Panel** — 320 ms debounced search across all loaded ontologies with type filters
- **SKOS Vocabulary Manager** — hierarchical concept browser with recursive tree and full SKOS annotation detail
- **16 new backend endpoints** under `/api/ontology`

### 📦 More in This Release

- **Parquet Ingestion** — `ParquetIngestor` with PyArrow; partitioned directory, selective columns, Hive-style partition discovery · `pip install semantica[ingest-parquet]`
- **O(log n) Indexed Search** — inverted index with exact/token/prefix tiers; 118k nodes: 24ms → 0.004ms
- **DuplicateDetector result limiting** — prevents a single entity from flooding output and gives callers precise control over ranking and thresholds. Four new params: `max_results` (global cap), `top_k_per_entity` (per-entity quota, OR semantics so high-quality pairs aren't silently dropped), `min_similarity` (extra floor `[0.0, 1.0]`), `sort_by` (`"confidence"` or `"similarity_score"`). All validated at construction; invalid values raise `ValueError`.
- **ConflictDetector unified API** — fixes `AttributeError` when calling `detect_conflicts()` with `method=` or `property_name=` kwargs and gives full control over conflict scope. Single consistent signature with `method=` choosing strategy: `"all"` · `"value"` · `"property"` · `"type"` · `"relationship"` · `"temporal"` · `"logical"` · `"entity"` — unknown values raise `ValueError`.
- **DeepSeek via OpenAI SDK** — `OpenAIProvider` rewritten via `openai.OpenAI(base_url=...)` replacing the defunct `deepseek` package

### 🔒 Security & Fixes

- **12 vulnerabilities fixed** — eval injection (CWE-95), pickle deserialization (CWE-502), SQL injection (CWE-89), XXE (CWE-611), SSRF, prompt injection (CWE-1336), ReDoS (CWE-1333), path traversal (CWE-22)
- **Windows** — `semantica[all]` no longer pulls `faiss-gpu`; `UnicodeEncodeError` on cp1252 consoles fixed
- **Circular import** in `semantic_extract` fixed; `TripleExtractor` alias added for backward compatibility
- **Lazy-load ingest backends** — core imports no longer fail when optional packages are absent

---

## 📅 Previous Releases

### v0.4.0 — Temporal Intelligence & Ontology

- **Temporal GraphRAG** — retrieve knowledge as it existed at any past point; zero LLM calls
- **Allen Interval Algebra** — 13 deterministic interval relations; gap detection, coverage, cycle analysis
- **Point-in-time Query Engine** — consistent graph snapshots at any timestamp with a built-in consistency validator
- **TemporalNormalizer** — converts ISO 8601, relative phrases ("Q1 2024"), and 13 domain maps to UTC; zero LLM calls
- **Bi-temporal Provenance** — every record stamped with transaction time; OWL-Time RDF export
- **SKOS Vocabulary Management** — add concepts with labels, hierarchy, definitions; SPARQL-backed search; REST API
- **SHACL Constraints** — auto-derive data contract shapes from any ontology; three strictness tiers; CI-ready validation
- **ContextGraph pagination** — O(N) → O(limit); Ollama remote support; API key logging removed

### v0.3.0 — First Stable Release

First `Production/Stable` release on PyPI — the foundation everything builds on.

- **Context Graphs** · **Decision Intelligence** · **KG Algorithms** (PageRank, Louvain, Node2Vec, link prediction)
- **Deduplication v2** — 63.6% faster candidate generation; semantic dedup 6.98x faster
- **Delta Processing** — SPARQL-based incremental diff, `delta_mode` pipelines, snapshot versioning
- **Export** — Parquet (Spark/BigQuery/Databricks ready), ArangoDB AQL, RDF format aliases
- **Graph Backends** — Apache AGE, AWS Neptune, FalkorDB, PgVector

→ [Full changelog](CHANGELOG.md) · [Release notes](RELEASE_NOTES.md)

---

## 🔌 Works With Every AI Tool

Semantica ships **native plugin bundles** for Claude Code, Cursor, and Codex, an **MCP server** for Windsurf, Cline, Continue, VS Code, Claude Desktop, and OpenClaw, and a **REST API** (109 endpoints, FastAPI, port 8000) for any other tool.

<table>

<tr>
<th colspan="3" align="left">🔌 Native Plugin Bundle</th>
<th colspan="5" align="left">⚡ MCP Server + Plugin</th>
</tr>
<tr>
<td align="center" width="12.5%">
<a href="https://claude.com/product/claude-code"><img src="https://github.com/anthropics.png?size=120" alt="Claude Code" width="48" height="48" /></a><br/>
<strong>Claude Code</strong><br/>
<sub>17 skills · 3 agents · hooks</sub>
</td>
<td align="center" width="12.5%">
<a href="https://cursor.com"><img src="https://www.freelogovectors.net/wp-content/uploads/2025/06/cursor-logo-freelogovectors.net_.png" alt="Cursor" width="48" height="48" /></a><br/>
<strong>Cursor</strong><br/>
<sub>17 skills · 3 agents</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/openai/codex"><img src="https://github.com/openai.png?size=120" alt="Codex CLI" width="48" height="48" /></a><br/>
<strong>Codex CLI</strong><br/>
<sub>17 skills · 3 agents</sub>
</td>
<td align="center" width="12.5%">
<a href="https://windsurf.com"><img src="https://exafunction.github.io/public/brand/windsurf-black-symbol.svg" alt="Windsurf" width="48" height="48" /></a><br/>
<strong>Windsurf</strong><br/>
<sub><a href="plugins/.windsurf-plugin/">plugin</a></sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/cline/cline"><img src="https://github.com/cline.png?size=120" alt="Cline" width="48" height="48" /></a><br/>
<strong>Cline</strong><br/>
<sub><a href="plugins/.cline-plugin/">plugin</a></sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/continuedev/continue"><img src="https://github.com/continuedev.png?size=120" alt="Continue" width="48" height="48" /></a><br/>
<strong>Continue</strong><br/>
<sub><a href="plugins/.continue-plugin/">plugin</a></sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/microsoft/vscode"><img src="https://github.com/microsoft.png?size=120" alt="VS Code" width="48" height="48" /></a><br/>
<strong>VS Code</strong><br/>
<sub><a href="plugins/.vscode-plugin/">plugin</a></sub>
</td>
<td align="center" width="12.5%">
<a href="integrations/openclaw/"><img src="https://github.com/openclaw.png?size=120" alt="OpenClaw" width="48" height="48" /></a><br/>
<strong>OpenClaw</strong><br/>
<sub>MCP + <a href="integrations/openclaw/">plugin</a></sub>
</td>
</tr>

<tr>
<th colspan="1" align="left">☁️ MCP Server</th>
<th colspan="7" align="left">🌐 REST API</th>
</tr>
<tr>
<td align="center" width="12.5%">
<a href="https://claude.ai/download"><img src="https://github.com/anthropics.png?size=120" alt="Claude Desktop" width="48" height="48" /></a><br/>
<strong>Claude Desktop</strong><br/>
<sub>MCP server</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/features/copilot"><img src="https://github.com/github.png?size=120" alt="GitHub Copilot" width="48" height="48" /></a><br/>
<strong>GitHub Copilot</strong><br/>
<sub>REST API</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/RooCodeInc/Roo-Code"><img src="https://github.com/RooCodeInc.png?size=120" alt="Roo Code" width="48" height="48" /></a><br/>
<strong>Roo Code</strong><br/>
<sub>REST API</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/block/goose"><img src="https://github.com/block.png?size=120" alt="Goose" width="48" height="48" /></a><br/>
<strong>Goose</strong><br/>
<sub>REST API</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/Kilo-Org/kilocode"><img src="https://github.com/Kilo-Org.png?size=120" alt="Kilo Code" width="48" height="48" /></a><br/>
<strong>Kilo Code</strong><br/>
<sub>REST API</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/Aider-AI/aider"><img src="https://github.com/Aider-AI.png?size=120" alt="Aider" width="48" height="48" /></a><br/>
<strong>Aider</strong><br/>
<sub>REST API</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/aws/amazon-q-developer-cli"><img src="https://github.com/aws.png?size=120" alt="Amazon Q" width="48" height="48" /></a><br/>
<strong>Amazon Q</strong><br/>
<sub>REST API</sub>
</td>
<td align="center" width="12.5%">
<a href="https://zed.dev"><img src="https://github.com/zed-industries.png?size=120" alt="Zed" width="48" height="48" /></a><br/>
<strong>Zed</strong><br/>
<sub>REST API</sub>
</td>
</tr>

<tr>
<th colspan="8" align="left">🔧 Any Tool</th>
</tr>
<tr>
<td align="center" colspan="8">
<img src="https://img.shields.io/badge/109-endpoints-1f6feb?style=flat-square" alt="REST API" /><br/>
<strong>Any agent</strong><br/>
<sub>109 REST endpoints · FastAPI · port 8000</sub>
</td>
</tr>

</table>

### Agentic Frameworks

<table>
<tr>
<th colspan="8" align="left">✅ Supported</th>
</tr>
<tr>
<td align="center" width="12.5%">
<a href="https://github.com/agno-agi/agno"><img src="https://github.com/agno-agi.png?size=120" alt="Agno" width="48" height="48" /></a><br/>
<strong>Agno</strong><br/>
<sub>First-class · <code>pip install semantica[agno]</code></sub>
</td>
</tr>
<tr>
<th colspan="8" align="left">🔜 Coming Soon</th>
</tr>
<tr>
<td align="center" width="12.5%">
<a href="https://github.com/langchain-ai/langchain"><img src="https://github.com/langchain-ai.png?size=120" alt="LangChain" width="48" height="48" /></a><br/>
<strong>LangChain</strong><br/>
<sub>Coming soon</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/langchain-ai/langgraph"><img src="https://github.com/langchain-ai.png?size=120" alt="LangGraph" width="48" height="48" /></a><br/>
<strong>LangGraph</strong><br/>
<sub>Coming soon</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/crewAIInc/crewAI"><img src="https://github.com/crewAIInc.png?size=120" alt="CrewAI" width="48" height="48" /></a><br/>
<strong>CrewAI</strong><br/>
<sub>Coming soon</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/run-llama/llama_index"><img src="https://github.com/run-llama.png?size=120" alt="LlamaIndex" width="48" height="48" /></a><br/>
<strong>LlamaIndex</strong><br/>
<sub>Coming soon</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/microsoft/autogen"><img src="https://github.com/microsoft.png?size=120" alt="AutoGen" width="48" height="48" /></a><br/>
<strong>AutoGen</strong><br/>
<sub>Coming soon</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/openai/openai-agents-python"><img src="https://github.com/openai.png?size=120" alt="OpenAI Agents SDK" width="48" height="48" /></a><br/>
<strong>OpenAI Agents</strong><br/>
<sub>Coming soon</sub>
</td>
<td align="center" width="12.5%">
<a href="https://github.com/google/adk-python"><img src="https://github.com/google.png?size=120" alt="Google ADK" width="48" height="48" /></a><br/>
<strong>Google ADK</strong><br/>
<sub>Coming soon</sub>
</td>
</tr>
</table>

### Agno — First-Class Integration · `pip install semantica[agno]`

Five integration modules in [`integrations/agno/`](integrations/agno/):

| Class | What it does |
|---|---|
| `AgnoContextStore` | Graph-backed agent memory |
| `AgnoKnowledgeGraph` | Implements Agno's `AgentKnowledge` protocol; full extraction pipeline |
| `AgnoDecisionKit` | 6 decision-intelligence tools for Agno agents |
| `AgnoKGToolkit` | 7 KG pipeline tools (build, query, enrich, export) |
| `AgnoSharedContext` | Shared context graph for multi-agent team coordination |

### Plugin Bundles

| Bundle | Directory | Tools |
|---|---|---|
| Claude Code | [`plugins/.claude-plugin/`](plugins/.claude-plugin/) | 17 skills · 3 agents · hooks |
| Cursor | [`plugins/.cursor-plugin/`](plugins/.cursor-plugin/) | 17 skills · 3 agents · hooks |
| Codex CLI | [`plugins/.codex-plugin/`](plugins/.codex-plugin/) | 17 skills · 3 agents |
| Windsurf | [`plugins/.windsurf-plugin/`](plugins/.windsurf-plugin/) | 17 skills · 3 agents · MCP config |
| Cline | [`plugins/.cline-plugin/`](plugins/.cline-plugin/) | 17 skills · 3 agents · MCP config |
| Continue | [`plugins/.continue-plugin/`](plugins/.continue-plugin/) | 17 skills · 3 agents · MCP config |
| VS Code | [`plugins/.vscode-plugin/`](plugins/.vscode-plugin/) | 17 skills · 3 agents · MCP config |
| OpenClaw | [`plugins/.openclaw-plugin/`](plugins/.openclaw-plugin/) | 17 skills · 3 agents · MCP config |

**17 domain skills:** `extract` · `ingest` · `query` · `ontology` · `validate` · `deduplicate` · `embed` · `reason` · `decision` · `causal` · `temporal` · `provenance` · `policy` · `explain` · `export` · `change` · `visualize`

**3 specialized agents:** `kg-assistant` · `decision-advisor` · `explainability`

**Hooks** (`plugins/hooks/hooks.json`) — `PreToolUse` / `PostToolUse` matchers for syntax validation and automated warnings. → [`plugins/.claude-plugin/README.md`](plugins/.claude-plugin/README.md)

### MCP Server

```bash
python -m semantica.mcp_server
```

```json
{
  "mcpServers": {
    "semantica": { "command": "python", "args": ["-m", "semantica.mcp_server"] }
  }
}
```

**12 tools:** `extract_entities` · `extract_relations` · `record_decision` · `query_decisions` · `find_precedents` · `get_causal_chain` · `add_entity` · `add_relationship` · `run_reasoning` · `get_graph_analytics` · `export_graph` · `get_graph_summary`

**3 resources:** `semantica://graph/summary` · `semantica://decisions/list` · `semantica://schema/info`

### MCP Client (Ingest from any MCP server)

```python
from semantica.ingest import MCPClient

client    = MCPClient("http://your-mcp-server:8080")
resources = client.list_resources()
data      = client.read_resource("resource://your-data")
```

Supported schemes: `http://` · `https://` · `mcp://` · `sse://` · JSON-RPC · auth · dynamic capability discovery

---

## 🖥️ Knowledge Explorer

A real-time visual interface under [`explorer/`](explorer/) — React 19 + Sigma.js.

| Workspace | What you can do |
|---|---|
| **Knowledge Graph** | Pan, zoom, and inspect a live graph canvas with ForceAtlas2 layout |
| **Timeline** | Scrub through temporal events and watch the graph evolve |
| **Decisions** | Browse the causal chain behind every recorded decision |
| **Registry** | Live audit log of every graph mutation — add-node, add-edge, merge, delete |
| **Entity Resolution** | Review and merge duplicates detected by the deduplication engine |
| **KG Overview** | Aggregate stats, community breakdown, centrality heatmap |
| **Ontology** | SKOS/OWL vocabulary hierarchy and auto-generated schema summary |

```bash
python -m semantica.server        # Terminal 1 — backend (port 8000)
cd explorer && npm install && npm run dev  # Terminal 2 — UI
```

Open **http://localhost:5173** — all `/api` and `/ws` traffic proxied by Vite, no CORS config needed. → [`explorer/README.md`](explorer/README.md)

---

## ✨ Features

| Capability | Highlights |
|---|---|
| **Context Graphs** | Structured, queryable graph of entities, decisions, and relationships; causal links; cross-graph navigation |
| **Decision Intelligence** | `record_decision()`, `trace_decision_chain()`, `find_similar_decisions()`, `analyze_decision_impact()`, `check_decision_rules()` |
| **Temporal Intelligence** | Point-in-time snapshots, Allen interval algebra, `TemporalNormalizer`, bi-temporal provenance, decision validity windows |
| **Semantic Extraction** | NER, relation extraction, triplet generation, temporal bounds; deduplication v2 up to **6.98x faster** |
| **Reasoning Engines** | Forward chaining, Rete network, deductive, abductive, SPARQL, Datalog — explainable output |
| **Provenance** | W3C PROV-O compliant; every fact traced to source; audit log export in JSON/CSV; OWL-Time RDF export |
| **Ontology & SHACL** | Auto-generate OWL ontologies; import OWL/RDF/Turtle/JSON-LD; auto-derive SHACL shapes; SKOS vocabularies |
| **Vector Store** | FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory; hybrid + filtered search |
| **Pipeline** | `PipelineBuilder` with stage chaining, parallel workers, validation, and retry policies |
| **Graph Databases** | Neo4j, FalkorDB, Apache AGE, AWS Neptune |
| **LLM Providers** | 100+ models via LiteLLM — OpenAI, Anthropic, Cohere, Mistral, Ollama, Groq, Azure, Bedrock, and more |

---

## 💻 Code Examples

### Temporal GraphRAG

```python
from semantica.kg import TemporalQueryRewriter, TemporalNormalizer
from semantica.context import TemporalGraphRetriever
from datetime import datetime, timezone

# Parse temporal intent from natural language — zero LLM calls
rewriter = TemporalQueryRewriter()
result   = rewriter.rewrite("What decisions were made before the 2024 merger?")
# result.temporal_intent → "before"
# result.at_time         → datetime(2024, ..., tzinfo=UTC)

retriever = TemporalGraphRetriever(
    base_retriever=your_retriever,
    at_time=datetime(2024, 3, 1, tzinfo=timezone.utc),
)
ctx = retriever.retrieve("supplier approval decisions")

# Normalize any date expression to UTC — zero LLM calls
start, end = TemporalNormalizer().normalize("Q1 2024")
# → (datetime(2024, 1, 1, UTC), datetime(2024, 3, 31, UTC))
```

### Semantic Extraction

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor, TripletExtractor
from semantica.semantic_extract.methods import extract_relations_llm

text = "OpenAI released GPT-4 in March 2023. Microsoft integrated it into Azure."

entities  = NERExtractor().extract_entities(text)
relations = RelationExtractor().extract_relations(text, entities=entities)
triplets  = TripletExtractor().extract_triplets(text)

# With temporal bounds — LLM annotates each relation with validity window
relations_temporal = extract_relations_llm(
    text, entities, provider="openai", extract_temporal_bounds=True
)
```

### Reasoning

```python
from semantica.reasoning import Reasoner, ReteEngine, Rule, Fact, RuleType

# Forward chaining
reasoner = Reasoner()
reasoner.add_rule("IF Person(?x) THEN Mortal(?x)")
results  = reasoner.infer_facts(["Person(Socrates)"])  # → ["Mortal(Socrates)"]

# High-throughput Rete network
rete = ReteEngine()
rete.build_network([Rule(
    rule_id="r1", name="flag_high_risk",
    conditions=[
        {"field": "amount",  "operator": ">",  "value": 10000},
        {"field": "country", "operator": "in", "value": ["IR", "KP", "SY"]},
    ],
    conclusion="flag_for_compliance_review",
    rule_type=RuleType.IMPLICATION,
)])
rete.add_fact(Fact("f1", "transaction", [{"amount": 15000, "country": "IR"}]))
matches = rete.match_patterns()
```

---

## 📦 Modules

| Module | What it provides |
|---|---|
| `semantica.context` | Context graphs, agent memory, decision tracking, causal analysis, precedent search, policy engine |
| `semantica.kg` | KG construction, graph algorithms, centrality, community detection, embeddings, link prediction, provenance |
| `semantica.semantic_extract` | NER, relation extraction, event extraction, coreference, triplet generation, LLM-enhanced extraction |
| `semantica.reasoning` | Forward chaining, Rete, deductive, abductive, SPARQL, Datalog reasoning |
| `semantica.vector_store` | FAISS, Pinecone, Weaviate, Qdrant, Milvus, PgVector, in-memory; hybrid & filtered search |
| `semantica.export` | RDF (Turtle/JSON-LD/N-Triples/XML), Parquet, ArangoDB AQL, OWL, SHACL, graph formats |
| `semantica.ingest` | Files (PDF, DOCX, CSV, HTML), web crawl, databases, Snowflake, MCP, email, repositories, Parquet |
| `semantica.ontology` | OWL auto-generation, import, validation, SHACL shape generation & validation, SKOS vocabulary management |
| `semantica.pipeline` | Pipeline DSL, parallel workers, validation, retry policies, failure handling |
| `semantica.graph_store` | Neo4j, FalkorDB, Apache AGE, Amazon Neptune; Cypher queries |
| `semantica.embeddings` | Sentence-Transformers, FastEmbed, OpenAI, BGE; similarity calculation |
| `semantica.deduplication` | Entity deduplication — blocking, hybrid, semantic strategies; result limiting |
| `semantica.provenance` | W3C PROV-O lineage, revision history, audit log export |
| `semantica.parse` | PDF, DOCX, PPTX, HTML, code, email, media with OCR (Docling integration) |
| `semantica.split` | Recursive, semantic, entity-aware, graph-based, ontology-aware chunking |
| `semantica.conflicts` | Multi-source conflict detection with resolution strategies |
| `semantica.change_management` | Version storage, checksums, audit trails, compliance support |
| `semantica.triplet_store` | Blazegraph, Jena, RDF4J; SPARQL queries and bulk loading |
| `semantica.visualization` | KG, ontology, embedding, and temporal graph visualization |
| [`explorer/`](explorer/) | React 19 + Sigma.js browser UI — graph canvas, decisions, entity resolution, ontology |
| `semantica.llms` | Groq, OpenAI, Novita AI, HuggingFace, LiteLLM |

---

## 🛠️ Installation

```bash
pip install semantica           # core
pip install semantica[all]      # everything

# pick what you need
pip install semantica[agno]
pip install semantica[vectorstore-pinecone]
pip install semantica[vectorstore-weaviate]
pip install semantica[vectorstore-qdrant]
pip install semantica[vectorstore-milvus]
pip install semantica[vectorstore-pgvector]
pip install semantica[db-snowflake]
pip install semantica[ingest-parquet]

# from source
git clone https://github.com/Hawksight-AI/semantica.git
cd semantica && pip install -e ".[dev]" && pytest tests/
```

---

## 🏆 Built for High-Stakes Domains

> Every answer explainable. Every decision auditable. Every fact traceable.

- 🏥 **Healthcare** — clinical decision support, drug interaction graphs, patient safety audit trails
- 💰 **Finance** — fraud detection, regulatory compliance, risk knowledge graphs
- ⚖️ **Legal** — evidence-backed research, contract analysis, case law reasoning
- 🔒 **Cybersecurity** — threat attribution, incident response timelines, provenance tracking
- 🏛️ **Government** — policy decision records, classified information governance
- 🏭 **Infrastructure** — power grids, transportation networks, operational decision logs
- 🤖 **Autonomous Systems** — decision logs, safety validation, explainable AI

---

## 🏢 Enterprise Support

**[Website](https://getsemantica.ai/)** — enterprise solutions, private cloud deployment, custom domain implementations, professional services.

---

## 🤝 Community & Support

| | |
|---|---|
| 💬 **Discord** | [discord.gg/sV34vps5hH](https://discord.gg/sV34vps5hH) — real-time help and showcases |
| 💡 **GitHub Discussions** | [Q&A and feature requests](https://github.com/Hawksight-AI/semantica/discussions) |
| 🐛 **GitHub Issues** | [Bug reports](https://github.com/Hawksight-AI/semantica/issues) |
| 📄 **Documentation** | [docs.getsemantica.ai](https://docs.getsemantica.ai/) |
| 🍳 **Cookbook** | [Runnable notebooks and recipes](https://github.com/Hawksight-AI/semantica/tree/main/cookbook) |
| 📋 **Changelog** | [CHANGELOG.md](CHANGELOG.md) · [Release Notes](RELEASE_NOTES.md) |

## 🤝 Contributing

All contributions welcome — bug fixes, features, tests, and docs.

1. Fork the repo and create a branch
2. `pip install -e ".[dev]"`
3. Write tests alongside your changes
4. Open a PR and tag `@KaifAhmad1` for review

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

<div align="center">

MIT License · Built by [Hawksight AI](https://github.com/Hawksight-AI) · [⭐ Star on GitHub](https://github.com/Hawksight-AI/semantica)

[GitHub](https://github.com/Hawksight-AI/semantica) · [Discord](https://discord.gg/sV34vps5hH) · [X / Twitter](https://x.com/BuildSemantica) · [Website](https://getsemantica.ai/)

</div>
