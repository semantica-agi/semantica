"""Smoke tests for the 'semantica temporal' CLI subcommands (issue #1809).

All five subcommands crashed on v0.7.0 because the CLI wrappers called methods
that no longer exist on the temporal engine classes. These tests drive each
subcommand through CliRunner against a tiny fixture graph so that class of
drift fails loudly.
"""

import json

from click.testing import CliRunner
import pytest

import semantica.cli as cli_module


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def silence_logging(monkeypatch):
    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **kw: None)


@pytest.fixture
def fixture_graph(monkeypatch):
    """Serve a tiny temporal graph through the memory backend loader."""
    from semantica.context import ContextGraph

    graph = ContextGraph()
    graph.add_node(
        "entity_alice",
        "entity",
        "Alice",
        valid_from="2025-01-01T00:00:00Z",
        valid_until="2025-02-01T00:00:00Z",
    )
    graph.add_node("entity_bob", "entity", "Bob", valid_from="2025-01-10T00:00:00Z")
    graph.add_edge(
        "entity_alice",
        "entity_bob",
        "knows",
        valid_from="2025-01-05T00:00:00Z",
        valid_until="2025-01-20T00:00:00Z",
    )
    monkeypatch.setattr(cli_module, "_load_context_graph", lambda cli_ctx: graph)
    return graph


class TestTemporalSnapshot:
    def test_snapshot_returns_graph_state_at_time(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main, ["temporal", "snapshot", "--at", "2025-01-15T00:00:00Z"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "entities" in payload
        rel_types = [r.get("type") for r in payload["relationships"]]
        assert "knows" in rel_types

    def test_snapshot_after_edge_expired_excludes_it(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main, ["temporal", "snapshot", "--at", "2025-01-25T00:00:00Z"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        rel_types = [r.get("type") for r in payload["relationships"]]
        assert "knows" not in rel_types


class TestTemporalQuery:
    def test_query_at_time(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main,
            ["temporal", "query", "status", "--at", "2025-01-15T00:00:00Z", "--json"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["query"] == "status"
        assert payload["num_relationships"] == 1

    def test_query_defaults_to_now(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main, ["temporal", "query", "status", "--json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "at_time" in payload


class TestTemporalHistory:
    def test_history_lists_entity_events(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main, ["temporal", "history", "entity_alice", "--format", "json"]
        )
        assert result.exit_code == 0
        events = json.loads(result.output)
        assert len(events) > 0
        change_types = {event["change_type"] for event in events}
        assert "added" in change_types

    def test_history_since_filter(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "history",
                "entity_alice",
                "--since",
                "2025-01-15",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        events = json.loads(result.output)
        for event in events:
            assert event["timestamp"] >= "2025-01-15"

    def test_history_unknown_entity_is_empty(self, runner, fixture_graph):
        result = runner.invoke(
            cli_module.main, ["temporal", "history", "nobody", "--format", "json"]
        )
        assert result.exit_code == 0
        assert json.loads(result.output) == []


class TestTemporalDistance:
    def test_distance_between_timestamps(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "distance",
                "--event1",
                "2025-01-01T00:00:00Z",
                "--event2",
                "2025-01-05T12:00:00Z",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["distance_seconds"] == 388800.0
        assert payload["distance_days"] == 4.5

    def test_distance_is_absolute(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "distance",
                "--event1",
                "2025-01-05T12:00:00Z",
                "--event2",
                "2025-01-01T00:00:00Z",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["distance_seconds"] == 388800.0

    def test_distance_rejects_garbage_timestamp(self, runner):
        result = runner.invoke(
            cli_module.main,
            ["temporal", "distance", "--event1", "a", "--event2", "b"],
        )
        assert result.exit_code != 0


class TestTemporalAllen:
    def test_allen_overlaps(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "allen",
                "--interval1",
                "2025-01-01/2025-01-05",
                "--interval2",
                "2025-01-03/2025-01-08",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["relation"] == "overlaps"

    def test_allen_before(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "allen",
                "--interval1",
                "2025-01-01/2025-01-02",
                "--interval2",
                "2025-02-01/2025-02-05",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["relation"] == "before"

    def test_allen_rejects_malformed_interval(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "allen",
                "--interval1",
                "not-an-interval",
                "--interval2",
                "2025-01-01/2025-01-02",
            ],
        )
        assert result.exit_code != 0


class TestTemporalPrecisionAndHistoryFixes:
    """Regression tests for review findings on the temporal CLI remap."""

    def test_allen_adjacent_intervals_meet(self, runner):
        # An end that equals the next interval's start is "meets", not
        # "overlaps": end-of-second expansion must not smear the boundary.
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "allen",
                "--interval1",
                "2025-01-01T00:00:00Z/2025-01-01T01:00:00Z",
                "--interval2",
                "2025-01-01T01:00:00Z/2025-01-01T02:00:00Z",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["relation"] == "meets"

    def test_allen_rejects_end_before_start(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "allen",
                "--interval1",
                "2025-01-02T00:00:00Z/2025-01-01T00:00:00Z",
                "--interval2",
                "2025-01-01T00:00:00Z/2025-01-03T00:00:00Z",
            ],
        )
        assert result.exit_code != 0

    def test_distance_preserves_subsecond_precision(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "temporal",
                "distance",
                "--event1",
                "2025-01-01T00:00:00.500+00:00",
                "--event2",
                "2025-01-01T00:00:00.900+00:00",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["distance_seconds"] == pytest.approx(0.4)
        assert ".500" in payload["event1"]

    def test_history_includes_recording_event_without_validity_dates(
        self, runner, monkeypatch
    ):
        # A decision recorded without explicit validity dates still has a
        # recorded_at, which must surface in its timeline.
        from semantica.context import ContextGraph

        graph = ContextGraph()
        graph.add_node(
            "decision_1",
            "decision",
            "Approve vendor X",
            recorded_at="2025-03-01T12:00:00Z",
        )
        monkeypatch.setattr(cli_module, "_load_context_graph", lambda cli_ctx: graph)
        result = runner.invoke(
            cli_module.main, ["temporal", "history", "decision_1", "--format", "json"]
        )
        assert result.exit_code == 0
        events = json.loads(result.output)
        assert len(events) == 1
        assert events[0]["timestamp"].startswith("2025-03-01 12:00:00")

    def test_temporal_commands_reject_non_memory_backend(self, runner):
        result = runner.invoke(
            cli_module.main,
            [
                "--store",
                "neo4j",
                "temporal",
                "snapshot",
                "--at",
                "2025-01-15T00:00:00Z",
            ],
        )
        assert result.exit_code != 0
        assert "not wired for the 'neo4j' backend yet" in result.output
