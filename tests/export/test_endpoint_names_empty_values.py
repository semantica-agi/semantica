"""``None`` and ``""`` endpoint values count as unset in ``endpoint_names`` (#2018).

An empty ``source_id`` next to a backend name such as ``start_node_id`` used to
stay empty, so ``export_knowledge_graph`` wrote blank endpoints to JSON, a
``None`` subject and object to Turtle, and raised for Parquet.
"""

import json

import pytest

from semantica.export.endpoint_names import canonical_endpoints, is_unset_id
from semantica.export.methods import export_knowledge_graph

BACKEND_EDGE = {
    "id": "r1",
    "source_id": "",
    "target_id": "",
    "start_node_id": "alice",
    "end_node_id": "acme",
    "type": "WORKS_AT",
}


def _graph():
    return {
        "entities": [
            {"id": "alice", "type": "Person", "text": "Alice"},
            {"id": "acme", "type": "Org", "text": "Acme"},
        ],
        "relationships": [dict(BACKEND_EDGE)],
    }


@pytest.mark.parametrize(
    "value, unset",
    [(None, True), ("", True), (0, False), ("0", False), ("alice", False)],
)
def test_is_unset_id(value, unset):
    assert is_unset_id(value) is unset


@pytest.mark.parametrize("empty", [None, ""])
def test_unset_canonical_endpoint_takes_the_backend_name(empty):
    edge = {**BACKEND_EDGE, "source_id": empty, "target_id": empty}

    [out] = canonical_endpoints([edge])

    assert (out["source_id"], out["target_id"]) == ("alice", "acme")


def test_empty_alias_defers_to_the_next_alias():
    edge = {"source": "", "start_node_id": "alice", "target": "", "end_id": "acme"}

    [out] = canonical_endpoints([edge])

    assert (out["source_id"], out["target_id"]) == ("alice", "acme")


@pytest.mark.parametrize(
    "edge",
    [
        {"source_id": 0, "start_node_id": "x", "target_id": "acme"},
        {"source_id": "", "target_id": ""},
    ],
)
def test_records_without_a_set_alias_are_returned_as_given(edge):
    records = [edge]

    assert canonical_endpoints(records) is records


def test_json_export_writes_the_backend_endpoints(tmp_path):
    target = tmp_path / "kg.json"

    export_knowledge_graph(_graph(), str(target), format="json")

    [rel] = json.loads(target.read_text(encoding="utf-8"))["relationships"]
    assert (rel["source_id"], rel["target_id"]) == ("alice", "acme")


def test_turtle_export_links_the_two_entities(tmp_path):
    pytest.importorskip("rdflib", reason="the RDF writer needs rdflib")
    target = tmp_path / "kg.ttl"

    export_knowledge_graph(_graph(), str(target))

    body = target.read_text(encoding="utf-8")
    assert "ns#None" not in body
    assert (
        "ns#alice> <https://semantica.dev/ns#WORKS_AT> <https://semantica.dev/ns#acme>"
        in body
    )


def test_parquet_export_keeps_the_relationship(tmp_path):
    pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")
    import pyarrow.parquet as pq

    export_knowledge_graph(_graph(), str(tmp_path / "kg.parquet"))

    table = pq.read_table(tmp_path / "kg_relationships.parquet")
    assert table.select(["source_id", "target_id"]).to_pylist() == [
        {"source_id": "alice", "target_id": "acme"}
    ]
