"""LPG exports must retain relationships whose endpoints use backend names."""

from copy import deepcopy

import pytest

from semantica.export import LPGExporter


def _export(tmp_path, records, vocabulary=("entities", "relationships")):
    path = tmp_path / "graph.cypher"
    graph = {
        vocabulary[0]: [{"id": "alice"}, {"id": "acme"}],
        vocabulary[1]: records,
    }
    LPGExporter(include_indexes=False).export(graph, path)
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "vocabulary", [("entities", "relationships"), ("nodes", "edges")]
)
@pytest.mark.parametrize(
    "source_key, target_key",
    [
        ("source_id", "target_id"),
        ("source", "target"),
        ("start_node_id", "end_node_id"),
        ("start_id", "end_id"),
    ],
)
def test_export_retains_relationship_for_each_endpoint_spelling(
    tmp_path, vocabulary, source_key, target_key
):
    record = {
        "id": "r1",
        source_key: "alice",
        target_key: "acme",
        "type": "WORKS_AT",
        "weight": 0.5,
    }
    original = deepcopy(record)

    text = _export(tmp_path, [record], vocabulary)

    assert text.count("CREATE (a)-[") == 1
    assert (
        "MATCH (a {id: 'alice'}), (b {id: 'acme'}) "
        "CREATE (a)-[r:WORKS_AT {id: 'r1', weight: 0.5}]->(b);"
    ) in text
    assert record == original


def test_export_retains_mixed_endpoint_spellings(tmp_path):
    text = _export(
        tmp_path,
        [
            {"source": "alice", "target_id": "acme", "type": "FIRST"},
            {"start_node_id": "acme", "end_id": "alice", "type": "SECOND"},
        ],
    )

    assert text.count("CREATE (a)-[") == 2
    assert "CREATE (a)-[r:FIRST]->(b);" in text
    assert "CREATE (a)-[r:SECOND]->(b);" in text


@pytest.mark.parametrize("source, target", [(0, 1), (1, 0)])
def test_export_retains_zero_endpoint_ids(tmp_path, source, target):
    path = tmp_path / "numeric.cypher"
    LPGExporter(include_indexes=False).export(
        {
            "nodes": [{"id": source}, {"id": target}],
            "edges": [{"start_node_id": source, "end_node_id": target}],
        },
        path,
    )

    text = path.read_text(encoding="utf-8")
    assert (
        f"MATCH (a {{id: {source}}}), (b {{id: {target}}}) "
        "CREATE (a)-[r:RELATED_TO]->(b);"
    ) in text
    # A node with id 0 keeps its id instead of a generated node_<n> placeholder.
    assert "node_" not in text


@pytest.mark.parametrize("empty", [None, ""])
def test_empty_earlier_names_fall_back_to_backend_names(tmp_path, empty):
    text = _export(
        tmp_path,
        [
            {
                "source_id": empty,
                "source": empty,
                "target_id": empty,
                "target": empty,
                "start_node_id": "alice",
                "end_node_id": "acme",
            }
        ],
    )

    assert "MATCH (a {id: 'alice'}), (b {id: 'acme'})" in text


def test_canonical_endpoints_take_precedence(tmp_path):
    text = _export(
        tmp_path,
        [
            {
                "source_id": "alice",
                "target_id": "acme",
                "source": "ignored",
                "target": "ignored",
                "start_node_id": "ignored",
                "end_node_id": "ignored",
            }
        ],
    )

    assert "MATCH (a {id: 'alice'}), (b {id: 'acme'})" in text
    assert "ignored" not in text


@pytest.mark.parametrize(
    "record",
    [{}, {"start_node_id": "alice"}, {"end_node_id": "acme"}],
)
def test_missing_endpoints_still_skip_the_relationship(tmp_path, record):
    assert "CREATE (a)-[" not in _export(tmp_path, [record])
