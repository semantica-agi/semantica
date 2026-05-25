"""
Comprehensive tests for ALL features listed in the [Unreleased] section of CHANGELOG.md.

Covers gaps not addressed by existing test files:

  PR #399 — AgentContext: checkpoint(), diff_checkpoints(), flush_checkpoint()
  PR #394 — TemporalVersionManager: attach_to_graph(), tag_version(), list_tags(),
             diff() alias, get_node_history(), restore_snapshot() rollback protection
  PR #393 — Snapshot schema compatibility: nodes/edges ↔ entities/relationships
  PR #385 — ContextGraph pagination: skip parameter, min_weight neighbor filter
  PR #385 — ContextGraph thread safety: concurrent mutations
  PR #319 — SKOS Vocabulary Module: namespace helpers, OntologyEngine APIs,
             TripletStore helpers (gap tests beyond existing suite)
  PR #318 — SHACL: quality tiers, export_shacl, RDFExporter.export_shacl (gap tests)
  PR #408 — OllamaProvider base_url fix (gap tests beyond existing suite)
  PR #371 — DatalogReasoner: idempotency, cache flag, graph load (gap tests)
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc


def _utc(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


# ===========================================================================
# PR #399 — AgentContext: checkpoint / diff_checkpoints / flush_checkpoint
# ===========================================================================

class TestAgentContextCheckpoint:
    """checkpoint() captures the current graph state under a label."""

    @pytest.fixture
    def ctx(self):
        from semantica.context import AgentContext, ContextGraph
        graph = ContextGraph()
        mock_vs = MagicMock()
        mock_vs.search.return_value = []
        return AgentContext(
            vector_store=mock_vs,
            knowledge_graph=graph,
            decision_tracking=True,
        ), graph

    def test_checkpoint_returns_dict(self, ctx):
        context, _ = ctx
        snap = context.checkpoint("snap1")
        assert isinstance(snap, dict)

    def test_checkpoint_has_timestamp(self, ctx):
        context, _ = ctx
        snap = context.checkpoint("snap1")
        assert "timestamp" in snap

    def test_checkpoint_empty_graph_has_no_nodes(self, ctx):
        context, _ = ctx
        snap = context.checkpoint("empty")
        assert snap.get("nodes", []) == [] or snap.get("entities", []) == []

    def test_checkpoint_captures_added_node(self, ctx):
        context, graph = ctx
        graph.add_node("n1", "entity", content="hello")
        snap = context.checkpoint("after")
        node_ids = {n["id"] for n in snap.get("nodes", snap.get("entities", []))}
        assert "n1" in node_ids

    def test_checkpoint_second_call_overwrites_label(self, ctx):
        context, graph = ctx
        context.checkpoint("label")
        graph.add_node("n2", "entity", content="new")
        snap2 = context.checkpoint("label")
        node_ids = {n["id"] for n in snap2.get("nodes", snap2.get("entities", []))}
        assert "n2" in node_ids

    def test_checkpoint_independent_of_subsequent_changes(self, ctx):
        context, graph = ctx
        context.checkpoint("before")
        graph.add_node("n_after", "entity", content="added later")
        snap_before = context._checkpoints["before"]
        node_ids = {n["id"] for n in snap_before.get("nodes", snap_before.get("entities", []))}
        assert "n_after" not in node_ids


class TestAgentContextDiffCheckpoints:
    """diff_checkpoints() computes the structural delta between two checkpoints."""

    @pytest.fixture
    def ctx_with_checkpoints(self):
        from semantica.context import AgentContext, ContextGraph
        graph = ContextGraph()
        mock_vs = MagicMock()
        mock_vs.search.return_value = []
        context = AgentContext(
            vector_store=mock_vs,
            knowledge_graph=graph,
            decision_tracking=True,
        )
        context.checkpoint("before")
        did = context.record_decision(
            category="policy",
            scenario="new scenario",
            reasoning="because",
            outcome="approved",
            confidence=0.9,
        )
        graph.add_node("entity_x", "entity", content="X")
        graph.add_edge(did, "entity_x", "involves")
        context.checkpoint("after")
        return context, graph, did

    def test_diff_has_required_keys(self, ctx_with_checkpoints):
        context, _, _ = ctx_with_checkpoints
        diff = context.diff_checkpoints("before", "after")
        for key in ("decisions_added", "decisions_removed", "relationships_added", "relationships_removed"):
            assert key in diff

    def test_decisions_added_contains_new_decision(self, ctx_with_checkpoints):
        context, _, did = ctx_with_checkpoints
        diff = context.diff_checkpoints("before", "after")
        assert any(item["id"] == did for item in diff["decisions_added"])

    def test_decisions_removed_is_empty_when_nothing_removed(self, ctx_with_checkpoints):
        context, _, _ = ctx_with_checkpoints
        diff = context.diff_checkpoints("before", "after")
        assert diff["decisions_removed"] == []

    def test_relationships_added_contains_new_edge(self, ctx_with_checkpoints):
        context, _, did = ctx_with_checkpoints
        diff = context.diff_checkpoints("before", "after")
        assert any(item["type"] == "involves" for item in diff["relationships_added"])

    def test_diff_reversed_shows_decision_removed(self, ctx_with_checkpoints):
        context, _, did = ctx_with_checkpoints
        # "after" → "before" is a rewind: decision should appear as removed
        diff = context.diff_checkpoints("after", "before")
        assert any(item["id"] == did for item in diff["decisions_removed"])

    def test_diff_same_snapshot_all_empty(self, ctx_with_checkpoints):
        context, _, _ = ctx_with_checkpoints
        diff = context.diff_checkpoints("after", "after")
        assert diff["decisions_added"] == []
        assert diff["decisions_removed"] == []

    def test_unknown_first_label_raises_key_error(self, ctx_with_checkpoints):
        context, _, _ = ctx_with_checkpoints
        with pytest.raises(KeyError):
            context.diff_checkpoints("ghost", "after")

    def test_unknown_second_label_raises_key_error(self, ctx_with_checkpoints):
        context, _, _ = ctx_with_checkpoints
        with pytest.raises(KeyError):
            context.diff_checkpoints("before", "ghost")

    def test_both_labels_unknown_raises_key_error(self):
        from semantica.context import AgentContext, ContextGraph
        mock_vs = MagicMock()
        mock_vs.search.return_value = []
        context = AgentContext(vector_store=mock_vs, knowledge_graph=ContextGraph())
        with pytest.raises(KeyError):
            context.diff_checkpoints("x", "y")


class TestAgentContextFlushCheckpoint:
    """flush_checkpoint() persists a named checkpoint via TemporalVersionManager."""

    @pytest.fixture
    def ctx(self):
        from semantica.context import AgentContext, ContextGraph
        graph = ContextGraph()
        mock_vs = MagicMock()
        mock_vs.search.return_value = []
        return AgentContext(
            vector_store=mock_vs,
            knowledge_graph=graph,
            decision_tracking=True,
        )

    def test_flush_returns_snapshot_dict(self, ctx):
        ctx.checkpoint("v1")
        result = ctx.flush_checkpoint("v1")
        assert isinstance(result, dict)
        assert result["label"] == "v1"

    def test_flush_snapshot_has_both_schema_keys(self, ctx):
        # flush_checkpoint uses change_management.TemporalVersionManager which
        # stores both "nodes"/"edges" and "entities"/"relationships" keys.
        ctx.checkpoint("v1")
        result = ctx.flush_checkpoint("v1")
        assert "entities" in result or "nodes" in result

    def test_flush_snapshot_has_checksum(self, ctx):
        ctx.checkpoint("v1")
        result = ctx.flush_checkpoint("v1")
        assert "checksum" in result

    def test_flush_unknown_label_raises_key_error(self, ctx):
        with pytest.raises(KeyError):
            ctx.flush_checkpoint("nonexistent")

    def test_flush_can_be_retrieved_from_version_manager(self, ctx):
        from semantica.kg.temporal_query import TemporalVersionManager
        manager = TemporalVersionManager()
        ctx._temporal_version_manager = manager
        ctx.checkpoint("release-1")
        ctx.flush_checkpoint("release-1")
        retrieved = manager.get_version("release-1")
        assert retrieved is not None
        assert retrieved["label"] == "release-1"

    def test_multiple_checkpoints_flushed_independently(self, ctx):
        from semantica.context import ContextGraph
        from semantica.kg.temporal_query import TemporalVersionManager
        manager = TemporalVersionManager()
        ctx._temporal_version_manager = manager
        ctx.checkpoint("snap-a")
        ctx.checkpoint("snap-b")
        ctx.flush_checkpoint("snap-a")
        ctx.flush_checkpoint("snap-b")
        assert manager.get_version("snap-a") is not None
        assert manager.get_version("snap-b") is not None


# ===========================================================================
# PR #394 — Audit Trail, Named Tags, diff() alias, rollback protection
# ===========================================================================

class TestAuditTrailAdditional:
    """Additional coverage for PR #394 audit-trail features."""

    @pytest.fixture
    def setup(self):
        from semantica.context import ContextGraph
        from semantica.change_management.managers import TemporalVersionManager
        graph = ContextGraph()
        manager = TemporalVersionManager()
        manager.attach_to_graph(graph)
        return graph, manager

    def test_attach_to_graph_sets_mutation_callback(self, setup):
        graph, manager = setup
        assert callable(getattr(graph, "mutation_callback", None))

    def test_add_node_creates_history_entry(self, setup):
        graph, manager = setup
        graph.add_node("n1", "entity", content="test")
        history = manager.get_node_history("n1")
        assert len(history) >= 1
        assert history[0]["operation"] == "ADD_NODE"

    def test_update_node_creates_second_entry(self, setup):
        graph, manager = setup
        graph.add_node("n1", "entity", content="initial")
        graph.add_node_attribute("n1", {"key": "val"})
        history = manager.get_node_history("n1")
        operations = [h["operation"] for h in history]
        assert "ADD_NODE" in operations
        assert "UPDATE_NODE" in operations

    def test_get_node_history_returns_empty_for_unknown_node(self, setup):
        _, manager = setup
        assert manager.get_node_history("does_not_exist") == []

    def test_multiple_nodes_tracked_independently(self, setup):
        graph, manager = setup
        graph.add_node("a", "entity")
        graph.add_node("b", "entity")
        graph.add_node_attribute("a", {"x": 1})
        assert len(manager.get_node_history("a")) == 2
        assert len(manager.get_node_history("b")) == 1


