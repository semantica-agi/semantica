"""
Tests for 'semantica kg find-path' entity resolution (#2179).
"""

import networkx as nx
import pytest
from click.exceptions import ClickException

from semantica.cli import _resolve_entity


def _neo4j_style_graph() -> nx.DiGraph:
    """Neo4j-backed graphs key nodes by integer IDs, not strings."""
    graph = nx.DiGraph()
    graph.add_node(3, name="Alice")
    graph.add_node(7, name="Bob")
    graph.add_edge(3, 7, weight=1.0)
    return graph


class TestResolveEntity:
    def test_numeric_token_resolves_integer_node_id(self):
        graph = _neo4j_style_graph()
        assert _resolve_entity(graph, "3") == 3

    def test_numeric_token_without_match_still_reports_unknown(self):
        graph = _neo4j_style_graph()
        with pytest.raises(ClickException, match="No entity named '42'"):
            _resolve_entity(graph, "42")

    def test_string_node_id_still_resolves(self):
        graph = nx.DiGraph()
        graph.add_node("alice-id", name="Alice")
        assert _resolve_entity(graph, "alice-id") == "alice-id"

    def test_name_resolution_unchanged(self):
        graph = _neo4j_style_graph()
        assert _resolve_entity(graph, "Alice") == 3

    def test_ambiguous_name_error_lists_integer_ids(self):
        graph = nx.DiGraph()
        graph.add_node(3, name="Alice")
        graph.add_node(9, name="Alice")
        with pytest.raises(ClickException, match="ambiguous.*3, 9"):
            _resolve_entity(graph, "Alice")


class TestResolveEntityUnicodeAndLongDigits:
    def test_superscript_digit_token_falls_through_to_unknown_entity_error(self):
        graph = nx.DiGraph()
        graph.add_node(42, name="answer")
        with pytest.raises(ClickException):
            _resolve_entity(graph, "\u00b2")

    def test_overlong_digit_token_falls_through_to_unknown_entity_error(self):
        graph = nx.DiGraph()
        graph.add_node(42, name="answer")
        with pytest.raises(ClickException):
            _resolve_entity(graph, "9" * 5000)

    def test_superscript_token_still_resolves_by_name(self):
        graph = nx.DiGraph()
        graph.add_node("node-1", name="x\u00b2")
        assert _resolve_entity(graph, "x\u00b2") == "node-1"
