"""
Tests for Hierarchical Community Structure and Multi-Level Coarsening.
"""

import networkx as nx
import pytest

from semantica.kg import (
    CommunityHierarchy,
    CommunityHierarchyBuilder,
    HierarchicalCommunity,
    KnowledgeGraph,
    build_community_hierarchy,
)
from semantica.kg.registry import algorithm_registry, method_registry


# ---------------------------------------------------------------------------
# HierarchicalCommunity Dataclass Tests
# ---------------------------------------------------------------------------

class TestHierarchicalCommunity:
    """Unit tests for HierarchicalCommunity dataclass."""

    def test_create_hierarchical_community_defaults(self):
        comm = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["node_b", "node_a"],
        )
        assert comm.id == "c_0_0"
        assert comm.level == 0
        assert comm.index == 0
        assert comm.entity_ids == ["node_a", "node_b"]
        assert comm.size == 2
        assert comm.child_ids == []
        assert comm.parent_id is None
        assert comm.metrics == {}
        assert len(comm.content_hash) == 64

    def test_content_hash_deterministic(self):
        comm1 = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["z", "a", "m"],
            child_ids=["c_prev_2", "c_prev_1"],
        )
        comm2 = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["a", "m", "z"],
            child_ids=["c_prev_1", "c_prev_2"],
        )
        assert comm1.content_hash == comm2.content_hash

    def test_content_hash_changes_on_difference(self):
        comm1 = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["a", "b"],
        )
        comm2 = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["a", "c"],
        )
        assert comm1.content_hash != comm2.content_hash

    def test_to_dict_and_from_dict(self):
        comm = HierarchicalCommunity(
            id="c_1_2",
            level=1,
            index=2,
            entity_ids=["n1", "n2"],
            child_ids=["c_0_1"],
            parent_id="c_2_0",
            metrics={"density": 0.75, "internal_edges": 1},
        )
        data = comm.to_dict()
        restored = HierarchicalCommunity.from_dict(data)
        assert restored.id == comm.id
        assert restored.level == comm.level
        assert restored.index == comm.index
        assert restored.entity_ids == comm.entity_ids
        assert restored.child_ids == comm.child_ids
        assert restored.parent_id == comm.parent_id
        assert restored.size == comm.size
        assert restored.metrics == comm.metrics
        assert restored.content_hash == comm.content_hash


# ---------------------------------------------------------------------------
# CommunityHierarchy Container Tests
# ---------------------------------------------------------------------------