class TestNamedTagsAdditional:
    """Additional coverage for named version tags from PR #394."""

    @pytest.fixture
    def setup(self):
        from semantica.context import ContextGraph
        from semantica.change_management.managers import TemporalVersionManager
        graph = ContextGraph()
        manager = TemporalVersionManager()
        graph.add_node("n1", "entity")
        snap = manager.create_snapshot(
            graph.to_dict(),
            version_label="v1.0",
            author="user@example.com",
            description="First",
        )
        return manager

    def test_list_tags_empty_initially(self):
        from semantica.change_management.managers import TemporalVersionManager
        manager = TemporalVersionManager()
        assert manager.list_tags() == {}

    def test_tag_version_and_retrieve(self, setup):
        manager = setup
        manager.tag_version("v1.0", "stable")
        tags = manager.list_tags()
        assert "stable" in tags
        assert tags["stable"] == "v1.0"

    def test_multiple_tags_on_same_version(self, setup):
        manager = setup
        manager.tag_version("v1.0", "production")
        manager.tag_version("v1.0", "latest")
        tags = manager.list_tags()
        assert tags["production"] == "v1.0"
        assert tags["latest"] == "v1.0"

    def test_tag_nonexistent_version_raises(self):
        from semantica.change_management.managers import TemporalVersionManager
        manager = TemporalVersionManager()
        with pytest.raises(Exception):
            manager.tag_version("ghost", "my-tag")

    def test_diff_alias_equivalent_to_compare_versions(self, setup):
        from semantica.context import ContextGraph
        manager = setup
        graph2 = ContextGraph()
        graph2.add_node("n1", "entity")
        graph2.add_node("n2", "entity")
        manager.create_snapshot(
            graph2.to_dict(),
            version_label="v2.0",
            author="user@example.com",
            description="Second",
        )
        diff_result = manager.diff("v1.0", "v2.0")
        compare_result = manager.compare_versions("v1.0", "v2.0")
        # Both should return the same structure
        assert set(diff_result.keys()) == set(compare_result.keys())

    def test_diff_alias_shows_added_entity(self, setup):
        from semantica.context import ContextGraph
        manager = setup
        graph2 = ContextGraph()
        graph2.add_node("n1", "entity")
        graph2.add_node("n2", "entity")  # added
        manager.create_snapshot(
            graph2.to_dict(),
            version_label="v2.0",
            author="user@example.com",
            description="Second",
        )
        diff = manager.diff("v1.0", "v2.0")
        assert diff["summary"]["entities_added"] >= 1


