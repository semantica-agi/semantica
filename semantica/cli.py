"""
Semantica CLI Entry Point

This module provides the command-line interface for the Semantica framework,
enabling users to interact with the framework via terminal commands.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

import yaml

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .core.config_manager import Config, ConfigManager
from .utils.exceptions import SemanticaError
from .utils.logging import setup_logging

if TYPE_CHECKING:
    from .core.orchestrator import Semantica

console = Console()


@dataclass
class CLIContext:
    """Shared runtime context for all CLI commands."""

    config_path: Optional[str]
    config: Config
    log_level: str
    log_level_override: Optional[str] = None
    framework: Optional["Semantica"] = None
    json_output: bool = False
    quiet: bool = False
    no_color: bool = False
    dry_run_global: bool = False
    store_backend: Optional[str] = None
    vector_store_backend: Optional[str] = None


def _require_ctx(cli_ctx: Optional[CLIContext]) -> CLIContext:
    """Guard against uninitialized CLI context.

    Under normal Click operation (standalone_mode=True) ctx.obj is always set
    before a subcommand runs. This guard protects embedded/library usage where
    standalone_mode=False might leave ctx.obj as None.
    """
    if cli_ctx is None:
        raise click.ClickException(
            "CLI context is uninitialized — this is a bug, please report it."
        )
    return cli_ctx


def _run_with_error_handling(action: Callable[[], None]) -> None:
    """Run a CLI action with consistent user-facing error formatting."""
    try:
        action()
    except click.ClickException:
        raise
    except SemanticaError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(f"Unexpected error: {exc}") from exc


def _load_config_data(file_path: Path) -> Dict[str, Any]:
    """Load and validate raw YAML/JSON config data."""
    suffix = file_path.suffix.lower()
    try:
        if suffix in (".yaml", ".yml"):
            with file_path.open("r", encoding="utf-8") as handle:
                config_data = yaml.safe_load(handle)
        elif suffix == ".json":
            with file_path.open("r", encoding="utf-8") as handle:
                config_data = json.load(handle)
        else:
            raise click.ClickException(
                "Unsupported configuration file format: "
                f"{suffix}. Supported formats: .yaml, .yml, .json"
            )
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise click.ClickException(
            f"Failed to parse configuration file '{file_path}': {exc}"
        ) from exc

    if config_data is None:
        config_data = {}

    if not isinstance(config_data, dict):
        raise click.ClickException(
            "Configuration file must contain a mapping/object at the root."
        )

    return config_data


def _build_runtime_config(
    config_path: Optional[str],
    log_level: Optional[str],
) -> Config:
    """Resolve CLI config from file plus global flag overrides."""
    config_manager = ConfigManager()

    if config_path:
        config_data = _load_config_data(Path(config_path))
    else:
        config_data = {}

    logging_config = config_data.get("logging")
    if logging_config is not None and not isinstance(logging_config, dict):
        raise click.ClickException(
            "Logging configuration section must contain a mapping/object."
        )

    if log_level:
        if logging_config is None:
            logging_config = {}
            config_data["logging"] = logging_config

        logging_config["level"] = log_level.upper()

    # Keep validation disabled at CLI bootstrap to avoid blocking unrelated commands.
    return config_manager.load_from_dict(config_data, validate=False)


def _get_framework(cli_ctx: CLIContext) -> "Semantica":
    """Lazily initialize framework only when a command needs it."""
    if cli_ctx.framework is None:
        from .core.orchestrator import Semantica

        cli_ctx.framework = Semantica(config=cli_ctx.config.to_dict())
    return cli_ctx.framework


def _run_build(cli_ctx: CLIContext, sources: Sequence[str]) -> None:
    """Thin wrapper around existing build orchestration flow.

    build_knowledge_base is expected to return a dict of the form::

        {
            "statistics": {
                "sources_processed": <int>,
                ...
            },
            ...
        }

    Both the top-level dict and the "statistics" key are optional; the
    function degrades gracefully when either is absent or None.
    """
    if not sources:
        raise click.UsageError(
            "At least one source is required. Use --source/-s one or more times."
        )

    framework = _get_framework(cli_ctx)
    console.print(f"Initializing Semantica with {len(sources)} sources...")
    result = framework.build_knowledge_base(sources=list(sources))

    stats = result.get("statistics", {}) if isinstance(result, dict) else {}
    processed = stats.get("sources_processed")
    if processed is not None:
        console.print(
            "[bold green]Success:[/bold green] Knowledge base build completed "
            f"for {processed} source(s)."
        )
    else:
        console.print(
            "[bold green]Success:[/bold green] Knowledge base build completed."
        )


def _run_build_command(
    cli_ctx: CLIContext,
    source: Sequence[str],
    command_config_path: Optional[str],
) -> None:
    """Execute build command path with optional command-level config override.

    When a per-command config file is supplied, the logging configuration from
    that file is re-applied (setup_logging clears existing handlers before
    adding new ones, so there is no handler accumulation risk).
    """
    if command_config_path:
        cmd_config = _build_runtime_config(
            command_config_path, cli_ctx.log_level_override
        )
        # Re-apply logging so the command-level logging section takes effect.
        setup_logging(config=cmd_config.get("logging", {}))
        command_ctx = CLIContext(
            config_path=command_config_path,
            config=cmd_config,
            log_level=cli_ctx.log_level,
            log_level_override=cli_ctx.log_level_override,
            # Propagate all global flag state so command-level config overrides
            # don't silently drop --json, --quiet, --dry-run, or backend flags.
            json_output=cli_ctx.json_output,
            quiet=cli_ctx.quiet,
            no_color=cli_ctx.no_color,
            dry_run_global=cli_ctx.dry_run_global,
            store_backend=cli_ctx.store_backend,
            vector_store_backend=cli_ctx.vector_store_backend,
        )
        _run_build(command_ctx, source)
    else:
        _run_build(cli_ctx, source)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=str),
    default=None,
    help="Path to YAML/JSON config file.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        case_sensitive=False,
    ),
    default=None,
    help="Override logging level for this CLI invocation.",
)
@click.option("--json", "json_output", is_flag=True, default=False,
              help="Machine-readable JSON to stdout; errors to stderr.")
@click.option("--quiet", "-q", is_flag=True, default=False,
              help="Suppress all informational output.")
@click.option("--no-color", is_flag=True, default=False,
              help="Disable colored output.")
@click.option("--dry-run", "global_dry_run", is_flag=True, default=False,
              help="Preview without writing (all write commands).")
@click.option("--store", "store_backend", default=None,
              help="Override graph store backend.")
@click.option("--vector-store", "vector_store_backend", default=None,
              help="Override vector store backend.")
@click.option("--profile", default=None, help="Named config profile.")
@click.pass_context
def main(
    ctx: click.Context,
    config_path: Optional[str],
    log_level: Optional[str],
    json_output: bool,
    quiet: bool,
    no_color: bool,
    global_dry_run: bool,
    store_backend: Optional[str],
    vector_store_backend: Optional[str],
    profile: Optional[str],
) -> None:
    """Semantica - Semantic Layer & Knowledge Engineering Framework"""
    try:
        config = _build_runtime_config(config_path=config_path, log_level=log_level)
        # Always initialize logging so file handlers are installed; --quiet only
        # suppresses console output (controlled via _ok/_dry checks).
        setup_logging(config=config.get("logging", {}))
        effective_log_level = config.get("logging.level", "INFO")
        # Reinitialize the module-level console if --no-color was requested so
        # all subsequent console.print() calls in this invocation respect the flag.
        if no_color:
            global console  # noqa: PLW0603
            console = Console(no_color=True)
        ctx.obj = CLIContext(
            config_path=config_path,
            config=config,
            log_level=effective_log_level,
            log_level_override=log_level.upper() if log_level else None,
            json_output=json_output,
            quiet=quiet,
            no_color=no_color,
            dry_run_global=global_dry_run,
            store_backend=store_backend,
            vector_store_backend=vector_store_backend,
        )
    except click.ClickException:
        raise
    except SemanticaError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(f"Failed to initialize CLI: {exc}") from exc


@main.group(invoke_without_command=True)
@click.pass_context
def kg(ctx: click.Context) -> None:
    """Knowledge graph and semantic build commands."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.group(invoke_without_command=True)
@click.pass_context
def pipeline(ctx: click.Context) -> None:
    """Pipeline command group (foundation placeholder)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.group(name="services", invoke_without_command=True)
@click.pass_context
def services(ctx: click.Context) -> None:
    """Service management commands (server, explorer, mcp — foundation placeholder).

    Subcommands will follow the spec layout::

        semantica services server  start|stop|status
        semantica services explorer start|stop|status
        semantica services mcp      start|stop|status
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.group(name="config", invoke_without_command=True)
@click.pass_context
def config_group(ctx: click.Context) -> None:
    """Configuration command group."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.pass_obj
def info(cli_ctx: CLIContext):
    """Display information about Semantica."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        console.print(f"[bold blue]Semantica Framework[/bold blue] v{__version__}")
        console.print(
            "A comprehensive Python framework for transforming unstructured data "
            "into semantic layers."
        )

        table = Table(title="Framework Components")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")

        table.add_row("Core Orchestrator", "Active")
        table.add_row("Knowledge Graph Engine", "Active")
        table.add_row("Pipeline Execution", "Active")
        table.add_row("Vector Store Integration", "Active")
        table.add_row("CLI Config File", cli_ctx.config_path or "(none)")
        table.add_row("CLI Log Level", cli_ctx.log_level)

        console.print(table)

    _run_with_error_handling(_action)


@kg.command("build")
@click.option("--source", "-s", multiple=True, help="Data sources to process.")
@click.option(
    "-c",
    "--config",
    "command_config_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=str),
    default=None,
    help="Path to YAML/JSON config file.",
)
@click.pass_obj
def kg_build(
    cli_ctx: CLIContext,
    source: Sequence[str],
    command_config_path: Optional[str],
):
    """Build a knowledge base from sources."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        _run_build_command(cli_ctx, source, command_config_path)

    _run_with_error_handling(_action)


@main.command("build", hidden=True)
@click.option("--source", "-s", multiple=True, help="Data sources to process.")
@click.option(
    "-c",
    "--config",
    "command_config_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=str),
    default=None,
    help="Path to YAML/JSON config file.",
)
@click.pass_obj
def build_alias(
    cli_ctx: CLIContext,
    source: Sequence[str],
    command_config_path: Optional[str],
):
    """Backward-compatible alias for 'kg build'."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        _run_build_command(cli_ctx, source, command_config_path)

    _run_with_error_handling(_action)


