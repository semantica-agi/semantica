from __future__ import annotations

import pytest

from benchmarks.context_graph_effectiveness.threshold_provenance import (
    THRESHOLD_PROVENANCE,
    THRESHOLD_SOURCE_REGISTRY,
    get_threshold_source,
    get_threshold_source_id,
)
from benchmarks.context_graph_effectiveness.thresholds import THRESHOLDS


EXPECTED_THRESHOLDS = {
    "decision_accuracy_delta": (">", 0.0),
    "hallucination_rate_delta": (">", 0.0),
    "citation_groundedness": (">=", 0.60),
    "policy_compliance_rate": (">=", 0.80),
    "direct_lookup_hit_rate": (">=", 0.90),
    "multi_hop_recall_2hop": (">=", 0.75),
    "multi_hop_recall_3hop": (">=", 0.65),
    "decision_precedent_mrr": (">=", 0.70),
    "stale_context_injection_rate": ("<", 0.05),
    "future_context_injection_rate": ("<", 0.05),
    "temporal_precision": (">=", 0.90),
    "temporal_recall": (">=", 0.80),
    "temporal_rewriter_accuracy": (">=", 0.85),
    "causal_chain_recall": (">=", 0.80),
    "causal_chain_precision": (">=", 0.85),
    "policy_compliance_hit_rate": (">=", 0.90),
    "community_nmi": (">=", 0.80),
    "link_predictor_auc": (">=", 0.70),
    "explanation_completeness": (">=", 0.90),
    "rete_inference_precision": (">=", 0.95),
    "allen_interval_accuracy": (">=", 1.0),
    "provenance_lineage_completeness": ("==", 1.0),
    "checksum_integrity": ("==", 1.0),
    "conflict_detection_recall": (">=", 0.85),
    "conflict_detection_precision": (">=", 0.90),
    "duplicate_detection_recall": (">=", 0.85),
    "duplicate_detection_precision": (">=", 0.85),
    "duplicate_detection_f1": (">=", 0.85),
    "semantic_coherence_delta": (">", 0.0),
    "hash_fallback_stability": ("==", 1.0),
    "snapshot_fidelity": ("==", 1.0),
    "version_diff_correctness": ("==", 1.0),
    "skill_activation_rate": (">=", 0.70),
    "ner_f1": (">=", 0.60),
    "relation_extraction_f1": (">=", 0.60),
    "event_detection_recall": (">=", 0.65),
    "kg_triplet_accuracy": (">=", 0.70),
    "context_relevance_score": (">=", 0.70),
    "context_noise_ratio": ("<", 0.30),
    "signal_to_context_ratio": (">=", 2.0),
    "redundancy_score": (">=", 0.80),
    "graph_triple_retrieval_rate": (">=", 0.95),
    "graph_relation_type_coverage": (">=", 0.90),
    "multi_hop_recall_4hop": (">=", 0.60),
    "hotpotqa_bridge_recall": (">=", 0.65),
    "hotpotqa_comparison_recall": (">=", 0.70),
    "abductive_cause_accuracy": (">=", 0.60),
    "abductive_effect_accuracy": (">=", 0.55),
    "deductive_chain_recall": (">=", 0.65),
    "entity_linker_precision": (">=", 0.80),
    "entity_linker_recall": (">=", 0.75),
    "graph_validator_false_positive_rate": ("<", 0.05),
    "ses_composite": (">=", 0.72),
    "ses_domain_minimum": (">=", 0.50),
    "metric_exactness_at_1": (">=", 0.85),
    "dimension_conformance_rate": (">=", 0.90),
    "metric_alias_resolution_rate": (">=", 0.80),
    "metric_node_storage_fidelity": ("==", 1.0),
    "semantic_layer_coverage": (">=", 0.90),
    "hybrid_recall": (">=", 0.75),
    "policy_metric_compliance": (">=", 0.85),
    "causal_root_accuracy": (">=", 0.70),
    "metric_policy_linkage_rate": (">=", 0.90),
    "hybrid_graph_coverage": (">=", 0.80),
    "metric_change_impact_score": (">=", 0.95),
    "decision_drift_rate": ("<=", 0.02),
    "change_type_coverage": (">=", 0.80),
    "impact_precision": (">=", 0.85),
    "cross_turn_metric_consistency": (">=", 0.90),
    "threshold_stability_rate": (">=", 0.95),
    "explicit_update_detection_rate": (">=", 0.80),
    "decision_consistency_rate": (">=", 0.85),
    "trace_buildability_rate": ("==", 1.0),
}


def test_every_threshold_key_has_provenance():
    assert set(THRESHOLDS) == set(THRESHOLD_PROVENANCE)


def test_provenance_sources_are_structurally_complete():
    required_fields = {"source_id", "title", "citation_type", "identifier", "url", "note"}

    for source_id, source in THRESHOLD_SOURCE_REGISTRY.items():
        assert required_fields <= set(source)
        assert source["source_id"] == source_id
        for field in required_fields:
            assert isinstance(source[field], str)
            assert source[field].strip()


def test_shared_source_reuse_works_correctly():
    left = get_threshold_source("decision_accuracy_delta")
    right = get_threshold_source("hallucination_rate_delta")

    assert get_threshold_source_id("decision_accuracy_delta") == get_threshold_source_id("hallucination_rate_delta")
    assert left is right


def test_missing_threshold_provenance_fails_deterministically():
    with pytest.raises(KeyError, match="Unknown threshold provenance key"):
        get_threshold_source_id("not_a_threshold")


def test_missing_source_definition_fails_deterministically(monkeypatch):
    monkeypatch.delitem(THRESHOLD_SOURCE_REGISTRY, "internal_decision_eval_2026")

    with pytest.raises(KeyError, match="is missing for 'decision_accuracy_delta'"):
        get_threshold_source("decision_accuracy_delta")


def test_malformed_source_definition_fails_deterministically(monkeypatch):
    monkeypatch.setitem(
        THRESHOLD_SOURCE_REGISTRY,
        "internal_decision_eval_2026",
        {
            "source_id": "internal_decision_eval_2026",
            "title": "Broken source",
            "citation_type": "internal_measurement",
            "identifier": "SEM-INT-DECISION-2026",
            "url": "https://example.invalid/semantica/internal/decision-eval-2026",
        },
    )

    with pytest.raises(KeyError, match="missing fields"):
        get_threshold_source("decision_accuracy_delta")


def test_threshold_values_remain_unchanged():
    assert THRESHOLDS == EXPECTED_THRESHOLDS