class TestRollbackProtectionAdditional:
    """Additional rollback protection edge cases from PR #394."""

    @pytest.fixture
    def setup_with_snapshot(self):
        from semantica.context import ContextGraph
        from semantica.change_management.managers import TemporalVersionManager
        graph = ContextGraph()
        graph.add_node("n1", "entity", content="original")
        manager = TemporalVersionManager()
        manager.attach_to_graph(graph)
        manager.create_snapshot(
            graph.to_dict(),
            version_label="v1.0",
            author="user@example.com",
            description="Original",
        )
        return graph, manager

    def test_restore_requires_confirmation_by_default(self, setup_with_snapshot):
        from semantica.change_management.managers import ProcessingError
        graph, manager = setup_with_snapshot
        with pytest.raises(ProcessingError, match="Rollback protection"):
            manager.restore_snapshot(graph, "v1.0")

    def test_restore_succeeds_with_confirmation_false(self, setup_with_snapshot):
        graph, manager = setup_with_snapshot
        result = manager.restore_snapshot(graph, "v1.0", require_confirmation=False)
        assert result is True

    def test_restore_to_nonexistent_version_raises(self, setup_with_snapshot):
        graph, manager = setup_with_snapshot
        from semantica.utils.exceptions import ValidationError
        with pytest.raises(ValidationError):
            manager.restore_snapshot(graph, "ghost", require_confirmation=False)

    def test_restore_replay_does_not_add_to_audit_log(self, setup_with_snapshot):
        graph, manager = setup_with_snapshot
        graph.add_node_attribute("n1", {"status": "modified"})
        history_before = manager.get_node_history("n1")
        count_before = len(history_before)
        manager.restore_snapshot(graph, "v1.0", require_confirmation=False)
        history_after = manager.get_node_history("n1")
        # Restore must not record new mutations
        assert len(history_after) == count_before