class TestCommunityHierarchyContainer:
    """Unit tests for CommunityHierarchy container."""

    def test_empty_hierarchy(self):
        hierarchy = CommunityHierarchy()
        assert hierarchy.is_empty is True
        assert len(hierarchy) == 0
        assert hierarchy.levels == []
        assert hierarchy.max_level == -1
        assert hierarchy.root_communities == []
        assert hierarchy.leaf_communities == []
        assert hierarchy.get_community("c_0_0") is None
        assert hierarchy.get_community_for_node("node_1") is None

    def test_container_indexing_and_traversal(self):
        c0_0 = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["n1", "n2"],
            parent_id="c_1_0",
        )
        c0_1 = HierarchicalCommunity(
            id="c_0_1",
            level=0,
            index=1,
            entity_ids=["n3"],
            parent_id="c_1_0",
        )
        c1_0 = HierarchicalCommunity(
            id="c_1_0",
            level=1,
            index=0,
            entity_ids=["n1", "n2", "n3"],
            child_ids=["c_0_0", "c_0_1"],
            parent_id=None,
        )

        hierarchy = CommunityHierarchy([c0_0, c0_1, c1_0])

        assert hierarchy.is_empty is False
        assert len(hierarchy) == 3
        assert hierarchy.levels == [0, 1]
        assert hierarchy.max_level == 1
        assert len(hierarchy.root_communities) == 1
        assert hierarchy.root_communities[0].id == "c_1_0"
        assert len(hierarchy.leaf_communities) == 2
        assert [c.id for c in hierarchy.leaf_communities] == ["c_0_0", "c_0_1"]

        # get_community
        assert hierarchy.get_community("c_0_0") == c0_0
        assert hierarchy.get_community("nonexistent") is None

        # get_communities_at_level
        assert hierarchy.get_communities_at_level(0) == [c0_0, c0_1]
        assert hierarchy.get_communities_at_level(1) == [c1_0]
        assert hierarchy.get_communities_at_level(99) == []

        # get_children
        assert hierarchy.get_children("c_1_0") == [c0_0, c0_1]
        assert hierarchy.get_children(c1_0) == [c0_0, c0_1]
        assert hierarchy.get_children("c_0_0") == []

        # get_parent
        assert hierarchy.get_parent("c_0_0") == c1_0
        assert hierarchy.get_parent(c0_1) == c1_0
        assert hierarchy.get_parent("c_1_0") is None

        # get_community_for_node (O(1))
        assert hierarchy.get_community_for_node("n1") == c0_0
        assert hierarchy.get_community_for_node("n1", level=0) == c0_0
        assert hierarchy.get_community_for_node("n1", level=1) == c1_0
        assert hierarchy.get_community_for_node("n3", level=0) == c0_1
        assert hierarchy.get_community_for_node("n3", level=1) == c1_0
        assert hierarchy.get_community_for_node("missing_node") is None
        assert hierarchy.get_community_for_node("n1", level=99) is None

        # Container dunder methods
        assert "c_0_0" in hierarchy
        assert "c_9_9" not in hierarchy
        assert hierarchy["c_0_0"] == c0_0
        all_comms = list(hierarchy)
        assert len(all_comms) == 3

    def test_to_dict_and_to_json_roundtrip(self):
        c0 = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["a", "b"]
        )
        hierarchy = CommunityHierarchy([c0])

        d = hierarchy.to_dict()
        restored_from_dict = CommunityHierarchy.from_dict(d)
        assert len(restored_from_dict) == 1
        assert restored_from_dict["c_0_0"].entity_ids == ["a", "b"]
        matched_comm = restored_from_dict.get_community_for_node("a")
        assert matched_comm == restored_from_dict["c_0_0"]

        json_str = hierarchy.to_json()
        assert isinstance(json_str, str)
        restored_from_json = CommunityHierarchy.from_json(json_str)
        assert len(restored_from_json) == 1
        assert restored_from_json["c_0_0"].id == "c_0_0"

    def test_get_subgraph_networkx(self):
        g = nx.Graph()
        g.add_edge("1", "2")
        g.add_edge("2", "3")
        g.add_edge("3", "4")

        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["1", "2"]
        )
        hierarchy = CommunityHierarchy([c], graph=g)

        sub = hierarchy.get_subgraph("c_0_0")
        assert isinstance(sub, nx.Graph)
        assert set(sub.nodes()) == {"1", "2"}
        assert sub.has_edge("1", "2")
        assert not sub.has_edge("2", "3")

    def test_get_subgraph_knowledge_graph(self):
        kg = KnowledgeGraph(
            entities=[{"id": "e1"}, {"id": "e2"}, {"id": "e3"}],
            relationships=[
                {"source": "e1", "target": "e2", "type": "KNOWS"},
                {"source": "e2", "target": "e3", "type": "KNOWS"},
            ],
            metadata={"source": "test"},
        )
        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["e1", "e2"]
        )
        hierarchy = CommunityHierarchy([c])

        sub = hierarchy.get_subgraph("c_0_0", graph=kg)
        assert isinstance(sub, KnowledgeGraph)
        assert len(sub.entities) == 2
        assert len(sub.relationships) == 1
        assert sub.relationships[0]["source"] == "e1"

    def test_get_subgraph_dict_representations(self):
        kg_dict = {
            "entities": [{"id": "x"}, {"id": "y"}, {"id": "z"}],
            "relationships": [
                {"source": "x", "target": "y", "weight": 1.0},
                {"source": "y", "target": "z", "weight": 1.0},
            ],
        }
        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["x", "y"]
        )
        hierarchy = CommunityHierarchy([c], graph=kg_dict)

        sub_kg = hierarchy.get_subgraph("c_0_0")
        assert len(sub_kg["entities"]) == 2
        assert len(sub_kg["relationships"]) == 1

        nodes_dict = {
            "nodes": [{"id": "p"}, {"id": "q"}],
            "edges": [{"source": "p", "target": "q"}],
        }
        c2 = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["p", "q"]
        )
        hierarchy2 = CommunityHierarchy([c2], graph=nodes_dict)
        sub_nodes = hierarchy2.get_subgraph("c_0_0")
        assert len(sub_nodes["nodes"]) == 2
        assert len(sub_nodes["edges"]) == 1

    def test_get_subgraph_errors(self):
        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["a"]
        )
        hierarchy = CommunityHierarchy([c])

        with pytest.raises(ValueError, match="graph must be provided"):
            hierarchy.get_subgraph("c_0_0")

        with pytest.raises(KeyError, match="not found"):
            hierarchy.get_subgraph("c_unknown", graph=nx.Graph())


