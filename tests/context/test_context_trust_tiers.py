"""
Tests for ContextRetriever trust-tiering (issue #1557, phase 2).

Verifies that retrieved facts are graded on evidence quality and that the
resulting tier can be filtered at retrieval time.

Run with: pytest tests/context/test_context_trust_tiers.py
"""
from unittest.mock import MagicMock, patch

import pytest

from semantica.context.context_retriever import ContextRetriever, RetrievedContext
from semantica.context.tiers import TrustTier


def _ctx(content, score=1.0, **meta):
    """Build a RetrievedContext with the given metadata overrides."""
    return RetrievedContext(content=content, score=score, metadata=dict(meta))


# ----------------------------------------------------------------------
# Signal extraction
# ----------------------------------------------------------------------


def test_tier_signals_from_metadata_only():
    retriever = ContextRetriever()
    corr, conf = retriever._tier_signals_for(_ctx("f", confidence=0.9))
    assert corr is None
    assert conf == 0.9


def test_tier_signals_from_corroboration_count_metadata():
    retriever = ContextRetriever()
    corr, conf = retriever._tier_signals_for(
        _ctx("f", confidence=0.9, corroboration_count=3)
    )
    assert corr == 3
    assert conf == 0.9


def test_tier_signals_uses_provenance_manager():
    pm = MagicMock()
    pm.get_all_sources.return_value = [{"src": "a"}, {"src": "b"}]
    retriever = ContextRetriever(provenance_manager=pm)
    corr, conf = retriever._tier_signals_for(
        _ctx("f", node_id="ent_1", confidence=0.9)
    )
    assert corr == 2
    assert conf == 0.9
    pm.get_all_sources.assert_called_once_with("ent_1")


def test_tier_signals_provenance_failure_falls_back_to_metadata():
    pm = MagicMock()
    pm.get_all_sources.side_effect = RuntimeError("store down")
    retriever = ContextRetriever(provenance_manager=pm)
    corr, conf = retriever._tier_signals_for(
        _ctx("f", node_id="ent_1", confidence=0.9, corroboration_count=1)
    )
    assert corr == 1
    assert conf == 0.9


# ----------------------------------------------------------------------
# Attachment
# ----------------------------------------------------------------------


def test_attach_tier_from_confidence_only():
    retriever = ContextRetriever()
    ctx = _ctx("f", confidence=0.9)
    retriever._attach_trust_tiers([ctx])
    assert ctx.metadata["trust_tier"] == TrustTier.BRONZE.value


def test_attach_tier_combines_corroboration_and_confidence():
    retriever = ContextRetriever()
    ctx = _ctx("f", confidence=0.9, corroboration_count=3)
    retriever._attach_trust_tiers([ctx])
    assert ctx.metadata["trust_tier"] == TrustTier.GOLD.value


def test_attach_leaves_unscored_items_untouched():
    retriever = ContextRetriever()
    ctx = _ctx("plain vector chunk")  # no node_id, no confidence
    retriever._attach_trust_tiers([ctx])
    assert "trust_tier" not in ctx.metadata


def test_attach_idempotent():
    retriever = ContextRetriever()
    ctx = _ctx("f", confidence=0.9)
    retriever._attach_trust_tiers([ctx])
    first = ctx.metadata["trust_tier"]
    retriever._attach_trust_tiers([ctx])
    assert ctx.metadata["trust_tier"] == first


def test_attach_grades_graph_fact_without_signals_as_quarantine():
    # A graph fact must always carry a tier: no readable signals degrade to
    # quarantine instead of staying unscored (issue #1557: missing evidence
    # is never trusted as high confidence).
    retriever = ContextRetriever()
    ctx = _ctx("f", node_id="ent_1")
    retriever._attach_trust_tiers([ctx])
    assert ctx.metadata["trust_tier"] == TrustTier.QUARANTINE.value


def test_attach_does_not_mutate_shared_metadata():
    # Retrieved metadata dicts can be shared with the vector store / memory;
    # writing the tier in place would persist a query-time grade into stored
    # state, where it goes stale as sources change.
    retriever = ContextRetriever()
    store_metadata = {"confidence": 0.9}
    ctx = RetrievedContext(content="f", score=1.0, metadata=store_metadata)
    retriever._attach_trust_tiers([ctx])
    assert ctx.metadata["trust_tier"] == TrustTier.BRONZE.value
    assert ctx.metadata is not store_metadata
    assert store_metadata == {"confidence": 0.9}


def test_attach_recomputes_stale_tier():
    # A pre-existing grade is never trusted: it is recomputed from current
    # signals, so a tier cannot outlive the evidence it was derived from.
    retriever = ContextRetriever()
    ctx = _ctx("f", trust_tier="gold", confidence=0.9)  # no corroboration
    retriever._attach_trust_tiers([ctx])
    assert ctx.metadata["trust_tier"] == TrustTier.BRONZE.value


# ----------------------------------------------------------------------
# Filtering
# ----------------------------------------------------------------------


def test_filter_by_tier_basic():
    retriever = ContextRetriever()
    items = [
        _ctx("gold", trust_tier="gold"),
        _ctx("bronze", trust_tier="bronze"),
        _ctx("none"),
    ]
    kept = retriever.filter_by_tier(items, TrustTier.SILVER)
    assert [c.content for c in kept] == ["gold"]


def test_filter_by_tier_include_unscored():
    retriever = ContextRetriever()
    items = [_ctx("gold", trust_tier="gold"), _ctx("none")]
    kept = retriever.filter_by_tier(
        items, TrustTier.SILVER, include_unscored=True
    )
    assert {c.content for c in kept} == {"gold", "none"}