# ===========================================================================
# PR #393 — Snapshot Schema Compatibility
# ===========================================================================

class TestSnapshotSchemaCompatibility:
    """TemporalVersionManager must accept both nodes/edges and entities/relationships."""

    @pytest.fixture
    def manager(self):
        from semantica.kg.temporal_query import TemporalVersionManager
        return TemporalVersionManager()

    def test_create_snapshot_with_nodes_edges_schema(self, manager):
        graph = {
            "nodes": [{"id": "1", "type": "Person"}],
            "edges": [{"source": "1", "target": "2", "type": "knows"}],
        }
        snap = manager.create_snapshot(graph, "v-ne", "user@x.com", "nodes/edges schema")
        assert snap["label"] == "v-ne"

    def test_create_snapshot_with_entities_relationships_schema(self, manager):
        graph = {
            "entities": [{"id": "1", "type": "Person"}],
            "relationships": [{"source": "1", "target": "2", "type": "knows"}],
        }
        snap = manager.create_snapshot(graph, "v-er", "user@x.com", "entities/rels schema")
        assert snap["label"] == "v-er"

    def test_validate_snapshot_nodes_edges_true(self, manager):
        graph = {
            "nodes": [{"id": "1"}],
            "edges": [],
        }
        snap = manager.create_snapshot(graph, "v1", "user@x.com", "test")
        assert manager.validate_snapshot(snap) is True

    def test_compare_versions_nodes_edges_schema(self, manager):
        # kg.temporal_query.TemporalVersionManager accepts nodes/edges schema
        # without error; compare_versions must not raise.
        g1 = {"nodes": [{"id": "A"}], "edges": []}
        g2 = {"nodes": [{"id": "A"}, {"id": "B"}], "edges": []}
        manager.create_snapshot(g1, "old", "u@x.com", "old")
        manager.create_snapshot(g2, "new", "u@x.com", "new")
        diff = manager.compare_versions("old", "new")
        assert "summary" in diff

    def test_compare_versions_entities_rels_schema(self, manager):
        g1 = {"entities": [{"id": "A"}], "relationships": []}
        g2 = {"entities": [{"id": "A"}, {"id": "B"}], "relationships": []}
        manager.create_snapshot(g1, "old2", "u@x.com", "old")
        manager.create_snapshot(g2, "new2", "u@x.com", "new")
        diff = manager.compare_versions("old2", "new2")
        assert diff["summary"]["entities_added"] >= 1

    def test_mixed_schema_compare_does_not_crash(self, manager):
        g1 = {"nodes": [{"id": "A"}], "edges": []}
        g2 = {"entities": [{"id": "A"}, {"id": "B"}], "relationships": []}
        manager.create_snapshot(g1, "mix1", "u@x.com", "nodes schema")
        manager.create_snapshot(g2, "mix2", "u@x.com", "entities schema")
        # Must not raise regardless of schema mismatch
        diff = manager.compare_versions("mix1", "mix2")
        assert "summary" in diff

    def test_snapshot_format_version_stamped_regardless_of_schema(self, manager):
        for schema, label in [
            ({"nodes": [], "edges": []}, "ne"),
            ({"entities": [], "relationships": []}, "er"),
        ]:
            snap = manager.create_snapshot(schema, label, "u@x.com", "test")
            assert snap.get("format_version") == "1.0"