# ---------------------------------------------------------------------------
# CommunityHierarchyBuilder Invariant Tests
# ---------------------------------------------------------------------------

class TestCommunityHierarchyBuilder:
    """Core tests for CommunityHierarchyBuilder algorithms and invariants."""

    def _verify_all_hierarchy_invariants(
        self, graph: nx.Graph, hierarchy: CommunityHierarchy
    ):
        """Helper to assert all structural and mathematical invariants."""
        assert not hierarchy.is_empty
        all_graph_nodes = {str(n) for n in graph.nodes()}
        levels = hierarchy.levels
        assert len(levels) >= 1

        for level in levels:
            level_comms = hierarchy.get_communities_at_level(level)
            assert len(level_comms) > 0

            # Disjoint and complete coverage invariant
            level_nodes = []
            for comm in level_comms:
                assert comm.level == level
                assert comm.size == len(comm.entity_ids)
                level_nodes.extend(comm.entity_ids)

            assert set(level_nodes) == all_graph_nodes
            assert len(level_nodes) == len(all_graph_nodes)

            # Inverted index consistency
            for comm in level_comms:
                for node_id in comm.entity_ids:
                    indexed_comm = hierarchy.get_community_for_node(
                        node_id, level=level
                    )
                    assert indexed_comm is not None
                    assert indexed_comm.id == comm.id

        # Hierarchical containment invariants between adjacent levels
        for l_idx in range(len(levels) - 1):
            child_level = levels[l_idx]
            parent_level = levels[l_idx + 1]

            children = hierarchy.get_communities_at_level(child_level)
            parents = hierarchy.get_communities_at_level(parent_level)
            parent_map = {p.id: p for p in parents}

            for child in children:
                assert child.parent_id is not None
                assert child.parent_id in parent_map
                parent = parent_map[child.parent_id]
                # Child entity set must be a subset of parent entity set
                assert set(child.entity_ids).issubset(set(parent.entity_ids))
                assert child.id in parent.child_ids

            # Parent entity set must be the exact union of child entity sets
            for parent in parents:
                assert len(parent.child_ids) > 0
                union_child_entities = set()
                for cid in parent.child_ids:
                    c = hierarchy.get_community(cid)
                    assert c is not None
                    union_child_entities.update(c.entity_ids)
                assert set(parent.entity_ids) == union_child_entities

        # Root communities must have parent_id == None
        top_level = hierarchy.max_level
        top_comms = hierarchy.get_communities_at_level(top_level)
        for c in top_comms:
            assert c.parent_id is None

        # Leaf communities must have child_ids == []
        bottom_level = levels[0]
        bottom_comms = hierarchy.get_communities_at_level(bottom_level)
        for c in bottom_comms:
            assert c.child_ids == []

    def test_build_louvain_karate_club(self):
        g = nx.karate_club_graph()
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(g)

        assert hierarchy.max_level >= 1
        self._verify_all_hierarchy_invariants(g, hierarchy)

    def test_build_leiden_karate_club(self):
        g = nx.karate_club_graph()
        builder = CommunityHierarchyBuilder(algorithm="leiden", seed=42)
        hierarchy = builder.build(g)

        assert hierarchy.max_level >= 1
        self._verify_all_hierarchy_invariants(g, hierarchy)

    def test_non_merging_communities_invariant(self):
        # Construct graph where one cluster merges, but another does not.
        g = nx.Graph()
        for u in range(10):
            for v in range(u + 1, 10):
                g.add_edge(str(u), str(v))
        g.add_edge("isolated_a", "isolated_b")

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(g)

        self._verify_all_hierarchy_invariants(g, hierarchy)

        if hierarchy.max_level >= 1:
            for parent in hierarchy.get_communities_at_level(1):
                if len(parent.child_ids) == 1:
                    child = hierarchy.get_community(parent.child_ids[0])
                    assert child is not None
                    assert set(parent.entity_ids) == set(child.entity_ids)

    def test_directed_graph_with_weakly_connected_refinement(self):
        g = nx.DiGraph()
        g.add_edges_from([("1", "2"), ("2", "3"), ("3", "1")])
        g.add_edges_from([("4", "5"), ("5", "6"), ("6", "4")])
        g.add_edge("3", "4")

        builder = CommunityHierarchyBuilder(
            algorithm="louvain", seed=42, directed=True
        )
        hierarchy = builder.build(g)

        self._verify_all_hierarchy_invariants(g, hierarchy)

        for comm in hierarchy:
            sub = g.subgraph(comm.entity_ids)
            assert nx.is_weakly_connected(sub)

    def test_isolated_nodes_handling(self):
        g = nx.erdos_renyi_graph(20, 0.15, seed=42)
        g.add_node(999)
        g.add_node(1000)

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(g)

        self._verify_all_hierarchy_invariants(g, hierarchy)

        for level in hierarchy.levels:
            c999 = hierarchy.get_community_for_node("999", level=level)
            c1000 = hierarchy.get_community_for_node("1000", level=level)
            assert c999 is not None
            assert c1000 is not None
            assert "999" in c999.entity_ids
            assert "1000" in c1000.entity_ids

    def test_empty_graph(self):
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(nx.Graph())
        assert hierarchy.is_empty is True
        assert hierarchy.levels == []
        assert hierarchy.max_level == -1

    def test_single_node_graph(self):
        g = nx.Graph()
        g.add_node("single")
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(g)

        assert not hierarchy.is_empty
        assert hierarchy.levels == [0]
        assert hierarchy.max_level == 0
        comm = hierarchy.get_community_for_node("single")
        assert comm is not None
        assert comm.entity_ids == ["single"]
        assert comm.parent_id is None
        assert comm.child_ids == []

    def test_deterministic_reproducibility(self):
        g = nx.erdos_renyi_graph(40, 0.1, seed=123)

        builder1 = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        builder2 = CommunityHierarchyBuilder(algorithm="louvain", seed=42)

        h1 = builder1.build(g)
        h2 = builder2.build(g)

        assert h1.to_dict() == h2.to_dict()

        builder_leiden1 = CommunityHierarchyBuilder(
            algorithm="leiden", seed=42
        )
        builder_leiden2 = CommunityHierarchyBuilder(
            algorithm="leiden", seed=42
        )

        hl1 = builder_leiden1.build(g)
        hl2 = builder_leiden2.build(g)

        assert hl1.to_dict() == hl2.to_dict()

    def test_knowledge_graph_dataclass_input(self):
        kg = KnowledgeGraph(
            entities=[{"id": f"n{i}"} for i in range(10)],
            relationships=[
                {"source": f"n{i}", "target": f"n{i+1}", "weight": 1.0}
                for i in range(9)
            ],
        )
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(kg)

        assert not hierarchy.is_empty
        for i in range(10):
            assert hierarchy.get_community_for_node(f"n{i}") is not None

    def test_semantica_dict_input(self):
        data = {
            "entities": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "relationships": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
            ],
        }
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(data)

        assert not hierarchy.is_empty
        assert hierarchy.get_community_for_node("a") is not None

    def test_max_levels_constraint(self):
        g = nx.erdos_renyi_graph(60, 0.08, seed=42)
        builder = CommunityHierarchyBuilder(
            algorithm="louvain", seed=42, max_levels=1
        )
        hierarchy = builder.build(g)

        assert len(hierarchy.levels) == 1
        assert hierarchy.max_level == 0

    def test_unsupported_algorithm_raises(self):
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            CommunityHierarchyBuilder(algorithm="invalid_algo")

    def test_community_metrics(self):
        g = nx.Graph()
        g.add_edges_from([("1", "2"), ("2", "3"), ("3", "1")])
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        hierarchy = builder.build(g)

        comm = hierarchy.get_community_for_node("1")
        assert comm is not None
        assert comm.metrics["internal_edges"] == 3
        assert comm.metrics["external_edges"] == 0
        assert comm.metrics["density"] == 1.0
        assert comm.metrics["conductance"] == 0.0


