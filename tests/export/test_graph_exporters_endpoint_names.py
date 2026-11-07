"""Graph, Arango and Neo4j CSV exporters must keep backend relationship endpoints."""

import csv
import json
import re
from copy import deepcopy
from xml.etree import ElementTree

import pytest

from semantica.export import Neo4jCSVExporter
from semantica.export.arango_aql_exporter import ArangoAQLExporter
from semantica.export.graph_exporter import GraphExporter

BACKEND_NAMES = [("start_node_id", "end_node_id"), ("start_id", "end_id")]
ENTITIES = [
    {"id": "alice", "name": "Alice", "type": "Person"},
    {"id": "acme", "name": "Acme", "type": "Org"},
]


def _graph(source_key, target_key, source="alice", target="acme", entities=None):
    record = {"id": "r1", source_key: source, target_key: target, "type": "WORKS_AT"}
    return {"entities": entities or deepcopy(ENTITIES), "relationships": [record]}


def _arango_docs(path):
    """The documents of each `FOR doc IN [...] INSERT doc INTO <collection>`."""
    body = path.read_text(encoding="utf-8")
    docs = {}
    for array, collection in re.findall(
        r"FOR doc IN (\[.*?\])\n  INSERT doc INTO (\w+)", body, re.DOTALL
    ):
        docs.setdefault(collection, []).extend(json.loads(array))
    return docs


@pytest.mark.parametrize("source_key, target_key", BACKEND_NAMES)
def test_graph_exporter_keeps_backend_endpoints(tmp_path, source_key, target_key):
    kg = _graph(source_key, target_key)
    original = deepcopy(kg)

    GraphExporter().export_knowledge_graph(kg, tmp_path / "g.json", format="json")
    [edge] = json.loads((tmp_path / "g.json").read_text(encoding="utf-8"))["edges"]
    assert (edge["source"], edge["target"]) == ("alice", "acme")

    GraphExporter().export_knowledge_graph(kg, tmp_path / "g.graphml", format="graphml")
    root = ElementTree.parse(tmp_path / "g.graphml").getroot()
    [element] = root.iter("{http://graphml.graphdrawing.org/xmlns}edge")
    assert (element.get("source"), element.get("target")) == ("alice", "acme")
    assert kg == original


@pytest.mark.parametrize("source_key, target_key", BACKEND_NAMES)
def test_arango_exporter_keeps_backend_endpoints(tmp_path, source_key, target_key):
    path = tmp_path / "kg.aql"
    ArangoAQLExporter().export(_graph(source_key, target_key), path)

    [edge] = _arango_docs(path)["edges"]
    assert (edge["_from"], edge["_to"]) == ("vertices/alice", "vertices/acme")
    # The endpoint names are structure, not edge properties.
    assert source_key not in edge and target_key not in edge


@pytest.mark.parametrize("source_key, target_key", BACKEND_NAMES)
def test_neo4j_csv_exporter_keeps_backend_endpoints(tmp_path, source_key, target_key):
    Neo4jCSVExporter().export(_graph(source_key, target_key), tmp_path)

    with open(tmp_path / "relationships.csv", encoding="utf-8", newline="") as handle:
        header, *rows = list(csv.reader(handle))
    assert header[:3] == [":START_ID", ":END_ID", ":TYPE"]
    assert [row[:3] for row in rows] == [["alice", "acme", "WORKS_AT"]]
    # The endpoint names are structure, not relationship properties.
    assert source_key not in header and target_key not in header


def test_graph_and_arango_exporters_keep_id_zero_on_both_ends(tmp_path):
    entities = [{"id": 0, "name": "Root"}, {"id": 1, "name": "Child"}]
    kg = _graph("start_node_id", "end_node_id", source=0, target=1, entities=entities)

    GraphExporter().export_knowledge_graph(kg, tmp_path / "g.json", format="json")
    graph = json.loads((tmp_path / "g.json").read_text(encoding="utf-8"))
    assert [node["id"] for node in graph["nodes"]] == [0, 1]
    assert [(e["source"], e["target"]) for e in graph["edges"]] == [(0, 1)]

    ArangoAQLExporter().export(kg, tmp_path / "kg.aql")
    docs = _arango_docs(tmp_path / "kg.aql")
    assert [vertex["_key"] for vertex in docs["vertices"]] == ["0", "1"]
    [edge] = docs["edges"]
    assert (edge["_from"], edge["_to"]) == ("vertices/0", "vertices/1")

    GraphExporter().export_knowledge_graph(kg, tmp_path / "g.graphml", format="graphml")
    root = ElementTree.parse(tmp_path / "g.graphml").getroot()
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    assert [node.get("id") for node in root.iter(ns + "node")] == ["0", "1"]
    [element] = root.iter(ns + "edge")
    assert (element.get("source"), element.get("target")) == ("0", "1")

    GraphExporter().export_knowledge_graph(kg, tmp_path / "g.dot", format="dot")
    assert '"0" -> "1"' in (tmp_path / "g.dot").read_text(encoding="utf-8")


def test_neo4j_csv_exporter_skips_empty_endpoint_names(tmp_path):
    kg = _graph("start_node_id", "end_node_id")
    kg["relationships"][0].update({"source": "", "target_id": ""})

    Neo4jCSVExporter().export(kg, tmp_path)

    with open(tmp_path / "relationships.csv", encoding="utf-8", newline="") as handle:
        _, *rows = list(csv.reader(handle))
    assert [row[:3] for row in rows] == [["alice", "acme", "WORKS_AT"]]
