"""CSV and Arrow exporters must keep a character offset of 0.

``EntityOut.start`` is the start character index. The first token of a
text therefore has ``start=0``. Both exporters used to resolve the offset
with ``or``, which treats 0 as missing and also lets ``start_offset``
replace an explicit 0.
"""

import csv

import pytest

from semantica.export import ArrowExporter, CSVExporter

pa = pytest.importorskip("pyarrow")
import pyarrow.ipc as ipc  # noqa: E402

ENTITIES = [
    {"id": "e0", "text": "Hello", "type": "WORD", "start": 0, "end": 5},
    {
        "id": "e1",
        "text": "Hi",
        "type": "WORD",
        "start_offset": 0,
        "end_offset": 2,
    },
    {
        "id": "e2",
        "text": "A",
        "type": "WORD",
        "start": 0,
        "end": 1,
        "start_offset": 9,
        "end_offset": 9,
    },
]


def test_csv_keeps_zero_character_offsets(tmp_path):
    out = tmp_path / "entities.csv"
    CSVExporter().export_entities(ENTITIES, out)

    with out.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [(row["start"], row["end"]) for row in rows] == [
        ("0", "5"),
        ("0", "2"),
        ("0", "1"),
    ]


def test_arrow_keeps_zero_character_offsets(tmp_path):
    out = tmp_path / "entities.arrow"
    ArrowExporter().export_entities(ENTITIES, out)

    with pa.OSFile(str(out), "rb") as sink:
        with ipc.open_file(sink) as reader:
            table = reader.read_all()

    assert table.column("start").to_pylist() == [0, 0, 0]
    assert table.column("end").to_pylist() == [5, 2, 1]


def test_missing_offsets_stay_blank(tmp_path):
    entity = [{"id": "e3", "text": "bare", "type": "WORD"}]
    csv_out = tmp_path / "bare.csv"
    CSVExporter().export_entities(entity, csv_out)
    with csv_out.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["start"] == ""
    assert row["end"] == ""

    arrow_out = tmp_path / "bare.arrow"
    ArrowExporter().export_entities(entity, arrow_out)
    with pa.OSFile(str(arrow_out), "rb") as sink:
        with ipc.open_file(sink) as reader:
            table = reader.read_all()
    assert table.column("start").to_pylist() == [None]
    assert table.column("end").to_pylist() == [None]
