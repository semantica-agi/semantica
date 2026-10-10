"""Exports must not fail on property values that ``json`` cannot serialise
natively (#1967).

``write_json_file`` called ``json.dump`` without a ``default=`` fallback, so a
``datetime`` property failed the whole export. ``ArangoAQLExporter`` had the
same gap in its two ``json.dumps`` calls.
"""

import json
import os
import tempfile
from datetime import datetime

from semantica.export import ArangoAQLExporter, JSONExporter


def _kg_with_datetime() -> dict:
    # metadata is the field JSON-LD copies (properties is dropped on main), so
    # put the value there too; that is the shape ContextGraph produces when
    # add_node aliases properties into metadata.
    return {
        "entities": [
            {
                "id": "X1",
                "text": "x",
                "type": "T",
                "properties": {"when": datetime(2026, 1, 1)},
                "metadata": {"when": datetime(2026, 1, 1)},
            }
        ],
        "relationships": [],
    }


def test_json_export_handles_datetime_property():
    path = os.path.join(tempfile.mkdtemp(), "g.json")
    JSONExporter().export_knowledge_graph(_kg_with_datetime(), path, format="json")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    json.loads(content)
    assert "2026-01-01" in content


def test_jsonld_export_handles_datetime_property():
    path = os.path.join(tempfile.mkdtemp(), "g.jsonld")
    JSONExporter().export_knowledge_graph(_kg_with_datetime(), path, format="json-ld")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    json.loads(content)
    assert "2026-01-01" in content


def test_arango_export_handles_datetime_property():
    path = os.path.join(tempfile.mkdtemp(), "g.aql")
    ArangoAQLExporter().export_entities(_kg_with_datetime()["entities"], path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "2026-01-01" in content
