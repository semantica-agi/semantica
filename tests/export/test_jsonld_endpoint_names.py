"""JSON-LD relationship nodes must retain backend endpoint names (#2018)."""

import json
from copy import deepcopy

import pytest

from semantica.export import JSONExporter
from semantica.export.rdf_exporter import mint_relationship_iri


def _assert_endpoints(record, source="alice", target="acme"):
    original = deepcopy(record)
    edge = JSONExporter()._relationship_to_jsonld(record, 0)
    assert edge["semantica:source"] == {"@id": source}
    assert edge["semantica:target"] == {"@id": target}
    assert edge["@id"] == mint_relationship_iri(0, source, target)
    assert record == original


@pytest.mark.parametrize(
    "source_key, target_key",
    [
        ("source_id", "target_id"),
        ("source", "target"),
        ("start_node_id", "end_node_id"),
        ("start_id", "end_id"),
        ("source_id", "end_id"),
    ],
)
def test_relationship_keeps_each_endpoint_spelling(source_key, target_key):
    _assert_endpoints({source_key: "alice", target_key: "acme"})


@pytest.mark.parametrize("empty", [None, ""])
def test_empty_canonical_endpoints_use_backend_aliases(empty):
    _assert_endpoints(
        {
            "source_id": empty,
            "target_id": empty,
            "source": empty,
            "target": empty,
            "start_node_id": "alice",
            "end_node_id": "acme",
        }
    )


def test_canonical_endpoints_win():
    _assert_endpoints(
        {
            "source_id": "alice",
            "target_id": "acme",
            "source": "ignored",
            "target": "ignored",
            "start_node_id": "ignored",
            "end_node_id": "ignored",
        }
    )


@pytest.mark.parametrize("source, target", [(0, 1), (1, 0)])
def test_zero_endpoint_is_kept(source, target):
    _assert_endpoints(
        {
            "source_id": source,
            "target_id": target,
            "start_node_id": "ignored",
            "end_node_id": "ignored",
        },
        source,
        target,
    )


@pytest.mark.parametrize("empty", [None, ""])
def test_unset_endpoints_keep_null_links_and_the_existing_minted_id(empty):
    edge = JSONExporter()._relationship_to_jsonld(
        {"source_id": empty, "target_id": empty}, 0
    )
    assert edge["semantica:source"] == {"@id": None}
    assert edge["semantica:target"] == {"@id": None}
    assert edge["@id"] == mint_relationship_iri(0, "", "")


@pytest.mark.parametrize(
    "method", ["export", "export_knowledge_graph", "export_relationships"]
)
def test_file_export_keeps_backend_endpoints(tmp_path, method):
    path = tmp_path / "graph.jsonld"
    record = {
        "id": "r1",
        "start_node_id": "alice",
        "end_node_id": "acme",
        "type": "WORKS_AT",
    }
    payload = (
        [record] if method == "export_relationships" else {"relationships": [record]}
    )
    getattr(JSONExporter(), method)(payload, path, format="json-ld")

    [edge] = json.loads(path.read_text(encoding="utf-8"))["semantica:relationships"]
    assert edge["@id"] == "r1"
    assert edge["semantica:source"] == {"@id": "alice"}
    assert edge["semantica:target"] == {"@id": "acme"}


def test_entity_zero_keeps_the_id_its_edges_use():
    exporter = JSONExporter()
    entity = exporter._entity_to_jsonld({"id": 0, "text": "alice"})
    edge = exporter._relationship_to_jsonld({"start_node_id": 0, "end_node_id": 1}, 0)
    assert entity["@id"] == edge["semantica:source"]["@id"] == 0
