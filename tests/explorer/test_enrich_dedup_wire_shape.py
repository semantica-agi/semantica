"""Regression tests for issue #1585.

``POST /api/enrich/dedup`` serialized ``DuplicateCandidate`` fields verbatim
(``entity1``/``entity2``/``similarity_score``), but the Entity Resolution tab
(``EntityResolutionTab.tsx::parseDuplicates``) reads only
``entity_a``/``entity_b``/``similarity|score``. The keys were disjoint, so
every flagged pair rendered with empty ids and a 0% score bar, and merge
POSTed empty ids.

Each test below fails while the backend omits the frontend-facing keys and
passes once the route maps candidates to the agreed pair shape.
"""

import pytest

# fastapi ships in the optional `explorer` extra, not in `dev`, so this module
# must skip rather than fail collection when it is absent.
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from semantica.context.context_graph import ContextGraph  # noqa: E402
from semantica.explorer.app import create_app  # noqa: E402
from semantica.explorer.session import GraphSession  # noqa: E402


def _client_with_duplicates() -> TestClient:
    graph = ContextGraph(advanced_analytics=False)
    graph.add_node("acme_inc", "Organization", content="Acme Corporation")
    graph.add_node("acme_corp", "Organization", content="Acme Corp")
    graph.add_node("globex", "Organization", content="Globex Industries")
    return TestClient(create_app(session=GraphSession(graph)))


def _parse_score(item: dict) -> float:
    """Mirror EntityResolutionTab.tsx::parseDuplicates score logic."""
    return float(item.get("similarity") if item.get("similarity") is not None else item.get("score", 0))


def _extract_id(entity) -> str:
    """Mirror EntityResolutionTab.tsx::extractId logic."""
    if not entity:
        return ""
    if isinstance(entity, str):
        return entity
    return str(entity.get("id", entity.get("text", entity)))


def test_dedup_pairs_use_frontend_shape():
    """Flagged pairs must carry entity_a/entity_b with resolvable ids.

    Fails before the fix: the backend emits entity1/entity2, so both ids
    resolve to "" and the score to 0 — exactly what the UI renders.
    """
    with _client_with_duplicates() as client:
        response = client.post("/api/enrich/dedup", json={"threshold": 0.5})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_flagged"] >= 1
    assert len(payload["duplicates"]) >= 1

    for item in payload["duplicates"]:
        assert _extract_id(item.get("entity_a")), f"entity_a id missing in {item}"
        assert _extract_id(item.get("entity_b")), f"entity_b id missing in {item}"
        assert "similarity" in item, f"similarity key missing in {item}"
        assert item["similarity"] == item["similarity_score"], f"similarity diverged in {item}"
        assert _parse_score(item) > 0, f"score is 0 in {item}"


def test_dedup_pair_ids_reference_graph_nodes():
    """The ids in each pair must be nodes that actually exist in the graph."""
    graph = ContextGraph(advanced_analytics=False)
    graph.add_node("acme_inc", "Organization", content="Acme Corporation")
    graph.add_node("acme_corp", "Organization", content="Acme Corp")

    with TestClient(create_app(session=GraphSession(graph))) as client:
        response = client.post("/api/enrich/dedup", json={"threshold": 0.5})

    assert response.status_code == 200, response.text
    node_ids = {node.get("id") for node in graph.to_kg_dict().get("entities", [])}
    for item in response.json()["duplicates"]:
        assert _extract_id(item.get("entity_a")) in node_ids
        assert _extract_id(item.get("entity_b")) in node_ids


def test_dedup_merge_round_trip():
    """Ids from a dedup pair must drive a successful merge.

    Covers the reported failure end to end: before the fix the pairs
    carried no frontend-facing ids, so a merge built from them POSTed
    empty ids and failed with 404 ``Primary node '' not found``.
    """
    with _client_with_duplicates() as client:
        scan = client.post("/api/enrich/dedup", json={"threshold": 0.5})
        assert scan.status_code == 200, scan.text
        assert scan.json()["duplicates"], "expected at least one flagged pair"
        first = scan.json()["duplicates"][0]
        primary_id = _extract_id(first.get("entity_a"))
        duplicate_id = _extract_id(first.get("entity_b"))
        assert primary_id and duplicate_id, f"pair ids missing in {first}"

        merge = client.post(
            "/api/enrich/merge",
            json={"primary_id": primary_id, "duplicate_ids": [duplicate_id]},
        )

    assert merge.status_code == 200, merge.text
    assert merge.json()["removed_ids"] == [duplicate_id]
