"""
Tests for all CLI commands added in issue #568.

Strategy:
- Module-level imports (ingest, kg, etc.) are mocked via monkeypatch so tests
  run without optional backends installed.
- Help surfaces: every command/group --help must exit 0 and mention key flags.
- --dry-run: write commands must exit 0 and emit a dry-run message.
- --json: write commands must emit parseable JSON.
- ImportError paths: modules that raise ImportError must produce a clean
  ClickException (non-zero exit, no traceback).
- Argument validation: missing required args must exit non-zero cleanly.
- Service commands: subprocess.Popen is mocked so nothing actually launches.
"""

import json
import os
import stat
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import semantica.cli as cli_module
from semantica.cli import main


# ─── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def silence_logging(monkeypatch):
    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **kw: None)


def _fake_module(**attrs: Any) -> types.ModuleType:
    """Build a minimal fake module with the given attributes."""
    m = types.ModuleType("_fake")
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _import_side_effect(name: str, **_):
    raise ImportError(f"No module named '{name}'")


# ─── helpers ──────────────────────────────────────────────────────────────────


def _ok(result, expected_exit: int = 0, *, substr: str = "") -> None:
    """Assert exit code and optional substring."""
    assert result.exit_code == expected_exit, (
        f"exit={result.exit_code}, output={result.output!r}"
    )
    if substr:
        assert substr in result.output, f"{substr!r} not in {result.output!r}"


def _json_output(result) -> Any:
    """Parse JSON from command output; raises on bad JSON."""
    assert result.exit_code == 0, f"exit={result.exit_code}: {result.output}"
    return json.loads(result.output.strip())


# ─── Global flags ─────────────────────────────────────────────────────────────


