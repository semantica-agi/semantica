"""Tests for Ontology Hub subissue 3 APIs."""

import pytest

from semantica.context.context_graph import ContextGraph
from semantica.explorer.app import create_app
from semantica.explorer.session import GraphSession

try:
    from starlette.testclient import TestClient
except ImportError:
    pytest.skip(
        "starlette TestClient is required for explorer tests. Install semantica[explorer].",
        allow_module_level=True,
    )


def _build_ontology_graph() -> ContextGraph:
    graph = ContextGraph(advanced_analytics=False)
    onto_a = "http://example.org/onto-a"
    onto_b = "http://example.org/onto-b"
    person_a = "http://example.org/onto-a#Person"
    person_b = "http://example.org/onto-b#PersonRecord"
    name_a = "http://example.org/onto-a#name"

    graph.add_node(
        onto_a,
        node_type="owl:Ontology",
        content="Ontology A",
        **{"rdfs:label": "Ontology A", "rdfs:comment": "Primary ontology", "version": "1.0.0"},
    )
    graph.add_node(
        onto_b,
        node_type="owl:Ontology",
        content="Ontology B",
        **{"rdfs:label": "Ontology B", "rdfs:comment": "Partner ontology", "version": "1.0.0"},
    )
    graph.add_node(
        person_a,
        node_type="owl:Class",
        content="Person",
        scheme_uri=onto_a,
        **{"rdfs:label": "Person", "rdfs:comment": "A person", "skos:definition": "Human actor"},
    )
    graph.add_node(
        name_a,
        node_type="owl:DatatypeProperty",
        content="name",
        scheme_uri=onto_a,
        **{"rdfs:label": "name", "rdfs:comment": "Display name"},
    )
    graph.add_node(
        person_b,
        node_type="owl:Class",
        content="Person Record",
        scheme_uri=onto_b,
        **{"rdfs:label": "Person Record", "rdfs:comment": "A person profile"},
    )
    graph.add_edge(name_a, person_a, edge_type="rdfs:domain")
    return graph


@pytest.fixture()
def client():
    app = create_app(session=GraphSession(_build_ontology_graph()))
    with TestClient(app) as test_client:
        yield test_client


def test_alignment_round_trip(client):
    payload = {
        "source_uri": "http://example.org/onto-a#Person",
        "target_uri": "http://example.org/onto-b#PersonRecord",
        "relation": "owl:equivalentClass",
        "confidence": 0.91,
        "provenance": "Reviewed from source mapping table",
        "source": "test",
        "reviewer": "qa",
    }
    created = client.post("/api/ontology/alignments", json=payload)
    assert created.status_code == 200
    alignment = created.json()
    assert alignment["confidence"] == 0.91
    assert alignment["provenance"] == "Reviewed from source mapping table"

    listed = client.get("/api/ontology/alignments")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [alignment["id"]]

    removed = client.delete(f"/api/ontology/alignments?id={alignment['id']}")
    assert removed.status_code == 200
    assert client.get("/api/ontology/alignments").json() == []


def test_alignment_suggestions_are_ranked(client):
    response = client.post(
        "/api/ontology/suggest-alignments",
        json={
            "source_ontology_uri": "http://example.org/onto-a",
            "target_ontology_uri": "http://example.org/onto-b",
            "threshold": 0.35,
            "limit": 5,
        },
    )
    assert response.status_code == 200
    suggestions = response.json()
    assert suggestions
    assert suggestions[0]["source_label"] == "Person"
    assert suggestions[0]["target_label"] == "Person Record"
    assert suggestions == sorted(suggestions, key=lambda item: item["score"], reverse=True)


def test_health_returns_dimensions_and_issues(client):
    response = client.get("/api/ontology/health?uri=http%3A%2F%2Fexample.org%2Fonto-a")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_score"] >= 0
    assert {dimension["key"] for dimension in payload["dimensions"]} == {
        "completeness",
        "consistency",
        "shacl",
        "alignment",
        "documentation",
    }
    assert isinstance(payload["issues"], list)


def test_shacl_generate_and_shapes(client):
    response = client.post(
        "/api/ontology/shacl/generate",
        json={"uri": "http://example.org/onto-a", "quality_tier": "strict"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "sh:NodeShape" in payload["shacl_turtle"]
    assert payload["shape_count"] >= 1

    shapes = client.get("/api/ontology/shacl/shapes?uri=http%3A%2F%2Fexample.org%2Fonto-a")
    assert shapes.status_code == 200
    assert shapes.json()["shapes"]


def test_shacl_validate_has_stable_contract(client):
    response = client.post(
        "/api/ontology/shacl/validate",
        json={
            "uri": "http://example.org/onto-a",
            "shacl_turtle": "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"success", "unavailable"}
    assert isinstance(payload["violations"], list)
