"""
Tests for functional methods and registries in semantica.context (PR #3).
"""

from semantica.context import (
    DriftSearchResult,
    GlobalSearchResult,
    MethodRegistry,
    drift_search,
    global_search,
    method_registry,
    retrieve_context,
    retrieve_drift,
    retrieve_global,
)
from semantica.context.context_retriever import RetrievedContext
from semantica.kg.community_summarizer import CommunityReport
from semantica.kg.registry import (
    algorithm_registry as kg_alg_registry,
    method_registry as kg_method_registry,
)


class TestContextMethodsAndRegistry:
    """Tests for context module functional methods and registry dispatch."""

    def _sample_report(self):
        return [
            CommunityReport(
                community_id="c_test",
                level=0,
                title="Testing Community",
                summary="Methods and registry validation summary.",
            )
        ]

    def test_retrieve_global_functional(self):
        res = retrieve_global("test query", reports=self._sample_report())
        assert isinstance(res, GlobalSearchResult)
        assert "c_test" in res.community_reports_used

        # Verify alias
        res_alias = global_search("test query", reports=self._sample_report())
        assert isinstance(res_alias, GlobalSearchResult)

    def test_retrieve_drift_functional(self):
        graph = {
            "nodes": [{"id": "NodeA"}, {"id": "NodeB"}],
            "edges": [{"source": "NodeA", "target": "NodeB", "relation": "TEST_REL"}],
        }
        res = retrieve_drift(
            "NodeA NodeB",
            knowledge_graph=graph,
            reports=self._sample_report(),
        )
        assert isinstance(res, DriftSearchResult)

        # Verify alias
        res_alias = drift_search(
            "NodeA NodeB",
            knowledge_graph=graph,
            reports=self._sample_report(),
        )
        assert isinstance(res_alias, DriftSearchResult)

    def test_retrieve_context_functional(self):
        contexts = retrieve_context(
            "test query",
            community_reports=self._sample_report(),
            mode="global",
            max_results=2,
        )
        assert isinstance(contexts, list)
        assert len(contexts) >= 1
        assert isinstance(contexts[0], RetrievedContext)

    def test_context_method_registry_lifecycle(self):
        reg = MethodRegistry()
        dummy_func = lambda q: f"Result for {q}"  # noqa: E731

        reg.register(
            "custom_task",
            "custom_algo",
            dummy_func,
            metadata={"version": "1.0"},
            capabilities=["fast", "accurate"],
        )

        assert reg.get("custom_task", "custom_algo") is dummy_func
        assert reg.has_capability("custom_task", "custom_algo", "fast")
        assert not reg.has_capability("custom_task", "custom_algo", "slow")
        meta = reg.get_metadata("custom_task", "custom_algo")
        assert meta["version"] == "1.0"

        all_methods = reg.list_all("custom_task")
        assert "custom_algo" in all_methods["custom_task"]

        # Unregister
        assert reg.unregister("custom_task", "custom_algo") is True
        assert reg.get("custom_task", "custom_algo") is None
        assert reg.unregister("custom_task", "custom_algo") is False

    def test_pre_registered_methods_in_context_registry(self):
        global_func = method_registry.get("retrieval", "global")
        assert global_func is not None
        assert global_func is retrieve_global

        drift_func = method_registry.get("retrieval", "drift")
        assert drift_func is not None
        assert drift_func is retrieve_drift

        context_func = method_registry.get("retrieval", "context")
        assert context_func is not None
        assert context_func is retrieve_context

    def test_cross_registration_in_kg_registries(self):
        # Verify registered in kg method_registry
        kg_global = kg_method_registry.get("global_retrieval", "default")
        assert kg_global is not None
        res = kg_global("test", reports=self._sample_report())
        assert isinstance(res, GlobalSearchResult)

        kg_drift = kg_method_registry.get("drift_search", "default")
        assert kg_drift is not None

        # Verify registered in kg algorithm_registry
        alg_global = kg_alg_registry.get("global_retrieval", "default")
        assert alg_global is None or callable(alg_global)
        caps = kg_alg_registry.get_capabilities("global_retrieval", "default")
        assert "map_reduce" in caps

        drift_caps = kg_alg_registry.get_capabilities("drift_search", "default")
        assert "directed_reasoning" in drift_caps
