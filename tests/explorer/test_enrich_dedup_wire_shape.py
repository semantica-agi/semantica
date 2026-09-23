"""Regression tests for issues #1585 and #1592.

``POST /api/enrich/dedup`` serialized ``DuplicateCandidate`` fields verbatim
(``entity1``/``entity2``/``similarity_score``), but the Entity Resolution tab
(``EntityResolutionTab.tsx::parseDuplicates``) reads only
``entity_a``/``entity_b``/``similarity|score``. The keys were disjoint, so
every flagged pair rendered with empty ids and a 0% score bar, and merge
POSTed empty ids.

#1585 fixed the mapping; #1592 moves the contract into the schema. The
``DedupResponse.duplicates`` list is now typed as ``DuplicatePair`` instead of
``List[Dict[str, Any]]``, so a producer that drifts off both the canonical and
the legacy spelling fails validation at the API boundary rather than shipping
rows the UI renders as 0%.

The route tests below fail while the backend omits the frontend-facing keys;
the schema tests fail while the wire shape is an untyped dict.
"""

import pytest

# fastapi ships in the optional `explorer` extra, not in `dev`, so this module
# must skip rather than fail collection when it is absent.
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from semantica.context.context_graph import ContextGraph  # noqa: E402
from semantica.explorer.app import create_app  # noqa: E402
from semantica.explorer.schemas import DedupResponse, DuplicatePair  # noqa: E402
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


def test_dedup_route_preserves_detector_extras():
    """``reasons``/``metadata`` must survive the typed boundary (#1592).

    ``DuplicatePair`` sets ``extra="allow"`` precisely so that constraining
    the wire shape does not silently drop detector diagnostics.
    """
    with _client_with_duplicates() as client:
        response = client.post("/api/enrich/dedup", json={"threshold": 0.5})

    assert response.status_code == 200, response.text
    assert response.json()["duplicates"], "expected at least one flagged pair"
    for item in response.json()["duplicates"]:
        assert "reasons" in item, f"reasons dropped from {item}"
        assert "metadata" in item, f"metadata dropped from {item}"


def test_dedup_route_rejects_drifted_pair_shape(monkeypatch):
    """A pair on neither spelling must fail loudly, not render as 0% (#1592).

    Before the typed response this returned 200 with unusable rows, which is
    exactly how #1585 reached users. The route now surfaces a contract error.
    """

    class _DriftedDetector:
        """Stands in for a future refactor that renames the pair fields."""

        def __init__(self, *args, **kwargs):
            pass

        def detect_duplicates(self, entities, **kwargs):
            return [{"left": "acme_inc", "right": "acme_corp", "sim": 0.95}]

    monkeypatch.setattr("semantica.deduplication.DuplicateDetector", _DriftedDetector)

    with _client_with_duplicates() as client:
        response = client.post("/api/enrich/dedup", json={"threshold": 0.5})

    assert response.status_code == 500, response.text
    assert "DuplicatePair" in response.json()["detail"]


def test_duplicate_pair_accepts_detector_keys():
    """Legacy DuplicateCandidate keys in, both spellings out.

    ``DuplicateCandidate`` always carries both ``similarity_score`` and
    ``confidence`` as distinct values.  The mirroring must map each to its own
    canonical twin without collapsing them.
    """
    pair = DuplicatePair.model_validate(
        {
            "entity1": {"id": "acme_inc", "text": "Acme Corporation"},
            "entity2": {"id": "acme_corp", "text": "Acme Corp"},
            "similarity_score": 0.91,
            "confidence": 0.87,
        }
    )
    dumped = pair.model_dump()

    assert dumped["entity_a"] == {"id": "acme_inc", "text": "Acme Corporation"}
    assert dumped["entity_b"] == {"id": "acme_corp", "text": "Acme Corp"}
    # Legacy keys stay on the wire for pre-#1586 clients.
    assert dumped["entity1"] == dumped["entity_a"]
    assert dumped["entity2"] == dumped["entity_b"]
    # similarity ← similarity_score, score ← confidence; they must stay distinct.
    assert dumped["similarity"] == 0.91
    assert dumped["similarity_score"] == 0.91
    assert dumped["score"] == 0.87
    assert dumped["confidence"] == 0.87
    assert dumped["similarity"] != dumped["score"]


def test_duplicate_pair_accepts_canonical_keys_and_backfills_legacy():
    """Canonical keys in, legacy twins mirrored out."""
    pair = DuplicatePair.model_validate(
        {"entity_a": "acme_inc", "entity_b": "acme_corp", "similarity": 0.8}
    )
    dumped = pair.model_dump()

    assert dumped["entity1"] == "acme_inc"
    assert dumped["entity2"] == "acme_corp"
    assert dumped["similarity_score"] == 0.8
    # No confidence was supplied, so `score` falls back to the similarity
    # rather than leaving the UI with a 0% bar.
    assert dumped["score"] == 0.8


def test_duplicate_pair_keeps_similarity_and_confidence_distinct():
    """Cross-filling must not collapse two genuinely different scores."""
    pair = DuplicatePair.model_validate(
        {
            "entity1": "a",
            "entity2": "b",
            "similarity_score": 0.95,
            "confidence": 0.60,
        }
    )

    assert pair.similarity == 0.95
    assert pair.score == 0.60


def test_duplicate_pair_rejects_drifted_keys():
    """The core #1592 guarantee: unknown-only pair keys fail validation."""
    with pytest.raises(ValidationError) as excinfo:
        DuplicatePair.model_validate(
            {"left": "acme_inc", "right": "acme_corp", "sim": 0.95}
        )

    missing = {error["loc"][0] for error in excinfo.value.errors()}
    assert {"entity_a", "entity_b", "similarity"} <= missing


def test_dedup_response_validates_nested_pairs():
    """``DedupResponse`` must reject a drifted pair, not accept any dict."""
    with pytest.raises(ValidationError):
        DedupResponse(duplicates=[{"left": "a", "right": "b"}], total_flagged=1)

    ok = DedupResponse(
        duplicates=[{"entity1": "a", "entity2": "b", "similarity_score": 0.9}],
        total_flagged=1,
    )
    assert ok.duplicates[0].entity_a == "a"


def test_duplicate_pair_fills_score_from_similarity():
    """``score`` is required but falls back to ``similarity`` when absent.

    A producer that only emits ``similarity`` (no ``confidence`` / ``score``)
    must still yield a non-zero score bar in the UI.  Both required float
    fields and every legacy twin must be populated from the single source.
    """
    pair = DuplicatePair.model_validate(
        {
            "entity_a": "a",
            "entity_b": "b",
            "similarity": 0.9,
        }
    )
    dumped = pair.model_dump()

    assert dumped["similarity"] == 0.9
    assert dumped["score"] == 0.9
    # Legacy twins must also be backfilled so pre-#1586 clients keep resolving.
    assert dumped["similarity_score"] == 0.9
    assert dumped["confidence"] == 0.9


def test_duplicate_pair_rejects_missing_score_family():
    """A pair with valid entity fields but no score family must fail validation.

    Entities without any of similarity / similarity_score / score / confidence
    cannot produce a usable score bar, so they must not silently pass through
    as a 0% row — the validator must surface a ``ValidationError`` instead.
    """
    with pytest.raises(ValidationError) as excinfo:
        DuplicatePair.model_validate({"entity_a": "a", "entity_b": "b"})

    missing = {error["loc"][0] for error in excinfo.value.errors()}
    assert {"similarity", "score"} <= missing
