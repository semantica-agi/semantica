"""
Unit and integration tests for DriftSearchEngine and DRIFT hybrid retrieval (PR #3).
"""

from unittest.mock import MagicMock

from semantica.context.context_retriever import RetrievedContext
from semantica.context.drift_search import (
    DriftFacet,
    DriftFacetSchema,
    DriftFacetsResponseSchema,
    DriftSearchEngine,
    DriftSearchResult,
)
from semantica.kg.community_summarizer import CommunityReport


class TestDriftDataModels:
    """Tests for DriftFacet, schemas, and DriftSearchResult."""

    def test_drift_facet_init_and_clamping(self):
        facet = DriftFacet(
            sub_query="What are the scaling limits?",
            target_entities=["GPU", "TPU", "GPU"],
            rationale="Compute bottleneck",
            depth=1,
            relevance_score=1.5,  # exceeds 1.0
        )
        assert facet.sub_query == "What are the scaling limits?"
        assert facet.relevance_score == 1.0
        assert facet.target_entities == ["GPU", "TPU"]
        assert facet.depth == 1

        # Test negative score clamp
        f_low = DriftFacet(sub_query="q", relevance_score=-0.5)
        assert f_low.relevance_score == 0.0

    def test_drift_facet_to_dict_and_from_dict(self):
        f = DriftFacet(
            sub_query="Query",
            target_entities=["E1"],
            rationale="Rat",
            depth=2,
            relevance_score=0.8,
        )
        d = f.to_dict()
        reconstructed = DriftFacet.from_dict(d)
        assert reconstructed.sub_query == f.sub_query
        assert reconstructed.target_entities == f.target_entities
        assert reconstructed.relevance_score == f.relevance_score

    def test_drift_facet_schemas_validation(self):
        raw = {
            "facets": [
                {
                    "sub_query": "Explore transformer architecture",
                    "target_entities": ["Attention", "FeedForward"],
                    "rationale": "Key mechanisms",
                    "score": 0.95,
                },
                "Direct string facet",
            ]
        }
        schema = DriftFacetsResponseSchema.model_validate(raw)
        assert len(schema.facets) == 2
        assert schema.facets[0].sub_query == "Explore transformer architecture"
        assert schema.facets[0].target_entities == ["Attention", "FeedForward"]
        assert schema.facets[0].relevance_score == 0.95
        assert schema.facets[1].sub_query == "Direct string facet"
        assert schema.facets[1].relevance_score == 1.0

    def test_drift_search_result_to_retrieved_contexts(self):
        result = DriftSearchResult(
            query="Deep learning architectures",
            answer=(
                "Answer: [Community c_1] explains that "
                "(Transformer -[USES]-> Attention)."
            ),
            thematic_framing="Macro context",
            global_reports_used=["c_1"],
            verified_local_contexts=[
                {
                    "source": "Transformer",
                    "target": "Attention",
                    "relation": "USES",
                    "description": "Mechanism for long-range dependencies",
                    "alignment_score": 0.85,
                    "depth": 1,
                    "attributes": {"weight": 1.0},
                }
            ],
            facets_explored=[
                DriftFacet(sub_query="Check Attention", target_entities=["Attention"])
            ],
            depth_reached=1,
            pruned_fact_count=2,
            citations=["[Community c_1]", "(Transformer -[USES]-> Attention)"],
            metrics={"time_taken": 0.25},
        )

        contexts = result.to_retrieved_contexts()
        assert len(contexts) == 2

        # Primary executive context
        primary = contexts[0]
        assert isinstance(primary, RetrievedContext)
        assert primary.score == 1.0
        assert primary.source == "drift_search"
        assert primary.content == result.answer

        # Verified local context
        fact_ctx = contexts[1]
        assert isinstance(fact_ctx, RetrievedContext)
        assert fact_ctx.score == 0.85
        assert "(Transformer) -[USES]-> (Attention)" in fact_ctx.content
        assert len(fact_ctx.related_entities) == 2
        assert fact_ctx.related_relationships[0]["type"] == "USES"

    def test_drift_search_result_to_and_from_dict(self):
        res = DriftSearchResult(
            query="q",
            answer="a",
            thematic_framing="tf",
            global_reports_used=["c0"],
            verified_local_contexts=[{"source": "A", "target": "B", "relation": "R"}],
            facets_explored=[DriftFacet(sub_query="sub")],
            depth_reached=1,
            pruned_fact_count=1,
            citations=["c0"],
            metrics={"time_taken": 0.1},
        )
        d = res.to_dict()
        reconstructed = DriftSearchResult.from_dict(d)
        assert reconstructed.query == "q"
        assert reconstructed.answer == "a"
        assert len(reconstructed.facets_explored) == 1
        assert len(reconstructed.verified_local_contexts) == 1