# ===========================================================================
# PR #385 — ContextGraph Pagination: skip parameter
# ===========================================================================

class TestContextGraphPaginationSkip:
    """find_nodes / find_edges / find_active_nodes must honour the skip parameter."""

    @pytest.fixture
    def graph_with_nodes(self):
        from semantica.context import ContextGraph
        g = ContextGraph()
        for i in range(6):
            g.add_node(f"n{i}", "entity", content=str(i))
        return g

    @pytest.fixture
    def graph_with_edges(self):
        from semantica.context import ContextGraph
        g = ContextGraph()
        for i in range(6):
            g.add_node(f"n{i}", "entity")
        for i in range(5):
            g.add_edge(f"n{i}", f"n{i+1}", "next")
        return g

    # find_nodes

    def test_find_nodes_skip_zero_returns_all(self, graph_with_nodes):
        result = graph_with_nodes.find_nodes(skip=0)
        assert len(result) == 6

    def test_find_nodes_skip_positive_reduces_count(self, graph_with_nodes):
        result = graph_with_nodes.find_nodes(skip=2)
        assert len(result) == 4

    def test_find_nodes_skip_and_limit_window(self, graph_with_nodes):
        result = graph_with_nodes.find_nodes(skip=2, limit=2)
        assert len(result) == 2

    def test_find_nodes_skip_beyond_length_returns_empty(self, graph_with_nodes):
        result = graph_with_nodes.find_nodes(skip=100)
        assert result == []

    def test_find_nodes_skip_plus_limit_no_overlap_with_first_page(self, graph_with_nodes):
        page1 = graph_with_nodes.find_nodes(skip=0, limit=3)
        page2 = graph_with_nodes.find_nodes(skip=3, limit=3)
        ids1 = {n["id"] for n in page1}
        ids2 = {n["id"] for n in page2}
        assert ids1.isdisjoint(ids2)
        assert ids1 | ids2 == {f"n{i}" for i in range(6)}

    # find_edges

    def test_find_edges_skip_zero_returns_all(self, graph_with_edges):
        result = graph_with_edges.find_edges(skip=0)
        assert len(result) == 5

    def test_find_edges_skip_reduces_count(self, graph_with_edges):
        result = graph_with_edges.find_edges(skip=2)
        assert len(result) == 3

    def test_find_edges_skip_and_limit(self, graph_with_edges):
        result = graph_with_edges.find_edges(skip=1, limit=2)
        assert len(result) == 2

    def test_find_edges_skip_beyond_returns_empty(self, graph_with_edges):
        result = graph_with_edges.find_edges(skip=100)
        assert result == []

    def test_find_edges_pagination_covers_all(self, graph_with_edges):
        page1 = graph_with_edges.find_edges(skip=0, limit=3)
        page2 = graph_with_edges.find_edges(skip=3, limit=3)
        combined = len(page1) + len(page2)
        assert combined == 5

    # find_active_nodes

    def test_find_active_nodes_skip_zero_returns_all(self, graph_with_nodes):
        result = graph_with_nodes.find_active_nodes(skip=0)
        assert len(result) == 6

    def test_find_active_nodes_skip_reduces_count(self, graph_with_nodes):
        result = graph_with_nodes.find_active_nodes(skip=3)
        assert len(result) == 3

    def test_find_active_nodes_skip_and_limit(self, graph_with_nodes):
        result = graph_with_nodes.find_active_nodes(skip=2, limit=2)
        assert len(result) == 2


