"""
Semantica MCP Server Package

A full Model Context Protocol (MCP) server for Semantica — exposes knowledge graph
construction, semantic extraction, decision intelligence, reasoning, analytics,
and export capabilities as MCP tools and resources.

Run the server:
    python -m mcp.server        # from repo root
    python -m semantica.mcp_server  # alias inside installed package

Configure in Claude Desktop, Windsurf, Cline, Continue, VS Code:
    {
        "mcpServers": {
            "semantica": {
                "command": "python",
                "args": ["-m", "mcp.server"],
                "cwd": "/path/to/semantica"
            }
        }
    }
"""

from .server import SemanticaMCPServer, main

__all__ = ["SemanticaMCPServer", "main"]
__version__ = "0.4.0"
