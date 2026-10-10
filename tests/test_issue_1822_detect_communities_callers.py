"""Regression tests for the detect_communities result wrapper in callers (#1822).

`CommunityDetector.detect_communities()` returns a wrapper dict
(``communities``, ``node_assignments``, ``modularity``, ``algorithm``).
Four production callers still consumed that wrapper as a flat
``{community_id: members}`` mapping, so they silently produced wrong community
data: a wrapper key such as ``node_assignments`` could be taken for a community
id, and ``len()`` of the wrapper reported ``4`` for every graph and algorithm.

Every graph used below has two communities, so a constant wrapper-key count
cannot accidentally pass.
"""

import unittest
from unittest import mock

from semantica.context import ContextGraph
from semantica.context.context_retriever import ContextRetriever
from semantica.context.decision_query import DecisionQuery
from semantica.kg import CommunityDetector
from semantica.vector_store.decision_embedding_pipeline import (
    DecisionEmbeddingPipeline,
)


def _two_community_graph() -> ContextGraph:
    """Two disjoint clusters: (alice, bob, carol) and (dave, erin)."""
    graph = ContextGraph(advanced_analytics=True)
    for name in ("alice", "bob", "carol", "dave", "erin"):
        graph.add_node(name, node_type="Person", content=name)
    graph.add_edge("alice", "bob", edge_type="knows")
    graph.add_edge("bob", "carol", edge_type="knows")
    graph.add_edge("dave", "erin", edge_type="knows")
    return graph


class TestAnalyzeGraphWithKgCommunityCount(unittest.TestCase):
    """`ContextGraph.analyze_graph_with_kg` must count groups, not wrapper keys."""

    def _analyze(self) -> dict:
        graph = _two_community_graph()
        # Keep the real community detector; stub the other components so only
        # the community path is exercised.
        graph.kg_components["centrality_calculator"] = mock.Mock(
            calculate_all_centrality=mock.Mock(return_value={"centrality_measures": {}})
        )
        graph.kg_components["connectivity_analyzer"] = mock.Mock(
            analyze_connectivity=mock.Mock(return_value={})
        )
        graph.kg_components["node_embedder"] = mock.Mock(
            compute_embeddings=mock.Mock(return_value={})
        )
        return graph.analyze_graph_with_kg()

    def test_num_communities_reports_detected_groups(self):
        analysis = self._analyze()
        self.assertNotIn("error", analysis, analysis)
        community_analysis = analysis["community_analysis"]
        self.assertEqual(community_analysis["num_communities"], 2)
        self.assertEqual(len(community_analysis["communities"]), 2)
        # The wrapper dict has four keys; a key count must never leak through.
        self.assertNotEqual(community_analysis["num_communities"], 4)


class TestExpandDecisionContextCommunity(unittest.TestCase):
    """`ContextRetriever._expand_decision_context` must read node_assignments."""

    def test_only_same_community_entities_are_added(self):
        graph = _two_community_graph()
        retriever = ContextRetriever(vector_store=mock.Mock(), knowledge_graph=graph)
        retriever.path_finder = None
        retriever.centrality_calculator = None
        retriever.community_detector = CommunityDetector()

        detected = CommunityDetector().detect_communities(graph)
        assignments = detected["node_assignments"]
        self.assertEqual(len(detected["communities"]), 2, assignments)
        alice_community = assignments["alice"]
        same_community = {
            node
            for node, community_id in assignments.items()
            if community_id == alice_community and node != "alice"
        }
        other_communities = {
            node
            for node, community_id in assignments.items()
            if community_id != alice_community
        }
        self.assertTrue(other_communities, assignments)

        expanded = retriever._expand_decision_context([{"name": "alice"}], max_hops=1)
        community_names = {
            entity["name"]
            for entity in expanded
            if entity.get("source") == "community_detector"
        }

        self.assertTrue(
            same_community & community_names,
            (same_community, community_names),
        )
        for leaked in other_communities:
            self.assertNotIn(leaked, community_names)
        # No wrapper key may ever surface as an entity name.
        self.assertNotIn("node_assignments", community_names)
        self.assertNotIn("communities", community_names)


class TestGetEntityCommunities(unittest.TestCase):
    """`DecisionEmbeddingPipeline._get_entity_communities` must use assignments."""

    def test_assignments_come_from_node_assignments(self):
        graph = _two_community_graph()
        pipeline = DecisionEmbeddingPipeline(
            vector_store=mock.Mock(),
            graph_store=graph,
            use_graph_features=True,
        )
        pipeline.community_detector = CommunityDetector()

        detected = CommunityDetector().detect_communities(graph)
        expected = detected["node_assignments"]
        self.assertEqual(len(detected["communities"]), 2, expected)

        got = pipeline._get_entity_communities(["alice", "carol", "dave"])
        self.assertEqual(got["alice"], expected["alice"])
        self.assertEqual(got["carol"], expected["carol"])
        self.assertEqual(got["dave"], expected["dave"])
        self.assertNotEqual(got["alice"], got["dave"])

        # An entity that is not in the graph is dropped, not mapped to a key.
        self.assertEqual(pipeline._get_entity_communities(["ghost"]), {})


class TestAnalyzeDecisionInfluenceCommunity(unittest.TestCase):
    """`DecisionQuery.analyze_decision_influence` must derive community data."""

    def _query_with(self, detector) -> DecisionQuery:
        graph_store = mock.Mock()
        graph_store.execute_query.return_value = {"success": True, "records": []}
        query = DecisionQuery(graph_store=graph_store, advanced_analytics=False)
        query.kg_components = {"community_detector": detector}
        return query

    def test_community_info_is_derived_from_node_assignments(self):
        detector = mock.Mock()
        detector.detect_communities.return_value = {
            "communities": [["d1", "d2"], ["d3", "d4", "d5"]],
            "node_assignments": {"d1": 0, "d2": 0, "d3": 1, "d4": 1, "d5": 1},
            "modularity": 0.4,
            "algorithm": "louvain",
        }
        analysis = self._query_with(detector).analyze_decision_influence("d4")

        info = analysis["community_info"]
        self.assertEqual(info["community_id"], 1)
        self.assertEqual(info["community_size"], 3)
        self.assertEqual(set(info["community_members"]), {"d3", "d4", "d5"})


if __name__ == "__main__":
    unittest.main()
