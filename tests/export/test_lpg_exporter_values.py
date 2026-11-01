"""Node properties and relationship matches must use the same Cypher literals."""

import pytest

from semantica.export import LPGExporter


@pytest.mark.parametrize("batch_size", [1, 1000])
def test_export_formats_node_values_and_endpoint_ids(tmp_path, batch_size):
    path = tmp_path / "graph.cypher"
    LPGExporter(include_indexes=False, batch_size=batch_size).export(
        {
            "nodes": [
                {"id": "alice", "name": "Alice"},
                {"id": 7, "name": "Seven"},
                {"id": "7"},
            ],
            "edges": [
                {"source": "alice", "target": 7, "id": "r1"},
                {"source": 7, "target": "7", "id": 2},
            ],
        },
        path,
    )

    statements = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("CREATE (", "MATCH ("))
    ]
    assert statements == [
        "CREATE (n0:Entity {id: 'alice', name: 'Alice'});",
        f"CREATE (n{1 if batch_size > 1 else 0}:Entity {{id: 7, name: 'Seven'}});",
        f"CREATE (n{2 if batch_size > 1 else 0}:Entity {{id: '7', name: ''}});",
        "MATCH (a {id: 'alice'}), (b {id: 7}) "
        "CREATE (a)-[r:RELATED_TO {id: 'r1'}]->(b);",
        "MATCH (a {id: 7}), (b {id: '7'}) CREATE (a)-[r:RELATED_TO {id: 2}]->(b);",
    ]


def test_export_escapes_apostrophes_and_backslashes(tmp_path):
    path = tmp_path / "graph.cypher"
    LPGExporter(include_indexes=False).export(
        {
            "nodes": [{"id": "o'brien", "name": "O'Brien"}, {"id": "acme"}],
            "edges": [{"source": "o'brien", "target": "acme", "note": "a\\b"}],
        },
        path,
    )

    text = path.read_text(encoding="utf-8")
    assert "CREATE (n0:Entity {id: 'o\\'brien', name: 'O\\'Brien'});" in text
    assert (
        "MATCH (a {id: 'o\\'brien'}), (b {id: 'acme'}) "
        "CREATE (a)-[r:RELATED_TO {note: 'a\\\\b'}]->(b);"
    ) in text
