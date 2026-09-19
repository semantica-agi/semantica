"""Regression tests for issue #1531.

``GET /api/decisions/causal-distance`` was unreachable because the dynamic
route ``GET /api/decisions/{decision_id}`` is registered before the static
``/causal-distance`` route in ``semantica/explorer/routes/decisions.py``.
Starlette matches routes in definition order, so a request to
``causal-distance`` was bound as ``decision_id="causal-distance"`` and
returned ``404 Decision 'causal-distance' not found``.

Each test below fails while the static route sits after ``/{decision_id}``
and passes once it is moved above it.
"""

import pytest

# fastapi ships in the optional `explorer` extra, not in `dev`, so this module
# must skip rather than fail collection when it is absent.
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from semantica.context.context_graph import ContextGraph  # noqa: E402
from semantica.explorer.app import create_app  # noqa: E402
from semantica.explorer.session import GraphSession  # noqa: E402


def _client() -> TestClient:
    graph = ContextGraph(advanced_analytics=False)
    return TestClient(create_app(session=GraphSession(graph)))


def test_causal_distance_route_is_not_shadowed_by_decision_id():
    """GET /api/decisions/causal-distance must reach the distance handler.

    Fails before the fix with: 404 {"detail": "Decision 'causal-distance' not found"}.
    After the fix the analyzer returns an unreachable-distance report (200).
    """
    with _client() as client:
        response = client.get(
            "/api/decisions/causal-distance", params={"source": "x", "target": "y"}
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_id"] == "x"
    assert payload["target_id"] == "y"


def test_causal_distance_between_linked_decisions():
    """Two causally linked decisions must report a 1-hop path."""
    graph = ContextGraph(advanced_analytics=False)
    first = graph.record_decision(
        category="credit_application",
        scenario="Personal loan review",
        reasoning="Income meets threshold",
        outcome="proceed_to_underwriting",
        confidence=0.88,
    )
    second = graph.record_decision(
        category="loan_underwriting",
        scenario="Underwriting review",
        reasoning="DTI within policy",
        outcome="approved",
        confidence=0.94,
    )
    graph.add_causal_relationship(first, second, relationship_type="CAUSED")

    with TestClient(create_app(session=GraphSession(graph))) as client:
        response = client.get(
            "/api/decisions/causal-distance",
            params={"source": first, "target": second},
        )

    assert response.status_code == 200, response.text
    assert response.json()["causal_hop_count"] == 1


def test_unknown_decision_id_still_404s():
    """Moving the static route must not change param-route 404 behavior."""
    with _client() as client:
        response = client.get("/api/decisions/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Decision 'does-not-exist' not found"}