def test_filter_by_tier_rejects_bad_minimum():
    retriever = ContextRetriever()
    with pytest.raises(TypeError):
        retriever.filter_by_tier([_ctx("x", trust_tier="gold")], "gold")


# ----------------------------------------------------------------------
# End-to-end through retrieve()
# ----------------------------------------------------------------------


def test_retrieve_attaches_tiers_and_filters():
    retriever = ContextRetriever()
    fake = [
        _ctx("gold", confidence=0.9, corroboration_count=3),
        _ctx("bronze", confidence=0.9),
        _ctx("low"),  # unscored
    ]
    with patch.object(retriever, "_retrieve_from_vector", return_value=fake):
        results = retriever.retrieve(
            "q", max_results=10, min_trust_tier=TrustTier.SILVER
        )
    # gold meets SILVER; bronze and the unscored item are dropped.
    assert [c.content for c in results] == ["gold"]
    assert results[0].metadata["trust_tier"] == TrustTier.GOLD.value


def test_retrieve_attaches_tiers_without_filter():
    retriever = ContextRetriever()
    fake = [
        _ctx("gold", confidence=0.9, corroboration_count=3),
        _ctx("bronze", confidence=0.9),
        _ctx("low"),
    ]
    with patch.object(retriever, "_retrieve_from_vector", return_value=fake):
        results = retriever.retrieve("q", max_results=10)
    assert len(results) == 3
    by_content = {c.content: c.metadata.get("trust_tier") for c in results}
    assert by_content["gold"] == TrustTier.GOLD.value
    assert by_content["bronze"] == TrustTier.BRONZE.value
    assert by_content["low"] is None  # "low" left unscored


def test_retrieve_global_attaches_tiers():
    retriever = ContextRetriever()
    fake = [_ctx("gold", confidence=0.9, corroboration_count=3)]
    with patch(
        "semantica.context.global_retriever.GlobalGraphRetriever"
    ) as GGR:
        instance = GGR.return_value
        res = MagicMock()
        res.to_retrieved_contexts.return_value = fake
        instance.search.return_value = res
        results = retriever.retrieve_global(
            "q", as_contexts=True, max_results=10
        )
    assert results[0].metadata["trust_tier"] == TrustTier.GOLD.value


# ----------------------------------------------------------------------
# Global / drift modes carry no per-fact signal, so a trust threshold must
# keep summary results rather than empty them (regression guard for #1557).
# ----------------------------------------------------------------------


def test_retrieve_global_keeps_unscored_summaries_with_min_trust_tier():
    retriever = ContextRetriever()
    fake = [_ctx("summary a"), _ctx("summary b")]
    with patch(
        "semantica.context.global_retriever.GlobalGraphRetriever"
    ) as GGR:
        instance = GGR.return_value
        res = MagicMock()
        res.to_retrieved_contexts.return_value = fake
        instance.search.return_value = res
        results = retriever.retrieve_global(
            "q", as_contexts=True, min_trust_tier=TrustTier.SILVER
        )
    # Must not return an empty list just because summaries are unscored.
    assert [c.content for c in results] == ["summary a", "summary b"]


def test_retrieve_global_filters_explicitly_tiered_context():
    retriever = ContextRetriever()
    fake = [
        _ctx("kept", trust_tier="gold"),
        _ctx("dropped", trust_tier="bronze"),
        _ctx("unscored summary"),
    ]
    with patch(
        "semantica.context.global_retriever.GlobalGraphRetriever"
    ) as GGR:
        instance = GGR.return_value
        res = MagicMock()
        res.to_retrieved_contexts.return_value = fake
        instance.search.return_value = res
        results = retriever.retrieve_global(
            "q", as_contexts=True, min_trust_tier=TrustTier.SILVER
        )
    assert {c.content for c in results} == {"kept", "unscored summary"}


def test_retrieve_drift_keeps_unscored_summaries_with_min_trust_tier():
    retriever = ContextRetriever()
    fake = [_ctx("drift summary a"), _ctx("drift summary b")]
    with patch(
        "semantica.context.drift_search.DriftSearchEngine"
    ) as DSE:
        instance = DSE.return_value
        res = MagicMock()
        res.to_retrieved_contexts.return_value = fake
        instance.search.return_value = res
        results = retriever.retrieve_drift(
            "q", as_contexts=True, min_trust_tier=TrustTier.SILVER
        )
    assert [c.content for c in results] == [
        "drift summary a",
        "drift summary b",
    ]


def test_retrieve_hybrid_keeps_global_summaries_with_min_trust_tier():
    # Hybrid merges local facts with structurally unscored global summaries;
    # the threshold must filter each leg with its own semantics, so the
    # summaries survive instead of being stripped from every hybrid response.
    retriever = ContextRetriever()
    local_fake = [_ctx("local gold", confidence=0.9, corroboration_count=3)]
    global_fake = [_ctx("global summary")]
    with patch.object(
        retriever, "_retrieve_from_vector", return_value=local_fake
    ), patch(
        "semantica.context.global_retriever.GlobalGraphRetriever"
    ) as GGR:
        instance = GGR.return_value
        res = MagicMock()
        res.to_retrieved_contexts.return_value = global_fake
        instance.search.return_value = res
        results = retriever.retrieve(
            "q",
            mode="hybrid",
            max_results=10,
            min_trust_tier=TrustTier.SILVER,
        )
    contents = {c.content for c in results}
    assert "local gold" in contents
    assert "global summary" in contents
