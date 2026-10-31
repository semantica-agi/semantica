"""RDF serializers and validation must retain backend relationship endpoints."""

import json
from copy import deepcopy
from xml.etree import ElementTree

import pytest

from semantica.export.rdf_exporter import (
    SEMANTICA_NS,
    RDFExporter,
    RDFValidator,
    mint_relationship_iri,
)

FORMATS = ["turtle", "rdfxml", "ntriples", "jsonld"]
BACKEND_EDGE = {
    "id": "r1",
    "start_node_id": "alice",
    "end_node_id": "acme",
    "type": "WORKS_AT",
}


def _assert_export(tmp_path, fmt, record, source="alice", target="acme"):
    path = tmp_path / fmt
    original = deepcopy(record)
    RDFExporter().export({"relationships": [record]}, path, format=fmt)
    body = path.read_text(encoding="utf-8")

    if fmt == "jsonld":
        [edge] = json.loads(body)["@graph"]
        assert edge["semantica:source"] == {"@id": source}
        assert edge["semantica:target"] == {"@id": target}
    elif fmt == "rdfxml":
        root = ElementTree.fromstring(body)
        rdf = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
        [description] = list(root)
        assert description.attrib[rdf + "about"] == SEMANTICA_NS + str(source)
        assert description.find("WORKS_AT").attrib[rdf + "resource"] == (
            SEMANTICA_NS + str(target)
        )
    else:
        rdflib = pytest.importorskip("rdflib")
        graph = rdflib.Graph().parse(
            data=body, format="nt" if fmt == "ntriples" else "turtle"
        )
        assert (
            tuple(
                rdflib.URIRef(SEMANTICA_NS + str(value))
                for value in (source, "WORKS_AT", target)
            )
            in graph
        )
    assert record == original


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize(
    "source_key, target_key",
    [
        ("source_id", "target_id"),
        ("source", "target"),
        ("start_node_id", "end_node_id"),
        ("start_id", "end_id"),
    ],
)
def test_export_keeps_each_endpoint_spelling(tmp_path, fmt, source_key, target_key):
    _assert_export(
        tmp_path,
        fmt,
        {"id": "r1", source_key: "alice", target_key: "acme", "type": "WORKS_AT"},
    )


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("empty", [None, ""])
def test_empty_canonical_endpoints_use_backend_aliases(tmp_path, fmt, empty):
    _assert_export(
        tmp_path,
        fmt,
        {
            **BACKEND_EDGE,
            "source_id": empty,
            "target_id": empty,
            "source": empty,
            "target": empty,
        },
    )


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("source, target", [(0, 1), (1, 0)])
def test_zero_endpoint_is_kept(tmp_path, fmt, source, target):
    _assert_export(
        tmp_path,
        fmt,
        {**BACKEND_EDGE, "source_id": source, "target_id": target},
        source,
        target,
    )


@pytest.mark.parametrize("fmt", FORMATS)
def test_canonical_endpoints_win(tmp_path, fmt):
    _assert_export(
        tmp_path,
        fmt,
        {
            **BACKEND_EDGE,
            "source_id": "alice",
            "target_id": "acme",
            "source": "ignored",
            "target": "ignored",
            "start_node_id": "ignored",
            "end_node_id": "ignored",
        },
    )


@pytest.mark.parametrize("source, target", [("alice", "acme"), (0, 1), (1, 0)])
def test_temporal_reification_uses_backend_endpoints(source, target):
    rdflib = pytest.importorskip("rdflib")
    edge = {
        "start_node_id": source,
        "end_node_id": target,
        "valid_from": "2026-01-01T00:00:00Z",
    }
    body = RDFExporter().export_to_rdf(
        {"relationships": [edge]}, format="turtle", include_temporal=True
    )
    graph = rdflib.Graph().parse(data=body, format="turtle")
    rel_id = rdflib.URIRef(mint_relationship_iri(0, source, target))
    for name, value in [("source", source), ("target", target)]:
        assert (
            rel_id,
            rdflib.URIRef(SEMANTICA_NS + name),
            rdflib.URIRef(SEMANTICA_NS + str(value)),
        ) in graph
    assert list(
        graph.objects(rel_id, rdflib.URIRef("http://www.w3.org/2006/time#hasTime"))
    )


@pytest.mark.parametrize("source, target", [("alice", "acme"), (0, 1), (1, 0)])
def test_validation_and_consistency_use_backend_endpoints(source, target):
    graph = {
        "entities": [{"id": source}, {"id": target}],
        "relationships": [{"start_node_id": source, "end_node_id": target}],
    }
    validator = RDFValidator()
    assert validator.validate_rdf_syntax(graph)["valid"]
    assert validator.check_rdf_consistency(graph)["consistent"]
    graph["entities"] = []
    assert len(validator.check_rdf_consistency(graph)["issues"]) == 2


@pytest.mark.parametrize("empty", [None, ""])
def test_validation_treats_empty_endpoints_as_unset(empty):
    result = RDFValidator().validate_rdf_syntax(
        {"relationships": [{"source_id": empty, "target_id": empty}]}
    )
    assert not result["valid"]
    assert len(result["errors"]) == 2


@pytest.mark.parametrize("fmt", FORMATS)
def test_entity_zero_and_its_edge_share_one_node(tmp_path, fmt):
    graph = {
        "entities": [{"id": 0, "text": "alice"}, {"id": 1, "text": "acme"}],
        "relationships": [{**BACKEND_EDGE, "start_node_id": 0, "end_node_id": 1}],
    }
    path = tmp_path / fmt
    RDFExporter().export(graph, path, format=fmt)
    body = path.read_text(encoding="utf-8")

    if fmt == "jsonld":
        nodes = json.loads(body)["@graph"]
        entity_ids = [n["@id"] for n in nodes if n["@type"] == "semantica:Entity"]
        [edge] = [n for n in nodes if n["@type"] == "semantica:Relationship"]
        assert edge["semantica:source"]["@id"] in entity_ids
    elif fmt == "rdfxml":
        rdf = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
        typed = {
            d.attrib[rdf + "about"]
            for d in ElementTree.fromstring(body)
            if d.find(rdf + "type") is not None
        }
        assert SEMANTICA_NS + "0" in typed
    else:
        rdflib = pytest.importorskip("rdflib")
        parsed = rdflib.Graph().parse(
            data=body, format="nt" if fmt == "ntriples" else "turtle"
        )
        zero = rdflib.URIRef(SEMANTICA_NS + "0")
        assert (zero, rdflib.RDF.type, None) in parsed
        assert (zero, rdflib.URIRef(SEMANTICA_NS + "WORKS_AT"), None) in parsed
