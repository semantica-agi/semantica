"""Graph, CSV, Arrow and Parquet exporters must resolve a nested confidence.

A decision added via ``ContextGraph.add_decision`` stores its confidence
under ``properties["confidence"]``; ``to_kg_dict()`` never copies it to the
entity's top level (#1796). ``JSONExporter``'s JSON-LD path is the reference
implementation for resolving the nested value (#1965).
"""

from datetime import datetime
from pathlib import Path

import pytest

from semantica.context import ContextGraph
from semantica.context.decision_models import Decision
from semantica.export import ArrowExporter, CSVExporter, GraphExporter, ParquetExporter

pa = pytest.importorskip("pyarrow")
import pyarrow.ipc as ipc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

CONFIDENCE = 0.91


def _kg_with_decision():
    graph = ContextGraph()
    graph.add_decision(
        Decision(
            decision_id="D1",
            category="terms",
            scenario="s",
            reasoning="r",
            outcome="approve",
            confidence=CONFIDENCE,
            timestamp=datetime(2026, 4, 1),
            decision_maker="cfo",
        )
    )
    kg = graph.to_kg_dict()
    entity = kg["entities"][0]
    assert entity.get("confidence") is None
    assert entity["properties"]["confidence"] == CONFIDENCE
    return kg


def test_graphml_exporter_writes_nested_decision_confidence(tmp_path):
    kg = _kg_with_decision()
    out = tmp_path / "out.graphml"
    GraphExporter(format="graphml").export_knowledge_graph(kg, out)

    content = out.read_text(encoding="utf-8")
    assert (
        f'<data key="confidence">{CONFIDENCE}</data>' in content
    ), f"expected confidence {CONFIDENCE} in GraphML output, got:\n{content}"


def test_csv_exporter_writes_nested_decision_confidence(tmp_path):
    kg = _kg_with_decision()
    base = tmp_path / "out"
    CSVExporter().export_knowledge_graph(kg, base)

    entities_csv = Path(f"{base}_entities.csv").read_text(encoding="utf-8")
    rows = entities_csv.strip().splitlines()
    header = rows[0].split(",")
    data = rows[1].split(",")
    confidence = dict(zip(header, data))["confidence"]
    assert confidence == str(
        CONFIDENCE
    ), f"expected confidence column '{CONFIDENCE}', got {confidence!r}"


def test_arrow_exporter_writes_nested_decision_confidence(tmp_path):
    kg = _kg_with_decision()
    base = tmp_path / "out"
    ArrowExporter().export_knowledge_graph(kg, base)

    entities_arrow = Path(f"{base}_entities.arrow")
    with pa.OSFile(str(entities_arrow), "rb") as sink:
        with ipc.open_file(sink) as reader:
            table = reader.read_all()

    confidence = table.column("confidence").to_pylist()[0]
    assert (
        confidence == CONFIDENCE
    ), f"expected confidence {CONFIDENCE}, got {confidence!r}"


def test_exporters_tolerate_non_dict_properties(tmp_path):
    kg = {
        "entities": [
            {"id": "E1", "text": "a", "type": "Entity", "properties": "not-a-dict"}
        ],
        "relationships": [],
    }
    CSVExporter().export_knowledge_graph(kg, tmp_path / "csv_out")
    GraphExporter(format="graphml").export_knowledge_graph(kg, tmp_path / "graph_out")
    ArrowExporter().export_knowledge_graph(kg, tmp_path / "arrow_out")


def test_csv_and_arrow_tolerate_non_dict_relationship_metadata(tmp_path):
    kg = {
        "entities": [
            {"id": "E1", "text": "a", "type": "Entity"},
            {"id": "E2", "text": "b", "type": "Entity"},
        ],
        "relationships": [
            {
                "id": "R1",
                "source_id": "E1",
                "target_id": "E2",
                "type": "rel",
                "metadata": "not-a-dict",
            }
        ],
    }
    CSVExporter().export_knowledge_graph(kg, tmp_path / "csv_out")
    ArrowExporter().export_knowledge_graph(kg, tmp_path / "arrow_out")


def test_parquet_exporter_writes_nested_confidence(tmp_path):
    kg = _kg_with_decision()
    kg["relationships"] = [
        {
            "id": "R1",
            "source_id": "D1",
            "target_id": "D1",
            "type": "rel",
            "metadata": {"confidence": CONFIDENCE},
        }
    ]
    base = tmp_path / "out"
    ParquetExporter().export_knowledge_graph(kg, base)

    entities = pq.read_table(Path(f"{base}_entities.parquet"))
    relationships = pq.read_table(Path(f"{base}_relationships.parquet"))
    assert entities.column("confidence").to_pylist() == [CONFIDENCE]
    assert relationships.column("confidence").to_pylist() == [CONFIDENCE]


def test_parquet_confidence_precedence_and_non_dict_nests(tmp_path):
    records = [
        {
            "id": "top",
            "confidence": 0.0,
            "properties": {"confidence": 0.5},
            "metadata": {"confidence": 0.6},
        },
        {
            "id": "properties",
            "properties": {"confidence": 0.5},
            "metadata": {"confidence": 0.6},
        },
        {
            "id": "metadata",
            "properties": "not-a-dict",
            "metadata": {"confidence": 0.6},
        },
        {"id": "missing", "properties": [], "metadata": "not-a-dict"},
    ]

    entities_out = tmp_path / "entities.parquet"
    ParquetExporter().export_entities(records, entities_out)
    entities = pq.read_table(entities_out)
    assert entities.column("confidence").to_pylist() == [0.0, 0.5, 0.6, None]

    relationships_out = tmp_path / "relationships.parquet"
    relationships = [
        {**record, "source_id": "E1", "target_id": "E2"} for record in records
    ]
    ParquetExporter().export_relationships(
        relationships,
        relationships_out,
    )
    table = pq.read_table(relationships_out)
    assert table.column("confidence").to_pylist() == [
        0.0,
        0.5,
        0.6,
        None,
    ]
