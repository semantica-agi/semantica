"""
Semantica CLI Entry Point

This module provides the command-line interface for the Semantica framework,
enabling users to interact with the framework via terminal commands.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence

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
            # Preserve the global --log-level override so nested config
            # lookups further down the call chain respect it.
            log_level_override=cli_ctx.log_level_override,
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
@click.pass_context
def main(ctx: click.Context, config_path: Optional[str], log_level: Optional[str]):
    """Semantica - Semantic Layer & Knowledge Engineering Framework"""
    try:
        config = _build_runtime_config(config_path=config_path, log_level=log_level)
        setup_logging(config=config.get("logging", {}))
        effective_log_level = config.get("logging.level", "INFO")
        ctx.obj = CLIContext(
            config_path=config_path,
            config=config,
            log_level=effective_log_level,
            log_level_override=log_level.upper() if log_level else None,
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


if __name__ == "__main__":
    main()