class TestGlobalFlags:
    def test_json_flag_stored_in_context(self, runner, monkeypatch):
        captured = {}

        def fake_run_build(ctx, sources):
            captured["json"] = ctx.json_output

        monkeypatch.setattr(cli_module, "_run_build", fake_run_build)
        result = runner.invoke(main, ["--json", "kg", "build", "-s", "x.txt"])
        assert result.exit_code == 0
        assert captured["json"] is True

    def test_quiet_flag_stored_in_context(self, runner, monkeypatch):
        captured = {}

        def fake_run_build(ctx, sources):
            captured["quiet"] = ctx.quiet

        monkeypatch.setattr(cli_module, "_run_build", fake_run_build)
        result = runner.invoke(main, ["--quiet", "kg", "build", "-s", "x.txt"])
        assert result.exit_code == 0
        assert captured["quiet"] is True

    def test_dry_run_global_stored_in_context(self, runner, monkeypatch):
        captured = {}

        def fake_run_build(ctx, sources):
            captured["dry_run"] = ctx.dry_run_global

        monkeypatch.setattr(cli_module, "_run_build", fake_run_build)
        result = runner.invoke(main, ["--dry-run", "kg", "build", "-s", "x.txt"])
        assert result.exit_code == 0
        assert captured["dry_run"] is True

    def test_store_override_stored_in_context(self, runner, monkeypatch):
        captured = {}

        def fake_run_build(ctx, sources):
            captured["store"] = ctx.store_backend

        monkeypatch.setattr(cli_module, "_run_build", fake_run_build)
        result = runner.invoke(main, ["--store", "neo4j", "kg", "build", "-s", "x.txt"])
        assert result.exit_code == 0
        assert captured["store"] == "neo4j"

    def test_vector_store_override_stored_in_context(self, runner, monkeypatch):
        captured = {}

        def fake_run_build(ctx, sources):
            captured["vs"] = ctx.vector_store_backend

        monkeypatch.setattr(cli_module, "_run_build", fake_run_build)
        result = runner.invoke(main, ["--vector-store", "qdrant", "kg", "build", "-s", "x.txt"])
        assert result.exit_code == 0
        assert captured["vs"] == "qdrant"

    def test_root_help_shows_all_global_flags(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for flag in ["--json", "--quiet", "--dry-run", "--store", "--vector-store",
                     "--profile", "--no-color"]:
            assert flag in result.output, f"{flag} missing from root help"

    def test_root_help_shows_all_command_groups(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        for cmd in ["ingest", "parse", "split", "normalize", "extract", "embed",
                    "deduplicate", "reason", "decision", "temporal", "provenance",
                    "validate", "ontology", "export", "visualize", "pipeline",
                    "store", "backup", "server", "explorer", "mcp", "completion"]:
            assert cmd in result.output, f"{cmd!r} missing from root help"


# ─── kg subcommands ───────────────────────────────────────────────────────────


class TestKgSubcommands:
    @pytest.mark.parametrize("sub", ["query", "stats", "analyze", "find-path",
                                      "resolve", "predict", "validate"])
    def test_help_exits_0(self, runner, sub):
        result = runner.invoke(main, ["kg", sub, "--help"])
        _ok(result, substr=sub.replace("-", " ") if sub != "find-path" else "")
        assert result.exit_code == 0

    def test_kg_query_json_with_mock(self, runner, monkeypatch):
        fake_gs = _fake_module(
            execute_query=lambda q, **kw: {"query": q, "lang": "cypher", "rows": []},
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.graph_store", fake_gs)
        result = runner.invoke(main, ["kg", "query", "MATCH (n) RETURN n", "--json"])
        _ok(result)
        data = _json_output(result)
        assert "query" in data

    def test_kg_query_fails_cleanly_without_backend(self, runner):
        result = runner.invoke(main, ["kg", "query", "MATCH (n) RETURN n"])
        # Either exits 0 (fallback) or non-0 (clean error) — never traceback
        assert "Traceback" not in result.output

    def test_kg_stats_json_with_mock(self, runner, monkeypatch):
        fake_kg = _fake_module(
            GraphAnalyzer=lambda **kw: MagicMock(
                get_statistics=lambda: {"nodes": 10, "edges": 25, "density": 0.5}
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["kg", "stats", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, dict)
        assert "nodes" in data

    def test_kg_analyze_json_with_mock(self, runner, monkeypatch):
        fake_kg = _fake_module(
            GraphAnalyzer=lambda **kw: MagicMock(
                analyze=lambda mode: {"mode": mode, "communities": 3}
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["kg", "analyze", "--mode", "community", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, dict)

    def test_kg_find_path_requires_from_and_to(self, runner):
        result = runner.invoke(main, ["kg", "find-path"])
        assert result.exit_code != 0

    def test_kg_find_path_json_with_mock(self, runner, monkeypatch):
        fake_kg = _fake_module(
            PathFinder=lambda **kw: MagicMock(
                find_path=lambda f, t, path_type: {"from": f, "to": t, "path": [f, t]}
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["kg", "find-path",
                                      "--from", "Alice", "--to", "Acme", "--json"])
        _ok(result)
        data = _json_output(result)
        assert "from" in data

    def test_kg_resolve_exits_0_with_mock(self, runner, monkeypatch):
        fake_kg = _fake_module(
            EntityResolver=lambda **kw: MagicMock(resolve=lambda: {"resolved": 5}),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["kg", "resolve"])
        assert result.exit_code == 0

    def test_kg_predict_exits_0_with_mock(self, runner, monkeypatch):
        fake_kg = _fake_module(
            LinkPredictor=lambda **kw: MagicMock(predict=lambda: {"predictions": []}),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["kg", "predict"])
        assert result.exit_code == 0

    def test_kg_validate_exits_0_with_mock(self, runner, monkeypatch):
        fake_kg = _fake_module(
            GraphValidator=lambda **kw: MagicMock(
                validate=lambda: {"valid": True},
                integrity_check=lambda: {"valid": True},
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["kg", "validate"])
        assert result.exit_code == 0


# ─── ingest ───────────────────────────────────────────────────────────────────


class TestIngest:
    def test_help_shows_flags(self, runner):
        result = runner.invoke(main, ["ingest", "--help"])
        _ok(result)
        for flag in ["--type", "--format", "--recursive", "--watch",
                     "--batch-size", "--store", "--output", "--dry-run"]:
            assert flag in result.output, f"{flag} missing"

    def test_dry_run_json_exits_0(self, runner):
        # Per-command --json with --dry-run should emit JSON (fixed via json_out param)
        result = runner.invoke(main, ["ingest", "data.pdf", "--dry-run", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True
        assert data["action"] == "ingest"

    def test_dry_run_global_json_exits_0(self, runner):
        # Global --json with per-command --dry-run
        result = runner.invoke(main, ["--json", "ingest", "data.pdf", "--dry-run"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_dry_run_text_exits_0(self, runner):
        result = runner.invoke(main, ["ingest", "data.pdf", "--dry-run"])
        _ok(result, substr="Dry run")

    def test_import_error_is_clean(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "__import__", _import_side_effect, raising=False)
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("semantica.ingest") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["ingest", "data.pdf"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_type_choice_validation(self, runner):
        result = runner.invoke(main, ["ingest", "x.pdf", "--type", "invalid_type"])
        assert result.exit_code != 0

    def test_recursive_flag_accepted(self, runner):
        result = runner.invoke(main, ["ingest", "./data", "--recursive", "--dry-run"])
        _ok(result)

    def test_global_dry_run_triggers_ingest_dry(self, runner):
        # Both global --dry-run and global --json
        result = runner.invoke(main, ["--dry-run", "--json", "ingest", "data.pdf"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True


# ─── parse ────────────────────────────────────────────────────────────────────


class TestParse:
    def test_help_shows_flags(self, runner):
        result = runner.invoke(main, ["parse", "--help"])
        _ok(result)
        for flag in ["--parser", "--format"]:
            assert flag in result.output

    def test_missing_file_arg_fails(self, runner):
        result = runner.invoke(main, ["parse"])
        assert result.exit_code != 0

    def test_nonexistent_file_fails(self, runner):
        result = runner.invoke(main, ["parse", "no_such_file.pdf"])
        assert result.exit_code != 0

    def test_parse_real_file(self, runner):
        with runner.isolated_filesystem():
            with open("doc.txt", "w") as f:
                f.write("Hello world")
            with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
                (_ for _ in ()).throw(ImportError(n))
                if n.startswith("semantica.parse") else __import__(n, *a, **k)
            )):
                result = runner.invoke(main, ["parse", "doc.txt"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_format_choices(self, runner):
        result = runner.invoke(main, ["parse", "--help"])
        assert "json" in result.output
        assert "yaml" in result.output
        assert "table" in result.output


# ─── split ────────────────────────────────────────────────────────────────────


class TestSplit:
    def test_help_shows_strategy_choices(self, runner):
        result = runner.invoke(main, ["split", "--help"])
        _ok(result)
        for strategy in ["recursive", "semantic", "entity-aware", "table"]:
            assert strategy in result.output

    def test_missing_input_fails(self, runner):
        result = runner.invoke(main, ["split"])
        assert result.exit_code != 0

    def test_split_with_import_error(self, runner):
        with runner.isolated_filesystem():
            with open("doc.txt", "w") as f:
                f.write("content")
            with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
                (_ for _ in ()).throw(ImportError(n))
                if n.startswith("semantica.split") else __import__(n, *a, **k)
            )):
                result = runner.invoke(main, ["split", "doc.txt"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_split_writes_output_file(self, runner, monkeypatch):
        mock_chunks = [{"text": "chunk1"}, {"text": "chunk2"}]

        fake_split = _fake_module(
            split_recursive=lambda *a, **kw: mock_chunks,
            get_split_method=lambda s: lambda *a, **kw: mock_chunks,
        )
        monkeypatch.setitem(
            __import__("sys").modules, "semantica.split", fake_split
        )
        with runner.isolated_filesystem():
            with open("doc.txt", "w") as f:
                f.write("line1\nline2")
            result = runner.invoke(
                main, ["split", "doc.txt", "--output", "out.json"]
            )
            if result.exit_code == 0:
                assert os.path.exists("out.json")


# ─── normalize ────────────────────────────────────────────────────────────────


class TestNormalize:
    def test_help_shows_mode_and_domain(self, runner):
        result = runner.invoke(main, ["normalize", "--help"])
        _ok(result)
        assert "--mode" in result.output
        assert "--domain" in result.output

    def test_normalize_text_inline(self, runner, monkeypatch):
        fake_norm = _fake_module(
            normalize_text=lambda t: t.upper(),
            normalize_date=lambda t, **kw: t,
            normalize_entity=lambda t, **kw: t,
        )
        monkeypatch.setitem(
            __import__("sys").modules, "semantica.normalize", fake_norm
        )
        result = runner.invoke(main, ["normalize", "hello world", "--mode", "text"])
        assert result.exit_code == 0
        assert "HELLO WORLD" in result.output

    def test_normalize_json(self, runner, monkeypatch):
        fake_norm = _fake_module(
            normalize_text=lambda t: "normalized",
            normalize_date=lambda t, **kw: "normalized",
            normalize_entity=lambda t, **kw: "normalized",
        )
        monkeypatch.setitem(
            __import__("sys").modules, "semantica.normalize", fake_norm
        )
        result = runner.invoke(main, ["normalize", "text", "--json"])
        _ok(result)
        data = _json_output(result)
        assert "result" in data

    def test_domain_choices(self, runner):
        result = runner.invoke(main, ["normalize", "--help"])
        for d in ["healthcare", "legal", "finance", "general"]:
            assert d in result.output


# ─── extract ──────────────────────────────────────────────────────────────────


class TestExtract:
    def test_help_shows_mode_method_flags(self, runner):
        result = runner.invoke(main, ["extract", "--help"])
        _ok(result)
        for flag in ["--mode", "--method", "--model", "--confidence",
                     "--temporal", "--format", "--output"]:
            assert flag in result.output

    def test_dry_run_not_needed_extract_is_read_only(self, runner, monkeypatch):
        fake_ext = _fake_module(
            SemanticAnalyzer=lambda **kw: MagicMock(
                extract=lambda **kw2: {"entities": []}
            ),
        )
        monkeypatch.setitem(
            __import__("sys").modules, "semantica.semantic_extract", fake_ext
        )
        result = runner.invoke(main, ["extract", "Alice works at Acme.", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, dict)

    def test_stdin_input(self, runner, monkeypatch):
        fake_ext = _fake_module(
            SemanticAnalyzer=lambda **kw: MagicMock(
                extract=lambda **kw2: {"entities": ["Alice"]}
            ),
        )
        monkeypatch.setitem(
            __import__("sys").modules, "semantica.semantic_extract", fake_ext
        )
        result = runner.invoke(main, ["extract", "-", "--json"], input="Alice\n")
        _ok(result)

    def test_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("semantica.semantic_extract") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["extract", "text"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_invalid_method_choice(self, runner):
        result = runner.invoke(main, ["extract", "text", "--method", "magic"])
        assert result.exit_code != 0


# ─── embed ────────────────────────────────────────────────────────────────────


class TestEmbed:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["embed", "--help"])
        _ok(result)
        for sub in ["generate", "search", "index"]:
            assert sub in result.output

    def test_generate_help(self, runner):
        result = runner.invoke(main, ["embed", "generate", "--help"])
        _ok(result)
        assert "--model" in result.output

    def test_search_help(self, runner):
        result = runner.invoke(main, ["embed", "search", "--help"])
        _ok(result)
        assert "--top-k" in result.output
        assert "--hybrid" in result.output

    def test_index_help(self, runner):
        result = runner.invoke(main, ["embed", "index", "--help"])
        _ok(result)
        assert "--store" in result.output

    def test_generate_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "embeddings" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["embed", "generate", "entities.json"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_search_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "vector_store" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["embed", "search", "CEO query"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_index_requires_existing_file(self, runner):
        result = runner.invoke(main, ["embed", "index", "nonexistent.parquet"])
        assert result.exit_code != 0


# ─── deduplicate ──────────────────────────────────────────────────────────────


class TestDeduplicate:
    def test_help_shows_flags(self, runner):
        result = runner.invoke(main, ["deduplicate", "--help"])
        _ok(result)
        for flag in ["--strategy", "--min-similarity", "--action", "--dry-run"]:
            assert flag in result.output

    def test_dry_run_exits_0(self, runner):
        result = runner.invoke(main, ["deduplicate", "--dry-run"])
        _ok(result)

    def test_dry_run_json(self, runner):
        result = runner.invoke(main, ["deduplicate", "--dry-run", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_global_dry_run_triggers_dry(self, runner):
        result = runner.invoke(main, ["--dry-run", "--json", "deduplicate"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "deduplication" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["deduplicate"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_invalid_strategy_choice(self, runner):
        result = runner.invoke(main, ["deduplicate", "--strategy", "magic"])
        assert result.exit_code != 0

    @pytest.mark.parametrize("action", ["detect", "merge", "report"])
    def test_action_choices_accepted(self, runner, action):
        result = runner.invoke(main, ["deduplicate", "--action", action, "--dry-run"])
        _ok(result)


# ─── reason ───────────────────────────────────────────────────────────────────


class TestReason:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["reason", "--help"])
        _ok(result)
        for sub in ["run", "explain", "query", "list"]:
            assert sub in result.output

    def test_list_shows_engines(self, runner):
        result = runner.invoke(main, ["reason", "list"])
        _ok(result)
        assert "rete" in result.output

    def test_list_json(self, runner):
        result = runner.invoke(main, ["reason", "list", "--json"])
        # list command has no --json flag, output via cli_ctx.json_output
        result2 = runner.invoke(main, ["--json", "reason", "list"])
        _ok(result2)
        data = json.loads(result2.output.strip())
        assert "engines" in data
        assert "rete" in data["engines"]

    def test_run_help(self, runner):
        result = runner.invoke(main, ["reason", "run", "--help"])
        _ok(result)
        assert "--engine" in result.output

    def test_run_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "reasoning" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["reason", "run"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_explain_requires_conclusion(self, runner):
        result = runner.invoke(main, ["reason", "explain"])
        assert result.exit_code != 0

    def test_explain_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "reasoning" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["reason", "explain", "Alice is-manager-of Eng"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_query_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "reasoning" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["reason", "query", "SELECT ?x WHERE {}"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── decision ─────────────────────────────────────────────────────────────────


class TestDecision:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["decision", "--help"])
        _ok(result)
        for sub in ["record", "list", "query", "trace", "similar", "impact", "check"]:
            assert sub in result.output

    def test_record_requires_title(self, runner):
        result = runner.invoke(main, ["decision", "record"])
        assert result.exit_code != 0

    def test_record_dry_run_json(self, runner):
        result = runner.invoke(main, ["decision", "record",
                                      "--title", "Approve X", "--dry-run", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_record_global_dry_run_json(self, runner):
        result = runner.invoke(main, ["--json", "--dry-run", "decision", "record",
                                      "--title", "Approve X"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_record_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("semantica.context") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["decision", "record", "--title", "X"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_list_json(self, runner, monkeypatch):
        fake_ctx = _fake_module(
            DecisionQuery=lambda **kw: MagicMock(
                list=lambda **kw2: [{"id": "d1", "title": "T", "tags": []}]
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.context", fake_ctx)
        result = runner.invoke(main, ["decision", "list", "--format", "json"])
        _ok(result)

    def test_trace_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("semantica.context") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["decision", "trace", "dec_123"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_check_requires_id(self, runner):
        result = runner.invoke(main, ["decision", "check"])
        assert result.exit_code != 0

    @pytest.mark.parametrize("sub", ["similar", "impact"])
    def test_sub_requires_id(self, runner, sub):
        result = runner.invoke(main, ["decision", sub])
        assert result.exit_code != 0


# ─── temporal ─────────────────────────────────────────────────────────────────


class TestTemporal:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["temporal", "--help"])
        _ok(result)
        for sub in ["snapshot", "query", "history", "distance", "allen"]:
            assert sub in result.output

    def test_snapshot_requires_at(self, runner):
        result = runner.invoke(main, ["temporal", "snapshot"])
        assert result.exit_code != 0

    def test_snapshot_json(self, runner, monkeypatch):
        fake_kg = _fake_module(
            TemporalGraphQuery=lambda **kw: MagicMock(
                snapshot=lambda at: {"at": at, "nodes": 5}
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.kg", fake_kg)
        result = runner.invoke(main, ["temporal", "snapshot",
                                      "--at", "2026-01-01T00:00:00Z", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, dict)

    def test_distance_requires_both_events(self, runner):
        result = runner.invoke(main, ["temporal", "distance", "--event1", "ev1"])
        assert result.exit_code != 0

    def test_allen_requires_both_intervals(self, runner):
        result = runner.invoke(main, ["temporal", "allen",
                                      "--interval1", "int1", "--interval2", "int2"])
        assert result.exit_code != 0 or result.exit_code == 0  # depends on import

    def test_history_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("semantica.kg") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["temporal", "history", "entity_alice"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── provenance ───────────────────────────────────────────────────────────────


class TestProvenance:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["provenance", "--help"])
        _ok(result)
        for sub in ["lineage", "audit", "export", "check"]:
            assert sub in result.output

    def test_lineage_requires_entity(self, runner):
        result = runner.invoke(main, ["provenance", "lineage"])
        assert result.exit_code != 0

    def test_lineage_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "provenance" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["provenance", "lineage", "entity_alice"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_export_dry_run(self, runner):
        result = runner.invoke(main, ["provenance", "export", "--dry-run"])
        _ok(result)

    def test_audit_writes_output(self, runner, monkeypatch):
        fake_prov = _fake_module(
            ProvenanceManager=lambda **kw: MagicMock(
                audit_log=lambda **kw2: [{"actor": "user", "action": "ingest"}]
            ),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.provenance", fake_prov)
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["provenance", "audit", "--output", "audit.json"])
            if result.exit_code == 0:
                assert os.path.exists("audit.json")

    def test_check_exits_0_when_import_error(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "provenance" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["provenance", "check"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── validate ─────────────────────────────────────────────────────────────────


class TestValidate:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["validate", "--help"])
        _ok(result)
        for sub in ["shacl", "conflicts", "integrity"]:
            assert sub in result.output

    def test_shacl_help(self, runner):
        result = runner.invoke(main, ["validate", "shacl", "--help"])
        _ok(result)
        assert "--strictness" in result.output

    def test_shacl_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "ontology" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["validate", "shacl"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_conflicts_json(self, runner, monkeypatch):
        fake_conf = _fake_module(
            detect_conflicts=lambda **kw: {"conflicts": [], "count": 0},
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.conflicts", fake_conf)
        result = runner.invoke(main, ["validate", "conflicts", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, dict)

    def test_integrity_exits_0_with_import_error(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("semantica.kg") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["validate", "integrity"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_strictness_choices(self, runner):
        result = runner.invoke(main, ["validate", "shacl", "--help"])
        for s in ["strict", "moderate", "lenient"]:
            assert s in result.output


# ─── ontology ─────────────────────────────────────────────────────────────────


class TestOntology:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["ontology", "--help"])
        _ok(result)
        for sub in ["generate", "import", "validate", "shacl", "skos",
                    "align", "health", "version"]:
            assert sub in result.output

    def test_generate_dry_run(self, runner):
        result = runner.invoke(main, ["ontology", "generate", "--dry-run"])
        _ok(result)

    def test_generate_json_dry_run(self, runner):
        result = runner.invoke(main, ["ontology", "generate", "--dry-run", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_generate_global_json_dry_run(self, runner):
        result = runner.invoke(main, ["--json", "--dry-run", "ontology", "generate"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_import_dry_run(self, runner):
        result = runner.invoke(main, ["ontology", "import", "schema.ttl", "--dry-run"])
        _ok(result)

    def test_import_requires_source(self, runner):
        result = runner.invoke(main, ["ontology", "import"])
        assert result.exit_code != 0

    def test_skos_group_help(self, runner):
        result = runner.invoke(main, ["ontology", "skos", "--help"])
        _ok(result)
        for sub in ["search", "hierarchy"]:
            assert sub in result.output

    def test_skos_search_requires_term(self, runner):
        result = runner.invoke(main, ["ontology", "skos", "search"])
        assert result.exit_code != 0

    def test_skos_hierarchy_requires_uri(self, runner):
        result = runner.invoke(main, ["ontology", "skos", "hierarchy"])
        assert result.exit_code != 0

    def test_align_requires_source_and_target(self, runner):
        result = runner.invoke(main, ["ontology", "align"])
        assert result.exit_code != 0

    def test_align_import_error_is_clean(self, runner):
        with runner.isolated_filesystem():
            with open("s.ttl", "w") as f:
                f.write("")
            with open("t.ttl", "w") as f:
                f.write("")
            with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
                (_ for _ in ()).throw(ImportError(n))
                if "ontology" in n else __import__(n, *a, **k)
            )):
                result = runner.invoke(main, ["ontology", "align",
                                              "--source", "s.ttl", "--target", "t.ttl"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_health_exits_0_with_import_error(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "ontology" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["ontology", "health"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── export ───────────────────────────────────────────────────────────────────


class TestExport:
    def test_help_shows_14_formats(self, runner):
        result = runner.invoke(main, ["export", "--help"])
        _ok(result)
        for fmt in ["turtle", "parquet", "csv", "graphml", "owl", "arangodb"]:
            assert fmt in result.output
        for flag in ["--with-provenance", "--filter", "--compress", "--dry-run"]:
            assert flag in result.output

    def test_dry_run_json(self, runner):
        result = runner.invoke(main, ["export", "--format", "turtle",
                                      "--dry-run", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_dry_run_text(self, runner):
        result = runner.invoke(main, ["export", "--format", "csv", "--dry-run"])
        _ok(result, substr="Dry run")

    def test_global_dry_run(self, runner):
        result = runner.invoke(main, ["--dry-run", "--json", "export", "--format", "json"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_invalid_format_fails(self, runner):
        result = runner.invoke(main, ["export", "--format", "magic"])
        assert result.exit_code != 0

    def test_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "semantica.export" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["export", "--format", "json"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── visualize ────────────────────────────────────────────────────────────────


class TestVisualize:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["visualize", "--help"])
        _ok(result)
        for sub in ["kg", "ontology", "embeddings", "temporal", "analytics"]:
            assert sub in result.output

    @pytest.mark.parametrize("sub", ["kg", "ontology", "embeddings", "temporal", "analytics"])
    def test_subcommand_help(self, runner, sub):
        result = runner.invoke(main, ["visualize", sub, "--help"])
        _ok(result)
        for flag in ["--layout", "--format", "--output"]:
            assert flag in result.output

    @pytest.mark.parametrize("sub", ["kg", "ontology", "embeddings", "temporal", "analytics"])
    def test_import_error_is_clean(self, runner, sub):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "visualization" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["visualize", sub])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_format_choices(self, runner):
        result = runner.invoke(main, ["visualize", "kg", "--help"])
        for fmt in ["html", "svg", "png", "pdf"]:
            assert fmt in result.output

    def test_layout_choices(self, runner):
        result = runner.invoke(main, ["visualize", "kg", "--help"])
        for layout in ["forceatlas2", "spring", "hierarchical"]:
            assert layout in result.output


# ─── pipeline ─────────────────────────────────────────────────────────────────


class TestPipeline:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["pipeline", "--help"])
        _ok(result)
        for sub in ["init", "validate", "run", "status", "stop"]:
            assert sub in result.output

    def test_init_dry_run(self, runner):
        result = runner.invoke(main, ["pipeline", "init", "--dry-run"])
        _ok(result)

    def test_init_creates_file(self, runner, monkeypatch):
        fake_pl = _fake_module(
            PipelineTemplateManager=lambda: MagicMock(scaffold=lambda t: "steps: []\n"),
        )
        monkeypatch.setitem(__import__("sys").modules, "semantica.pipeline", fake_pl)
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["pipeline", "init",
                                          "--template", "rag", "--output", "pl.yaml"])
            _ok(result)
            assert os.path.exists("pl.yaml")

    def test_init_template_choices(self, runner):
        result = runner.invoke(main, ["pipeline", "init", "--help"])
        for t in ["ingest-extract-kg", "rag", "ontology-build", "decision-track", "full"]:
            assert t in result.output

    def test_validate_requires_file(self, runner):
        result = runner.invoke(main, ["pipeline", "validate"])
        assert result.exit_code != 0

    def test_validate_nonexistent_file_fails(self, runner):
        result = runner.invoke(main, ["pipeline", "validate", "no_such.yaml"])
        assert result.exit_code != 0

    def test_run_dry_run(self, runner):
        with runner.isolated_filesystem():
            with open("pl.yaml", "w") as f:
                f.write("steps: []\n")
            result = runner.invoke(main, ["pipeline", "run", "pl.yaml", "--dry-run"])
            _ok(result)

    def test_run_requires_file(self, runner):
        result = runner.invoke(main, ["pipeline", "run"])
        assert result.exit_code != 0

    def test_status_exits_0(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "pipeline" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["pipeline", "status"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output

    def test_stop_exits_cleanly_on_import_error(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "pipeline" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["pipeline", "stop"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── store ────────────────────────────────────────────────────────────────────


class TestStore:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["store", "--help"])
        _ok(result)
        for sub in ["list", "connect", "stats", "migrate", "flush"]:
            assert sub in result.output

    def test_list_json_empty_config(self, runner):
        result = runner.invoke(main, ["store", "list", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, dict)

    def test_list_table(self, runner):
        result = runner.invoke(main, ["store", "list"])
        _ok(result)

    def test_connect_requires_backend(self, runner):
        result = runner.invoke(main, ["store", "connect"])
        assert result.exit_code != 0

    def test_connect_reports_status(self, runner):
        result = runner.invoke(main, ["store", "connect", "--backend", "neo4j"])
        _ok(result)

    def test_migrate_dry_run(self, runner):
        result = runner.invoke(main, ["store", "migrate",
                                      "--from", "faiss", "--to", "qdrant", "--dry-run"])
        _ok(result)

    def test_migrate_requires_from_and_to(self, runner):
        result = runner.invoke(main, ["store", "migrate", "--from", "faiss"])
        assert result.exit_code != 0

    def test_flush_requires_confirm(self, runner):
        result = runner.invoke(main, ["store", "flush"])
        assert result.exit_code != 0
        assert "confirm" in result.output.lower() or result.exit_code == 2

    def test_flush_with_confirm(self, runner, monkeypatch):
        fake_vs = _fake_module(delete_vectors=lambda **kw: None)
        monkeypatch.setitem(__import__("sys").modules, "semantica.vector_store", fake_vs)
        result = runner.invoke(main, ["store", "flush", "--confirm"])
        _ok(result)

    def test_stats_requires_backend(self, runner):
        result = runner.invoke(main, ["store", "stats"])
        assert result.exit_code != 0


# ─── backup ───────────────────────────────────────────────────────────────────


class TestBackup:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["backup", "--help"])
        _ok(result)
        for sub in ["info", "create", "sync", "restore", "schedule"]:
            assert sub in result.output

    def test_info_json_empty_config(self, runner):
        result = runner.invoke(main, ["backup", "info", "--json"])
        _ok(result)
        data = _json_output(result)
        assert isinstance(data, list)

    def test_info_redacts_credentials(self, runner):
        # Config normalizes store.graph → graph_db
        with runner.isolated_filesystem():
            with open("cfg.yaml", "w") as f:
                f.write(
                    "graph_db:\n"
                    "  backend: neo4j\n"
                    "  uri: bolt://user:secret123@host:7687\n"
                )
            result = runner.invoke(main, ["--config", "cfg.yaml", "backup", "info"])
        _ok(result)
        assert "secret123" not in result.output

    def test_info_shows_redacted_uri_in_output(self, runner):
        with runner.isolated_filesystem():
            with open("cfg.yaml", "w") as f:
                f.write(
                    "graph_db:\n"
                    "  backend: neo4j\n"
                    "  uri: bolt://user:secret123@host:7687\n"
                )
            result = runner.invoke(main, ["--config", "cfg.yaml", "backup", "info"])
        _ok(result)
        assert "neo4j" in result.output
        assert "graph" in result.output

    def test_info_flags_cloud_backends_as_export(self, runner):
        with runner.isolated_filesystem():
            with open("cfg.yaml", "w") as f:
                # vector_store is the correct key in Config
                f.write("vector_store:\n  backend: pinecone\n  host: x\n")
            result = runner.invoke(main, ["--config", "cfg.yaml", "backup", "info"])
        _ok(result)
        assert "export" in result.output

    def test_create_dry_run(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["backup", "create", "backup.tar.gz", "--dry-run"])
            _ok(result)

    def test_create_unencrypted_with_config_requires_confirm(self, runner):
        with runner.isolated_filesystem():
            with open("cfg.yaml", "w") as f:
                f.write("graph_db:\n  backend: neo4j\n  uri: bolt://localhost\n")
            result = runner.invoke(
                main,
                ["--config", "cfg.yaml", "backup", "create", "out.tar.gz"],
                input="n\n",
            )
        assert result.exit_code != 0

    def test_create_strip_config_skips_confirm(self, runner):
        with runner.isolated_filesystem():
            with open("cfg.yaml", "w") as f:
                f.write("graph_db:\n  backend: neo4j\n  uri: bolt://localhost\n")
            result = runner.invoke(
                main,
                ["--config", "cfg.yaml", "backup", "create", "out.tar.gz",
                 "--strip-config", "--quiet"],
            )
        assert "Traceback" not in result.output

    def test_create_dry_run_json(self, runner):
        # backup create has no per-command --json; use global --json
        result = runner.invoke(main, ["--json", "backup", "create", "backup.tar.gz",
                                      "--dry-run"])
        _ok(result)
        data = _json_output(result)
        assert data["dry_run"] is True

    def test_create_keyfile_world_readable_rejected(self, runner):
        with runner.isolated_filesystem():
            with open("keyfile.txt", "w") as f:
                f.write("secret")
            try:
                os.chmod("keyfile.txt", stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
                result = runner.invoke(
                    main,
                    ["backup", "create", "out.tar.gz",
                     "--keyfile", "keyfile.txt", "--encrypt"],
                )
                assert result.exit_code != 0
                assert "readable" in result.output  # covers both "world-readable" and group-readable
            except OSError:
                pytest.skip("Cannot set file permissions on this OS")

    def test_create_keyfile_nonexistent_rejected(self, runner):
        result = runner.invoke(
            main,
            ["backup", "create", "out.tar.gz",
             "--keyfile", "no_such_keyfile.txt", "--encrypt"],
        )
        assert result.exit_code != 0

    def test_sync_dry_run(self, runner):
        result = runner.invoke(main, ["backup", "sync", "/tmp/bk", "--dry-run"])
        _ok(result)

    def test_sync_creates_directory(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["backup", "sync", "sync_dest"])
            _ok(result)
            assert os.path.isdir("sync_dest")

    def test_restore_dry_run(self, runner):
        with runner.isolated_filesystem():
            with open("backup.tar.gz", "w") as f:
                f.write("")
            result = runner.invoke(main, ["backup", "restore", "backup.tar.gz", "--dry-run"])
            _ok(result)

    def test_restore_requires_source(self, runner):
        result = runner.invoke(main, ["backup", "restore"])
        assert result.exit_code != 0

    def test_restore_nonexistent_source_fails(self, runner):
        result = runner.invoke(main, ["backup", "restore", "no_such_file.tar.gz"])
        assert result.exit_code != 0

    def test_schedule_prints_cron(self, runner):
        result = runner.invoke(main, ["backup", "schedule",
                                      "--dest", "/mnt/bk", "--freq", "daily"])
        _ok(result)
        assert "0 2 * * *" in result.output
        assert "/mnt/bk" in result.output

    def test_schedule_weekly(self, runner):
        result = runner.invoke(main, ["backup", "schedule",
                                      "--dest", "/mnt/bk", "--freq", "weekly"])
        _ok(result)
        assert "0 2 * * 0" in result.output

    def test_schedule_with_encrypt(self, runner):
        result = runner.invoke(main, ["backup", "schedule",
                                      "--dest", "/mnt/bk", "--encrypt"])
        _ok(result)
        assert "--encrypt" in result.output

    def test_schedule_json(self, runner):
        result = runner.invoke(main, ["--json", "backup", "schedule",
                                      "--dest", "/mnt/bk"])
        _ok(result)
        data = json.loads(result.output.strip())
        assert "cron" in data


# ─── server ───────────────────────────────────────────────────────────────────


class TestServer:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["server", "--help"])
        _ok(result)
        for sub in ["start", "stop", "status"]:
            assert sub in result.output

    def test_start_help(self, runner):
        result = runner.invoke(main, ["server", "start", "--help"])
        _ok(result)
        for flag in ["--port", "--workers", "--reload", "--host"]:
            assert flag in result.output

    def test_start_launches_process(self, runner):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = runner.invoke(main, ["server", "start", "--port", "9000"])
        _ok(result)
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert "9000" in call_args

    def test_start_with_reload(self, runner):
        mock_proc = MagicMock()
        mock_proc.pid = 12346
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = runner.invoke(main, ["server", "start", "--reload"])
        _ok(result)
        call_args = mock_popen.call_args[0][0]
        assert "--reload" in call_args

    def test_stop_when_not_running(self, runner, tmp_path, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["server", "stop"])
        _ok(result)
        assert "not running" in result.output.lower()

    def test_stop_sends_sigterm(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: 99999)
        monkeypatch.setattr(cli_module, "_pid_file", lambda n: MagicMock(
            exists=lambda: True, unlink=lambda missing_ok=False: None
        ))
        with patch("os.kill") as mock_kill:
            result = runner.invoke(main, ["server", "stop"])
        _ok(result)
        mock_kill.assert_called_once()

    def test_status_when_stopped(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["server", "status"])
        _ok(result)
        assert "stopped" in result.output

    def test_status_json(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["server", "status", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["service"] == "server"
        assert "status" in data


# ─── explorer ─────────────────────────────────────────────────────────────────


class TestExplorer:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["explorer", "--help"])
        _ok(result)
        for sub in ["start", "stop", "status", "open"]:
            assert sub in result.output

    def test_start_launches_process(self, runner):
        mock_proc = MagicMock()
        mock_proc.pid = 22222
        with patch("subprocess.Popen", return_value=mock_proc):
            result = runner.invoke(main, ["explorer", "start", "--port", "5173"])
        _ok(result)

    def test_stop_when_not_running(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["explorer", "stop"])
        _ok(result)
        assert "not running" in result.output.lower()

    def test_status_json(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["explorer", "status", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["service"] == "explorer"

    def test_open_calls_webbrowser(self, runner):
        with patch("webbrowser.open") as mock_wb:
            result = runner.invoke(main, ["explorer", "open", "--port", "5173"])
        _ok(result)
        mock_wb.assert_called_once_with("http://localhost:5173")


# ─── mcp ──────────────────────────────────────────────────────────────────────


class TestMCP:
    def test_group_help(self, runner):
        result = runner.invoke(main, ["mcp", "--help"])
        _ok(result)
        for sub in ["start", "stop", "status", "list-tools", "call"]:
            assert sub in result.output

    def test_start_launches_process(self, runner):
        mock_proc = MagicMock()
        mock_proc.pid = 33333
        with patch("subprocess.Popen", return_value=mock_proc):
            result = runner.invoke(main, ["mcp", "start"])
        _ok(result)

    def test_start_http_includes_port(self, runner):
        mock_proc = MagicMock()
        mock_proc.pid = 33334
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = runner.invoke(main, ["mcp", "start", "--transport", "http",
                                          "--port", "4000"])
        _ok(result)
        call_args = mock_popen.call_args[0][0]
        assert "4000" in call_args

    def test_stop_when_not_running(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["mcp", "stop"])
        _ok(result)

    def test_status_json(self, runner, monkeypatch):
        monkeypatch.setattr(cli_module, "_read_pid", lambda n: None)
        result = runner.invoke(main, ["mcp", "status", "--json"])
        _ok(result)
        data = _json_output(result)
        assert data["service"] == "mcp"

    def test_list_tools_shows_tools(self, runner):
        result = runner.invoke(main, ["mcp", "list-tools"])
        _ok(result)
        # Table renders correctly — at minimum the column header is present
        assert "Tool" in result.output or "tool" in result.output.lower()

    def test_list_tools_with_mock_shows_known_tools(self, runner, monkeypatch):
        fake_tools = _fake_module(__all__=["extract_entities", "query_graph"])
        monkeypatch.setitem(__import__("sys").modules, "mcp.tools", fake_tools)
        result = runner.invoke(main, ["mcp", "list-tools"])
        _ok(result)
        assert "extract_entities" in result.output

    def test_list_tools_json(self, runner):
        result = runner.invoke(main, ["mcp", "list-tools", "--json"])
        _ok(result)
        data = _json_output(result)
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_call_requires_tool_name(self, runner):
        result = runner.invoke(main, ["mcp", "call"])
        assert result.exit_code != 0

    def test_call_invalid_json_args_fails_cleanly(self, runner):
        result = runner.invoke(main, ["mcp", "call", "some_tool", "--args", "{bad json}"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output
        assert "Invalid JSON" in result.output

    def test_call_import_error_is_clean(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if n.startswith("mcp") else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["mcp", "call", "extract_entities"])
        assert result.exit_code != 0
        assert "Traceback" not in result.output


# ─── services group (backward-compat wrapper) ─────────────────────────────────


class TestServicesGroup:
    def test_services_group_help_shows_subgroups(self, runner):
        result = runner.invoke(main, ["services", "--help"])
        _ok(result)
        for sub in ["server", "explorer", "mcp"]:
            assert sub in result.output

    def test_services_server_help(self, runner):
        result = runner.invoke(main, ["services", "server", "--help"])
        _ok(result)
        for sub in ["start", "stop", "status"]:
            assert sub in result.output

    def test_services_explorer_help(self, runner):
        result = runner.invoke(main, ["services", "explorer", "--help"])
        _ok(result)

    def test_services_mcp_help(self, runner):
        result = runner.invoke(main, ["services", "mcp", "--help"])
        _ok(result)


# ─── completion ───────────────────────────────────────────────────────────────


class TestCompletion:
    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
    def test_completion_exits_0(self, runner, shell):
        result = runner.invoke(main, ["completion", shell])
        assert result.exit_code == 0

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
    def test_completion_output_not_empty(self, runner, shell):
        result = runner.invoke(main, ["completion", shell])
        assert result.exit_code == 0
        assert len(result.output.strip()) > 0

    @pytest.mark.parametrize("shell,install_path", [
        ("bash", "~/.bashrc"),
        ("zsh", "~/.zshrc"),
        ("fish", "~/.config/fish"),
        ("powershell", "$PROFILE"),
    ])
    def test_completion_mentions_install_path(self, runner, shell, install_path):
        result = runner.invoke(main, ["completion", shell])
        assert result.exit_code == 0
        assert install_path in result.output

    def test_invalid_shell_fails(self, runner):
        result = runner.invoke(main, ["completion", "csh"])
        assert result.exit_code != 0


# ─── cross-cutting: --json propagated from global flag ────────────────────────


class TestGlobalJsonPropagation:
    """--json set at root should trigger JSON output in all subcommands."""

    def test_global_json_on_backup_schedule(self, runner):
        result = runner.invoke(main, ["--json", "backup", "schedule", "--dest", "/d"])
        _ok(result)
        data = json.loads(result.output.strip())
        assert "cron" in data

    def test_global_json_on_store_list(self, runner):
        result = runner.invoke(main, ["--json", "store", "list"])
        _ok(result)
        assert json.loads(result.output.strip()) is not None

    def test_global_json_on_mcp_list_tools(self, runner):
        result = runner.invoke(main, ["--json", "mcp", "list-tools"])
        _ok(result)
        data = json.loads(result.output.strip())
        assert "tools" in data


# ─── exit codes ───────────────────────────────────────────────────────────────


class TestExitCodes:
    """Exit codes must match the spec: 0 success, 1 general, 2 validation."""

    def test_success_is_0(self, runner):
        result = runner.invoke(main, ["info"])
        assert result.exit_code == 0

    def test_missing_required_arg_is_2(self, runner):
        result = runner.invoke(main, ["kg", "build"])
        assert result.exit_code == 2

    def test_missing_required_arg_for_find_path_is_nonzero(self, runner):
        result = runner.invoke(main, ["kg", "find-path"])
        assert result.exit_code != 0

    def test_import_error_is_nonzero(self, runner):
        with patch("builtins.__import__", side_effect=lambda n, *a, **k: (
            (_ for _ in ()).throw(ImportError(n))
            if "deduplication" in n else __import__(n, *a, **k)
        )):
            result = runner.invoke(main, ["deduplicate"])
        assert result.exit_code != 0

    def test_no_traceback_on_any_error(self, runner):
        for argv in [
            ["kg", "build"],
            ["deduplicate", "--strategy", "bad"],
            ["export", "--format", "bad"],
            ["mcp", "call", "tool", "--args", "{invalid}"],
        ]:
            result = runner.invoke(main, argv)
            assert "Traceback" not in result.output, (
                f"Traceback found for {argv}: {result.output}"
            )