class TestDriftAdjacencyIndex:
    """Tests for in-memory graph index building across representations."""

    def test_dict_graph_nodes_edges(self):
        graph = {
            "nodes": [{"id": "Python"}, {"id": "Guido"}],
            "edges": [
                {
                    "source": "Python",
                    "target": "Guido",
                    "relation": "CREATED_BY",
                    "description": "Creator",
                }
            ],
        }
        engine = DriftSearchEngine(knowledge_graph=graph)
        assert "Python" in engine._adjacency_index
        assert "Guido" in engine._adjacency_index
        # Verify outgoing and inverse incoming edges
        py_edges = engine._adjacency_index["Python"]
        assert len(py_edges) >= 1
        assert py_edges[0]["target"] == "Guido"

    def test_dict_graph_entities_relationships(self):
        graph = {
            "entities": [{"name": "AI"}, {"name": "ML"}],
            "relationships": [
                {
                    "from": "AI",
                    "to": "ML",
                    "type": "INCLUDES",
                    "desc": "Subfield",
                }
            ],
        }
        engine = DriftSearchEngine(knowledge_graph=graph)
        assert "AI" in engine._adjacency_index
        assert "ML" in engine._adjacency_index
        ai_edges = engine._adjacency_index["AI"]
        assert ai_edges[0]["relation"] == "INCLUDES"

    def test_tuple_and_object_graph(self):
        class MockEdge:
            def __init__(self, src, tgt, rel, desc):
                self.source = src
                self.target = tgt
                self.type = rel
                self.description = desc
                self.attributes = {}

        class MockGraph:
            def __init__(self):
                self.nodes = ["E1", "E2"]
                self.relationships = [MockEdge("E1", "E2", "LINKS", "Edge info")]

        engine = DriftSearchEngine(knowledge_graph=MockGraph())
        assert "E1" in engine._adjacency_index
        assert engine._adjacency_index["E1"][0]["target"] == "E2"