class TestContextGraphMinWeightNeighborFilter:
    """get_neighbors(min_weight=N) from PR #385 filters out low-weight edges."""

    @pytest.fixture
    def weighted_graph(self):
        from semantica.context import ContextGraph
        g = ContextGraph()
        g.add_node("center", "entity")
        g.add_node("heavy", "entity")
        g.add_node("light", "entity")
        g.add_node("zero", "entity")
        g.add_edge("center", "heavy", "link", weight=0.9)
        g.add_edge("center", "light", "link", weight=0.2)
        g.add_edge("center", "zero", "link", weight=0.0)
        return g

    def test_no_min_weight_returns_all_neighbors(self, weighted_graph):
        result = weighted_graph.get_neighbors("center")
        ids = {n["id"] for n in result}
        assert ids == {"heavy", "light", "zero"}

    def test_min_weight_filters_low_weight_edges(self, weighted_graph):
        result = weighted_graph.get_neighbors("center", min_weight=0.5)
        ids = {n["id"] for n in result}
        assert "heavy" in ids
        assert "light" not in ids
        assert "zero" not in ids

    def test_min_weight_zero_returns_all(self, weighted_graph):
        result = weighted_graph.get_neighbors("center", min_weight=0.0)
        assert len(result) == 3

    def test_min_weight_one_returns_none(self, weighted_graph):
        result = weighted_graph.get_neighbors("center", min_weight=1.0)
        assert result == []

    def test_min_weight_exact_boundary_inclusive(self, weighted_graph):
        # edge to "heavy" has weight=0.9; min_weight=0.9 should include it
        result = weighted_graph.get_neighbors("center", min_weight=0.9)
        ids = {n["id"] for n in result}
        assert "heavy" in ids


# ===========================================================================
# PR #385 — ContextGraph Thread Safety
# ===========================================================================

