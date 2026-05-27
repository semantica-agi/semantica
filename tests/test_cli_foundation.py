import click
import pytest
from click.testing import CliRunner, Result

import semantica.cli as cli_module


@pytest.fixture
def runner() -> CliRunner:
    # Click's CliRunner captures all output in result.output by default; error
    # messages from ClickException / UsageError are included.  If the project
    # ever moves to a Click version that separates stderr (mix_stderr=False),
    # update assertions that check error text to use result.stderr instead.
    return CliRunner()


@pytest.fixture(autouse=True)
def disable_cli_logging(monkeypatch):
    monkeypatch.setattr(cli_module, "setup_logging", lambda *args, **kwargs: None)


# ---------------------------------------------------------------------------
# Help surfaces
# ---------------------------------------------------------------------------


def test_root_help_shows_expected_groups(runner):
    result = runner.invoke(cli_module.main, ["--help"])

    assert result.exit_code == 0
    assert (
        "Semantica - Semantic Layer & Knowledge Engineering Framework"
        in result.output
    )
    assert "kg" in result.output
    assert "pipeline" in result.output
    assert "services" in result.output


def test_kg_group_help_shows_build_command(runner):
    result = runner.invoke(cli_module.main, ["kg", "--help"])

    assert result.exit_code == 0
    assert "Knowledge graph and semantic build commands." in result.output
    assert "build" in result.output


def test_kg_build_help_shows_source_and_config_flags(runner):
    result = runner.invoke(cli_module.main, ["kg", "build", "--help"])

    assert result.exit_code == 0
    assert "--source" in result.output
    assert "-s" in result.output
    assert "--config" in result.output
    assert "-c" in result.output


# ---------------------------------------------------------------------------
# info command
# ---------------------------------------------------------------------------


def test_info_command_shows_framework_components(runner):
    result = runner.invoke(cli_module.main, ["info"])

    assert result.exit_code == 0
    assert "Semantica Framework" in result.output
    assert "Core Orchestrator" in result.output
    assert "CLI Log Level" in result.output


def test_info_command_shows_config_path_when_supplied(runner):
    # click.Path(resolve_path=True) turns cfg.yml into an absolute path, and
    # Rich's table may truncate long paths with '…'.  Assert the row is present
    # and the "(none)" placeholder has been replaced by some path value.
    with runner.isolated_filesystem():
        with open("cfg.yml", "w", encoding="utf-8") as handle:
            handle.write("logging:\n  level: INFO\n")

        result: Result = runner.invoke(
            cli_module.main, ["--config", "cfg.yml", "info"]
        )

        assert result.exit_code == 0
        assert "CLI Config File" in result.output
        assert "(none)" not in result.output


# ---------------------------------------------------------------------------
# Global --log-level override
# ---------------------------------------------------------------------------


def test_log_level_global_override_stores_in_context(runner, monkeypatch):
    """--log-level at the root level propagates into CLIContext."""
    captured = {}

    def fake_run_build(cli_ctx, sources):
        captured["log_level_override"] = cli_ctx.log_level_override
        captured["log_level"] = cli_ctx.log_level

    monkeypatch.setattr(cli_module, "_run_build", fake_run_build)

    result = runner.invoke(
        cli_module.main,
        ["--log-level", "DEBUG", "kg", "build", "-s", "src.txt"],
    )

    assert result.exit_code == 0
    assert captured["log_level_override"] == "DEBUG"


# ---------------------------------------------------------------------------
# Command-level config
# ---------------------------------------------------------------------------


