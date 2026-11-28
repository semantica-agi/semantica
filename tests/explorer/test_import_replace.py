"""Regression tests for ``POST /api/import?mode=replace`` (#1817).

The default import is additive, so re-importing an updated source left every
entity that had disappeared from it behind in the session. ``mode=replace``
rebuilds the session graph from the upload instead.
"""

import json

import pytest

from semantica.context.context_graph import ContextGraph

# fastapi ships in the optional `explorer` extra; skip rather than fail
# collection when it is absent (same guard as test_explorer_api.py).
pytest.importorskip("fastapi")

from semantica.explorer.app import create_app  # noqa: E402
from semantica.explorer.session import GraphSession  # noqa: E402

from starlette.testclient import TestClient  # noqa: E402


def _graph_file(nodes, edges=()):
    return json.dumps({"nodes": list(nodes), "edges": list(edges)})


def _post(client, payload, *, mode=None, name="graph.json"):
    params = {"mode": mode} if mode is not None else None
    return client.post(
        "/api/import",
        params=params,
        files={"file": (name, payload, "application/json")},
    )


def _node_ids(session):
    return set(session.graph.nodes)


def _indexed_ids(session, query):
    matches, _ = session._search_index.search(query, limit=50, filters={})
    return {node_id for node_id, _score in matches}


@pytest.fixture()
def session():
    graph = ContextGraph(advanced_analytics=False)
    sess = GraphSession(graph)
    sess.add_nodes_and_edges(
        [
            {"id": "A", "type": "entity", "properties": {"content": "stale apple"}},
            {"id": "K", "type": "entity", "properties": {"content": "kept kiwi"}},
        ],
        [{"source_id": "A", "target_id": "K", "type": "related_to"}],
    )
    return sess


@pytest.fixture()
def events(session):
    """Every (event, entity_id, payload) the graph emits from here on.

    Installed before ``create_app`` so the app's mutation bridge chains to it,
    the way a change tracker attached to the graph would be.
    """
    recorded = []
    session.graph.mutation_callback = lambda event, entity_id, payload: recorded.append(
        (event, entity_id, payload)
    )
    return recorded


@pytest.fixture()
def client(session, events):
    # TestClient as a context manager runs the lifespan, which installs the
    # mutation bridge -- the configuration the real Explorer runs in.
    with TestClient(create_app(session=session)) as test_client:
        yield test_client


# The source after the edit described in the issue: A removed, B added.
_UPDATED_SOURCE = _graph_file(
    [
        {"id": "K", "type": "entity", "text": "kept kiwi"},
        {"id": "B", "type": "entity", "text": "brand new banana"},
    ],
    [{"source": "K", "target": "B", "type": "related_to"}],
)


class TestAdditiveDefault:
    def test_default_mode_still_only_adds(self, client, session):
        response = _post(client, _UPDATED_SOURCE)
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "add"
        assert body["nodes_removed"] == 0
        assert body["edges_removed"] == 0
        # Backward compatible: A is still there, exactly as before the fix.
        assert _node_ids(session) == {"A", "K", "B"}

    def test_explicit_add_matches_default(self, client, session):
        response = _post(client, _UPDATED_SOURCE, mode="add")
        assert response.status_code == 200
        assert response.json()["mode"] == "add"
        assert _node_ids(session) == {"A", "K", "B"}