# ---------------------------------------------------------------------------
# Integration & Registry Tests
# ---------------------------------------------------------------------------

class TestIntegrationAndRegistry:
    """Tests for integration into semantica.kg, methods.py, and registry.py."""

    def test_build_community_hierarchy_convenience_function(self):
        g = nx.karate_club_graph()
        h_louvain = build_community_hierarchy(g, method="louvain", seed=42)
        assert isinstance(h_louvain, CommunityHierarchy)
        assert not h_louvain.is_empty

        h_leiden = build_community_hierarchy(g, method="leiden", seed=42)
        assert isinstance(h_leiden, CommunityHierarchy)
        assert not h_leiden.is_empty

    def test_method_registry_integration(self):
        default_fn = method_registry.get("community_hierarchy", "default")
        louvain_fn = method_registry.get("community_hierarchy", "louvain")
        leiden_fn = method_registry.get("community_hierarchy", "leiden")

        assert callable(default_fn)
        assert callable(louvain_fn)
        assert callable(leiden_fn)

    def test_algorithm_registry_integration(self):
        cls_louvain = algorithm_registry.get("community_hierarchy", "louvain")
        cls_leiden = algorithm_registry.get("community_hierarchy", "leiden")
        cls_default = algorithm_registry.get("community_hierarchy", "default")

        assert cls_louvain is CommunityHierarchyBuilder
        assert cls_leiden is CommunityHierarchyBuilder
        assert cls_default is CommunityHierarchyBuilder

        inst_louvain = algorithm_registry.create_instance(
            "community_hierarchy", "louvain", seed=42
        )
        assert isinstance(inst_louvain, CommunityHierarchyBuilder)
        assert inst_louvain.algorithm == "louvain"

        inst_leiden = algorithm_registry.create_instance(
            "community_hierarchy", "leiden", seed=42
        )
        assert isinstance(inst_leiden, CommunityHierarchyBuilder)
        assert inst_leiden.algorithm == "leiden"

        inst_default = algorithm_registry.create_instance(
            "community_hierarchy", "default", seed=42
        )
        assert isinstance(inst_default, CommunityHierarchyBuilder)
        assert inst_default.algorithm == "louvain"

    def test_build_community_hierarchy_default_method(self):
        g = nx.karate_club_graph()
        h_default = build_community_hierarchy(g, method="default", seed=42)
        assert isinstance(h_default, CommunityHierarchy)
        assert not h_default.is_empty


