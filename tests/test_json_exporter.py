"""JSON-LD export must not drop entity properties, validity windows, or
relationship weights (#1961).

JSON-LD is advertised as a lossless interchange format. Before the fix,
``_entity_to_jsonld`` copied only ``metadata`` and read confidence from the
top level only, and ``_relationship_to_jsonld`` dropped ``weight`` and the
validity window entirely.
"""

import json
import os
import tempfile
from datetime import datetime

import pytest

from semantica.context import ContextGraph
from semantica.context.decision_models import Decision
from semantica.export import JSONExporter


def _build_graph() -> ContextGraph:
    g = ContextGraph()
    g.add_decision(
        Decision(
            decision_id="D1",
            category="terms",
            scenario="extend terms",
            reasoning="why",
            outcome="approve",
            confidence=0.9,
            timestamp=datetime(2026, 4, 1),
            decision_maker="cfo",
            valid_from="2026-04-01T00:00:00",
            valid_until="2026-09-30T00:00:00",
        )
    )
    g.add_node(
        "C1",
        "Customer",
        "Acme",
        terms_days=60,
        valid_from="2026-03-30",
        valid_until="2026-12-31",
    )
    g.add_edge("D1", "C1", "about", weight=0.5, valid_from="2026-04-01")
    return g


def _export_jsonld(g: ContextGraph) -> dict:
    path = os.path.join(tempfile.mkdtemp(), "g.jsonld")
    JSONExporter().export_knowledge_graph(g.to_kg_dict(), path, format="json-ld")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _entity(doc: dict, entity_id: str) -> dict:
    return next(e for e in doc["semantica:entities"] if e["@id"] == entity_id)


def test_entity_properties_are_not_dropped():
    doc = _export_jsonld(_build_graph())
    props = _entity(doc, "D1")["semantica:properties"]
    assert props["category"] == "terms"
    assert props["reasoning"] == "why"
    assert props["outcome"] == "approve"
    assert props["decision_maker"] == "cfo"
    assert props["timestamp"] == "2026-04-01T00:00:00"


def test_entity_confidence_uses_stored_value():
    doc = _export_jsonld(_build_graph())
    # 0.9 lives in properties, not at the top level; the old code read only the
    # top level and wrote the 1.0 default.
    assert _entity(doc, "D1")["semantica:confidence"] == 0.9


def test_entity_validity_window_is_exported():
    doc = _export_jsonld(_build_graph())
    d1 = _entity(doc, "D1")
    assert d1["semantica:validFrom"] == "2026-04-01T00:00:00"
    assert d1["semantica:validUntil"] == "2026-09-30T00:00:00"
    c1 = _entity(doc, "C1")
    # A date-only value is completed to the declared xsd:dateTime (#1966).
    assert c1["semantica:validFrom"] == "2026-03-30T00:00:00"
    assert c1["semantica:validUntil"] == "2026-12-31T00:00:00"


def test_relationship_weight_and_validity_are_exported():
    doc = _export_jsonld(_build_graph())
    rel = doc["semantica:relationships"][0]
    assert rel["semantica:weight"] == 0.5
    assert rel["semantica:validFrom"] == "2026-04-01T00:00:00"


def test_datetime_validity_object_is_rendered_as_isoformat():
    from datetime import datetime as _dt

    g = ContextGraph()
    g.add_node("N1", "T", "x", valid_from=_dt(2026, 3, 30, 12, 0))
    path = os.path.join(tempfile.mkdtemp(), "n.jsonld")
    JSONExporter().export_knowledge_graph(g.to_kg_dict(), path, format="json-ld")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    # A datetime object is rendered with isoformat(), not str() — the latter
    # would be "2026-03-30 12:00:00", outside the xsd:dateTime lexical space
    # (#1966, and the case #1967's default=str would otherwise expose).
    assert _entity(doc, "N1")["semantica:validFrom"] == "2026-03-30T12:00:00"


@pytest.mark.parametrize(
    "stored, expected",
    [
        ("2026-03-30", "2026-03-30T00:00:00"),
        ("2026-03-30 ", "2026-03-30T00:00:00"),
        ("2026-03-30T00:00", "2026-03-30T00:00:00"),
        ("2026-03-30 00:00:00", "2026-03-30T00:00:00"),
        ("2026-03-30T12:34:56", "2026-03-30T12:34:56"),
        ("not a date", "not a date"),
    ],
)
def test_validity_strings_are_completed_to_xsd_datetime(stored, expected):
    g = ContextGraph()
    g.add_node("N1", "T", "x", valid_from=stored)
    path = os.path.join(tempfile.mkdtemp(), "n.jsonld")
    JSONExporter().export_knowledge_graph(g.to_kg_dict(), path, format="json-ld")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    assert _entity(doc, "N1")["semantica:validFrom"] == expected
