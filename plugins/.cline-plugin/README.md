# Semantica — Cline Plugin

> **v0.4.0** — Adds all 17 Semantica skills, 3 agents, and hook configuration to Cline (VS Code extension).

## MCP Server Setup (recommended)

In Cline settings, add a new MCP server:

```json
{
  "semantica": {
    "command": "python",
    "args": ["-m", "semantica.mcp_server"],
    "env": {}
  }
}
```

Cline will discover all 17 Semantica skills and 3 agents automatically on connection.

## Knowledge Explorer

```bash
semantica-explorer --graph my_graph.json --port 8000
```

Open `http://localhost:5174` for the interactive dashboard.

## Requirements

- Python 3.10+
- `pip install semantica`