# ---------------------------------------------------------------------------
# Extended Edge Case & Robustness Tests
# ---------------------------------------------------------------------------

class TestCommunityHierarchyEdgeCases:
    """Rigorous robustness tests for edge cases and input variants."""

    def test_entity_and_child_ids_deduplication(self):
        comm = HierarchicalCommunity(
            id="c_0_0",
            level=0,
            index=0,
            entity_ids=["b", "a", "b", "a"],
            child_ids=["c_prev_1", "c_prev_1"],
        )
        assert comm.entity_ids == ["a", "b"]
        assert comm.size == 2
        assert comm.child_ids == ["c_prev_1"]

    def test_multigraph_parallel_edges_weight_aggregation(self):
        mg = nx.MultiGraph()
        mg.add_edge("a", "b", weight=2.0)
        mg.add_edge("a", "b", weight=3.0)
        mg.add_edge("b", "c", weight=1.0)

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        converted = builder._to_networkx(mg)
        assert converted.get_edge_data("a", "b")["weight"] == 5.0
        assert converted.get_edge_data("b", "c")["weight"] == 1.0

        hierarchy = builder.build(mg)
        assert not hierarchy.is_empty

    def test_multidigraph_parallel_edges_weight_aggregation(self):
        mdg = nx.MultiDiGraph()
        mdg.add_edge("x", "y", weight=1.5)
        mdg.add_edge("x", "y", weight=2.5)

        builder = CommunityHierarchyBuilder(
            algorithm="louvain", directed=True, seed=42
        )
        converted = builder._to_networkx(mdg)
        assert converted.is_directed()
        assert converted.get_edge_data("x", "y")["weight"] == 4.0

    def test_empty_and_invalid_resolution_handling(self):
        builder_empty = CommunityHierarchyBuilder(resolution=[])
        assert builder_empty.resolution == [1.0]

        with pytest.raises(ValueError, match="Resolution.*must be positive"):
            CommunityHierarchyBuilder(resolution=0.0)

        with pytest.raises(ValueError, match="Resolution.*must be positive"):
            CommunityHierarchyBuilder(resolution=[1.0, -0.5])

    def test_invalid_max_levels_handling(self):
        with pytest.raises(ValueError, match="max_levels.*positive"):
            CommunityHierarchyBuilder(max_levels=0)

        with pytest.raises(ValueError, match="max_levels.*positive"):
            CommunityHierarchyBuilder(max_levels=-2)

    def test_leiden_multi_resolution_list(self):
        g = nx.erdos_renyi_graph(30, 0.15, seed=42)
        builder = CommunityHierarchyBuilder(
            algorithm="leiden", resolution=[1.5, 0.8], seed=42
        )
        hierarchy = builder.build(g)
        assert not hierarchy.is_empty
        assert hierarchy.max_level >= 0

    def test_get_subgraph_adjacency_dict(self):
        adj = {
            "node_1": ["node_2"],
            "node_2": ["node_1", "node_3"],
            "node_3": ["node_2"],
        }
        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["node_1", "node_2"]
        )
        hierarchy = CommunityHierarchy([c])
        sub = hierarchy.get_subgraph("c_0_0", graph=adj)
        assert isinstance(sub, dict)
        assert set(sub.keys()) == {"node_1", "node_2"}
        assert sub["node_1"] == ["node_2"]
        assert sub["node_2"] == ["node_1"]

    def test_get_subgraph_source_id_target_id(self):
        kg = KnowledgeGraph(
            entities=[{"id": "e1"}, {"id": "e2"}, {"id": "e3"}],
            relationships=[
                {"source_id": "e1", "target_id": "e2", "type": "KNOWS"},
                {"source_id": "e2", "target_id": "e3", "type": "KNOWS"},
            ],
        )
        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["e1", "e2"]
        )
        hierarchy = CommunityHierarchy([c])
        sub = hierarchy.get_subgraph("c_0_0", graph=kg)
        assert isinstance(sub, KnowledgeGraph)
        assert len(sub.entities) == 2
        assert len(sub.relationships) == 1
        assert sub.relationships[0]["source_id"] == "e1"

    def test_get_community_for_node_lowest_available_level(self):
        c = HierarchicalCommunity(
            id="c_2_0", level=2, index=0, entity_ids=["alpha", "beta"]
        )
        hierarchy = CommunityHierarchy([c])
        matched = hierarchy.get_community_for_node("alpha", level=None)
        assert matched is not None
        assert matched.id == "c_2_0"

    def test_from_dict_with_communities_as_list(self):
        c = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["n1"]
        )
        data = {"communities": [c.to_dict()]}
        restored = CommunityHierarchy.from_dict(data)
        assert len(restored) == 1
        assert "c_0_0" in restored

    def test_edge_weight_sanitization(self):
        g = nx.Graph()
        g.add_edge("1", "2", weight="invalid")
        g.add_edge("2", "3", weight=-5.0)
        g.add_edge("3", "4", weight=float("nan"))
        g.add_edge("4", "5", weight=None)

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        converted = builder._to_networkx(g)
        assert converted.get_edge_data("1", "2")["weight"] == 1.0
        assert converted.get_edge_data("2", "3")["weight"] == 0.0
        assert converted.get_edge_data("3", "4")["weight"] == 1.0
        assert converted.get_edge_data("4", "5")["weight"] == 1.0

        hierarchy = builder.build(g)
        assert not hierarchy.is_empty

    def test_edge_weight_change_invalidates_content_hash(self):
        g1 = nx.Graph()
        g1.add_edge("a", "b", weight=1.0)
        g1.add_edge("b", "c", weight=1.0)
        g1.add_edge("a", "c", weight=1.0)

        g2 = nx.Graph()
        g2.add_edge("a", "b", weight=5.0)
        g2.add_edge("b", "c", weight=1.0)
        g2.add_edge("a", "c", weight=1.0)

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        h1 = builder.build(g1)
        h2 = builder.build(g2)

        c1 = h1.get_community_for_node("a", level=0)
        c2 = h2.get_community_for_node("a", level=0)
        assert c1 is not None and c2 is not None
        assert c1.entity_ids == c2.entity_ids
        assert c1.content_hash != c2.content_hash

    def test_edge_topology_change_invalidates_content_hash(self):
        g1 = nx.Graph()
        g1.add_edge("a", "b")
        g1.add_edge("b", "c")
        g1.add_edge("a", "c")

        g2 = nx.Graph()
        g2.add_edge("a", "b")
        g2.add_edge("b", "c")

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        h1 = builder.build(g1)
        h2 = builder.build(g2)

        c1 = h1.get_community_for_node("a", level=0)
        c2 = h2.get_community_for_node("a", level=0)
        assert c1 is not None and c2 is not None
        assert c1.entity_ids == c2.entity_ids
        assert c1.content_hash != c2.content_hash

    def test_node_identifier_collision_networkx_raises(self):
        g = nx.Graph()
        g.add_node(1)
        g.add_node("1")
        g.add_edge(1, 2)

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        with pytest.raises(ValueError, match="collision detected"):
            builder.build(g)

    def test_node_identifier_collision_dict_entities_raises(self):
        graph_dict = {
            "entities": [{"id": 1}, {"id": "1"}],
            "relationships": [{"source": 1, "target": 2}],
        }
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        with pytest.raises(ValueError, match="collision detected"):
            builder.build(graph_dict)

    def test_node_identifier_collision_adjacency_dict_raises(self):
        adj_dict = {
            1: [2],
            "1": [3],
        }
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        with pytest.raises(ValueError, match="collision detected"):
            builder.build(adj_dict)

    def test_louvain_multi_resolution_list(self):
        g = nx.karate_club_graph()
        builder = CommunityHierarchyBuilder(
            algorithm="louvain",
            resolution=[3.0, 1.0, 0.3],
            seed=42,
        )
        hierarchy = builder.build(g)
        assert len(hierarchy.levels) >= 1
        assert hierarchy.metadata.get("algorithm") == "louvain"
        assert hierarchy.metadata.get("fallback") is False

    def test_custom_method_receives_resolution_and_seed(self):
        captured_kwargs = {}

        def dummy_custom(graph, **kwargs):
            captured_kwargs.update(kwargs)
            return CommunityHierarchy(communities={}, graph=graph)

        method_registry.register(
            "community_hierarchy", "test_custom_method_args", dummy_custom
        )

        g = nx.path_graph(3)
        res = build_community_hierarchy(
            g,
            method="test_custom_method_args",
            resolution=2.75,
            seed=999,
        )
        assert isinstance(res, CommunityHierarchy)
        assert captured_kwargs.get("resolution") == 2.75
        assert captured_kwargs.get("seed") == 999

    def test_hierarchy_metadata_to_dict_and_from_dict(self):
        c0 = HierarchicalCommunity(
            id="c_0_0", level=0, index=0, entity_ids=["a", "b"]
        )
        hierarchy = CommunityHierarchy(
            [c0], metadata={"algorithm": "leiden", "fallback": False}
        )
        d = hierarchy.to_dict()
        assert d["metadata"] == {"algorithm": "leiden", "fallback": False}
        restored = CommunityHierarchy.from_dict(d)
        assert restored.metadata == {"algorithm": "leiden", "fallback": False}

    def test_canonicalize_edges_idempotency_and_no_nested_attributes(self):
        from semantica.kg.community_hierarchy import canonicalize_edges

        raw = [("a", "b", {"weight": 2.5, "label": "FRIEND"})]
        c1 = canonicalize_edges(raw)
        c2 = canonicalize_edges(c1)
        c3 = canonicalize_edges(c2)

        assert c1 == c2 == c3
        assert "attributes" in c1[0]
        assert "attributes" not in c1[0]["attributes"]
        assert c1[0]["attributes"]["weight"] == 2.5
        assert c1[0]["attributes"]["label"] == "FRIEND"

    def test_directed_edge_endpoints_orientation_preserved(self):
        g = nx.DiGraph()
        nx.add_cycle(g, ["z", "a", "b"])

        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)
        h = builder.build(g)
        c = h.get_community_for_node("z", level=0)
        assert c is not None
        assert c.directed is True

        edge_pairs = [(e["source"], e["target"]) for e in c.edges]
        assert ("z", "a") in edge_pairs
        assert ("a", "b") in edge_pairs
        assert ("b", "z") in edge_pairs
        assert ("a", "z") not in edge_pairs

        d = c.to_dict()
        assert d["directed"] is True
        c_restored = HierarchicalCommunity.from_dict(d)
        assert c_restored.edges == c.edges
        assert c_restored.directed is True

    def test_node_collision_in_relationships_without_entities_raises(self):
        g = {
            "relationships": [
                {"source": 1, "target": 2},
                {"source": "1", "target": 3},
            ]
        }
        builder = CommunityHierarchyBuilder(seed=42)
        with pytest.raises(ValueError, match="collision detected"):
            builder.build(g)

    def test_node_collision_in_adjacency_neighbors_raises(self):
        adj = {1: [2], 3: ["2"]}
        builder = CommunityHierarchyBuilder(seed=42)
        with pytest.raises(ValueError, match="collision detected"):
            builder.build(adj)

    def test_builder_fallback_flag_resets_on_subsequent_builds(self):
        builder = CommunityHierarchyBuilder(algorithm="louvain", seed=42)

        g_fail = nx.Graph()
        g_fail.add_edge("a", "b", weight=0.0)
        h1 = builder.build(g_fail)
        assert h1.metadata.get("fallback") is True

        g_ok = nx.karate_club_graph()
        h2 = builder.build(g_ok)
        assert h2.metadata.get("fallback") is False

    def test_custom_weight_attribute_name_preserved(self):
        g = nx.Graph()
        g.add_edge("a", "b", score=10.0)
        g.add_edge("b", "c", score=10.0)
        g.add_edge("a", "c", score=10.0)
        g.add_edge("c", "d", score=0.1)
        g.add_edge("d", "e", score=10.0)
        g.add_edge("e", "f", score=10.0)
        g.add_edge("d", "f", score=10.0)

        builder = CommunityHierarchyBuilder(
            algorithm="louvain", weight="score", seed=42
        )
        h = builder.build(g)
        c0 = h.get_community_for_node("a", level=0)
        assert c0 is not None
        assert all("score" in e["attributes"] for e in c0.edges)
        assert all("weight" not in e["attributes"] for e in c0.edges)