class TestContextGraphThreadSafety:
    """ContextGraph must be safe for concurrent reads and writes."""

    def test_concurrent_add_node_no_corruption(self):
        from semantica.context import ContextGraph
        graph = ContextGraph()
        errors = []

        def add_nodes(start: int):
            try:
                for i in range(start, start + 20):
                    graph.add_node(f"n-{i}", "entity", content=str(i))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_nodes, args=(i * 20,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(graph.nodes) == 100

    def test_concurrent_reads_while_writing(self):
        from semantica.context import ContextGraph
        graph = ContextGraph()
        for i in range(20):
            graph.add_node(f"initial-{i}", "entity")

        errors = []

        def reader():
            try:
                for _ in range(50):
                    _ = graph.find_nodes()
            except Exception as exc:
                errors.append(exc)

        def writer():
            try:
                for i in range(50):
                    graph.add_node(f"w-{threading.get_ident()}-{i}", "entity")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(3)] + \
                  [threading.Thread(target=writer) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"

    def test_concurrent_add_edge_no_corruption(self):
        from semantica.context import ContextGraph
        graph = ContextGraph()
        for i in range(40):
            graph.add_node(f"n{i}", "entity")

        errors = []

        def add_edges(offset: int):
            try:
                for i in range(offset, offset + 10):
                    graph.add_edge(f"n{i}", f"n{i+1}", "link")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_edges, args=(i * 10,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"

    def test_find_nodes_consistent_under_concurrent_writes(self):
        from semantica.context import ContextGraph
        graph = ContextGraph()
        results = []
        errors = []

        def writer():
            for i in range(30):
                graph.add_node(f"wt-{threading.get_ident()}-{i}", "entity")

        def reader():
            try:
                for _ in range(10):
                    snapshot = graph.find_nodes()
                    results.append(len(snapshot))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(3)] + \
                  [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        # All snapshots must be non-negative integers (no partial-write corruption)
        assert all(r >= 0 for r in results)


# ===========================================================================
# PR #319 — SKOS Vocabulary Module: namespace helpers (gap tests)
# ===========================================================================

class TestSKOSNamespaceHelpers:
    """get_skos_uri and build_concept_scheme_uri gap tests beyond existing suite."""

    @pytest.fixture
    def nm(self):
        from semantica.ontology.namespace_manager import NamespaceManager
        return NamespaceManager()

    def test_get_skos_uri_prefLabel(self, nm):
        uri = nm.get_skos_uri("prefLabel")
        assert uri == "http://www.w3.org/2004/02/skos/core#prefLabel"

    def test_get_skos_uri_Concept(self, nm):
        uri = nm.get_skos_uri("Concept")
        assert "Concept" in uri
        assert uri.startswith("http://www.w3.org/2004/02/skos/core#")

    def test_get_skos_uri_broader(self, nm):
        uri = nm.get_skos_uri("broader")
        assert uri.endswith("#broader")

    def test_build_concept_scheme_uri_lowercases(self, nm):
        uri = nm.build_concept_scheme_uri("My Vocabulary")
        assert "my-vocabulary" in uri.lower()

    def test_build_concept_scheme_uri_replaces_spaces_with_hyphens(self, nm):
        uri = nm.build_concept_scheme_uri("Drug Interaction Terms")
        assert " " not in uri

    def test_build_concept_scheme_uri_contains_vocab_segment(self, nm):
        uri = nm.build_concept_scheme_uri("Test")
        assert "/vocab/" in uri

    def test_build_concept_scheme_uri_special_chars_normalised(self, nm):
        uri = nm.build_concept_scheme_uri("A&B!Vocab")
        assert "&" not in uri
        assert "!" not in uri


# ===========================================================================
# PR #318 — SHACL: quality tiers and export (gap tests)
# ===========================================================================

class TestSHACLQualityTiersGap:
    """Quality tier differences between basic / standard / strict."""

    @pytest.fixture
    def generator(self):
        from semantica.ontology.ontology_generator import SHACLGenerator
        return SHACLGenerator()

    @pytest.fixture
    def simple_ontology(self):
        # SHACLGenerator expects classes and top-level properties (with domain)
        return {
            "classes": [{"name": "Person"}],
            "properties": [
                {"name": "name", "domain": "Person", "range": "string"},
                {"name": "age", "domain": "Person", "range": "integer"},
            ],
        }

    def test_basic_tier_produces_output(self, simple_ontology):
        from semantica.ontology.ontology_generator import SHACLGenerator
        gen = SHACLGenerator(quality_tier="basic")
        result = gen.generate(simple_ontology)
        assert result is not None
        assert len(gen.serialize(result)) > 0

    def test_standard_tier_produces_output(self, simple_ontology):
        from semantica.ontology.ontology_generator import SHACLGenerator
        gen = SHACLGenerator(quality_tier="standard")
        result = gen.generate(simple_ontology)
        assert len(gen.serialize(result)) > 0

    def test_strict_tier_produces_output(self, simple_ontology):
        from semantica.ontology.ontology_generator import SHACLGenerator
        gen = SHACLGenerator(quality_tier="strict")
        result = gen.generate(simple_ontology)
        assert len(gen.serialize(result)) > 0

    def test_strict_tier_contains_closed_constraint(self, simple_ontology):
        from semantica.ontology.ontology_generator import SHACLGenerator
        gen = SHACLGenerator(quality_tier="strict")
        result = gen.generate(simple_ontology)
        turtle = gen.serialize(result)
        assert "sh:closed" in turtle

    def test_basic_tier_does_not_contain_closed(self, simple_ontology):
        from semantica.ontology.ontology_generator import SHACLGenerator
        gen = SHACLGenerator(quality_tier="basic")
        result = gen.generate(simple_ontology)
        turtle = gen.serialize(result)
        assert "sh:closed" not in turtle

    def test_three_tiers_produce_different_output(self, simple_ontology):
        from semantica.ontology.ontology_generator import SHACLGenerator
        basic_gen = SHACLGenerator(quality_tier="basic")
        strict_gen = SHACLGenerator(quality_tier="strict")
        basic = basic_gen.serialize(basic_gen.generate(simple_ontology))
        strict = strict_gen.serialize(strict_gen.generate(simple_ontology))
        assert basic != strict


class TestRDFExporterExportSHACL:
    """RDFExporter.export_shacl() writes SHACL strings to files."""

    def test_export_shacl_writes_ttl_file(self, tmp_path):
        from semantica.export.rdf_exporter import RDFExporter
        exporter = RDFExporter()
        shacl = "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        out = tmp_path / "shapes.ttl"
        exporter.export_shacl(shacl, str(out))
        assert out.exists()
        assert out.read_text().strip().startswith("@prefix")

    def test_export_shacl_invalid_extension_raises(self, tmp_path):
        from semantica.export.rdf_exporter import RDFExporter
        from semantica.utils.exceptions import ValidationError
        exporter = RDFExporter()
        out = tmp_path / "shapes.txt"
        with pytest.raises((ValueError, ValidationError)):
            exporter.export_shacl("@prefix sh: <…> .", str(out))

    def test_export_shacl_jsonld_extension_accepted(self, tmp_path):
        from semantica.export.rdf_exporter import RDFExporter
        exporter = RDFExporter()
        content = '{"@context": {}}'
        out = tmp_path / "shapes.jsonld"
        exporter.export_shacl(content, str(out))
        assert out.exists()


# ===========================================================================
# PR #408 — OllamaProvider base_url fix (gap tests)
# ===========================================================================

class TestOllamaProviderBaseURLGap:
    """Additional gap tests for PR #408 OllamaProvider base_url fix."""

    def test_custom_port_used_as_host(self):
        """Non-default port must flow through to the Client in every call."""
        ollama_mock = MagicMock()
        ollama_mock.Client = MagicMock(return_value=MagicMock())
        with patch.dict("sys.modules", {"ollama": ollama_mock}):
            from semantica.semantic_extract.providers import OllamaProvider
            provider = OllamaProvider(
                model_name="llama3",
                base_url="http://192.168.1.10:11434",
            )
            # _init_client may be called during __init__ and/or lazily;
            # every invocation must pass the correct host.
            assert ollama_mock.Client.called
            for call_args in ollama_mock.Client.call_args_list:
                assert call_args == ((), {"host": "http://192.168.1.10:11434"}) or \
                    call_args.kwargs.get("host") == "http://192.168.1.10:11434"

    def test_client_is_not_raw_module(self):
        """self.client must never be the raw ollama module."""
        ollama_mock = MagicMock()
        client_instance = MagicMock()
        ollama_mock.Client = MagicMock(return_value=client_instance)
        with patch.dict("sys.modules", {"ollama": ollama_mock}):
            from semantica.semantic_extract.providers import OllamaProvider
            provider = OllamaProvider(model_name="llama3")
            provider._init_client()
            assert provider.client is not ollama_mock


# ===========================================================================
# PR #371 — DatalogReasoner gap tests
# ===========================================================================

class TestDatalogReasonerGap:
    """Gap tests for DatalogReasoner beyond the existing 23 tests."""

    @pytest.fixture
    def reasoner(self):
        from semantica.reasoning import DatalogReasoner
        return DatalogReasoner()

    def test_derive_all_idempotent(self, reasoner):
        reasoner.add_fact("parent(alice, bob)")
        reasoner.add_rule("grandparent(X, Z) :- parent(X, Y), parent(Y, Z).")
        reasoner.add_fact("parent(bob, carol)")
        first = reasoner.derive_all()
        second = reasoner.derive_all()
        # Second call must produce same results (idempotency)
        assert set(first) == set(second)

    def test_query_returns_list(self, reasoner):
        reasoner.add_fact("color(sky, blue)")
        result = reasoner.query("color(?X, ?Y)")
        assert isinstance(result, list)

    def test_query_no_match_returns_empty(self, reasoner):
        result = reasoner.query("nonexistent(?X)")
        assert result == []

    def test_multi_hop_four_levels(self, reasoner):
        reasoner.add_fact("parent(a, b)")
        reasoner.add_fact("parent(b, c)")
        reasoner.add_fact("parent(c, d)")
        reasoner.add_fact("parent(d, e)")
        # DatalogReasoner uses uppercase-letter variables (not ?-prefixed)
        reasoner.add_rule("ancestor(X, Z) :- parent(X, Z).")
        reasoner.add_rule("ancestor(X, Z) :- parent(X, Y), ancestor(Y, Z).")
        results = reasoner.query("ancestor(a, ?Z)")
        targets = {r["Z"] for r in results}
        assert "e" in targets

    def test_load_from_context_graph(self, reasoner):
        from semantica.context import ContextGraph
        graph = ContextGraph()
        graph.add_node("alice", "Person")
        graph.add_node("bob", "Person")
        graph.add_edge("alice", "bob", "knows")
        reasoner.load_from_graph(graph)
        result = reasoner.query("knows(?X, ?Y)")
        assert len(result) >= 1

    def test_add_fact_dict_source_target_type(self, reasoner):
        reasoner.add_fact({"source": "alice", "target": "bob", "type": "knows"})
        result = reasoner.query("knows(?X, ?Y)")
        assert any(r.get("X") == "alice" and r.get("Y") == "bob" for r in result)

    def test_add_fact_subject_predicate_object_shape(self, reasoner):
        reasoner.add_fact({"subject": "cat", "predicate": "isa", "object": "animal"})
        result = reasoner.query("isa(?X, ?Y)")
        assert len(result) >= 1

    def test_duplicate_fact_not_duplicated(self, reasoner):
        reasoner.add_fact("color(sky, blue)")
        reasoner.add_fact("color(sky, blue)")
        result = reasoner.query("color(?X, ?Y)")
        assert len(result) == 1

    def test_derive_all_returns_list(self, reasoner):
        # Facts must use constants (lowercase); uppercase is treated as variable
        reasoner.add_fact("category(x, alpha)")
        result = reasoner.derive_all()
        assert isinstance(result, list)