def test_command_config_preserves_global_log_level_override(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Global --log-level is forwarded into command_ctx.log_level_override."""
    captured: dict[str, object] = {}

    def fake_run_build(cli_ctx: cli_module.CLIContext, _: object) -> None:
        captured["log_level_override"] = cli_ctx.log_level_override

    monkeypatch.setattr(cli_module, "_run_build", fake_run_build)

    with runner.isolated_filesystem():
        with open("cfg.yml", "w", encoding="utf-8") as handle:
            handle.write("logging:\n  level: INFO\n")

        result = runner.invoke(
            cli_module.main,
            ["--log-level", "DEBUG", "kg", "build", "-s", "src.txt", "-c", "cfg.yml"],
        )

    assert result.exit_code == 0
    assert captured["log_level_override"] == "DEBUG"


def test_command_config_keeps_own_logging_without_global_override(runner, monkeypatch):
    captured = {}

    def fake_run_build(cli_ctx, sources):
        captured["logging_level"] = cli_ctx.config.get("logging.level")
        captured["sources"] = list(sources)

    monkeypatch.setattr(cli_module, "_run_build", fake_run_build)

    with runner.isolated_filesystem():
        with open("cfg.yml", "w", encoding="utf-8") as handle:
            handle.write("logging:\n  level: DEBUG\n")

        result = runner.invoke(
            cli_module.main,
            ["kg", "build", "-s", "README.md", "-c", "cfg.yml"],
        )

    assert result.exit_code == 0
    assert captured["sources"] == ["README.md"]
    assert captured["logging_level"] == "DEBUG"


# ---------------------------------------------------------------------------
# Legacy / new command parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["kg", "build", "-s", "README.md"],
        ["build", "-s", "README.md"],
    ],
)
def test_build_paths_invoke_shared_wrapper(runner, monkeypatch, argv):
    captured = {}

    def fake_run_build(cli_ctx, sources):
        captured["config_path"] = cli_ctx.config_path
        captured["sources"] = list(sources)

    monkeypatch.setattr(cli_module, "_run_build", fake_run_build)

    result = runner.invoke(cli_module.main, argv)

    assert result.exit_code == 0
    assert captured["sources"] == ["README.md"]


@pytest.mark.parametrize(
    "argv",
    [
        ["kg", "build", "-s", "README.md", "-c", "cfg.yml"],
        ["kg", "build", "-s", "README.md", "--config", "cfg.yml"],
        ["build", "-s", "README.md", "-c", "cfg.yml"],
        ["build", "-s", "README.md", "--config", "cfg.yml"],
    ],
)
def test_build_config_short_and_long_flags_are_compatible(runner, monkeypatch, argv):
    captured = {}

    def fake_run_build(cli_ctx, sources):
        captured["config_path"] = cli_ctx.config_path
        captured["sources"] = list(sources)

    monkeypatch.setattr(cli_module, "_run_build", fake_run_build)

    with runner.isolated_filesystem():
        with open("cfg.yml", "w", encoding="utf-8") as handle:
            handle.write("logging:\n  level: INFO\n")

        result = runner.invoke(cli_module.main, argv)

    assert result.exit_code == 0
    assert captured["sources"] == ["README.md"]
    assert captured["config_path"] is not None


# ---------------------------------------------------------------------------
# build_knowledge_base result handling
# ---------------------------------------------------------------------------


class _MockFramework:
    """Lightweight stand-in for Semantica used to test _run_build result paths."""

    def __init__(self, return_value):
        self._return_value = return_value

    def build_knowledge_base(self, sources):
        return self._return_value


def test_build_result_with_stats_shows_source_count(runner, monkeypatch):
    """When build returns statistics.sources_processed, that count appears in output."""
    monkeypatch.setattr(
        cli_module,
        "_get_framework",
        lambda _: _MockFramework({"statistics": {"sources_processed": 3}}),
    )

    result = runner.invoke(
        cli_module.main,
        ["kg", "build", "-s", "a.txt", "-s", "b.txt", "-s", "c.txt"],
    )

    assert result.exit_code == 0
    assert "3 source(s)" in result.output


def test_build_result_without_stats_shows_generic_success(runner, monkeypatch):
    """When build result has no statistics key, generic success message is shown."""
    monkeypatch.setattr(
        cli_module,
        "_get_framework",
        lambda _: _MockFramework({}),
    )

    result = runner.invoke(cli_module.main, ["kg", "build", "-s", "src.txt"])

    assert result.exit_code == 0
    assert "Knowledge base build completed" in result.output
    assert "source(s)" not in result.output


def test_build_result_none_shows_generic_success(runner, monkeypatch):
    """When build_knowledge_base returns None, generic success message is shown."""
    monkeypatch.setattr(
        cli_module,
        "_get_framework",
        lambda _: _MockFramework(None),
    )

    result = runner.invoke(cli_module.main, ["kg", "build", "-s", "src.txt"])

    assert result.exit_code == 0
    assert "Knowledge base build completed" in result.output


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["kg", "build"],
        ["build"],
    ],
)
def test_missing_input_errors_are_clean_and_click_safe(runner, argv):
    result = runner.invoke(cli_module.main, argv)

    assert result.exit_code != 0
    assert "At least one source is required" in result.output
    assert "Traceback" not in result.output


def test_invalid_root_config_error_is_clean_and_click_safe(runner):
    with runner.isolated_filesystem():
        with open("bad.md", "w", encoding="utf-8") as handle:
            handle.write("not-a-config")

        result = runner.invoke(cli_module.main, ["--config", "bad.md", "info"])

    assert result.exit_code != 0
    assert "Unsupported configuration file format" in result.output
    assert "Traceback" not in result.output


def test_invalid_command_config_error_is_clean_and_click_safe(runner):
    with runner.isolated_filesystem():
        with open("bad.md", "w", encoding="utf-8") as handle:
            handle.write("not-a-config")

        result = runner.invoke(
            cli_module.main,
            ["kg", "build", "-s", "README.md", "-c", "bad.md"],
        )

    assert result.exit_code != 0
    assert "Unsupported configuration file format" in result.output
    assert "Traceback" not in result.output


def test_empty_yaml_config_is_accepted(runner):
    with runner.isolated_filesystem():
        with open("cfg.yml", "w", encoding="utf-8") as handle:
            handle.write("")

        result = runner.invoke(cli_module.main, ["--config", "cfg.yml", "info"])

    assert result.exit_code == 0


def test_malformed_logging_section_is_clean_and_click_safe(runner):
    with runner.isolated_filesystem():
        with open("cfg.yml", "w", encoding="utf-8") as handle:
            handle.write("logging: []\n")

        result = runner.invoke(
            cli_module.main,
            ["--config", "cfg.yml", "--log-level", "INFO", "info"],
        )

    assert result.exit_code != 0
    assert (
        "Logging configuration section must contain a mapping/object"
        in result.output
    )
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    "file_name, config_text, expected_error",
    [
        ("cfg.json", "{not-json", "Failed to parse configuration file"),
        (
            "cfg.yml",
            "- item\n- item2\n",
            "Configuration file must contain a mapping/object",
        ),
    ],
)
def test_command_config_parse_errors_are_clean_and_click_safe(
    runner,
    file_name,
    config_text,
    expected_error,
):
    with runner.isolated_filesystem():
        with open(file_name, "w", encoding="utf-8") as handle:
            handle.write(config_text)

        result = runner.invoke(
            cli_module.main,
            ["kg", "build", "-s", "README.md", "-c", file_name],
        )

    assert result.exit_code != 0
    assert expected_error in result.output
    assert "Traceback" not in result.output


def test_runtime_errors_are_click_safe_without_traceback(runner, monkeypatch):
    def boom(_cli_ctx, _sources):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "_run_build", boom)

    result = runner.invoke(cli_module.main, ["kg", "build", "-s", "README.md"])

    assert result.exit_code != 0
    assert "Unexpected error: boom" in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Lazy initialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["kg", "--help"],
        ["kg", "build", "--help"],
        ["build", "--help"],
    ],
)
def test_help_calls_do_not_initialize_framework(runner, monkeypatch, argv):
    def fail_get_framework(_):
        raise AssertionError("framework initialization must not happen on help")

    monkeypatch.setattr(cli_module, "_get_framework", fail_get_framework)

    result = runner.invoke(cli_module.main, argv)

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# _require_ctx guard
# ---------------------------------------------------------------------------


def test_require_ctx_raises_click_exception_on_none():
    """_require_ctx converts None ctx into a clean ClickException."""
    with pytest.raises(
        click.ClickException,
        match="CLI context is uninitialized",
    ):
        cli_module._require_ctx(None)


def test_require_ctx_returns_ctx_unchanged():
    """_require_ctx is a pass-through when ctx is valid."""
    from semantica.core.config_manager import Config, ConfigManager

    cfg = ConfigManager().load_from_dict({}, validate=False)
    ctx = cli_module.CLIContext(config_path=None, config=cfg, log_level="INFO")
    assert cli_module._require_ctx(ctx) is ctx
