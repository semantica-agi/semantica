"""Graph, CSV and Arrow exporters must resolve a nested confidence (#1796).

A decision added via ``ContextGraph.add_decision`` stores its confidence
under ``properties["confidence"]``; ``to_kg_dict()`` never copies it to the
entity's top level. ``GraphExporter``, ``CSVExporter`` and ``ArrowExporter``
all read only ``entity.get("confidence", ...)``, so a decision's 0.91 is
replaced by each exporter's default instead of being written through.
``JSONExporter``'s JSON-LD path is the reference implementation for
resolving the nested value (#1965).
"""

from datetime import datetime
from pathlib import Path

import pytest

from semantica.context import ContextGraph
from semantica.context.decision_models import Decision
from semantica.export import ArrowExporter, CSVExporter, GraphExporter

pa = pytest.importorskip("pyarrow")
import pyarrow.ipc as ipc  # noqa: E402

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
    assert f'<data key="confidence">{CONFIDENCE}</data>' in content, (
        f"expected confidence {CONFIDENCE} in GraphML output, got:\n{content}"
    )


def test_csv_exporter_writes_nested_decision_confidence(tmp_path):
    kg = _kg_with_decision()
    base = tmp_path / "out"
    CSVExporter().export_knowledge_graph(kg, base)

    entities_csv = Path(f"{base}_entities.csv").read_text(encoding="utf-8")
    rows = entities_csv.strip().splitlines()
    header = rows[0].split(",")
    data = rows[1].split(",")
    confidence = dict(zip(header, data))["confidence"]
    assert confidence == str(CONFIDENCE), (
        f"expected confidence column '{CONFIDENCE}', got {confidence!r}"
    )


def test_arrow_exporter_writes_nested_decision_confidence(tmp_path):
    kg = _kg_with_decision()
    base = tmp_path / "out"
    ArrowExporter().export_knowledge_graph(kg, base)

    entities_arrow = Path(f"{base}_entities.arrow")
    with pa.OSFile(str(entities_arrow), "rb") as sink:
        with ipc.open_file(sink) as reader:
            table = reader.read_all()

    confidence = table.column("confidence").to_pylist()[0]
    assert confidence == CONFIDENCE, (
        f"expected confidence {CONFIDENCE}, got {confidence!r}"
    )