class TestDriftSearchPipeline:
    """Tests for end-to-end DRIFT search pipeline stages."""

    def _sample_graph(self):
        return {
            "nodes": [
                {"id": "Semantica"},
                {"id": "GraphRAG"},
                {"id": "HierarchicalLeiden"},
                {"id": "UnrelatedCooking"},
            ],
            "edges": [
                {
                    "source": "Semantica",
                    "target": "GraphRAG",
                    "relation": "IMPLEMENTS",
                    "description": "High-performance GraphRAG retrieval framework",
                },
                {
                    "source": "GraphRAG",
                    "target": "HierarchicalLeiden",
                    "relation": "USES_COMMUNITIES",
                    "description": "Hierarchical multi-level community clustering",
                },
                {
                    "source": "Semantica",
                    "target": "UnrelatedCooking",
                    "relation": "UNRELATED",
                    "description": "Baking bread and pastries",
                },
            ],
        }

    def _sample_reports(self):
        return [
            CommunityReport(
                community_id="c_graphrag",
                level=0,
                title="GraphRAG Architecture",
                summary=(
                    "Hierarchical knowledge graph retrieval and community detection."
                ),
                findings=[
                    {"summary": "Graph retrieval works well for global reasoning"}
                ],
                member_entities=["Semantica", "GraphRAG"],
            )
        ]

    def test_thematic_framing_stage1(self):
        reports = self._sample_reports()
        engine = DriftSearchEngine(reports=reports, top_k_reports=1)
        framing, rep_ids = engine._extract_thematic_framing("GraphRAG retrieval")
        assert "c_graphrag" in rep_ids
        assert "GraphRAG Architecture" in framing

    def test_directed_facet_generation_stage2(self):
        mock_llm = MagicMock()
        mock_llm.generate_typed.return_value = DriftFacetsResponseSchema(
            facets=[
                DriftFacetSchema(
                    sub_query="How does GraphRAG use Leiden?",
                    target_entities=["GraphRAG"],
                    rationale="Community clustering mechanism",
                    score=0.9,
                )
            ]
        )

        engine = DriftSearchEngine(
            reports=self._sample_reports(),
            knowledge_graph=self._sample_graph(),
            llm=mock_llm,
        )

        facets = engine._generate_facets("GraphRAG query", "thematic framing")
        assert len(facets) == 1
        assert facets[0].sub_query == "How does GraphRAG use Leiden?"
        assert facets[0].target_entities == ["GraphRAG"]

    def test_extractive_facets_fallback_when_no_llm(self):
        engine = DriftSearchEngine(
            reports=self._sample_reports(),
            knowledge_graph=self._sample_graph(),
            llm=None,
        )
        facets = engine._generate_facets("Semantica GraphRAG", "thematic framing")
        assert len(facets) >= 1
        target_ents = [ent for f in facets for ent in f.target_entities]
        assert "Semantica" in target_ents or "GraphRAG" in target_ents

    def test_semantic_drift_pruning_stage4(self):
        # The query and framing are focused on GraphRAG and Semantica.
        # "UnrelatedCooking" should be pruned because its alignment score is low!
        engine = DriftSearchEngine(
            reports=self._sample_reports(),
            knowledge_graph=self._sample_graph(),
            drift_threshold=0.30,
            max_depth=2,
            llm=None,
        )

        facets = [
            DriftFacet(
                sub_query="Explore Semantica",
                target_entities=["Semantica"],
            )
        ]

        verified, depth, pruned = engine._traverse_and_prune(
            facets, "Semantica GraphRAG knowledge graph", "Hierarchical GraphRAG"
        )

        verified_relations = [f["relation"] for f in verified]
        assert "IMPLEMENTS" in verified_relations
        assert "UNRELATED" not in verified_relations
        assert pruned >= 1

    def test_iterative_deepening_stage5(self):
        # 1-hop starting at Semantica finds GraphRAG.
        # 2-hop starting at Semantica extends through GraphRAG to HierarchicalLeiden.
        engine = DriftSearchEngine(
            reports=self._sample_reports(),
            knowledge_graph=self._sample_graph(),
            drift_threshold=0.10,
            max_depth=2,
            llm=None,
        )

        facets = [
            DriftFacet(
                sub_query="Explore Semantica",
                target_entities=["Semantica"],
            )
        ]

        verified, depth, pruned = engine._traverse_and_prune(
            facets,
            "Semantica GraphRAG HierarchicalLeiden community",
            "Knowledge graph framework",
        )

        assert depth == 2
        targets = [f["target"] for f in verified]
        assert "HierarchicalLeiden" in targets

    def test_hybrid_synthesis_stage6_with_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate_typed.return_value = DriftFacetsResponseSchema(
            facets=[
                DriftFacetSchema(
                    sub_query="Investigate GraphRAG",
                    target_entities=["Semantica"],
                )
            ]
        )
        mock_llm.generate.return_value = (
            "Executive summary: [Community c_graphrag] defines the macro model. "
            "Micro evidence confirms (Semantica -[IMPLEMENTS]-> GraphRAG)."
        )

        engine = DriftSearchEngine(
            reports=self._sample_reports(),
            knowledge_graph=self._sample_graph(),
            llm=mock_llm,
        )

        result = engine.search("How does Semantica implement GraphRAG?")
        assert "[Community c_graphrag]" in result.citations
        assert "(Semantica -[IMPLEMENTS]-> GraphRAG)" in result.citations
        assert len(result.verified_local_contexts) >= 1
        assert result.metrics["verified_facts_count"] >= 1

    def test_deterministic_synthesis_without_llm(self):
        engine = DriftSearchEngine(
            reports=self._sample_reports(),
            knowledge_graph=self._sample_graph(),
            llm=None,
            drift_threshold=0.10,
        )

        result = engine.search("Semantica GraphRAG")
        assert "DRIFT Hybrid Response" in result.answer
        assert result.depth_reached >= 1
        assert len(result.global_reports_used) >= 1

    def test_context_graph_and_context_edge_ingestion(self):
        from semantica.context.context_graph import ContextGraph

        cg = ContextGraph()
        cg.add_node("AgentContext", "class", label="Agent Context Engine")
        cg.add_node("MemoryStore", "component", label="Memory Component")
        cg.add_edge(
            "AgentContext",
            "MemoryStore",
            "INTEGRATES_WITH",
            {"description": "Manages conversational memory"},
        )

        engine = DriftSearchEngine(knowledge_graph=cg)
        # Check node info
        assert "AgentContext" in engine._node_meta
        assert engine._node_meta["AgentContext"].get("type") == "class"
        assert not engine._node_meta["AgentContext"]["name"].startswith("ContextNode(")

        # Check edge info
        adj_edges = engine._adjacency_index.get("AgentContext", [])
        assert len(adj_edges) >= 1
        assert adj_edges[0]["relation"] == "INTEGRATES_WITH"
        assert "conversational memory" in adj_edges[0]["description"]

    def test_no_duplicate_inverted_edges_in_traversal(self):
        graph = {
            "nodes": [{"id": "NodeA"}, {"id": "NodeB"}, {"id": "NodeC"}],
            "edges": [
                {
                    "source": "NodeA",
                    "target": "NodeB",
                    "relation": "CONNECTS_TO",
                    "description": "Forward link from A to B",
                },
                {
                    "source": "NodeB",
                    "target": "NodeC",
                    "relation": "DEPENDS_ON",
                    "description": "Forward link from B to C",
                },
            ],
        }
        engine = DriftSearchEngine(
            knowledge_graph=graph,
            max_depth=2,
            drift_threshold=0.0,
        )
        facets = [DriftFacet(sub_query="Explore NodeA", target_entities=["NodeA"])]
        verified, depth, pruned = engine._traverse_and_prune(
            facets, "NodeA NodeB NodeC", "Network framing"
        )

        # Must have NodeA->NodeB and NodeB->NodeC
        relations = [f["relation"] for f in verified]
        assert "CONNECTS_TO" in relations
        assert "DEPENDS_ON" in relations
        # Must NOT have synthetic INVERSE relations or back-edge duplicates
        assert not any("INVERSE" in r for r in relations)
        assert len(verified) == 2

    def test_drift_to_retrieved_contexts_empty_when_no_data(self):
        result = DriftSearchResult(
            query="unknown query",
            answer="No data available.",
            thematic_framing="",
            global_reports_used=[],
            verified_local_contexts=[],
        )
        assert result.to_retrieved_contexts() == []

    def test_extract_json_multi_item_facets_array(self):
        engine = DriftSearchEngine()
        raw_facets = (
            '[\n'
            '  {"sub_query": "Sub 1", "target_entities": ["E1"], "rationale": "R1"},\n'
            '  {"sub_query": "Sub 2", "target_entities": ["E2"], "rationale": "R2"}\n'
            ']'
        )
        parsed = engine._extract_json(raw_facets)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

        resp = engine._coerce_facets_response(parsed)
        assert resp is not None
        assert len(resp.facets) == 2
        assert resp.facets[0].sub_query == "Sub 1"
        assert resp.facets[1].sub_query == "Sub 2"