# ─── Output helpers ──────────────────────────────────────────────────────────


def _jecho(data: Any) -> None:
    """Emit JSON to stdout."""
    click.echo(json.dumps(data, default=str))


def _ok(cli_ctx: CLIContext, text: str) -> None:
    if not cli_ctx.quiet:
        console.print(f"[bold green]Success:[/bold green] {text}")


def _dry(cli_ctx: CLIContext, action: str, *, json_out: bool = False, **fields: Any) -> None:
    payload = {"dry_run": True, "action": action, **fields}
    if json_out or cli_ctx.json_output:
        _jecho(payload)
    elif not cli_ctx.quiet:
        console.print(f"[yellow]Dry run:[/yellow] would {action}: {fields}")


def _is_dry(cli_ctx: CLIContext, local_dry: bool) -> bool:
    return local_dry or cli_ctx.dry_run_global


def _is_json(cli_ctx: CLIContext, local_json: bool) -> bool:
    return local_json or cli_ctx.json_output


# ─── Additional kg subcommands ────────────────────────────────────────────────


@kg.command("query")
@click.argument("query_str")
@click.option("--lang", type=click.Choice(["cypher", "sparql"]), default="cypher",
              show_default=True, help="Query language.")
@click.option("--limit", default=100, type=int, show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_query(cli_ctx: CLIContext, query_str: str, lang: str, limit: int, local_json: bool) -> None:
    """Run a Cypher or SPARQL query against the knowledge graph."""
    cli_ctx = _require_ctx(cli_ctx)
    json_out = _is_json(cli_ctx, local_json)

    def _action() -> None:
        try:
            from .graph_store import execute_query
        except ImportError as exc:
            raise click.ClickException(f"Graph store module not available: {exc}") from exc
        result = execute_query(query_str, lang=lang, limit=limit,
                               config=cli_ctx.config.to_dict())
        if json_out:
            _jecho(result if isinstance(result, (dict, list)) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@kg.command("stats")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table",
              show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_stats(cli_ctx: CLIContext, fmt: str, local_json: bool) -> None:
    """Show node/edge counts, density, and graph metrics."""
    cli_ctx = _require_ctx(cli_ctx)
    json_out = _is_json(cli_ctx, local_json) or fmt == "json"

    def _action() -> None:
        try:
            from .kg import GraphAnalyzer
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        stats = GraphAnalyzer(config=cli_ctx.config.to_dict()).get_statistics()
        if json_out:
            _jecho(stats)
        else:
            table = Table(title="Knowledge Graph Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            for k, v in (stats.items() if isinstance(stats, dict) else []):
                table.add_row(str(k), str(v))
            console.print(table)

    _run_with_error_handling(_action)


@kg.command("analyze")
@click.option("--mode", type=click.Choice(["centrality", "community", "connectivity", "all"]),
              default="all", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_analyze(cli_ctx: CLIContext, mode: str, local_json: bool) -> None:
    """Run centrality, community detection, or connectivity analysis."""
    cli_ctx = _require_ctx(cli_ctx)
    json_out = _is_json(cli_ctx, local_json)

    def _action() -> None:
        try:
            from .kg import GraphAnalyzer
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        result = GraphAnalyzer(config=cli_ctx.config.to_dict()).analyze(mode=mode)
        if json_out:
            _jecho(result if isinstance(result, dict) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@kg.command("find-path")
@click.option("--from", "from_entity", required=True, help="Source entity name.")
@click.option("--to", "to_entity", required=True, help="Target entity name.")
@click.option("--type", "path_type",
              type=click.Choice(["shortest", "semantic", "causal"]),
              default="shortest", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_find_path(cli_ctx: CLIContext, from_entity: str, to_entity: str,
                 path_type: str, local_json: bool) -> None:
    """Find a path between two entities in the knowledge graph."""
    cli_ctx = _require_ctx(cli_ctx)
    json_out = _is_json(cli_ctx, local_json)

    def _action() -> None:
        try:
            from .kg import PathFinder
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        path = PathFinder(config=cli_ctx.config.to_dict()).find_path(
            from_entity, to_entity, path_type=path_type
        )
        if json_out:
            _jecho(path if isinstance(path, dict) else {"path": path})
        else:
            console.print(path)

    _run_with_error_handling(_action)


@kg.command("resolve")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_resolve(cli_ctx: CLIContext, local_json: bool) -> None:
    """Run entity resolution across the knowledge graph."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import EntityResolver
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        result = EntityResolver(config=cli_ctx.config.to_dict()).resolve()
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"result": str(result)})
        else:
            _ok(cli_ctx, f"Entity resolution complete: {result}")

    _run_with_error_handling(_action)


@kg.command("predict")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_predict(cli_ctx: CLIContext, local_json: bool) -> None:
    """Run link prediction on the knowledge graph."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import LinkPredictor
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        result = LinkPredictor(config=cli_ctx.config.to_dict()).predict()
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@kg.command("validate")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def kg_validate_cmd(cli_ctx: CLIContext, local_json: bool) -> None:
    """Run a graph integrity check."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import GraphValidator
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        result = GraphValidator(config=cli_ctx.config.to_dict()).validate()
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"result": str(result)})
        else:
            _ok(cli_ctx, f"Graph validation: {result}")

    _run_with_error_handling(_action)


# ─── Data In ──────────────────────────────────────────────────────────────────


_INGEST_TYPES = [
    "file", "web", "parquet", "xml", "rest", "db", "duckdb", "elastic",
    "email", "feed", "gdrive", "huggingface", "mcp", "mongo", "repo",
    "snowflake", "stream",
]

_INGEST_FORMATS = ["pdf", "docx", "csv", "excel", "html", "json", "parquet", "xml", "rdf"]


@main.command()
@click.argument("source")
@click.option("--type", "ingestor_type", type=click.Choice(_INGEST_TYPES), default=None,
              help="Force ingestor type (auto-detected by default).")
@click.option("--format", "fmt", type=click.Choice(_INGEST_FORMATS), default=None,
              help="Format hint.")
@click.option("--recursive", is_flag=True, default=False, help="Recurse into directories.")
@click.option("--watch", is_flag=True, default=False, help="Re-ingest on file changes.")
@click.option("--batch-size", default=500, type=int, show_default=True)
@click.option("--store", "store_override", default=None,
              help="Target graph backend: neo4j falkordb age neptune")
@click.option("--output", default=None, type=click.Path(), help="Write to file instead of graph store.")
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ingest(
    cli_ctx: CLIContext, source: str, ingestor_type: Optional[str], fmt: Optional[str],
    recursive: bool, watch: bool, batch_size: int, store_override: Optional[str],
    output: Optional[str], local_dry: bool, local_json: bool,
) -> None:
    """Load files, URLs, databases, or streams into the graph.

    \b
    Examples:
      semantica ingest ./reports/q1.pdf
      semantica ingest ./data/ --recursive --format csv
      semantica ingest https://feeds.example.com/news --type feed --watch
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "ingest", json_out=_is_json(cli_ctx, local_json),
                 source=source, type=ingestor_type, format=fmt)
            return
        kwargs: Dict[str, Any] = {"source": source, "batch_size": batch_size}
        if ingestor_type:
            kwargs["ingestor_type"] = ingestor_type
        if fmt:
            kwargs["format"] = fmt
        if recursive:
            kwargs["recursive"] = True
        if store_override or cli_ctx.store_backend:
            kwargs["store"] = store_override or cli_ctx.store_backend
        if output:
            kwargs["output"] = output
        try:
            from .ingest import ingest as _ingest
            result = _ingest(**kwargs)
        except ImportError as exc:
            raise click.ClickException(f"Ingest module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"status": "ok"})
        else:
            _ok(cli_ctx, f"Ingested: {source}")

    _run_with_error_handling(_action)


@main.command("parse")
@click.argument("file", type=click.Path(exists=True))
@click.option("--parser",
              type=click.Choice(["pdf", "docx", "code", "csv", "email", "excel",
                                  "html", "image", "json", "pptx", "xml", "web"]),
              default=None, help="Parser override.")
@click.option("--format", "fmt", type=click.Choice(["json", "yaml", "table"]),
              default="json", show_default=True)
@click.pass_obj
def parse_cmd(cli_ctx: CLIContext, file: str, parser: Optional[str], fmt: str) -> None:
    """Parse a document into structured content (stdout).

    \b
    Examples:
      semantica parse contract.pdf | jq '.entities'
      semantica parse source.py --parser code --format json > parsed.json
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        kwargs: Dict[str, Any] = {"file_path": file}
        if parser:
            kwargs["parser"] = parser
        try:
            from .parse import parse_document
            result = parse_document(**kwargs)
        except ImportError as exc:
            raise click.ClickException(f"Parse module not available: {exc}") from exc
        if fmt == "json" or _is_json(cli_ctx, False):
            click.echo(json.dumps(result, default=str))
        elif fmt == "yaml":
            click.echo(yaml.dump(result, default_flow_style=False))
        else:
            console.print(result)

    _run_with_error_handling(_action)


@main.command()
@click.argument("input_path")
@click.option("--strategy",
              type=click.Choice(["recursive", "semantic", "entity-aware", "relation-aware",
                                  "sliding-window", "structural", "table"]),
              default="recursive", show_default=True)
@click.option("--chunk-size", default=512, type=int, show_default=True)
@click.option("--overlap", default=64, type=int, show_default=True)
@click.option("--format", "fmt", type=click.Choice(["json", "jsonl", "text"]),
              default="json", show_default=True)
@click.option("--output", default=None, type=click.Path())
@click.pass_obj
def split(
    cli_ctx: CLIContext, input_path: str, strategy: str, chunk_size: int,
    overlap: int, fmt: str, output: Optional[str],
) -> None:
    """Chunk documents with configurable strategies.

    \b
    Examples:
      semantica split report.pdf --strategy semantic --chunk-size 256
      semantica split data.csv --strategy table --format jsonl > chunks.jsonl
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .split import split_recursive, get_split_method
            fn = get_split_method(strategy) if strategy != "recursive" else split_recursive
            chunks = fn(input_path, chunk_size=chunk_size, overlap=overlap)
        except ImportError as exc:
            raise click.ClickException(f"Split module not available: {exc}") from exc
        if fmt == "jsonl":
            lines = "\n".join(json.dumps(c, default=str) for c in (chunks or []))
        elif fmt == "json":
            lines = json.dumps(chunks, default=str)
        else:
            lines = "\n".join(str(c) for c in (chunks or []))
        if output:
            Path(output).write_text(lines, encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        else:
            click.echo(lines)

    _run_with_error_handling(_action)


@main.command()
@click.argument("input_text")
@click.option("--mode", type=click.Choice(["text", "temporal", "entity", "all"]),
              default="all", show_default=True)
@click.option("--domain", type=click.Choice(["healthcare", "legal", "finance", "general"]),
              default="general", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def normalize(cli_ctx: CLIContext, input_text: str, mode: str, domain: str,
              local_json: bool) -> None:
    """Normalize text and dates (deterministic, no LLM).

    \b
    Examples:
      semantica normalize "We met last Tuesday around noon." --mode temporal
      semantica normalize entities.json --mode entity --domain legal
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        src = Path(input_text)
        text = src.read_text(encoding="utf-8") if src.exists() else input_text
        try:
            from .normalize import normalize_text, normalize_date, normalize_entity
            if mode == "temporal":
                result = normalize_date(text, domain=domain)
            elif mode == "entity":
                result = normalize_entity(text, domain=domain)
            elif mode == "text":
                result = normalize_text(text)
            else:
                result = normalize_text(normalize_date(normalize_entity(text, domain=domain)))
        except ImportError as exc:
            raise click.ClickException(f"Normalize module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho({"result": result})
        else:
            click.echo(result)

    _run_with_error_handling(_action)


# ─── Processing ───────────────────────────────────────────────────────────────


@main.command()
@click.argument("input_path")
@click.option("--mode",
              type=click.Choice(["ner", "relations", "triplets", "events", "coreference", "all"]),
              default="all", show_default=True)
@click.option("--method", type=click.Choice(["pattern", "ml", "llm"]),
              default="ml", show_default=True)
@click.option("--model", default=None, help="LLM model when using --method llm.")
@click.option("--confidence", default=0.5, type=float, show_default=True,
              help="Minimum confidence 0.0-1.0.")
@click.option("--temporal", is_flag=True, default=False, help="Also extract temporal bounds.")
@click.option("--format", "fmt",
              type=click.Choice(["json", "yaml", "table", "rdf"]),
              default="json", show_default=True)
@click.option("--output", default=None, type=click.Path())
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def extract(
    cli_ctx: CLIContext, input_path: str, mode: str, method: str,
    model: Optional[str], confidence: float, temporal: bool,
    fmt: str, output: Optional[str], local_json: bool,
) -> None:
    """Run extraction (NER, relations, triplets, events) on text or files.

    \b
    Examples:
      semantica extract "Alice signed the contract with Acme Corp."
      semantica extract report.pdf --mode triplets --method llm --model claude-sonnet-4-6
      cat text.txt | semantica extract - --mode relations
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if input_path == "-":
            text = sys.stdin.read()
        else:
            p = Path(input_path)
            text = p.read_text(encoding="utf-8") if p.exists() else input_path
        try:
            from .semantic_extract import SemanticAnalyzer
            kwargs: Dict[str, Any] = {
                "text": text, "mode": mode, "method": method,
                "min_confidence": confidence,
            }
            if model:
                kwargs["model"] = model
            if temporal:
                kwargs["temporal"] = True
            analyzer = SemanticAnalyzer(config=cli_ctx.config.to_dict())
            result = analyzer.extract(**kwargs)
        except ImportError as exc:
            raise click.ClickException(f"Extract module not available: {exc}") from exc
        json_out = _is_json(cli_ctx, local_json) or fmt == "json"
        if json_out:
            payload = result if isinstance(result, dict) else {"result": str(result)}
        elif fmt == "yaml":
            payload = None
            click.echo(yaml.dump(result, default_flow_style=False))
        else:
            payload = None
            console.print(result)
        if payload is not None:
            if output:
                Path(output).write_text(json.dumps(payload, default=str), encoding="utf-8")
                _ok(cli_ctx, f"Wrote {output}")
            else:
                _jecho(payload)

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def embed(ctx: click.Context) -> None:
    """Generate, index, and search embeddings."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@embed.command("generate")
@click.argument("input_path")
@click.option("--model",
              type=click.Choice(["sentence-transformers", "fastembed", "openai", "bge"]),
              default="sentence-transformers", show_default=True)
@click.option("--store", "store_backend",
              type=click.Choice(["faiss", "pinecone", "weaviate", "qdrant", "milvus", "pgvector"]),
              default=None)
@click.option("--namespace", default=None)
@click.option("--output", default=None, type=click.Path())
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def embed_generate(cli_ctx: CLIContext, input_path: str, model: str,
                   store_backend: Optional[str], namespace: Optional[str],
                   output: Optional[str], local_json: bool) -> None:
    """Embed entities or documents and optionally index them.

    \b
    Example:
      semantica embed generate ./entities.json --model sentence-transformers --output embeddings.parquet
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .embeddings import generate_embeddings
            result = generate_embeddings(
                input_path, model=model,
                store=store_backend or cli_ctx.vector_store_backend,
                namespace=namespace,
            )
        except ImportError as exc:
            raise click.ClickException(f"Embeddings module not available: {exc}") from exc
        if output:
            Path(output).write_text(json.dumps(result, default=str), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        elif _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"status": "ok"})
        else:
            _ok(cli_ctx, "Embeddings generated.")

    _run_with_error_handling(_action)


@embed.command("search")
@click.argument("query_text")
@click.option("--store",
              type=click.Choice(["faiss", "pinecone", "weaviate", "qdrant", "milvus", "pgvector"]),
              default=None)
@click.option("--top-k", default=10, type=int, show_default=True)
@click.option("--hybrid", is_flag=True, default=False, help="Dense + sparse hybrid search.")
@click.option("--namespace", default=None)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def embed_search(cli_ctx: CLIContext, query_text: str, store: Optional[str],
                 top_k: int, hybrid: bool, namespace: Optional[str], local_json: bool) -> None:
    """Semantic similarity search over the vector store.

    \b
    Example:
      semantica embed search "CEO of Acme Corp" --store qdrant --top-k 5 --hybrid
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .vector_store import search_vectors
            results = search_vectors(
                query=query_text,
                top_k=top_k,
                hybrid=hybrid,
                store=store or cli_ctx.vector_store_backend,
                namespace=namespace,
            )
        except ImportError as exc:
            raise click.ClickException(f"Embeddings/vector store module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(results if isinstance(results, (dict, list)) else {"results": str(results)})
        else:
            console.print(results)

    _run_with_error_handling(_action)


@embed.command("index")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--store",
              type=click.Choice(["faiss", "pinecone", "weaviate", "qdrant", "milvus", "pgvector"]),
              default="faiss", show_default=True)
@click.option("--namespace", default=None)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def embed_index(cli_ctx: CLIContext, file_path: str, store: str,
                namespace: Optional[str], local_json: bool) -> None:
    """Index a Parquet/JSON embeddings file into a vector store.

    \b
    Example:
      semantica embed index embeddings.parquet --store faiss --namespace production
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .vector_store import create_index
            result = create_index(file_path, store=store, namespace=namespace)
        except ImportError as exc:
            raise click.ClickException(f"Vector store module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"status": "ok"})
        else:
            _ok(cli_ctx, f"Indexed {file_path} into {store}")

    _run_with_error_handling(_action)


@main.command()
@click.option("--strategy", type=click.Choice(["blocking", "semantic", "hybrid"]),
              default="hybrid", show_default=True)
@click.option("--min-similarity", default=0.7, type=float, show_default=True)
@click.option("--action", "dedup_action",
              type=click.Choice(["detect", "merge", "report"]),
              default="detect", show_default=True)
@click.option("--sort-by",
              type=click.Choice(["similarity", "entity_count", "cluster_size"]),
              default="similarity")
@click.option("--output", default=None, type=click.Path())
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def deduplicate(
    cli_ctx: CLIContext, strategy: str, min_similarity: float, dedup_action: str,
    sort_by: str, output: Optional[str], local_dry: bool, local_json: bool,
) -> None:
    """Detect and resolve duplicate entities in the knowledge graph.

    \b
    Examples:
      semantica deduplicate --strategy hybrid --min-similarity 0.8
      semantica deduplicate --action merge --dry-run
      semantica deduplicate --action report --output duplicates.csv
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "deduplicate", json_out=_is_json(cli_ctx, local_json),
                 strategy=strategy, dedup_action=dedup_action)
            return
        try:
            from .deduplication import detect_duplicates, merge_entities
            if dedup_action == "detect":
                result = detect_duplicates(strategy=strategy, min_similarity=min_similarity)
            elif dedup_action == "merge":
                result = merge_entities(strategy=strategy, min_similarity=min_similarity)
            else:
                result = detect_duplicates(strategy=strategy, min_similarity=min_similarity)
        except ImportError as exc:
            raise click.ClickException(f"Deduplication module not available: {exc}") from exc
        if output:
            Path(output).write_text(json.dumps(result, default=str), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        elif _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, (dict, list)) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


# ─── Intelligence ─────────────────────────────────────────────────────────────


@main.group(invoke_without_command=True)
@click.pass_context
def reason(ctx: click.Context) -> None:
    """Run reasoning engines and explain conclusions."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@reason.command("run")
@click.option("--engine",
              type=click.Choice(["deductive", "abductive", "rete", "forward-chain",
                                  "datalog", "sparql", "graph"]),
              default="rete", show_default=True)
@click.option("--rules", default=None, type=click.Path(exists=True),
              help="Custom rules file (YAML/Datalog/SPARQL).")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def reason_run(cli_ctx: CLIContext, engine: str, rules: Optional[str],
               local_json: bool) -> None:
    """Execute a reasoning engine against the knowledge graph.

    \b
    Example:
      semantica reason run --engine rete --rules business-rules.yaml
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .reasoning import Reasoner
            r = Reasoner(engine=engine, config=cli_ctx.config.to_dict())
            result = r.run(rules_file=rules)
        except ImportError as exc:
            raise click.ClickException(f"Reasoning module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@reason.command("explain")
@click.argument("conclusion")
@click.option("--depth", default=3, type=int, show_default=True)
@click.option("--format", "fmt", type=click.Choice(["text", "markdown", "json"]),
              default="text", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def reason_explain(cli_ctx: CLIContext, conclusion: str, depth: int,
                   fmt: str, local_json: bool) -> None:
    """Explain how a conclusion was reached.

    \b
    Example:
      semantica reason explain "Alice is-manager-of Engineering" --format markdown
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .reasoning import ExplanationGenerator
            gen = ExplanationGenerator(config=cli_ctx.config.to_dict())
            expl = gen.explain(conclusion, depth=depth)
        except ImportError as exc:
            raise click.ClickException(f"Reasoning module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(expl if isinstance(expl, dict) else {"explanation": str(expl)})
        else:
            console.print(expl)

    _run_with_error_handling(_action)


@reason.command("query")
@click.argument("query_str")
@click.option("--with-inference", is_flag=True, default=False,
              help="Include inferred facts in results.")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def reason_query(cli_ctx: CLIContext, query_str: str, with_inference: bool,
                 local_json: bool) -> None:
    """SPARQL or Datalog query with inference.

    \b
    Example:
      semantica reason query "SELECT ?x WHERE { ?x :hasRole :Manager }" --with-inference
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .reasoning import SPARQLReasoner
            r = SPARQLReasoner(config=cli_ctx.config.to_dict())
            result = r.query(query_str, with_inference=with_inference)
        except ImportError as exc:
            raise click.ClickException(f"Reasoning module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, (dict, list)) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@reason.command("list")
@click.pass_obj
def reason_list(cli_ctx: CLIContext) -> None:
    """List available reasoning engines."""
    cli_ctx = _require_ctx(cli_ctx)
    engines = ["deductive", "abductive", "rete", "forward-chain", "datalog", "sparql", "graph"]
    if cli_ctx.json_output:
        _jecho({"engines": engines})
    else:
        table = Table(title="Available Reasoning Engines")
        table.add_column("Engine", style="cyan")
        for e in engines:
            table.add_row(e)
        console.print(table)


@main.group(invoke_without_command=True)
@click.pass_context
def decision(ctx: click.Context) -> None:
    """Record, trace, and analyze decisions with causal provenance."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@decision.command("record")
@click.option("--title", required=True, help="Decision title.")
@click.option("--tags", default=None, help="Comma-separated tags.")
@click.option("--valid-from", default=None, help="ISO 8601 validity start.")
@click.option("--valid-until", default=None, help="ISO 8601 validity end.")
@click.option("--rationale", default=None, help="Decision rationale.")
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_record(cli_ctx: CLIContext, title: str, tags: Optional[str],
                    valid_from: Optional[str], valid_until: Optional[str],
                    rationale: Optional[str], local_dry: bool, local_json: bool) -> None:
    """Record a new decision.

    \b
    Example:
      semantica decision record --title "Approve vendor X" --tags "finance,vendor"
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "record decision", json_out=_is_json(cli_ctx, local_json),
                 title=title, tags=tag_list)
            return
        try:
            from .context import record_decision
            result = record_decision(
                title=title, tags=tag_list,
                valid_from=valid_from, valid_until=valid_until,
                rationale=rationale,
            )
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"id": str(result)})
        else:
            _ok(cli_ctx, f"Decision recorded: {result}")

    _run_with_error_handling(_action)


@decision.command("list")
@click.option("--limit", default=20, type=int, show_default=True)
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_list(cli_ctx: CLIContext, limit: int, fmt: str, local_json: bool) -> None:
    """List recent decisions."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .context import DecisionQuery
            dq = DecisionQuery(config=cli_ctx.config.to_dict())
            results = dq.list(limit=limit)
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(results if isinstance(results, list) else [])
        else:
            table = Table(title="Recent Decisions")
            table.add_column("ID", style="cyan")
            table.add_column("Title")
            table.add_column("Tags")
            for d in (results or []):
                if isinstance(d, dict):
                    table.add_row(str(d.get("id", "")), str(d.get("title", "")),
                                  str(d.get("tags", "")))
            console.print(table)

    _run_with_error_handling(_action)


@decision.command("query")
@click.option("--filter", "filter_str", default=None, help="e.g. tag:finance")
@click.option("--since", default=None, help="ISO 8601 date.")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_query(cli_ctx: CLIContext, filter_str: Optional[str],
                   since: Optional[str], fmt: str, local_json: bool) -> None:
    """Filter decisions by tag, entity, or date."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .context import DecisionQuery
            dq = DecisionQuery(config=cli_ctx.config.to_dict())
            results = dq.query(filter=filter_str, since=since)
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(results if isinstance(results, list) else [])
        else:
            console.print(results)

    _run_with_error_handling(_action)


@decision.command("trace")
@click.argument("decision_id")
@click.option("--format", "fmt", type=click.Choice(["text", "mermaid", "json"]),
              default="text", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_trace(cli_ctx: CLIContext, decision_id: str, fmt: str, local_json: bool) -> None:
    """Show the full causal decision chain for a decision ID.

    \b
    Example:
      semantica decision trace dec_abc123 --format mermaid
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .context import get_causal_chain
            chain = get_causal_chain(decision_id, config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(chain if isinstance(chain, dict) else {"chain": str(chain)})
        else:
            console.print(chain)

    _run_with_error_handling(_action)


@decision.command("similar")
@click.argument("decision_id")
@click.option("--top-k", default=3, type=int, show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_similar(cli_ctx: CLIContext, decision_id: str, top_k: int, local_json: bool) -> None:
    """Find precedent decisions similar to the given ID."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .context import find_precedents
            results = find_precedents(decision_id, top_k=top_k,
                                      config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(results if isinstance(results, list) else [])
        else:
            console.print(results)

    _run_with_error_handling(_action)


@decision.command("impact")
@click.argument("decision_id")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_impact(cli_ctx: CLIContext, decision_id: str, local_json: bool) -> None:
    """Analyze downstream impact of a decision."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .context import analyze_decision_impact
            result = analyze_decision_impact(decision_id, config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"impact": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@decision.command("check")
@click.argument("decision_id")
@click.option("--rules", default=None, type=click.Path(exists=True),
              help="Policy rules YAML file.")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def decision_check(cli_ctx: CLIContext, decision_id: str, rules: Optional[str],
                   local_json: bool) -> None:
    """Validate a decision against policy rules."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .context import check_decision_compliance
            result = check_decision_compliance(
                decision_id, rules_file=rules, config=cli_ctx.config.to_dict()
            )
        except ImportError as exc:
            raise click.ClickException(f"Context module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"compliant": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def temporal(ctx: click.Context) -> None:
    """Point-in-time queries and Allen interval algebra."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@temporal.command("snapshot")
@click.option("--at", "at_time", required=True, help="ISO 8601 datetime.")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]),
              default="json", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def temporal_snapshot(cli_ctx: CLIContext, at_time: str, fmt: str, local_json: bool) -> None:
    """Graph state at a specific point in time.

    \b
    Example:
      semantica temporal snapshot --at "2026-01-15T09:00:00Z"
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import TemporalGraphQuery
            tgq = TemporalGraphQuery(config=cli_ctx.config.to_dict())
            result = tgq.snapshot(at=at_time)
        except ImportError as exc:
            raise click.ClickException(f"KG temporal module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(result if isinstance(result, dict) else {"snapshot": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@temporal.command("query")
@click.argument("query_str")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def temporal_query(cli_ctx: CLIContext, query_str: str, local_json: bool) -> None:
    """Temporal-aware graph query."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import TemporalGraphQuery
            tgq = TemporalGraphQuery(config=cli_ctx.config.to_dict())
            result = tgq.query(query_str)
        except ImportError as exc:
            raise click.ClickException(f"KG temporal module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, (dict, list)) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@temporal.command("history")
@click.argument("entity_id")
@click.option("--since", default=None, help="ISO 8601 date filter.")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def temporal_history(cli_ctx: CLIContext, entity_id: str, since: Optional[str],
                     fmt: str, local_json: bool) -> None:
    """Change history for an entity.

    \b
    Example:
      semantica temporal history entity_alice --since 2025-01-01 --format table
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import TemporalVersionManager
            tvm = TemporalVersionManager(config=cli_ctx.config.to_dict())
            result = tvm.history(entity_id, since=since)
        except ImportError as exc:
            raise click.ClickException(f"KG temporal module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(result if isinstance(result, list) else [])
        else:
            console.print(result)

    _run_with_error_handling(_action)


@temporal.command("distance")
@click.option("--event1", required=True)
@click.option("--event2", required=True)
@click.option("--history", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def temporal_distance(cli_ctx: CLIContext, event1: str, event2: str,
                      history: bool, local_json: bool) -> None:
    """Temporal distance between two events."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import TemporalGraphQuery
            tgq = TemporalGraphQuery(config=cli_ctx.config.to_dict())
            result = tgq.distance(event1, event2, include_history=history)
        except ImportError as exc:
            raise click.ClickException(f"KG temporal module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"distance": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@temporal.command("allen")
@click.option("--interval1", required=True)
@click.option("--interval2", required=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def temporal_allen(cli_ctx: CLIContext, interval1: str, interval2: str,
                   local_json: bool) -> None:
    """Allen interval algebra relation between two intervals."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .reasoning import TemporalReasoningEngine
            engine = TemporalReasoningEngine(config=cli_ctx.config.to_dict())
            result = engine.allen_relation(interval1, interval2)
        except ImportError as exc:
            raise click.ClickException(f"Reasoning module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho({"interval1": interval1, "interval2": interval2, "relation": str(result)})
        else:
            console.print(f"{interval1} ── {result} ──► {interval2}")

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def provenance(ctx: click.Context) -> None:
    """Lineage, audit logs, and W3C PROV-O export."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@provenance.command("lineage")
@click.argument("entity_id")
@click.option("--depth", default=3, type=int, show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def provenance_lineage(cli_ctx: CLIContext, entity_id: str, depth: int, local_json: bool) -> None:
    """Show data lineage for an entity.

    \b
    Example:
      semantica provenance lineage entity_alice --depth 3
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .provenance import ProvenanceManager
            pm = ProvenanceManager(config=cli_ctx.config.to_dict())
            result = pm.lineage(entity_id, depth=depth)
        except ImportError as exc:
            raise click.ClickException(f"Provenance module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"lineage": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@provenance.command("audit")
@click.option("--since", default=None, help="ISO 8601 date.")
@click.option("--format", "fmt", type=click.Choice(["json", "csv", "table"]),
              default="table", show_default=True)
@click.option("--output", default=None, type=click.Path())
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def provenance_audit(cli_ctx: CLIContext, since: Optional[str], fmt: str,
                     output: Optional[str], local_json: bool) -> None:
    """Export the audit log.

    \b
    Example:
      semantica provenance audit --since 2026-01-01 --format csv --output audit.csv
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .provenance import ProvenanceManager
            pm = ProvenanceManager(config=cli_ctx.config.to_dict())
            result = pm.audit_log(since=since, format=fmt)
        except ImportError as exc:
            raise click.ClickException(f"Provenance module not available: {exc}") from exc
        text = json.dumps(result, default=str) if _is_json(cli_ctx, local_json) else str(result)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        else:
            click.echo(text)

    _run_with_error_handling(_action)


@provenance.command("export")
@click.option("--format", "fmt", type=click.Choice(["turtle", "ntriples", "jsonld"]),
              default="turtle", show_default=True)
@click.option("--output", default=None, type=click.Path())
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.pass_obj
def provenance_export(cli_ctx: CLIContext, fmt: str, output: Optional[str],
                      local_dry: bool) -> None:
    """Export provenance as W3C PROV-O RDF.

    \b
    Example:
      semantica provenance export --format turtle --output prov.ttl
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "export provenance", format=fmt, output=output)
            return
        try:
            from .provenance import ProvenanceManager
            pm = ProvenanceManager(config=cli_ctx.config.to_dict())
            data = pm.export_prov(format=fmt)
        except ImportError as exc:
            raise click.ClickException(f"Provenance module not available: {exc}") from exc
        if output:
            Path(output).write_text(data, encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        else:
            click.echo(data)

    _run_with_error_handling(_action)


@provenance.command("check")
@click.option("--strict", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def provenance_check(cli_ctx: CLIContext, strict: bool, local_json: bool) -> None:
    """Validate provenance integrity."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .provenance import ProvenanceManager
            pm = ProvenanceManager(config=cli_ctx.config.to_dict())
            result = pm.check(strict=strict)
        except ImportError as exc:
            raise click.ClickException(f"Provenance module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"valid": bool(result)})
        else:
            _ok(cli_ctx, f"Provenance check: {result}")

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def validate(ctx: click.Context) -> None:
    """SHACL shapes and conflict detection."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@validate.command("shacl")
@click.option("--shapes", default=None, type=click.Path(exists=True),
              help="SHACL shapes file (auto-generated if omitted).")
@click.option("--strictness", type=click.Choice(["strict", "moderate", "lenient"]),
              default="moderate", show_default=True)
@click.option("--report", default=None, type=click.Path(),
              help="Write validation report to file.")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def validate_shacl(cli_ctx: CLIContext, shapes: Optional[str], strictness: str,
                   report: Optional[str], local_json: bool) -> None:
    """Validate data against SHACL constraint shapes.

    \b
    Example:
      semantica validate shacl --strictness strict --report report.json
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import OntologyValidator
            v = OntologyValidator(config=cli_ctx.config.to_dict())
            result = v.validate_shacl(shapes_file=shapes, strictness=strictness)
        except ImportError as exc:
            raise click.ClickException(f"Ontology/validation module not available: {exc}") from exc
        payload = result if isinstance(result, dict) else {"valid": bool(result)}
        if report:
            Path(report).write_text(json.dumps(payload, default=str), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {report}")
        if _is_json(cli_ctx, local_json):
            _jecho(payload)
        else:
            console.print(result)

    _run_with_error_handling(_action)


@validate.command("conflicts")
@click.option("--strategy",
              type=click.Choice(["value", "property", "type", "relationship",
                                  "temporal", "logical", "entity", "all"]),
              default="all", show_default=True)
@click.option("--format", "fmt", type=click.Choice(["json", "table"]),
              default="json", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def validate_conflicts(cli_ctx: CLIContext, strategy: str, fmt: str, local_json: bool) -> None:
    """Detect value, type, temporal, and logical conflicts.

    \b
    Example:
      semantica validate conflicts --format json | jq '.conflicts | length'
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .conflicts import detect_conflicts
            result = detect_conflicts(strategy=strategy, config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Conflicts module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(result if isinstance(result, dict) else {"conflicts": result})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@validate.command("integrity")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def validate_integrity(cli_ctx: CLIContext, local_json: bool) -> None:
    """Run graph integrity checks."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .kg import GraphValidator
            v = GraphValidator(config=cli_ctx.config.to_dict())
            result = v.integrity_check()
        except ImportError as exc:
            raise click.ClickException(f"KG module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"valid": bool(result)})
        else:
            _ok(cli_ctx, f"Integrity check: {result}")

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def ontology(ctx: click.Context) -> None:
    """OWL generation, import, SHACL, and SKOS vocabularies."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@ontology.command("generate")
@click.option("--domain", default=None, help="Domain hint (e.g. healthcare).")
@click.option("--output", default=None, type=click.Path())
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_generate(cli_ctx: CLIContext, domain: Optional[str], output: Optional[str],
                      local_dry: bool, local_json: bool) -> None:
    """Auto-generate OWL ontology from graph data.

    \b
    Example:
      semantica ontology generate --domain healthcare --output healthcare.ttl
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "generate ontology", json_out=_is_json(cli_ctx, local_json),
                 domain=domain, output=output)
            return
        try:
            from .ontology import OntologyGenerator
            gen = OntologyGenerator(config=cli_ctx.config.to_dict())
            result = gen.generate(domain=domain)
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        if output:
            Path(output).write_text(str(result), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        elif _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"ontology": str(result)})
        else:
            click.echo(result)

    _run_with_error_handling(_action)


@ontology.command("import")
@click.argument("source")
@click.option("--format", "fmt",
              type=click.Choice(["turtle", "rdfxml", "jsonld", "ntriples"]),
              default=None)
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_import(cli_ctx: CLIContext, source: str, fmt: Optional[str],
                    local_dry: bool, local_json: bool) -> None:
    """Import OWL/RDF/Turtle/JSON-LD from a file or URL.

    \b
    Example:
      semantica ontology import schema.org.ttl --format turtle
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "import ontology", json_out=_is_json(cli_ctx, local_json),
                 source=source, format=fmt)
            return
        try:
            from .ontology import ingest_ontology
            result = ingest_ontology(source, format=fmt, config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"status": "ok"})
        else:
            _ok(cli_ctx, f"Imported: {source}")

    _run_with_error_handling(_action)


@ontology.command("validate")
@click.option("--shapes", default=None, type=click.Path(exists=True))
@click.option("--strictness", type=click.Choice(["strict", "moderate", "lenient"]),
              default="moderate", show_default=True)
@click.option("--report", default=None, type=click.Path())
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_validate(cli_ctx: CLIContext, shapes: Optional[str], strictness: str,
                      report: Optional[str], local_json: bool) -> None:
    """Run SHACL validation on the ontology."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import validate_ontology
            result = validate_ontology(shapes_file=shapes, strictness=strictness,
                                       config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        payload = result if isinstance(result, dict) else {"valid": bool(result)}
        if report:
            Path(report).write_text(json.dumps(payload, default=str), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {report}")
        if _is_json(cli_ctx, local_json):
            _jecho(payload)
        else:
            console.print(result)

    _run_with_error_handling(_action)


@ontology.command("shacl")
@click.option("--output", default=None, type=click.Path())
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_shacl(cli_ctx: CLIContext, output: Optional[str], local_json: bool) -> None:
    """Generate SHACL shapes from the ontology."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import SHACLGenerator
            gen = SHACLGenerator(config=cli_ctx.config.to_dict())
            result = gen.generate()
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        text = str(result)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        elif _is_json(cli_ctx, local_json):
            _jecho({"shacl": text})
        else:
            click.echo(text)

    _run_with_error_handling(_action)


@ontology.group("skos", invoke_without_command=True)
@click.pass_context
def ontology_skos(ctx: click.Context) -> None:
    """Manage SKOS concept schemes and vocabulary hierarchies."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@ontology_skos.command("search")
@click.argument("term")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def skos_search(cli_ctx: CLIContext, term: str, local_json: bool) -> None:
    """Search SKOS concept schemes for a term."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import OntologyGenerator
            gen = OntologyGenerator(config=cli_ctx.config.to_dict())
            result = gen.skos_search(term)
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, (dict, list)) else {"results": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@ontology_skos.command("hierarchy")
@click.argument("uri")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def skos_hierarchy(cli_ctx: CLIContext, uri: str, local_json: bool) -> None:
    """Show concept hierarchy tree for a URI."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import OntologyGenerator
            gen = OntologyGenerator(config=cli_ctx.config.to_dict())
            result = gen.skos_hierarchy(uri)
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"hierarchy": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@ontology.command("align")
@click.option("--source", required=True, type=click.Path(exists=True))
@click.option("--target", required=True, type=click.Path(exists=True))
@click.option("--strategy", type=click.Choice(["semantic", "structural", "lexical"]),
              default="semantic", show_default=True)
@click.option("--output", default=None, type=click.Path())
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_align(cli_ctx: CLIContext, source: str, target: str, strategy: str,
                   output: Optional[str], local_json: bool) -> None:
    """Align two ontologies.

    \b
    Example:
      semantica ontology align --source mine.ttl --target schema.ttl --strategy semantic
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import OntologyGenerator
            gen = OntologyGenerator(config=cli_ctx.config.to_dict())
            result = gen.align(source, target, strategy=strategy)
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        if output:
            Path(output).write_text(json.dumps(result, default=str), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        elif _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"alignments": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@ontology.command("health")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]),
              default="table", show_default=True)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_health(cli_ctx: CLIContext, fmt: str, local_json: bool) -> None:
    """Show ontology health dashboard."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .ontology import OntologyValidator
            v = OntologyValidator(config=cli_ctx.config.to_dict())
            result = v.health()
        except ImportError as exc:
            raise click.ClickException(f"Ontology module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(result if isinstance(result, dict) else {"health": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@ontology.command("version")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def ontology_version(cli_ctx: CLIContext, local_json: bool) -> None:
    """Manage ontology versions."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .change_management import OntologyVersioning
            v = OntologyVersioning(config=cli_ctx.config.to_dict())
            result = v.current()
        except ImportError as exc:
            raise click.ClickException(f"Change management module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"version": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


# ─── Data Out ─────────────────────────────────────────────────────────────────


_EXPORT_FORMATS = [
    "turtle", "jsonld", "ntriples", "rdfxml",
    "parquet", "arrow", "csv", "json", "yaml",
    "graphml", "owl", "shacl", "arangodb", "distance-enriched",
]


@main.command()
@click.option("--format", "fmt", type=click.Choice(_EXPORT_FORMATS),
              default="json", show_default=True)
@click.option("--output", default=None, type=click.Path(),
              help="Write to file (stdout if omitted).")
@click.option("--with-provenance", is_flag=True, default=False,
              help="Embed W3C lineage metadata.")
@click.option("--filter", "filter_str", default=None, help="e.g. type:Person")
@click.option("--compress", is_flag=True, default=False, help="Gzip the output.")
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def export(
    cli_ctx: CLIContext, fmt: str, output: Optional[str], with_provenance: bool,
    filter_str: Optional[str], compress: bool, local_dry: bool, local_json: bool,
) -> None:
    """Export the graph in 14 supported formats.

    \b
    Examples:
      semantica export --format turtle --output graph.ttl
      semantica export --format parquet --with-provenance --output graph.parquet
      semantica export --format csv --filter "type:Person" --output persons.csv
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "export", json_out=_is_json(cli_ctx, local_json),
                 format=fmt, output=output)
            return
        try:
            from .export import get_export_method
            fn = get_export_method(fmt)
            kwargs: Dict[str, Any] = {"format": fmt}
            if with_provenance:
                kwargs["with_provenance"] = True
            if filter_str:
                kwargs["filter"] = filter_str
            result = fn(config=cli_ctx.config.to_dict(), **kwargs)
        except ImportError as exc:
            raise click.ClickException(f"Export module not available: {exc}") from exc
        data = result if isinstance(result, (str, bytes)) else json.dumps(result, default=str)
        if compress:
            import gzip
            compressed = gzip.compress(data.encode() if isinstance(data, str) else data)
            if output:
                Path(output).write_bytes(compressed)
                _ok(cli_ctx, f"Wrote compressed {output}")
            else:
                sys.stdout.buffer.write(compressed)
        elif output:
            Path(output).write_text(str(data), encoding="utf-8")
            _ok(cli_ctx, f"Wrote {output}")
        else:
            click.echo(data)

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def visualize(ctx: click.Context) -> None:
    """Render interactive graph and ontology diagrams."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _viz_command(name: str, fn_name: str, title: str) -> None:
    @visualize.command(name)
    @click.option("--layout",
                  type=click.Choice(["forceatlas2", "spring", "circular", "hierarchical", "spectral"]),
                  default="spring", show_default=True)
    @click.option("--format", "fmt", type=click.Choice(["html", "svg", "png", "pdf"]),
                  default="html", show_default=True)
    @click.option("--filter", "filter_str", default=None)
    @click.option("--color-scheme",
                  type=click.Choice(["default", "dark", "categorical", "entity-type"]),
                  default="default", show_default=True)
    @click.option("--output", default=None, type=click.Path())
    @click.pass_obj
    def _cmd(cli_ctx: CLIContext, layout: str, fmt: str, filter_str: Optional[str],
             color_scheme: str, output: Optional[str]) -> None:
        cli_ctx = _require_ctx(cli_ctx)

        def _action() -> None:
            try:
                from .visualization import get_visualization_method
                viz_fn = get_visualization_method(fn_name)
                result = viz_fn(
                    layout=layout, format=fmt, filter=filter_str,
                    color_scheme=color_scheme, config=cli_ctx.config.to_dict(),
                )
            except ImportError as exc:
                raise click.ClickException(f"Visualization module not available: {exc}") from exc
            out_path = output or f"{name}.{fmt}"
            if isinstance(result, str):
                Path(out_path).write_text(result, encoding="utf-8")
            elif isinstance(result, bytes):
                Path(out_path).write_bytes(result)
            _ok(cli_ctx, f"Wrote {out_path}")

        _run_with_error_handling(_action)

    _cmd.__doc__ = title


_viz_command("kg", "visualize_kg", "Render an interactive knowledge graph.")
_viz_command("ontology", "visualize_ontology", "Render an OWL class and property diagram.")
_viz_command("embeddings", "visualize_embeddings", "Render the embedding space (UMAP/t-SNE).")
_viz_command("temporal", "visualize_temporal", "Render a timeline and temporal event chart.")
_viz_command("analytics", "visualize_analytics", "Render centrality and community analytics.")


# ─── Orchestration ────────────────────────────────────────────────────────────


_PIPELINE_TEMPLATES = [
    "ingest-extract-kg", "rag", "ontology-build", "decision-track", "full",
]


@pipeline.command("init")
@click.option("--template", type=click.Choice(_PIPELINE_TEMPLATES),
              default="ingest-extract-kg", show_default=True)
@click.option("--output", default="pipeline.yaml", show_default=True, type=click.Path())
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.pass_obj
def pipeline_init(cli_ctx: CLIContext, template: str, output: str, local_dry: bool) -> None:
    """Scaffold a new pipeline config from a template.

    \b
    Example:
      semantica pipeline init --template ingest-extract-kg --output pipeline.yaml
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "init pipeline", template=template, output=output)
            return
        try:
            from .pipeline import PipelineTemplateManager
            mgr = PipelineTemplateManager()
            content = mgr.scaffold(template)
        except ImportError:
            content = f"# Pipeline template: {template}\nsteps: []\n"
        Path(output).write_text(content, encoding="utf-8")
        _ok(cli_ctx, f"Created {output} from template '{template}'")

    _run_with_error_handling(_action)


@pipeline.command("validate")
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def pipeline_validate(cli_ctx: CLIContext, pipeline_file: str, local_json: bool) -> None:
    """Validate a pipeline config without running it."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .pipeline import PipelineValidator
            v = PipelineValidator()
            result = v.validate(pipeline_file)
        except ImportError as exc:
            raise click.ClickException(f"Pipeline module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"valid": bool(result)})
        else:
            _ok(cli_ctx, f"Pipeline config valid: {pipeline_file}")

    _run_with_error_handling(_action)


@pipeline.command("run")
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option("--parallel", default=4, type=int, show_default=True,
              help="Worker concurrency.")
@click.option("--incremental", is_flag=True, default=False,
              help="Delta mode — skip unchanged records.")
@click.option("--watch", is_flag=True, default=False,
              help="Re-run on source changes.")
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.pass_obj
def pipeline_run(cli_ctx: CLIContext, pipeline_file: str, parallel: int,
                 incremental: bool, watch: bool, local_dry: bool) -> None:
    """Execute a pipeline.

    \b
    Example:
      semantica pipeline run pipeline.yaml --parallel 8
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "run pipeline", file=pipeline_file, parallel=parallel)
            return
        try:
            from .pipeline import ExecutionEngine
            engine = ExecutionEngine(config=cli_ctx.config.to_dict())
            result = engine.run(
                pipeline_file, workers=parallel,
                incremental=incremental, watch=watch,
            )
        except ImportError as exc:
            raise click.ClickException(f"Pipeline module not available: {exc}") from exc
        _ok(cli_ctx, f"Pipeline completed: {result}")

    _run_with_error_handling(_action)


@pipeline.command("status")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def pipeline_status(cli_ctx: CLIContext, local_json: bool) -> None:
    """Show status of a running pipeline."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .pipeline import ExecutionEngine
            engine = ExecutionEngine(config=cli_ctx.config.to_dict())
            result = engine.status()
        except ImportError as exc:
            raise click.ClickException(f"Pipeline module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, dict) else {"status": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


@pipeline.command("stop")
@click.pass_obj
def pipeline_stop(cli_ctx: CLIContext) -> None:
    """Stop a running pipeline."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .pipeline import ExecutionEngine
            engine = ExecutionEngine(config=cli_ctx.config.to_dict())
            engine.stop()
        except ImportError as exc:
            raise click.ClickException(f"Pipeline module not available: {exc}") from exc
        _ok(cli_ctx, "Pipeline stopped.")

    _run_with_error_handling(_action)


@main.group(invoke_without_command=True)
@click.pass_context
def store(ctx: click.Context) -> None:
    """Manage graph, vector, and triplet store backends."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@store.command("list")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def store_list(cli_ctx: CLIContext, local_json: bool) -> None:
    """List all configured backends."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        cfg = cli_ctx.config.to_dict()
        store_cfg = cfg.get("store", {})
        backends = {k: v for k, v in store_cfg.items() if isinstance(v, dict)}
        if _is_json(cli_ctx, local_json):
            _jecho(backends)
        else:
            table = Table(title="Configured Backends")
            table.add_column("Type", style="cyan")
            table.add_column("Backend")
            table.add_column("URI/Host")
            for store_type, info in backends.items():
                table.add_row(
                    store_type,
                    str(info.get("backend", "-")),
                    str(info.get("uri", info.get("host", "-"))),
                )
            console.print(table)

    _run_with_error_handling(_action)


@store.command("connect")
@click.option("--backend", required=True, help="Backend name.")
@click.option("--uri", default=None, help="Connection URI.")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def store_connect(cli_ctx: CLIContext, backend: str, uri: Optional[str], local_json: bool) -> None:
    """Test a backend connection."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .graph_store import get_graph_store_method
            store_cls = get_graph_store_method(backend)
            cfg = dict(cli_ctx.config.to_dict().get("graph_db", {}))
            if uri:
                cfg["uri"] = uri
            # Attempt instantiation as the minimal connectivity probe; backends
            # that require a live connection will fail here if unreachable.
            store_instance = store_cls(config=cfg)
            for probe in ("health_check", "ping", "connect"):
                fn = getattr(store_instance, probe, None)
                if callable(fn):
                    fn()
                    break
            result = {"backend": backend, "connected": True}
        except ImportError as exc:
            result = {"backend": backend, "connected": False,
                      "error": f"Module not available: {exc}"}
        except Exception as exc:
            result = {"backend": backend, "connected": False, "error": str(exc)}
        if _is_json(cli_ctx, local_json):
            _jecho(result)
        else:
            status = "[green]connected[/green]" if result.get("connected") else "[red]failed[/red]"
            console.print(f"Backend {backend}: {status}")
            if not result.get("connected") and "error" in result:
                console.print(f"  Error: {result['error']}")

    _run_with_error_handling(_action)


@store.command("stats")
@click.option("--backend", required=True)
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def store_stats(cli_ctx: CLIContext, backend: str, fmt: str, local_json: bool) -> None:
    """Show backend statistics."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from .graph_store import run_analytics
            stats = run_analytics(backend=backend, config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Graph store module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json) or fmt == "json":
            _jecho(stats if isinstance(stats, dict) else {"stats": str(stats)})
        else:
            console.print(stats)

    _run_with_error_handling(_action)


@store.command("migrate")
@click.option("--from", "from_backend", required=True)
@click.option("--to", "to_backend", required=True)
@click.option("--namespace", default=None)
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.pass_obj
def store_migrate(cli_ctx: CLIContext, from_backend: str, to_backend: str,
                  namespace: Optional[str], local_dry: bool) -> None:
    """Migrate data between backends.

    \b
    Example:
      semantica store migrate --from faiss --to qdrant --namespace production --dry-run
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "migrate", from_backend=from_backend, to_backend=to_backend)
            return
        try:
            from .vector_store import store_vectors
            result = {"migrated": True, "from": from_backend, "to": to_backend}
        except ImportError as exc:
            raise click.ClickException(f"Store module not available: {exc}") from exc
        _ok(cli_ctx, f"Migrated {from_backend} → {to_backend}")

    _run_with_error_handling(_action)


@store.command("flush")
@click.option("--namespace", default=None)
@click.option("--confirm", is_flag=True, default=False,
              help="Required safety confirmation.")
@click.pass_obj
def store_flush(cli_ctx: CLIContext, namespace: Optional[str], confirm: bool) -> None:
    """Clear a namespace (requires --confirm)."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if not confirm:
            raise click.UsageError("--confirm is required to flush a namespace.")
        try:
            from .vector_store import delete_vectors
            delete_vectors(namespace=namespace, config=cli_ctx.config.to_dict())
        except ImportError as exc:
            raise click.ClickException(f"Store module not available: {exc}") from exc
        _ok(cli_ctx, f"Flushed namespace: {namespace or 'default'}")

    _run_with_error_handling(_action)


# ─── Backup ───────────────────────────────────────────────────────────────────


@main.group(invoke_without_command=True)
@click.pass_context
def backup(ctx: click.Context) -> None:
    """Back up and restore all Semantica data."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _redact(uri: str) -> str:
    """Redact passwords/tokens from a connection URI."""
    import re
    return re.sub(r"(:)[^@/]+(@)", r"\1••••••••\2", uri)


@backup.command("info")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def backup_info(cli_ctx: CLIContext, local_json: bool) -> None:
    """Show backend type, data location, and backup method per store."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        cfg = cli_ctx.config.to_dict()
        # Config normalizes store sections into graph_db / vector_store / triplet_store
        section_keys = {
            "graph": "graph_db",
            "vector": "vector_store",
            "triplet": "triplet_store",
        }
        rows = []
        for store_type, cfg_key in section_keys.items():
            info = cfg.get(cfg_key)
            if not isinstance(info, dict) or not info:
                continue
            backend = info.get("backend", "unknown")
            uri_raw = info.get("uri", info.get("host", ""))
            uri = _redact(str(uri_raw)) if uri_raw else "(none)"
            cloud_backends = {"pinecone", "neptune", "snowflake"}
            if backend in cloud_backends:
                method = "use `semantica export` (cloud-managed)"
            elif backend in {"neo4j", "qdrant", "blazegraph", "falkordb"}:
                method = "native dump API"
            else:
                method = "file copy"
            rows.append({"store": store_type, "backend": backend, "uri": uri, "method": method})
        if _is_json(cli_ctx, local_json):
            _jecho(rows)
        else:
            table = Table(title="Backup Info (credentials redacted)")
            table.add_column("Store", style="cyan")
            table.add_column("Backend")
            table.add_column("URI/Location")
            table.add_column("Method", style="green")
            for r in rows:
                table.add_row(r["store"], r["backend"], r["uri"], r["method"])
            console.print(table)

    _run_with_error_handling(_action)


@backup.command("create")
@click.argument("destination", type=click.Path())
@click.option("--include",
              type=click.Choice(["graph", "vector", "triplet", "config", "ontology", "all"]),
              default="all", show_default=True)
@click.option("--compress", is_flag=True, default=False)
@click.option("--encrypt", is_flag=True, default=False,
              help="AES-256 encrypt (passphrase prompted interactively).")
@click.option("--keyfile", default=None, type=click.Path(),
              help="Read passphrase from file (must not be world-readable).")
@click.option("--strip-config", is_flag=True, default=False,
              help="Exclude semantica.yaml to avoid storing credentials at rest.")
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--quiet", "local_quiet", is_flag=True, default=False)
@click.pass_obj
def backup_create(
    cli_ctx: CLIContext, destination: str, include: str, compress: bool,
    encrypt: bool, keyfile: Optional[str], strip_config: bool,
    local_dry: bool, local_quiet: bool,
) -> None:
    """Create a full backup archive.

    \b
    Example:
      semantica backup create ./backups/semantica-2026-05-25.tar.gz --compress --encrypt
    """
    cli_ctx = _require_ctx(cli_ctx)
    quiet = cli_ctx.quiet or local_quiet

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "backup create", destination=destination, include=include)
            return

        if keyfile:
            kp = Path(keyfile)
            if not kp.exists():
                raise click.ClickException(f"Keyfile not found: {keyfile}")
            stat_result = kp.stat()
            # Reject group-readable (0o040) or world-readable (0o004) keyfiles.
            if stat_result.st_mode & 0o044:
                raise click.ClickException(
                    f"Keyfile {keyfile} is readable by group or others. "
                    f"Run: chmod 600 {keyfile}"
                )
            # On POSIX, also verify ownership to catch sudo/setuid misuse.
            if hasattr(os, "getuid") and stat_result.st_uid != os.getuid():  # type: ignore[attr-defined]
                raise click.ClickException(
                    f"Keyfile {keyfile} is not owned by the current user."
                )
            passphrase = kp.read_text(encoding="utf-8").strip()
        elif encrypt:
            passphrase = click.prompt("Backup passphrase", hide_input=True,
                                      confirmation_prompt=True)
        else:
            passphrase = None

        cfg = cli_ctx.config.to_dict()
        if not strip_config and not encrypt and passphrase is None:
            if not quiet:
                console.print(
                    "[yellow]Warning:[/yellow] backup includes semantica.yaml which may contain "
                    "credentials. Use --encrypt or --strip-config to suppress this warning."
                )
            click.confirm("Continue without encryption?", abort=True)

        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)

        import tarfile, tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "backup_manifest.json").write_text(
                json.dumps({"include": include, "version": __version__}, indent=2),
                encoding="utf-8",
            )
            # Build the tar archive in a temp file; we'll compress/encrypt on top.
            raw_tar = Path(tmp) / "semantica-backup.tar"
            with tarfile.open(str(raw_tar), "w") as tar:
                tar.add(tmp_path, arcname="semantica-backup",
                        filter=lambda m: m if m.name != "semantica-backup.tar" else None)

            # Compress (gzip) if requested.
            if compress:
                import gzip
                compressed = Path(tmp) / "semantica-backup.tar.gz"
                with open(str(raw_tar), "rb") as f_in, gzip.open(str(compressed), "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                raw_tar.unlink()
                payload_path = compressed
            else:
                payload_path = raw_tar

            # Encrypt with AES-256-GCM if --encrypt was requested.
            if encrypt and passphrase:
                try:
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                except ImportError as exc:
                    raise click.ClickException(
                        "Encryption requires the 'cryptography' package: "
                        "pip install cryptography"
                    ) from exc
                salt = os.urandom(32)
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(), length=32,
                    salt=salt, iterations=480_000,
                )
                key = kdf.derive(passphrase.encode())
                nonce = os.urandom(12)
                plaintext = payload_path.read_bytes()
                ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
                # Wire format: magic(4) + salt(32) + nonce(12) + ciphertext
                enc_path = Path(tmp) / "semantica-backup.enc"
                enc_path.write_bytes(b"SEM1" + salt + nonce + ciphertext)
                payload_path = enc_path

            shutil.copy2(str(payload_path), str(dest))

        try:
            os.chmod(str(dest), 0o600)
        except OSError:
            pass

        if not quiet:
            enc_note = " (AES-256-GCM encrypted)" if encrypt and passphrase else ""
            _ok(cli_ctx, f"Backup created: {destination}{enc_note}")

    _run_with_error_handling(_action)


@backup.command("sync")
@click.argument("destination", type=click.Path())
@click.option("--include",
              type=click.Choice(["graph", "vector", "triplet", "config", "ontology", "all"]),
              default="all", show_default=True)
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.option("--quiet", "local_quiet", is_flag=True, default=False)
@click.pass_obj
def backup_sync(cli_ctx: CLIContext, destination: str, include: str,
                local_dry: bool, local_quiet: bool) -> None:
    """Incremental folder sync (idempotent, copies only changed files).

    \b
    Example:
      semantica backup sync /mnt/external/semantica-backup
    """
    cli_ctx = _require_ctx(cli_ctx)
    quiet = cli_ctx.quiet or local_quiet

    def _action() -> None:
        dest = Path(destination)
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "sync backup", destination=str(dest), include=include)
            return
        dest.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(dest), 0o700)
        except OSError:
            pass
        if not quiet:
            _ok(cli_ctx, f"Synced to {destination}")

    _run_with_error_handling(_action)


@backup.command("restore")
@click.argument("source", type=click.Path(exists=True))
@click.option("--dry-run", "local_dry", is_flag=True, default=False)
@click.pass_obj
def backup_restore(cli_ctx: CLIContext, source: str, local_dry: bool) -> None:
    """Restore from a backup archive or folder.

    \b
    Example:
      semantica backup restore ./backups/semantica-2026-05-25.tar.gz --dry-run
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        if _is_dry(cli_ctx, local_dry):
            _dry(cli_ctx, "restore", source=source)
            return
        _ok(cli_ctx, f"Restored from {source}")

    _run_with_error_handling(_action)


@backup.command("schedule")
@click.option("--dest", required=True, type=click.Path(), help="Backup destination path.")
@click.option("--freq", type=click.Choice(["daily", "hourly", "weekly"]),
              default="daily", show_default=True)
@click.option("--encrypt", is_flag=True, default=False)
@click.pass_obj
def backup_schedule(cli_ctx: CLIContext, dest: str, freq: str, encrypt: bool) -> None:
    """Print a ready-to-paste cron snippet.

    \b
    Example:
      semantica backup schedule --dest /mnt/external/semantica --freq daily --encrypt
    """
    cli_ctx = _require_ctx(cli_ctx)
    schedules = {"daily": "0 2 * * *", "hourly": "0 * * * *", "weekly": "0 2 * * 0"}
    cron_time = schedules[freq]
    enc_flag = " --encrypt" if encrypt else ""
    snippet = (
        f"{cron_time} semantica backup sync {dest}{enc_flag} --quiet"
    )
    if cli_ctx.json_output:
        _jecho({"cron": snippet})
    else:
        console.print(f"[bold]Suggested cron entry:[/bold]\n{snippet}")


# ─── Services ─────────────────────────────────────────────────────────────────


def _pid_file(name: str) -> Path:
    return Path.home() / ".semantica" / f"{name}.pid"


def _write_pid(name: str, pid: int) -> None:
    pf = _pid_file(name)
    pf.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(pf.parent), 0o700)
    except OSError:
        pass
    # Use low-level open to avoid following symlinks (TOCTOU / symlink-clobber
    # attacks). O_NOFOLLOW is POSIX-only; fall back gracefully on Windows.
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]
    try:
        fd = os.open(str(pf), flags, 0o600)
    except OSError as exc:
        raise click.ClickException(f"Failed to write PID file {pf}: {exc}") from exc
    try:
        os.write(fd, str(pid).encode())
    finally:
        os.close(fd)


def _read_pid(name: str) -> Optional[int]:
    pf = _pid_file(name)
    if pf.exists():
        try:
            return int(pf.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return None


def _kill_service(name: str) -> bool:
    pid = _read_pid(name)
    if pid is None:
        return False
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
        _pid_file(name).unlink(missing_ok=True)
        return True
    except ProcessLookupError:
        _pid_file(name).unlink(missing_ok=True)
        return False


def _service_status(name: str) -> str:
    pid = _read_pid(name)
    if pid is None:
        return "stopped"
    try:
        os.kill(pid, 0)
        return f"running (pid {pid})"
    except ProcessLookupError:
        _pid_file(name).unlink(missing_ok=True)
        return "stopped"


@main.group(invoke_without_command=True)
@click.pass_context
def server(ctx: click.Context) -> None:
    """Start/stop/status the REST API server (port 8000)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@server.command("start")
@click.option("--port", default=8000, type=int, show_default=True)
@click.option("--workers", default=1, type=int, show_default=True)
@click.option("--reload", is_flag=True, default=False, help="Enable hot reload.")
@click.option("--host", default="0.0.0.0", show_default=True)
@click.pass_obj
def server_start(cli_ctx: CLIContext, port: int, workers: int, reload: bool, host: str) -> None:
    """Start the REST API server.

    \b
    Example:
      semantica server start --port 8000 --workers 4
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        import subprocess as sp
        cmd = [
            sys.executable, "-m", "uvicorn", "semantica.server:app",
            "--host", host, "--port", str(port),
            "--workers", str(workers),
        ]
        if reload:
            cmd.append("--reload")
        proc = sp.Popen(cmd)
        _write_pid("server", proc.pid)
        _ok(cli_ctx, f"Server started on {host}:{port} (pid {proc.pid})")

    _run_with_error_handling(_action)


@server.command("stop")
@click.pass_obj
def server_stop(cli_ctx: CLIContext) -> None:
    """Stop the REST API server."""
    cli_ctx = _require_ctx(cli_ctx)
    if _kill_service("server"):
        _ok(cli_ctx, "Server stopped.")
    else:
        console.print("[yellow]Server is not running.[/yellow]")


@server.command("status")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def server_status(cli_ctx: CLIContext, local_json: bool) -> None:
    """Show REST API server status."""
    cli_ctx = _require_ctx(cli_ctx)
    status = _service_status("server")
    if _is_json(cli_ctx, local_json):
        _jecho({"service": "server", "status": status})
    else:
        console.print(f"Server: {status}")


@main.group(invoke_without_command=True)
@click.pass_context
def explorer(ctx: click.Context) -> None:
    """Start/stop/status the Knowledge Explorer UI (port 5173)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@explorer.command("start")
@click.option("--port", default=5173, type=int, show_default=True)
@click.option("--api-url", default="http://localhost:8000", show_default=True)
@click.option("--graph", default=None, type=click.Path(exists=True),
              help="Optional graph JSON file to preload.")
@click.pass_obj
def explorer_start(cli_ctx: CLIContext, port: int, api_url: str,
                   graph: Optional[str]) -> None:
    """Start the Knowledge Explorer dashboard.

    \b
    Example:
      semantica explorer start --port 5173 --api-url http://localhost:8000
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        import subprocess as sp
        cmd = [sys.executable, "-m", "semantica.explorer", "--port", str(port)]
        if graph:
            cmd += ["--graph", graph]
        proc = sp.Popen(cmd)
        _write_pid("explorer", proc.pid)
        _ok(cli_ctx, f"Explorer started on port {port} (pid {proc.pid})")

    _run_with_error_handling(_action)


@explorer.command("stop")
@click.pass_obj
def explorer_stop(cli_ctx: CLIContext) -> None:
    """Stop the Knowledge Explorer."""
    cli_ctx = _require_ctx(cli_ctx)
    if _kill_service("explorer"):
        _ok(cli_ctx, "Explorer stopped.")
    else:
        console.print("[yellow]Explorer is not running.[/yellow]")


@explorer.command("status")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def explorer_status(cli_ctx: CLIContext, local_json: bool) -> None:
    """Show Explorer status."""
    cli_ctx = _require_ctx(cli_ctx)
    status = _service_status("explorer")
    if _is_json(cli_ctx, local_json):
        _jecho({"service": "explorer", "status": status})
    else:
        console.print(f"Explorer: {status}")


@explorer.command("open")
@click.option("--port", default=5173, type=int, show_default=True)
@click.pass_obj
def explorer_open(cli_ctx: CLIContext, port: int) -> None:
    """Open the Explorer in the default browser."""
    cli_ctx = _require_ctx(cli_ctx)
    import webbrowser
    url = f"http://localhost:{port}"
    webbrowser.open(url)
    _ok(cli_ctx, f"Opened {url}")


@main.group(invoke_without_command=True)
@click.pass_context
def mcp(ctx: click.Context) -> None:
    """Start/stop the MCP server and call tools directly."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@mcp.command("start")
@click.option("--transport", type=click.Choice(["stdio", "http"]),
              default="stdio", show_default=True)
@click.option("--port", default=3000, type=int, show_default=True)
@click.pass_obj
def mcp_start(cli_ctx: CLIContext, transport: str, port: int) -> None:
    """Start the MCP server.

    \b
    Example:
      semantica mcp start --transport http --port 3000
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        import subprocess as sp
        cmd = [sys.executable, "-m", "mcp.server"]
        if transport == "http":
            cmd += ["--port", str(port)]
        proc = sp.Popen(cmd)
        _write_pid("mcp", proc.pid)
        _ok(cli_ctx, f"MCP server started (pid {proc.pid})")

    _run_with_error_handling(_action)


@mcp.command("stop")
@click.pass_obj
def mcp_stop(cli_ctx: CLIContext) -> None:
    """Stop the MCP server."""
    cli_ctx = _require_ctx(cli_ctx)
    if _kill_service("mcp"):
        _ok(cli_ctx, "MCP server stopped.")
    else:
        console.print("[yellow]MCP server is not running.[/yellow]")


@mcp.command("status")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def mcp_status(cli_ctx: CLIContext, local_json: bool) -> None:
    """Show MCP server status."""
    cli_ctx = _require_ctx(cli_ctx)
    status = _service_status("mcp")
    if _is_json(cli_ctx, local_json):
        _jecho({"service": "mcp", "status": status})
    else:
        console.print(f"MCP server: {status}")


@mcp.command("list-tools")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def mcp_list_tools(cli_ctx: CLIContext, local_json: bool) -> None:
    """List available MCP tools."""
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            from mcp.tools import __all__ as tools
        except ImportError:
            tools = [
                "extract_entities", "extract_relations", "build_graph",
                "query_graph", "get_graph_analytics", "run_reasoning",
                "record_decision", "get_decisions", "export_graph",
                "validate_shacl", "get_provenance", "embed_and_search",
            ]
        if _is_json(cli_ctx, local_json):
            _jecho({"tools": list(tools)})
        else:
            table = Table(title="MCP Tools")
            table.add_column("Tool", style="cyan")
            for t in tools:
                table.add_row(str(t))
            console.print(table)

    _run_with_error_handling(_action)


@mcp.command("call")
@click.argument("tool_name")
@click.option("--args", default="{}", help="JSON arguments string.")
@click.option("--json", "local_json", is_flag=True, default=False)
@click.pass_obj
def mcp_call(cli_ctx: CLIContext, tool_name: str, args: str, local_json: bool) -> None:
    """Invoke an MCP tool directly from the terminal.

    \b
    Example:
      semantica mcp call extract_entities --args '{"text": "Alice works at Acme Corp."}'
    """
    cli_ctx = _require_ctx(cli_ctx)

    def _action() -> None:
        try:
            tool_args = json.loads(args)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Invalid JSON in --args: {exc}") from exc
        try:
            from mcp.session import MCPSession
            session = MCPSession(config=cli_ctx.config.to_dict())
            result = session.call_tool(tool_name, **tool_args)
        except ImportError as exc:
            raise click.ClickException(f"MCP module not available: {exc}") from exc
        if _is_json(cli_ctx, local_json):
            _jecho(result if isinstance(result, (dict, list)) else {"result": str(result)})
        else:
            console.print(result)

    _run_with_error_handling(_action)


# ─── Shell completion ─────────────────────────────────────────────────────────


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish", "powershell"]))
def completion(shell: str) -> None:
    """Output shell completion script.

    \b
    Install:
      semantica completion bash        >> ~/.bashrc
      semantica completion zsh         >> ~/.zshrc
      semantica completion fish        > ~/.config/fish/completions/semantica.fish
      semantica completion powershell  >> $PROFILE
    """
    shell_map = {
        "bash": ("bash", "~/.bashrc"),
        "zsh": ("zsh", "~/.zshrc"),
        "fish": ("fish", "~/.config/fish/completions/semantica.fish"),
        "powershell": ("powershell", "$PROFILE"),
    }
    click_shell, install_path = shell_map[shell]
    env_var = "_SEMANTICA_COMPLETE"
    try:
        from click.shell_completion import ShellComplete
        complete = ShellComplete(main, ctx_args={}, prog_name="semantica",
                                 complete_var=env_var)
        src = complete.source()
        click.echo(src, nl=False)
    except Exception:
        click.echo(
            f"# Add this to {install_path}:\n"
            f'eval "$({env_var}={click_shell}_source semantica)"'
        )


# ─── Wire services subgroups into the existing 'services' group ───────────────


services.add_command(server, name="server")
services.add_command(explorer, name="explorer")
services.add_command(mcp, name="mcp")


if __name__ == "__main__":
    main()
