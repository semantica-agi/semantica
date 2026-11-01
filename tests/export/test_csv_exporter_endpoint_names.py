"""Tests for relationship endpoint names in ``CSVExporter.export_relationships``.

The normalizing path read only ``source``/``source_id`` and
``target``/``target_id``, so a record shaped by a graph backend
(``start_node_id``/``end_node_id`` for Neo4j, FalkorDB and Neptune,
``start_id``/``end_id`` for raw AGE edges) was written with both endpoint
columns empty. Parquet and Arrow already take the accepted names from
``semantica.export.endpoint_names``; these tests keep CSV in step with them.

The exporter is run for real and the file is read back with ``csv``, since the
behaviour under test is what lands on disk.
"""

import csv

import pytest

from semantica.export import CSVExporter
from semantica.export.endpoint_names import (
    SOURCE_ENDPOINT_NAMES,
    TARGET_ENDPOINT_NAMES,
)


def _export(tmp_path, records):
    path = tmp_path / "rel.csv"
    CSVExporter().export_relationships(records, path)
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize(
    "source_key, target_key",
    [
        ("source_id", "target_id"),
        ("source", "target"),
        ("start_node_id", "end_node_id"),
        ("start_id", "end_id"),
    ],
)
def test_endpoints_are_written_under_every_accepted_spelling(
    tmp_path, source_key, target_key
):
    record = {
        "id": "r1",
        source_key: "alice",
        target_key: "acme",
        "type": "WORKS_AT",
    }

    rows = _export(tmp_path, [record])

    assert len(rows) == 1
    assert rows[0]["id"] == "r1"
    assert rows[0]["source_id"] == "alice"
    assert rows[0]["target_id"] == "acme"
    assert rows[0]["type"] == "WORKS_AT"
    # Only the canonical columns are written, not the backend's own names.
    assert set(rows[0]) == {"id", "source_id", "target_id", "type", "confidence"}


def test_every_name_in_endpoint_names_is_recognised(tmp_path):
    """CSV must not keep its own list: whatever the shared module accepts works."""
    for source_key in SOURCE_ENDPOINT_NAMES:
        for target_key in TARGET_ENDPOINT_NAMES:
            rows = _export(tmp_path, [{"id": "r1", source_key: "a", target_key: "b"}])
            assert (rows[0]["source_id"], rows[0]["target_id"]) == ("a", "b")


def test_mixed_spellings_in_one_export(tmp_path):
    records = [
        {"id": "r1", "source_id": "a", "target_id": "b", "type": "T"},
        {"id": "r2", "source": "b", "target": "c", "relationship_type": "T"},
        {"id": "r3", "start_node_id": "c", "end_node_id": "d", "type": "T"},
        {"id": "r4", "start_id": "d", "end_id": "e", "type": "T"},
    ]

    rows = _export(tmp_path, records)

    assert [(r["source_id"], r["target_id"]) for r in rows] == [
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
        ("d", "e"),
    ]


def test_canonical_name_wins_over_a_backend_alias(tmp_path):
    record = {
        "id": "r1",
        "source_id": "kept",
        "start_node_id": "ignored",
        "target_id": "kept-too",
        "end_node_id": "ignored-too",
    }

    rows = _export(tmp_path, [record])

    assert rows[0]["source_id"] == "kept"
    assert rows[0]["target_id"] == "kept-too"


def test_empty_source_id_still_falls_back_to_source(tmp_path):
    """An empty canonical value has always deferred to ``source``; keep that."""
    record = {"id": "r1", "source_id": "", "source": "alice", "target": "acme"}

    rows = _export(tmp_path, [record])

    assert rows[0]["source_id"] == "alice"
    assert rows[0]["target_id"] == "acme"


@pytest.mark.parametrize(
    ("record", "source", "target"),
    [
        (
            {
                "source_id": "",
                "start_node_id": "alice",
                "target_id": "",
                "end_node_id": "acme",
            },
            "alice",
            "acme",
        ),
        (
            {
                "source_id": "",
                "source": "",
                "start_id": "alice",
                "target": "",
                "end_id": "acme",
            },
            "alice",
            "acme",
        ),
        (
            {
                "source_id": None,
                "start_node_id": "alice",
                "target_id": None,
                "end_node_id": "acme",
            },
            "alice",
            "acme",
        ),
    ],
)
def test_empty_earlier_spelling_still_reaches_a_backend_alias(
    tmp_path, record, source, target
):
    """An empty canonical value or alias must not hide a populated backend alias."""
    rows = _export(tmp_path, [{"id": "r1", **record}])

    assert rows[0]["source_id"] == source
    assert rows[0]["target_id"] == target


def test_zero_is_a_real_backend_id(tmp_path):
    """Neo4j node ids start at 0; a falsy id must not be written as empty."""
    record = {"id": "r1", "start_node_id": 0, "end_node_id": 1}

    rows = _export(tmp_path, [record])

    assert rows[0]["source_id"] == "0"
    assert rows[0]["target_id"] == "1"


def test_numeric_backend_ids_are_written(tmp_path):
    """Neo4j, FalkorDB and AGE return integer ids."""
    record = {"id": 7, "start_node_id": 1, "end_node_id": 2, "type": "KNOWS"}

    rows = _export(tmp_path, [record])

    assert rows[0]["id"] == "7"
    assert rows[0]["source_id"] == "1"
    assert rows[0]["target_id"] == "2"


def test_caller_records_are_not_modified(tmp_path):
    record = {"id": "r1", "start_node_id": "alice", "end_node_id": "acme"}
    records = [record]

    _export(tmp_path, records)

    assert record == {"id": "r1", "start_node_id": "alice", "end_node_id": "acme"}
    assert records == [record]


def test_knowledge_graph_relationships_keep_backend_endpoints(tmp_path):
    kg = {
        "entities": [{"id": "alice", "name": "Alice"}, {"id": "acme", "name": "Acme"}],
        "relationships": [
            {
                "id": "r1",
                "start_node_id": "alice",
                "end_node_id": "acme",
                "type": "WORKS_AT",
            }
        ],
    }

    files = CSVExporter().export_knowledge_graph(kg, tmp_path / "kg")

    rel_file = next(f for f in files if f.name.endswith("_relationships.csv"))
    with open(rel_file, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["source_id"] == "alice"
    assert rows[0]["target_id"] == "acme"
