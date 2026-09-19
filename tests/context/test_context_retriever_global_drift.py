"""
Integration tests for ContextRetriever global, drift, and hybrid modes (PR #3).
"""

from unittest.mock import MagicMock

import pytest

from semantica.context.context_retriever import ContextRetriever, RetrievedContext
from semantica.context.drift_search import DriftSearchResult
from semantica.context.global_retriever import GlobalSearchResult
from semantica.kg.community_summarizer import CommunityReport


class TestContextRetrieverGlobalDrift:
    """Tests for ContextRetriever mode dispatch and convenience methods."""

    def _sample_reports(self):
        return [
            CommunityReport(
                community_id="c_1",
                level=0,
                title="Distributed Systems",
                summary="Consensus algorithms, Raft, and Paxos.",
                findings=[{"summary": "Raft is leader-based"}],
                member_entities=["Raft", "Paxos", "Leader"],
            )
        ]

    def _sample_graph(self):
        return {
            "nodes": [{"id": "Raft"}, {"id": "Paxos"}],
            "edges": [
                {
                    "source": "Raft",
                    "target": "Paxos",
                    "relation": "EQUIVALENT_CONSENSUS",
                    "description": "Both achieve distributed consensus",
                }
            ],
        }

    def test_backward_compatibility_default_local_mode(self):
        # Mock vector store
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"content": "Local vector memory", "score": 0.9, "metadata": {}}
        ]

        retriever = ContextRetriever(vector_store=mock_vs)
        # Calling retrieve without specifying mode defaults to local
        results = retriever.retrieve("distributed systems", max_results=2)
        assert len(results) >= 1
        assert isinstance(results[0], RetrievedContext)
        mock_vs.search.assert_called_once()

    def test_mode_global_delegation(self):
        reports = self._sample_reports()
        retriever = ContextRetriever(community_reports=reports)

        contexts = retriever.retrieve(
            "consensus algorithms",
            mode="global",
            max_results=3,
        )
        assert len(contexts) >= 1
        assert isinstance(contexts[0], RetrievedContext)
        assert contexts[0].source == "global_search"

    def test_mode_drift_delegation(self):
        reports = self._sample_reports()
        graph = self._sample_graph()
        retriever = ContextRetriever(
            community_reports=reports,
            knowledge_graph=graph,
        )

        contexts = retriever.retrieve(
            "Raft consensus",
            mode="drift",
            max_results=3,
        )
        assert len(contexts) >= 1
        assert isinstance(contexts[0], RetrievedContext)
        assert contexts[0].source == "drift_search"

    def test_mode_hybrid_delegation(self):
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            {"content": "Local vector text", "score": 0.85, "metadata": {}}
        ]
        reports = self._sample_reports()

        retriever = ContextRetriever(
            vector_store=mock_vs,
            community_reports=reports,
        )

        contexts = retriever.retrieve(
            "consensus algorithms",
            mode="hybrid",
            max_results=4,
        )
        assert len(contexts) >= 1
        sources = {c.source for c in contexts}
        assert any("vector" in s or "global" in s for s in sources)

    def test_unsupported_mode_raises_value_error(self):
        retriever = ContextRetriever()
        with pytest.raises(ValueError, match="Unsupported retrieval mode"):
            retriever.retrieve("test query", mode="quantum_teleportation")

    def test_retrieve_global_convenience_method(self):
        reports = self._sample_reports()
        retriever = ContextRetriever(community_reports=reports)

        # Default returns GlobalSearchResult object
        res_obj = retriever.retrieve_global("distributed consensus")
        assert isinstance(res_obj, GlobalSearchResult)
        assert len(res_obj.community_reports_used) >= 1

        # as_contexts=True returns List[RetrievedContext]
        contexts = retriever.retrieve_global(
            "distributed consensus", as_contexts=True, max_results=2
        )
        assert isinstance(contexts, list)
        assert len(contexts) >= 1
        assert isinstance(contexts[0], RetrievedContext)

    def test_retrieve_drift_convenience_method(self):
        reports = self._sample_reports()
        graph = self._sample_graph()
        retriever = ContextRetriever(
            community_reports=reports,
            knowledge_graph=graph,
        )

        # Default returns DriftSearchResult object
        res_obj = retriever.retrieve_drift("Raft Paxos")
        assert isinstance(res_obj, DriftSearchResult)
        assert res_obj.depth_reached >= 1

        # as_contexts=True returns List[RetrievedContext]
        contexts = retriever.retrieve_drift(
            "Raft Paxos", as_contexts=True, max_results=2
        )
        assert isinstance(contexts, list)
        assert len(contexts) >= 1
        assert isinstance(contexts[0], RetrievedContext)

    def test_options_override_init_parameters(self):
        init_reports = self._sample_reports()
        override_report = [
            CommunityReport(
                community_id="c_override",
                level=0,
                title="Override Community",
                summary="Overridden content",
            )
        ]

        retriever = ContextRetriever(community_reports=init_reports)
        res = retriever.retrieve_global(
            "test",
            community_reports=override_report,
        )
        assert "c_override" in res.community_reports_used

    def test_missing_reports_graceful_handling(self):
        retriever = ContextRetriever()
        res = retriever.retrieve_global("anything")
        assert isinstance(res, GlobalSearchResult)
        assert res.key_points == []
        assert "No community reports" in res.response

    def test_options_override_reports_and_graph_alias(self):
        retriever = ContextRetriever()
        reports = self._sample_reports()
        graph = self._sample_graph()

        res_global = retriever.retrieve_global("test", reports=reports)
        assert isinstance(res_global, GlobalSearchResult)
        assert "c_1" in res_global.community_reports_used

        res_drift = retriever.retrieve_drift("test", reports=reports, graph=graph)
        assert isinstance(res_drift, DriftSearchResult)
        assert "c_1" in res_drift.global_reports_used
