# Semantica — Continue Plugin

> **v0.4.0** — Adds Semantica as an MCP server and context provider to [Continue.dev](https://continue.dev).

## MCP Server Setup

Add to `~/.continue/config.json`:

```json
{
  "mcpServers": [
    {
      "name": "semantica",
      "command": "python",
      "args": ["-m", "semantica.mcp_server"]
    }
  ]
}
```

Continue will show all 17 Semantica skills in the `@semantica` context provider dropdown.

## Knowledge Explorer

```bash
semantica-explorer --graph my_graph.json --port 8000
```

Open `http://localhost:5174` for the interactive graph dashboard.

## Requirements

- Python 3.10+
- `pip install semantica`
