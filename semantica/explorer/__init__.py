"""
Semantica Knowledge Explorer : CLI Entry Point

Provides the ``semantica-explorer`` command that loads a graph from a
JSON file, starts a FastAPI server, and optionally opens the browser.

Usage::

    semantica-explorer --graph my_graph.json --port 8000
    python -m semantica.explorer --graph my_graph.json
"""

import argparse
import sys
import webbrowser

from rich.console import Console
from rich.panel import Panel

_out = Console()
_err = Console(stderr=True)


def _browser_origin(host, port):
    """The Origin a browser sends for a page served from ``host``:``port``.

    An IPv6 literal is written in brackets, as it is in a URL, so
    ``--host fe80::1`` gives ``http://[fe80::1]:<port>``.
    """
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{port}"


def main(argv=None):
    """CLI entry point for the Knowledge Explorer server."""
    parser = argparse.ArgumentParser(
        prog="semantica-explorer",
        description="Semantica Knowledge Explorer — interactive dashboard for KG exploration",
    )
    parser.add_argument(
        "--graph", "-g",
        required=True,
        help="Path to a ContextGraph JSON file to load.",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically.",
    )
    args = parser.parse_args(argv)


    import os
    if not os.path.isfile(args.graph):
        _err.print(f"[bold red]Error:[/bold red] graph file not found: {args.graph}")
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        _err.print(
            "[bold red]Error:[/bold red] uvicorn is required.  Install with:\n"
            "  [dim]pip install semantica[explorer][/dim]"
        )
        sys.exit(1)

    from .session import GraphSession
    from .app import create_app

    with _out.status("[dim]Loading graph…[/dim]", spinner="dots"):
        session = GraphSession.from_file(args.graph)
    stats = session.get_stats()
    _out.print(
        f"[bold green]✓[/bold green] Graph loaded — "
        f"[cyan]{stats.get('node_count', 0)}[/cyan] nodes, "
        f"[cyan]{stats.get('edge_count', 0)}[/cyan] edges"
    )

    allowed_origins = None
    if "ALLOWED_ORIGINS" not in os.environ and "EXPLORER_CORS_ORIGINS" not in os.environ:
        default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
        # With --port 0 the OS picks the port after this list is built, so
        # there is no port to allow here.
        if args.port != 0:
            default_origins += [
                _browser_origin("localhost", args.port),
                _browser_origin("127.0.0.1", args.port),
            ]
            # A non-loopback --host is also allowed as an origin, so a browser
            # opened on the address the Explorer is reached at can connect.
            if args.host not in ("127.0.0.1", "localhost", "0.0.0.0", "::1", "::"):
                default_origins.append(_browser_origin(args.host, args.port))
        allowed_origins = list(dict.fromkeys(default_origins))

    app = create_app(session=session, allowed_origins=allowed_origins)

    # The page is served at its origin, so the URL the browser opens and the
    # banner shows is written the same way (an IPv6 host in brackets).
    url = _browser_origin(args.host, args.port)

    _LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
    if args.host not in _LOOPBACK_HOSTS:
        import os as _os
        if _os.environ.get("SEMANTICA_ALLOW_ANONYMOUS", "").strip().lower() == "true":
            _err.print(
                f"[bold yellow]Warning:[/bold yellow] Binding to "
                f"[cyan]{args.host}[/cyan] with SEMANTICA_ALLOW_ANONYMOUS=true "
                "exposes the Explorer to the network with no authentication — "
                "all graph data will be readable and writable by any host that "
                "can reach this port."
            )
        elif not _os.environ.get("SEMANTICA_API_KEY"):
            _err.print(
                f"[bold yellow]Warning:[/bold yellow] Binding to "
                f"[cyan]{args.host}[/cyan] but SEMANTICA_API_KEY is not set — "
                "protected routes will refuse all requests (503) until it is "
                "configured."
            )

    if not args.no_browser:
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    _out.print(
        Panel(
            f"[cyan]API docs[/cyan]  {url}/docs\n[cyan]Health[/cyan]    {url}/api/health",
            title=f"[bold]Semantica Explorer[/bold] · [dim]{url}[/dim]",
            border_style="cyan",
            expand=False,
        )
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
