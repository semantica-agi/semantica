# Semantica — OpenClaw Plugin

> **v0.4.0** — Adds all 17 Semantica skills, 3 agents, and the full MCP integration to [OpenClaw](https://openclaw.ai) — the open-source personal AI agent platform.

## MCP Server Setup (recommended)

### 1. Start the Semantica MCP server

```bash
python -m semantica.mcp_server
```

### 2. Add to `mcporter.json`

Paste the following into your OpenClaw `mcporter.json` (usually `~/.openclaw/mcporter.json`):

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

OpenClaw will automatically discover all 17 Semantica tools and 3 agents.

## Skills

All 17 skills under [`plugins/skills/`](../skills/) are available once the plugin is loaded:

`extract` · `ingest` · `query` · `ontology` · `validate` · `deduplicate` · `embed` · `reason` · `decision` · `causal` · `temporal` · `provenance` · `policy` · `explain` · `export` · `change` · `visualize`

## Native Tool (REST, no MCP gateway)

For agents that cannot use the MCP gateway, use the `OpenClawKGTool` REST wrapper:

```python
from integrations.openclaw import OpenClawKGTool

tool = OpenClawKGTool(base_url="http://localhost:8000")
entities = tool.extract_entities("Alice manages the project.")
tool.record_decision("Deploy model v2 to production")
summary = tool.get_graph_summary()
```

See [`integrations/openclaw/README.md`](../../integrations/openclaw/README.md) for the full guide, including SOUL.md agent snippets.

## Requirements

- Python 3.10+
- `pip install semantica`
- OpenClaw — [openclaw.ai](https://openclaw.ai)
