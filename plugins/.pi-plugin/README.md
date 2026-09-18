# Semantica — pi Plugin

> Adds all 17 Semantica skills to [pi](https://pi.dev) — the AI coding assistant — as a [pi package](https://pi.dev/packages).

## Install

```bash
pi install git:github.com/semantica-agi/semantica
```

Or try it without installing:

```bash
pi -e git:github.com/semantica-agi/semantica
```

## Skills

All 17 skills under [`plugins/skills/`](../skills/) are loaded automatically:

`extract` · `ingest` · `query` · `ontology` · `validate` · `deduplicate` · `embed` · `reason` · `decision` · `causal` · `temporal` · `provenance` · `policy` · `explain` · `export` · `change` · `visualize`

## MCP Server (recommended)

The skills reference the Semantica Python API directly. For tool-style access from pi, run the Semantica MCP server:

```bash
python -m semantica.mcp_server
```

Then register it with your MCP client of choice (stdio transport). See [MCP Server](../../README.md#mcp-server) in the main README.

## Requirements

- Python 3.9.2+ (`pyproject.toml` requires-python) with `pip install semantica`
