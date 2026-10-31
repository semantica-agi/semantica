"""Structural precedent scores preserve full-scan ranking and follow graph changes."""

import math
import unittest
from concurrent.futures import ThreadPoolExecutor

from semantica.context import ContextGraph


class TestPrecedentStructuralScores(unittest.TestCase):
    def make_graph(self):
        graph = ContextGraph(advanced_analytics=True)
        for index in range(4):
            graph.add_node(f"target-{index}", "target")
        decisions = [
            graph.record_decision(
                category="test",
                scenario=f"case {index} shared term",
                reasoning="fixture",
                outcome="retain",
                confidence=0.8,
            )
            for index in range(4)
        ]
        graph.add_edge(decisions[0], "target-0")
        graph.add_edge(decisions[0], "target-1")
        graph.add_edge(decisions[1], "target-0")
        graph.add_edge(decisions[2], "target-0")
        return graph, decisions

    def test_structural_scores_equal_full_scan_and_follow_mutations(self):
        graph, decisions = self.make_graph()
        for decision_id in decisions:
            with self.subTest(decision_id=decision_id):
                fast = graph._precedent_structural_scores(set(decisions))[decision_id]
                slow = graph._calculate_structural_similarity_for_decision(
                    decision_id, "case"
                )
                self.assertTrue(math.isclose(fast, slow))

        before = graph._precedent_structural_scores(set(decisions))
        graph.add_edge(decisions[3], "target-2")
        after = graph._precedent_structural_scores(set(decisions))
        self.assertNotEqual(before, after)
        self.assertTrue(graph.config["advanced_analytics"])

    def test_structural_scores_equal_full_scan_with_mixed_node_types(self):
        graph = ContextGraph(advanced_analytics=True)
        targets = [f"target-{index}" for index in range(6)]
        for target in targets:
            graph.add_node(target, "entity")
        decisions = [
            graph.record_decision(
                category="test", scenario=f"case {index}", reasoning="fixture",
                outcome="retain", confidence=0.8,
            )
            for index in range(5)
        ]
        # Same-type nodes that are not recorded decisions still count.
        graph.add_node("bare-decision", "decision")
        # An entity hub one degree away from decisions[0]; it must be ignored.
        graph.add_node("hub", "entity")
        for target in targets[:4]:
            graph.add_edge("hub", target)

        # Each decision starts with one category edge.
        graph.add_edge(decisions[0], decisions[0])  # self-loop
        graph.add_edge(decisions[0], targets[0])
        for target in targets[:3]:
            graph.add_edge(decisions[1], target)
        graph.add_edge(decisions[1], targets[0], edge_type="cites")
        for target in targets:
            graph.add_edge(decisions[4], target)
        # decisions[2] and decisions[3] share degree 1; bare-decision has 0.

        node_ids = set(decisions) | {"bare-decision"}
        fast = graph._precedent_structural_scores(node_ids)
        for node_id in node_ids:
            with self.subTest(node_id=node_id):
                slow = graph._calculate_structural_similarity_for_decision(
                    node_id, "case"
                )
                self.assertEqual(fast[node_id], slow)

    def test_singleton_and_same_degree_nodes(self):
        graph = ContextGraph(advanced_analytics=True)
        first = graph.record_decision(
            category="test", scenario="first", reasoning="fixture",
            outcome="retain", confidence=0.8,
        )
        self.assertEqual(graph._precedent_structural_scores({first})[first], 0.0)
        second = graph.record_decision(
            category="test", scenario="second", reasoning="fixture",
            outcome="retain", confidence=0.8,
        )
        scores = graph._precedent_structural_scores({first, second})
        self.assertEqual(scores[first], 1.0)
        self.assertEqual(scores[second], 1.0)

    def test_precedent_ranking_matches_full_scan(self):
        graph, decisions = self.make_graph()
        scenario = "case 0 shared term"
        expected = []
        for decision_id in decisions:
            decision = graph._decisions[decision_id]
            content = graph._calculate_decision_content_similarity(scenario, decision)
            structural = graph._calculate_structural_similarity_for_decision(
                decision_id, scenario
            )
            expected.append((decision_id, 0.7 * content + 0.3 * structural))
        expected.sort(key=lambda item: item[1], reverse=True)

        actual = graph.find_precedents_by_scenario(
            scenario, limit=4, similarity_threshold=0.0
        )
        # Set iteration makes the order of equal-scoring decisions undefined.
        self.assertEqual(actual[0]["decision"]["id"], decisions[0])
        self.assertEqual(
            sorted((row["decision"]["id"], row["similarity"]) for row in actual),
            sorted(expected),
        )
        self.assertEqual(
            [row["similarity"] for row in actual],
            [score for _, score in expected],
        )

    def test_parallel_readers_share_no_index_state(self):
        graph, decisions = self.make_graph()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(
                lambda _: graph.find_precedents_by_scenario(
                    "case 0 shared term", limit=4, similarity_threshold=0.0
                ),
                range(8),
            ))
        ids = [[row["decision"]["id"] for row in rows] for rows in results]
        self.assertTrue(all(row == ids[0] for row in ids))
        self.assertEqual(len(ids[0]), len(decisions))
