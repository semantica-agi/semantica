"""Tests for literal annotation preservation in ontology load."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from semantica.explorer.app import create_app


TTL = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/a#> .
<http://example.org/a> a owl:Ontology .
ex:Task a owl:Class ; rdfs:label "Task" ; ex:emittedAs "task" .
ex:Goal a owl:Class ; rdfs:label "Goal" ; ex:emittedAs "goal" ; skos:altLabel "objective"@en .
"""

SHAPE = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/a#> .
ex:Declared a sh:NodeShape ; sh:targetObjectsOf ex:emittedAs ; sh:in ( "goal" ) .
"""


def test_literal_annotation_preserved_in_session_graph():
    """Load ontology with custom literal annotation and validate via SHACL."""
    with TestClient(create_app()) as c:
        # Load ontology
        r1 = c.post(
            "/api/ontology/load",
            json={"content": TTL, "format": "turtle"},
        )
        assert r1.status_code == 200, f"Load failed: {r1.text}"

        # Validate with SHACL shape that targets the literal annotation
        r2 = c.post(
            "/api/ontology/shacl/validate",
            json={
                "uri": "http://example.org/a",
                "shacl_turtle": SHAPE,
            },
        )
        assert r2.status_code == 200, f"Validate failed: {r2.text}"
        data = r2.json()

        # The shape allows only "goal" in ex:emittedAs, so the ontology
        # should NOT conform because it has "task" as well.
        assert data["status"] == "success"
        assert data["conforms"] is False, (
            "SHACL validation should find violation for 'task' annotation"
        )
        assert len(data["violations"]) >= 1, "Should have at least one violation"


def test_literal_annotation_on_property():
    """Property custom annotations are preserved in session graph."""
    ttl = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/b#> .
<http://example.org/b> a owl:Ontology .
ex:hasTask a owl:ObjectProperty ; rdfs:label "has task" ; ex:priority "high" .
"""
    shape = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/b#> .
ex:PropShape a sh:NodeShape ; sh:targetObjectsOf ex:priority ; sh:in ( "low" ) .
"""
    with TestClient(create_app()) as c:
        r1 = c.post(
            "/api/ontology/load",
            json={"content": ttl, "format": "turtle"},
        )
        assert r1.status_code == 200

        r2 = c.post(
            "/api/ontology/shacl/validate",
            json={"uri": "http://example.org/b", "shacl_turtle": shape},
        )
        data = r2.json()
        assert data["conforms"] is False, (
            "Property annotation 'high' should violate shape allowing only 'low'"
        )


def test_namespace_preserved_in_annotations():
    """Annotations from other namespaces (skos, dc, etc.) are correctly preserved."""
    shape_alt_label = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/a#> .
ex:AltLabelShape a sh:NodeShape ; sh:targetObjectsOf skos:altLabel ; sh:in ( "objective" ) .
"""
    with TestClient(create_app()) as c:
        r1 = c.post(
            "/api/ontology/load",
            json={"content": TTL, "format": "turtle"},
        )
        assert r1.status_code == 200

        # Validate that skos:altLabel from external namespace is correctly reconstructed
        r2 = c.post(
            "/api/ontology/shacl/validate",
            json={"uri": "http://example.org/a", "shacl_turtle": shape_alt_label},
        )
        data = r2.json()
        # Should conform since skos:altLabel "objective" matches the shape
        assert data["conforms"] is True, (
            "skos:altLabel annotation should be correctly preserved and validate"
        )


def test_url_like_literal_not_treated_as_uri():
    """Literal values starting with http/https are not mistakenly treated as URIs."""
    ttl = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/c#> .
<http://example.org/c> a owl:Ontology .
ex:Document a owl:Class ; rdfs:label "Document" ; ex:sourceUrl "https://example.com/data" .
"""

    shape = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/c#> .
ex:UrlShape a sh:NodeShape ; sh:targetObjectsOf ex:sourceUrl ; sh:pattern "^https://" .
"""

    with TestClient(create_app()) as c:
        r1 = c.post(
            "/api/ontology/load",
            json={"content": ttl, "format": "turtle"},
        )
        assert r1.status_code == 200

        r2 = c.post(
            "/api/ontology/shacl/validate",
            json={"uri": "http://example.org/c", "shacl_turtle": shape},
        )
        data = r2.json()
        # Should conform since the value is a literal matching the pattern
        assert data["conforms"] is True, (
            "URL-like literal should be treated as literal, not converted to URI"
        )


def test_reserved_property_not_overwritten():
    """Annotations cannot overwrite reserved internal properties like scheme_uri."""
    ttl = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/d#> .
<http://example.org/d> a owl:Ontology .
ex:Item a owl:Class ; rdfs:label "Item" ; ex:scheme_uri "http://malicious.org/ontology" .
"""

    with TestClient(create_app()) as c:
        r1 = c.post(
            "/api/ontology/load",
            json={"content": ttl, "format": "turtle"},
        )
        assert r1.status_code == 200

        # Fetch the ontology graph and verify scheme_uri is not overwritten
        r2 = c.get("/api/ontology/graph?uri=http://example.org/d")
        assert r2.status_code == 200
        graph = r2.json()
        
        # Find the Item class node
        item_node = None
        for node in graph.get("nodes", []):
            if node.get("id") == "http://example.org/d#Item":
                item_node = node
                break
        
        assert item_node is not None, "Should find ex:Item in the graph"
        props = item_node.get("properties", {})
        # scheme_uri should remain the ontology URI, not be overwritten
        assert props.get("scheme_uri") == "http://example.org/d", (
            "Reserved property scheme_uri should not be overwritten by annotation"
        )