class TestReplaceMode:
    def test_removed_source_entities_leave_the_session(self, client, session):
        response = _post(client, _UPDATED_SOURCE, mode="replace")
        assert response.status_code == 200
        body = response.json()

        assert body["mode"] == "replace"
        assert body["nodes_removed"] == 1  # A
        assert body["nodes_added"] == 1  # B
        assert body["nodes_imported"] == 2  # K, B
        assert body["edges_removed"] == 1  # A -> K
        assert body["edges_added"] == 1  # K -> B

        assert _node_ids(session) == {"K", "B"}
        assert client.get("/api/graph/node/A").status_code == 404
        assert client.get("/api/graph/node/B").status_code == 200
        assert all(
            "A" not in (edge.source_id, edge.target_id) for edge in session.graph.edges
        )

    def test_search_index_drops_removed_nodes(self, client, session):
        assert "A" in _indexed_ids(session, "stale")
        _post(client, _UPDATED_SOURCE, mode="replace")
        assert "A" not in _indexed_ids(session, "stale")
        assert "B" in _indexed_ids(session, "banana")

    def test_unchanged_entities_are_not_counted_as_added(self, client):
        payload = _graph_file(
            [
                {"id": "A", "type": "entity", "text": "stale apple"},
                {"id": "K", "type": "entity", "text": "kept kiwi"},
            ],
            [{"source": "A", "target": "K", "type": "related_to"}],
        )
        body = _post(client, payload, mode="replace").json()
        assert body["nodes_added"] == 0
        assert body["nodes_removed"] == 0
        assert body["edges_added"] == 0
        assert body["edges_removed"] == 0
        assert body["nodes_imported"] == 2

    def test_node_content_comes_from_the_new_source(self, client, session):
        payload = _graph_file([{"id": "K", "type": "entity", "text": "rewritten kiwi"}])
        assert _post(client, payload, mode="replace").status_code == 200
        assert session.graph.nodes["K"].content == "rewritten kiwi"

    def test_csv_replace(self, client, session):
        csv_payload = "id,type,content\nB,entity,Only B\n"
        response = client.post(
            "/api/import",
            params={"mode": "replace"},
            files={"file": ("graph.csv", csv_payload, "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["nodes_removed"] == 2
        assert _node_ids(session) == {"B"}

    def test_derived_state_is_reset(self, client, session):
        session.graph._analytics_cache["centrality"] = {"A": 1.0}
        revision = session._graph_revision
        _post(client, _UPDATED_SOURCE, mode="replace")
        assert session.graph._analytics_cache == {}
        assert session._graph_revision > revision

    def test_annotations_follow_their_nodes(self, client, session):
        gone = session.add_annotation({"node_id": "A", "content": "about A"})
        kept = session.add_annotation({"node_id": "K", "content": "about K"})

        body = _post(client, _UPDATED_SOURCE, mode="replace").json()

        assert body["annotations_removed"] == 1
        assert session.get_annotation(gone) is None
        assert session.get_annotation(kept) is not None


class TestReplaceIsSafe:
    def test_invalid_mode_is_rejected(self, client, session):
        response = _post(client, _UPDATED_SOURCE, mode="wipe")
        assert response.status_code == 422
        assert _node_ids(session) == {"A", "K"}

    @pytest.mark.parametrize("payload", ['{"nodes": [], "edges": []}', "[]"])
    def test_empty_payload_does_not_wipe_the_session(self, client, session, payload):
        response = _post(client, payload, mode="replace")
        assert response.status_code == 422
        assert "empty" in response.json()["detail"].lower()
        assert _node_ids(session) == {"A", "K"}

    def test_empty_payload_is_still_fine_in_additive_mode(self, client, session):
        assert _post(client, '{"nodes": [], "edges": []}').status_code == 200
        assert _node_ids(session) == {"A", "K"}

    def test_rejected_payload_leaves_the_session_untouched(self, client, session):
        cyclic = _graph_file(
            [{"id": "X", "type": "concept"}, {"id": "Y", "type": "concept"}],
            [
                {"source": "X", "target": "Y", "type": "skos:broader"},
                {"source": "Y", "target": "X", "type": "skos:broader"},
            ],
        )
        response = _post(client, cyclic, mode="replace")
        assert response.status_code == 422
        # Validation runs before the clear, so nothing was lost.
        assert _node_ids(session) == {"A", "K"}
        assert len(session.graph.edges) == 1

    def test_existing_skos_edges_do_not_veto_the_new_graph(self, client, session):
        session.add_edges(
            [{"source_id": "K", "target_id": "A", "type": "skos:broader"}]
        )
        # Adding A -> K broader on top would be a cycle; replacing must not be.
        payload = _graph_file(
            [{"id": "A", "type": "concept"}, {"id": "K", "type": "concept"}],
            [{"source": "A", "target": "K", "type": "skos:broader"}],
        )
        assert _post(client, payload, mode="replace").status_code == 200
        assert _node_ids(session) == {"A", "K"}


class TestSessionWithoutBridge:
    """A bare GraphSession has no mutation bridge; it must sync itself."""

    def test_replace_rebuilds_the_index_and_bumps_the_revision(self, session):
        revision = session._graph_revision
        summary = session.replace_nodes_and_edges(
            [
                {
                    "id": "B",
                    "type": "entity",
                    "properties": {"content": "brand new banana"},
                }
            ],
            [],
        )
        assert summary["nodes_removed"] == 2
        assert summary["nodes_added"] == 1
        assert _node_ids(session) == {"B"}
        assert _indexed_ids(session, "stale") == set()
        assert _indexed_ids(session, "banana") == {"B"}
        assert session._graph_revision > revision


class TestUnloadablePayloads:
    """The empty-payload guard must look at what can be *loaded* (Qodo #2)."""

    @pytest.mark.parametrize(
        "payload",
        [
            '{"nodes": [{"text": "orphan, no id"}], "edges": []}',
            '{"nodes": [{"type": "entity"}], "edges": [{"type": "related_to"}]}',
        ],
    )
    def test_records_the_loader_skips_do_not_wipe_the_session(
        self, client, session, payload
    ):
        response = _post(client, payload, mode="replace")
        assert response.status_code == 422
        assert "no loadable" in response.json()["detail"]
        assert _node_ids(session) == {"A", "K"}
        assert len(session.graph.edges) == 1

    def test_one_loadable_record_is_enough(self, client, session):
        payload = (
            '{"nodes": [{"text": "orphan, no id"}, {"id": "B", "type": "entity"}]}'
        )
        assert _post(client, payload, mode="replace").status_code == 200
        assert _node_ids(session) == {"B"}


class TestRemovalsArePublished:
    """Removals must reach everything listening to the graph (Qodo #1, #3)."""

    def test_removed_ids_are_emitted_edges_first_then_a_reload(
        self, client, session, events
    ):
        removed_edge_id = session.graph.edges[0].edge_id
        events.clear()

        _post(client, _UPDATED_SOURCE, mode="replace")

        names = [name for name, _id, _payload in events]
        assert ("REMOVE_NODE", "A") in [(n, i) for n, i, _ in events]
        assert ("REMOVE_EDGE", removed_edge_id) in [(n, i) for n, i, _ in events]
        assert not [i for n, i, _ in events if n == "REMOVE_NODE" and i != "A"]

        last_remove = max(i for i, n in enumerate(names) if n.startswith("REMOVE_"))
        first_remove = min(i for i, n in enumerate(names) if n.startswith("REMOVE_"))
        assert names.index("REMOVE_EDGE") < names.index("REMOVE_NODE")
        assert names[-1] == "RELOAD_GRAPH"
        assert last_remove < len(names) - 1
        # Removals describe the final graph: they come after the rebuild's adds.
        assert first_remove > max(
            i for i, n in enumerate(names) if n.startswith("ADD_")
        )

        payload = next(p for n, i, p in events if n == "REMOVE_NODE" and i == "A")
        assert payload == {
            "entity_id": "A",
            "entity_kind": "node",
            "reason": "import_replace",
        }

    def test_nothing_is_removed_when_nothing_disappeared(self, client, events):
        payload = _graph_file(
            [
                {"id": "A", "type": "entity", "text": "stale apple"},
                {"id": "K", "type": "entity", "text": "kept kiwi"},
                {"id": "B", "type": "entity", "text": "banana"},
            ],
            [{"source": "A", "target": "K", "type": "related_to"}],
        )
        events.clear()
        _post(client, payload, mode="replace")
        assert not [n for n, _i, _p in events if n.startswith("REMOVE_")]

    def test_websocket_clients_are_told_what_was_removed(self, client):
        with client.websocket_connect("/ws/graph-updates") as socket:
            assert socket.receive_json()["event"] == "connection_ack"
            _post(client, _UPDATED_SOURCE, mode="replace")

            seen = set()
            for _ in range(50):
                message = socket.receive_json()
                data = message.get("data") or {}
                seen.add((data.get("event_type"), data.get("entity_id")))
                if data.get("event_type") == "RELOAD_GRAPH":
                    break
        assert ("REMOVE_NODE", "A") in seen

    def test_session_without_a_bridge_still_notifies_a_plain_callback(self):
        graph = ContextGraph(advanced_analytics=False)
        recorded = []
        graph.mutation_callback = lambda e, i, p: recorded.append((e, i))
        session = GraphSession(graph)
        session.add_nodes_and_edges(
            [{"id": "A", "type": "entity"}, {"id": "K", "type": "entity"}], []
        )
        recorded.clear()

        session.replace_nodes_and_edges([{"id": "K", "type": "entity"}], [])

        assert ("REMOVE_NODE", "A") in recorded
        assert recorded[-1] == ("RELOAD_GRAPH", "")


class TestProvenanceIsNotRewritten:
    """The audit store is independent and append-only; replace leaves it alone.

    ``/api/provenance`` answers from it before looking at the graph at all (it
    serves entities that were never graph nodes), exactly as it does for a node
    removed by a purge or a merge. Pinned here so changing it is a deliberate
    decision rather than a side effect of replace (Qodo #4).
    """

    def test_lineage_of_a_removed_node_stays_in_the_audit_store(self, client, session):
        session.provenance_manager.track_entity(
            entity_id="A", source="doc_1", entity_type="named_entity"
        )
        _post(client, _UPDATED_SOURCE, mode="replace")

        assert "A" not in _node_ids(session)
        response = client.get("/api/provenance", params={"node_id": "A"})
        assert response.status_code == 200
        assert response.json()["source"] == "audit"
