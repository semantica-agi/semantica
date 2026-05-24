---
title: "MCP Server"
description: "Model Context Protocol server — expose Semantica's full capability set to Claude Desktop, VS Code, Cursor, and any MCP-aware tool."
icon: "plug"
---

`semantica.mcp_server` exposes Semantica's knowledge graph, decision intelligence, semantic extraction, and reasoning capabilities as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server over stdio.

Once configured, any connected AI assistant can extract entities, record decisions, query the graph, run reasoning, and export results — without writing a single line of Python.

Compatible with **Claude Desktop**, **Windsurf**, **Cline**, **Continue**, **VS Code**, **Roo Code**, **Cursor**, and any MCP-aware client.

## Server Interface

```json
// Configure in your MCP client (Claude Desktop, Windsurf, Cursor, VS Code, etc.)
{
  "mcpServers": {
    "semantica": {
      "command": "semantica-mcp"
    }
  }
}
```

```bash
# Or run directly
semantica-mcp
# or
python -m semantica.mcp_server
```

<Tip>
  `semantica.mcp_server` is a **stdio server process**, not a Python library. It exposes no importable classes — all interaction happens through MCP tool calls from a connected AI client.
</Tip>

## What You Get

<CardGroup cols={2}>
  <Card title="12 MCP Tools" icon="wrench">
    Extract entities, extract relations, record decisions, query decisions, find precedents, trace causal chains, add entities, add relationships, run analytics, summarise graph, run reasoning, export.
  </Card>
  <Card title="3 Readable Resources" icon="book-open">
    Live graph JSON (`semantica://graph/summary`), decision list, and schema/version info — readable by any MCP client.
  </Card>
  <Card title="Zero Infrastructure" icon="bolt">
    Runs over stdio — no server, no port, no Docker required. One config block to activate in any MCP client.
  </Card>
  <Card title="Persistent Graphs" icon="database">
    Point `SEMANTICA_KG_PATH` at a saved graph file to reload it automatically on every server startup.
  </Card>
  <Card title="Decision Intelligence" icon="brain">
    Record decisions, find precedents via hybrid similarity search, and trace causal chains across agent runs.
  </Card>
  <Card title="REST Alternative" icon="globe">
    The [Explorer](explorer) module offers a full HTTP API and browser dashboard if you prefer programmatic access.
  </Card>
</CardGroup>

## Installation

```bash
pip install semantica
```

The MCP server is included in the base install — no extras required.

## Configuration

<Steps>
  <Step title="Find your MCP client's settings file">

    | Client | Settings file |
    | ------ | ------------- |
    | Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
    | Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
    | Cursor | `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` globally |
    | VS Code / Continue | `.vscode/mcp.json` or user settings |
    | Windsurf / Cline / Roo Code | App-specific settings → MCP Servers |

  </Step>
  <Step title="Add the Semantica MCP server config">

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

    ```json Cursor
    {
      "mcpServers": {
        "semantica": {
          "command": "semantica-mcp",
          "env": {
            "SEMANTICA_KG_PATH": "/path/to/my_graph.json"
          }
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

  </Step>
  <Step title="Test locally before configuring your client">
    ```bash
    # Run the server directly (reads from stdin, writes to stdout)
    semantica-mcp

    # Or via Python module
    python -m semantica.mcp_server

    # Send a JSON-RPC initialize message to confirm it's working
    echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | semantica-mcp
    ```
  </Step>
</Steps>

## Environment Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `SEMANTICA_KG_PATH` | *(none)* | Path to a persisted graph to load on startup |
| `SEMANTICA_LOG_LEVEL` | `WARNING` | Log verbosity: `DEBUG`, `INFO`, `WARNING` |

## Tools

The MCP server exposes 12 tools that any connected AI assistant can call:

| Tool | Category | Description |
| ---- | -------- | ----------- |
| `extract_entities` | Extraction | NER — find people, places, organisations, concepts |
| `extract_relations` | Extraction | Typed relation and triplet extraction |
| `record_decision` | Decision Intelligence | Save a decision with reasoning and outcome |
| `query_decisions` | Decision Intelligence | Search recorded decisions by natural language |
| `find_precedents` | Decision Intelligence | Hybrid similarity search over past decisions |
| `get_causal_chain` | Decision Intelligence | Trace upstream / downstream causal chains |
| `add_entity` | Graph Operations | Add a node to the live graph |
| `add_relationship` | Graph Operations | Add a directed edge between two nodes |
| `get_graph_analytics` | Graph Operations | PageRank + community detection |
| `get_graph_summary` | Graph Operations | Node count, decision count, health status |
| `run_reasoning` | Reasoning & Export | Forward-chain IF/THEN rules over facts |
| `export_graph` | Reasoning & Export | Serialise the graph (Turtle, JSON-LD, JSON, etc.) |

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

The MCP server exposes three readable resources:

| URI | Description |
| --- | ----------- |
| `semantica://graph/summary` | High-level graph statistics |
| `semantica://decisions/list` | All recorded decisions (up to 50) |
| `semantica://schema/info` | Server version and available tools |

## Tips and Common Pitfalls

<Warning>
  **Build the `ContextGraph` before starting the server.** The MCP server operates on a pre-built `ContextGraph` — it doesn't build the knowledge graph on demand. Construct and populate the graph first (ingest → extract → build KG → set `ContextGraph`), then pass it to `SemanticaMCPServer`. An empty or None graph results in empty query responses.
</Warning>

<Tip>
  **Use `decision_tracking=True` for accountable agents.** Without decision tracking, `record_decision` and `query_decisions` calls succeed but nothing is stored. Enable it in the `ContextGraph` constructor when you want agents' decisions to be queryable for audit, compliance, or iterative reasoning.
</Tip>

<Tip>
  **Use `find_precedents` before high-stakes decisions.** The tool performs hybrid similarity search across all recorded decisions. Call it at the start of any significant decision path — it surfaces past reasoning that may be directly applicable, reducing redundant work and improving consistency across agent runs.
</Tip>

<Warning>
  **Configure your MCP client's `command` field exactly.** The `command` field must point to the exact executable path (use `which semantica-mcp` on macOS/Linux to find it). A wrong path fails silently — the server just doesn't appear in the tools list. Test with the raw `echo | semantica-mcp` command first to confirm the binary works.
</Warning>

<Warning>
  **The server communicates over stdio — don't add logging to stdout.** Any `print()` or logger output directed to stdout will corrupt the JSON-RPC message stream. Configure logging to write to a file or stderr only (`logging.basicConfig(filename="mcp.log")`). The MCP protocol assumes stdout carries only JSON-RPC frames.
</Warning>

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
