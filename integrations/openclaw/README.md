# Semantica × OpenClaw Integration

Connect [OpenClaw](https://openclaw.ai) — the open-source personal AI agent — to Semantica's full knowledge-graph and decision-intelligence stack.

Two integration paths are available:

| Path | When to use |
|---|---|
| **MCP (recommended)** | OpenClaw Gateway is running; zero extra code needed |
| **REST / native tool** | Embedding Semantica directly in a SOUL.md agent config |

---

## Path 1 — MCP Server (recommended)

### 1. Start the Semantica MCP server

```bash
python -m semantica.mcp_server
```

### 2. Add to `mcporter.json`

```json
{
  "mcpServers": {
    "semantica": {
      "command": "python",
      "args": ["-m", "semantica.mcp_server"],
      "transport": "stdio"
    }
  }
}
```

### 3. Restart the OpenClaw Gateway

```bash
openclaw gateway restart
```

All **12 Semantica tools** are now available to any OpenClaw agent:

| Tool | What it does |
|---|---|
| `extract_entities` | Named entity recognition from text |
| `extract_relations` | Relation / triplet extraction from text |
| `record_decision` | Record a decision with causal links |
| `query_decisions` | Search recorded decisions |
| `find_precedents` | Find past decisions similar to a query |
| `get_causal_chain` | Trace cause-effect chains from a node |
| `add_entity` | Add a node to the knowledge graph |
| `add_relationship` | Add an edge between two nodes |
| `run_reasoning` | Forward-chain rules over facts |
| `get_graph_analytics` | Centrality, communities, topology stats |
| `export_graph` | Export graph (JSON, RDF, GraphML, …) |
| `get_graph_summary` | High-level graph overview |

**3 resources** are also exposed: `semantica://graph/summary`, `semantica://decisions/list`, `semantica://schema/info`.

---

## Path 2 — Native Tool (REST)

Use `OpenClawKGTool` when you prefer a direct Python integration without the MCP gateway.

### Install

```bash
pip install semantica[openclaw]   # pulls in 'requests'
```

### Quick start

```python
from integrations.openclaw import OpenClawKGTool

tool = OpenClawKGTool(base_url="http://localhost:8000")

# Extract knowledge from text
entities = tool.extract_entities("OpenClaw is an open-source AI agent built in Python.")
relations = tool.extract_relations("Alice manages the OpenClaw project at Hawksight.")

# Record and query decisions
tool.record_decision("Deploy model v2 to production", context="latency improved by 40%")
precedents = tool.find_precedents("roll back production deployment")

# Graph analytics
summary = tool.get_graph_summary()
analytics = tool.get_graph_analytics()

# Export
ttl = tool.export_graph(fmt="ttl")
```

### Generate `mcporter.json` programmatically

```python
from integrations.openclaw import OpenClawMCPConfig

cfg = OpenClawMCPConfig()
print(cfg.to_json())   # → paste into mcporter.json
```

---

## SOUL.md agent snippet

Add Semantica to any OpenClaw agent by referencing the tool in your `SOUL.md`:

```markdown
## Tools

- name: semantica_kg
  description: >
    Semantica knowledge-graph tool. Supports entity extraction, decision
    recording, graph querying, causal chain analysis, reasoning, and
    multi-format export.
  endpoint: http://localhost:8000
  auth: none

## Instructions

You have access to `semantica_kg`. Use it to:
- Extract entities and relations from any text the user provides.
- Record important decisions and retrieve precedents before recommending actions.
- Run graph analytics and export results when the user asks for a summary.
```

---

## Requirements

- Python 3.8+
- `pip install semantica` (core)
- `pip install semantica[openclaw]` (adds `requests` for the REST path)
- OpenClaw ≥ latest — [openclaw.ai](https://openclaw.ai)
