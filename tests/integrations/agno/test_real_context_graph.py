"""AgnoKGToolkit and AgnoKnowledgeGraph read what ContextGraph returns (#1726)."""

import json

import pytest

from integrations.agno.kg_toolkit import AgnoKGToolkit
from integrations.agno.knowledge_graph import AgnoKnowledgeGraph
from semantica.context import ContextGraph


@pytest.fixture
def graph():
    graph = ContextGraph()
    graph.add_node("Alice", "Person", content="Alice Smith")
    graph.add_node("Acme", "Organization", content="Acme Corp")
    graph.add_edge("Alice", "Acme", "WORKS_AT")
    return graph


@pytest.fixture
def toolkit(graph):
    return AgnoKGToolkit(context=graph)


def test_query_graph_matches_node_ids(toolkit):
    result = json.loads(toolkit.query_graph("Alice"))

    assert result["results"] == [{"label": "Alice", "type": "Person", "id": "Alice"}]


def test_find_related_returns_neighbors(toolkit):
    result = json.loads(toolkit.find_related("Alice"))

    assert result["related"] == ["Acme"]


def test_infer_facts_derives_facts_from_graph_nodes(toolkit):
    result = json.loads(toolkit.infer_facts(json.dumps(["IF Person(?x) THEN Human(?x)"])))

    assert result["inferred_facts"] == ["Human(Alice)"]


def test_export_subgraph_serializes_the_graph(toolkit):
    result = json.loads(toolkit.export_subgraph())

    assert result["format"] == "json-ld"
    assert "Alice" in result["data"]
    assert "WORKS_AT" in result["data"]


def test_graph_context_names_the_edge_and_neighbor(graph):
    knowledge = AgnoKnowledgeGraph(context_graph=graph)

    assert knowledge.get_graph_context("Alice") == (
        "Entity: Alice\n  --[WORKS_AT]--> Acme (type: Organization)"
    )
    assert knowledge._graph_context_for(["Alice"]) == (
        "- Alice --[WORKS_AT]--> Acme (Organization)"
    )
