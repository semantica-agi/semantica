"""Tests for relationship endpoint names in the Parquet and Arrow exporters.

``export_relationships`` on both exporters built its own two-name fallback
(``source``/``source_id``, ``target``/``target_id``) before the shared helper
was reached, so a record shaped by a graph backend (``start_node_id``/
``end_node_id`` for Neo4j, FalkorDB and Neptune, ``start_id``/``end_id`` for raw
AGE edges) raised in Parquet and was written with empty ids in Arrow (#2018).

The exporters are run for real and the file is read back, since the behaviour
under test is what lands on disk.
"""

import pytest

from semantica.export import ArrowExporter, ParquetExporter
from semantica.utils.exceptions import ValidationError

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

SPELLINGS = [
    ("source_id", "target_id"),
    ("source", "target"),
    ("start_node_id", "end_node_id"),
    ("start_id", "end_id"),
]


def _parquet(tmp_path, records):
    path = tmp_path / "rel.parquet"
    ParquetExporter().export_relationships(records, path)
    return pq.read_table(path).to_pylist()


def _arrow(tmp_path, records):
    path = tmp_path / "rel.arrow"
    ArrowExporter().export_relationships(records, path)
    with pa.ipc.open_file(path) as reader:
        return reader.read_all().to_pylist()


EXPORTERS = [pytest.param(_parquet, id="parquet"), pytest.param(_arrow, id="arrow")]


@pytest.mark.parametrize("export", EXPORTERS)
@pytest.mark.parametrize("source_key, target_key", SPELLINGS)
def test_endpoints_are_written_under_every_accepted_spelling(
    tmp_path, export, source_key, target_key
):
    record = {
        "id": "r1",
        source_key: "alice",
        target_key: "acme",
        "type": "WORKS_AT",
    }

    rows = export(tmp_path, [record])

    assert len(rows) == 1
    assert rows[0]["id"] == "r1"
    assert rows[0]["source_id"] == "alice"
    assert rows[0]["target_id"] == "acme"
    assert rows[0]["type"] == "WORKS_AT"


@pytest.mark.parametrize("export", EXPORTERS)
def test_an_empty_canonical_value_falls_through_to_the_backend_name(tmp_path, export):
    record = {
        "id": "r1",
        "source_id": "",
        "target_id": None,
        "start_node_id": "alice",
        "end_node_id": "acme",
    }

    rows = export(tmp_path, [record])

    assert (rows[0]["source_id"], rows[0]["target_id"]) == ("alice", "acme")


@pytest.mark.parametrize("export", EXPORTERS)
def test_canonical_names_win_over_backend_names(tmp_path, export):
    record = {
        "id": "r1",
        "source_id": "alice",
        "target_id": "acme",
        "start_node_id": "other",
        "end_node_id": "elsewhere",
    }

    rows = export(tmp_path, [record])

    assert (rows[0]["source_id"], rows[0]["target_id"]) == ("alice", "acme")


@pytest.mark.parametrize("export", EXPORTERS)
def test_the_callers_records_are_left_untouched(tmp_path, export):
    record = {"id": "r1", "start_node_id": "alice", "end_node_id": "acme"}

    export(tmp_path, [record])

    assert record == {"id": "r1", "start_node_id": "alice", "end_node_id": "acme"}


def test_parquet_still_accepts_from_and_to(tmp_path):
    rows = _parquet(tmp_path, [{"id": "r1", "from": "alice", "to": "acme"}])

    assert (rows[0]["source_id"], rows[0]["target_id"]) == ("alice", "acme")


def test_parquet_still_refuses_a_record_with_no_endpoints(tmp_path):
    with pytest.raises(ValidationError):
        _parquet(tmp_path, [{"id": "r1", "type": "WORKS_AT"}])


def test_a_batch_mixes_spellings(tmp_path):
    records = [
        {"id": "r1", "source": "a", "target": "b"},
        {"id": "r2", "start_node_id": "b", "end_node_id": "c"},
        {"id": "r3", "start_id": "c", "end_id": "d"},
    ]

    for export in (_parquet, _arrow):
        rows = export(tmp_path, records)
        assert [(r["source_id"], r["target_id"]) for r in rows] == [
            ("a", "b"),
            ("b", "c"),
            ("c", "d"),
        ]


@pytest.mark.parametrize("export", EXPORTERS)
@pytest.mark.parametrize("source_key, target_key", SPELLINGS)
def test_an_integer_id_of_zero_is_a_real_id(tmp_path, export, source_key, target_key):
    record = {"id": "r1", source_key: 0, target_key: 1}

    rows = export(tmp_path, [record])

    assert (rows[0]["source_id"], rows[0]["target_id"]) == ("0", "1")


def test_arrow_still_writes_empty_ids_for_a_record_with_no_endpoints(tmp_path):
    rows = _arrow(tmp_path, [{"id": "r1", "type": "WORKS_AT"}])

    assert (rows[0]["source_id"], rows[0]["target_id"]) == ("", "")
