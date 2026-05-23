---
title: "MCP Server"
description: "Model Context Protocol server — expose Semantica's full capability set to Claude Desktop, VS Code, Cursor, and any MCP-aware tool."
icon: "plug"
---

`semantica.mcp_server` exposes Semantica's knowledge graph, decision intelligence, semantic extraction, and reasoning capabilities as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server over stdio.

Compatible with **Claude Desktop**, **Windsurf**, **Cline**, **Continue**, **VS Code**, **Roo Code**, **Cursor**, and any MCP-aware client.

## What You Get

- **12 MCP tools** — extract entities, build graphs, run SPARQL, find paths, get recommendations, embed, cluster, and more
- **3 readable resources** — live graph JSON, entity list, and relationship list
- **Zero infrastructure** — runs over stdio, no server or port needed
- **Claude Desktop ready** — one config block to add to `claude_desktop_config.json`
- **REST alternative** — the Explorer module offers a full HTTP API if you prefer

## Installation

```bash
pip install semantica
```

The MCP server is included in the base install — no extras required.

## Configuration

Add Semantica to your MCP client's settings file:

<CodeGroup>

```json Claude Desktop / Windsurf / Cline
{
  "mcpServers": {
    "semantica": {
      "command": "semantica-mcp"
    }
  }
}
```

```json VS Code / Continue / Roo Code
{
  "mcpServers": {
    "semantica": {
      "command": "python",
      "args": ["-m", "semantica.mcp_server"]
    }
  }
}
```

```json With persistent graph
{
  "mcpServers": {
    "semantica": {
      "command": "semantica-mcp",
      "env": {
        "SEMANTICA_KG_PATH": "/path/to/my_graph.json",
        "SEMANTICA_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

</CodeGroup>

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `SEMANTICA_KG_PATH` | *(none)* | Path to a persisted graph to load on startup |
| `SEMANTICA_LOG_LEVEL` | `WARNING` | Log verbosity: `DEBUG`, `INFO`, `WARNING` |

## Tools

The MCP server exposes 12 tools that any connected AI assistant can call:

### Knowledge Extraction

<AccordionGroup>

<Accordion title="extract_entities" icon="tag">

Extract named entities (people, places, organisations, concepts) from text using Semantica NER.

**Input:**
```json
{ "text": "Apple Inc. was founded by Steve Jobs in Cupertino in 1976." }
```

**Output:**
```json
{
  "entities": [
    { "label": "Apple Inc.", "type": "ORGANIZATION", "start": 0,  "end": 10 },
    { "label": "Steve Jobs", "type": "PERSON",       "start": 26, "end": 36 },
    { "label": "Cupertino",  "type": "LOCATION",     "start": 40, "end": 49 },
    { "label": "1976",       "type": "DATE",          "start": 53, "end": 57 }
  ]
}
```

</Accordion>

<Accordion title="extract_relations" icon="arrows-left-right">

Extract typed relations and `(subject, predicate, object)` triplets from text.

**Input:**
```json
{ "text": "Steve Jobs founded Apple Inc. and led it until 2011." }
```

**Output:**
```json
{
  "relations": [
    { "source": "Steve Jobs", "type": "founded", "target": "Apple Inc." }
  ],
  "triplets": [
    { "subject": "Steve Jobs", "predicate": "founded", "object": "Apple Inc." }
  ]
}
```

</Accordion>

</AccordionGroup>

### Decision Intelligence

<AccordionGroup>

<Accordion title="record_decision" icon="check-circle">

Record a decision with full context, reasoning, and metadata into the knowledge graph.

**Input:**
```json
{
  "category": "model_selection",
  "scenario": "Choose LLM for production reasoning pipeline",
  "reasoning": "GPT-4 benchmark advantage justifies 3x cost increase",
  "outcome": "selected_gpt4",
  "confidence": 0.91,
  "decision_maker": "product_team"
}
```

**Output:**
```json
{ "decision_id": "dec_a1b2c3", "status": "recorded" }
```

</Accordion>

<Accordion title="query_decisions" icon="magnifying-glass">

Query recorded decisions by natural language, category, or retrieve all recent decisions.

**Input:**
```json
{ "query": "model selection", "limit": 5 }
```

</Accordion>

<Accordion title="find_precedents" icon="clock-rotate-left">

Find past decisions similar to a given scenario using hybrid similarity search.

**Input:**
```json
{ "scenario": "Choose cloud provider for HIPAA workload", "max_results": 3 }
```

</Accordion>

<Accordion title="get_causal_chain" icon="diagram-project">

Trace the causal chain upstream or downstream from a decision.

**Input:**
```json
{ "decision_id": "dec_a1b2c3", "direction": "downstream", "max_depth": 5 }
```

</Accordion>

</AccordionGroup>

### Graph Operations

<AccordionGroup>

<Accordion title="add_entity" icon="circle-plus">

Add a node/entity to the live knowledge graph.

**Input:**
```json
{
  "id": "apple_inc",
  "label": "Apple Inc.",
  "type": "Organization",
  "metadata": { "founded": 1976, "hq": "Cupertino" }
}
```

</Accordion>

<Accordion title="add_relationship" icon="arrow-right">

Add a directed relationship (edge) between two existing entities.

**Input:**
```json
{
  "source": "steve_jobs",
  "target": "apple_inc",
  "type": "FOUNDED",
  "metadata": { "year": 1976 }
}
```

</Accordion>

<Accordion title="get_graph_analytics" icon="chart-bar">

Compute PageRank centrality and community detection over the current graph. Returns top nodes by influence and community count.

</Accordion>

<Accordion title="get_graph_summary" icon="info-circle">

Return node count, decision count, and graph health status.

</Accordion>

</AccordionGroup>

### Reasoning & Export

<AccordionGroup>

<Accordion title="run_reasoning" icon="brain">

Run forward-chaining IF/THEN rules over a set of facts to derive new facts.

**Input:**
```json
{
  "facts": ["Employee(John)", "Manager(John)"],
  "rules": ["IF Manager(?x) THEN HasAuthority(?x)"]
}
```

**Output:**
```json
{ "derived_facts": ["HasAuthority(John)"] }
```

</Accordion>

<Accordion title="export_graph" icon="file-export">

Export the current knowledge graph to a serialization format.

**Input:**
```json
{ "format": "json-ld" }
```

Supported formats: `turtle`, `ttl`, `nt`, `xml`, `json-ld`, `json`.

</Accordion>

</AccordionGroup>

## Resources

The MCP server also exposes three readable resources:

| URI | Description |
| --- | ----------- |
| `semantica://graph/summary` | High-level graph statistics |
| `semantica://decisions/list` | All recorded decisions (up to 50) |
| `semantica://schema/info` | Server version and available tools |

## Test Locally

```bash
# Run the server directly (reads from stdin, writes to stdout)
semantica-mcp

# Or via Python module
python -m semantica.mcp_server
```

Send a JSON-RPC `initialize` message to confirm it's working:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | semantica-mcp
```

<CardGroup cols={2}>
  <Card title="Context" icon="brain" href="context">
    The ContextGraph that the MCP server operates on.
  </Card>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    NER and relation extraction powering the MCP tools.
  </Card>
  <Card title="Reasoning" icon="microchip" href="reasoning">
    Forward-chaining engine behind run_reasoning.
  </Card>
  <Card title="Agno Integration" icon="robot" href="../integrations/agno">
    Use Semantica inside Agno multi-agent teams.
  </Card>
</CardGroup>
