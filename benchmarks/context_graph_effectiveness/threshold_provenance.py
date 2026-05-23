from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

ThresholdSource = dict[str, str]

THRESHOLD_SOURCE_REGISTRY: dict[str, ThresholdSource] = {
    "internal_decision_eval_2026": {
        "source_id": "internal_decision_eval_2026",
        "title": "Semantica internal decision-quality evaluation notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-DECISION-2026",
        "url": "https://example.invalid/semantica/internal/decision-eval-2026",
        "note": "Applies to decision lift, hallucination, citation groundedness, policy compliance, skill activation, and SES composite thresholds.",
    },
    "retrieval_benchmark_suite": {
        "source_id": "retrieval_benchmark_suite",
        "title": "Semantica retrieval benchmark suite notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-RETRIEVAL-2026",
        "url": "https://example.invalid/semantica/internal/retrieval-suite-2026",
        "note": "Applies to direct lookup, multi-hop retrieval, and decision precedent ranking thresholds.",
    },
    "temporal_validity_suite": {
        "source_id": "temporal_validity_suite",
        "title": "Semantica temporal validity benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-TEMPORAL-2026",
        "url": "https://example.invalid/semantica/internal/temporal-suite-2026",
        "note": "Applies to stale/future context injection and temporal precision/recall thresholds.",
    },
    "causal_reasoning_suite": {
        "source_id": "causal_reasoning_suite",
        "title": "Semantica causal reasoning benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-CAUSAL-2026",
        "url": "https://example.invalid/semantica/internal/causal-suite-2026",
        "note": "Applies to causal chain quality and abductive/deductive reasoning thresholds.",
    },
    "kg_algorithms_suite": {
        "source_id": "kg_algorithms_suite",
        "title": "Semantica graph algorithm benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-KG-ALG-2026",
        "url": "https://example.invalid/semantica/internal/kg-algorithms-2026",
        "note": "Applies to community detection and link prediction thresholds.",
    },
    "reasoning_quality_suite": {
        "source_id": "reasoning_quality_suite",
        "title": "Semantica reasoning-quality benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-REASONING-2026",
        "url": "https://example.invalid/semantica/internal/reasoning-suite-2026",
        "note": "Applies to explanation, rete, and Allen interval thresholds.",
    },
    "w3c_prov_o": {
        "source_id": "w3c_prov_o",
        "title": "W3C PROV-O Recommendation",
        "citation_type": "spec",
        "identifier": "W3C PROV-O",
        "url": "https://www.w3.org/TR/prov-o/",
        "note": "Applies to provenance integrity thresholds.",
    },
    "conflict_resolution_suite": {
        "source_id": "conflict_resolution_suite",
        "title": "Semantica conflict-resolution benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-CONFLICT-2026",
        "url": "https://example.invalid/semantica/internal/conflict-suite-2026",
        "note": "Applies to conflict detection thresholds.",
    },
    "deepmatcher_dblp_acm": {
        "source_id": "deepmatcher_dblp_acm",
        "title": "DeepMatcher DBLP-ACM benchmark",
        "citation_type": "paper",
        "identifier": "10.1145/3183713.3196926",
        "url": "https://dl.acm.org/doi/10.1145/3183713.3196926",
        "note": "Applies to deduplication recall, precision, and F1 thresholds.",
    },
    "embedding_quality_suite": {
        "source_id": "embedding_quality_suite",
        "title": "Semantica embedding-quality benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-EMBEDDING-2026",
        "url": "https://example.invalid/semantica/internal/embedding-suite-2026",
        "note": "Applies to embedding quality thresholds.",
    },
    "change_management_suite": {
        "source_id": "change_management_suite",
        "title": "Semantica change-management benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-CHANGE-2026",
        "url": "https://example.invalid/semantica/internal/change-suite-2026",
        "note": "Applies to snapshot fidelity, version diff correctness, and governance impact thresholds.",
    },
    "semantic_extraction_suite": {
        "source_id": "semantic_extraction_suite",
        "title": "Semantica semantic-extraction benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-EXTRACT-2026",
        "url": "https://example.invalid/semantica/internal/semantic-extraction-2026",
        "note": "Applies to NER, relation extraction, event detection, and triplet accuracy thresholds.",
    },
    "context_quality_suite": {
        "source_id": "context_quality_suite",
        "title": "Semantica context-quality benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-CONTEXT-2026",
        "url": "https://example.invalid/semantica/internal/context-suite-2026",
        "note": "Applies to context relevance, noise, signal, and redundancy thresholds.",
    },
    "graph_integrity_suite": {
        "source_id": "graph_integrity_suite",
        "title": "Semantica graph-structural integrity benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-GRAPH-2026",
        "url": "https://example.invalid/semantica/internal/graph-integrity-2026",
        "note": "Applies to graph triple retrieval and relation coverage thresholds.",
    },
    "hotpotqa_benchmark_suite": {
        "source_id": "hotpotqa_benchmark_suite",
        "title": "HotpotQA / multi-hop benchmark notes",
        "citation_type": "benchmark",
        "identifier": "HotpotQA",
        "url": "https://hotpotqa.github.io/",
        "note": "Applies to extended multi-hop recall thresholds.",
    },
    "entity_linking_suite": {
        "source_id": "entity_linking_suite",
        "title": "Semantica entity-linking benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-ENTITY-2026",
        "url": "https://example.invalid/semantica/internal/entity-linking-2026",
        "note": "Applies to entity linking and validator false-positive thresholds.",
    },
    "semantic_layer_exactness_suite": {
        "source_id": "semantic_layer_exactness_suite",
        "title": "dbt semantic layer evaluation notes",
        "citation_type": "paper",
        "identifier": "dbt semantic layer 2025",
        "url": "https://docs.getdbt.com/docs/build/metricflow",
        "note": "Applies to semantic metric exactness and semantic layer coverage thresholds.",
    },
    "metric_graph_hybrid_suite": {
        "source_id": "metric_graph_hybrid_suite",
        "title": "Semantica metric-graph hybrid benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-HYBRID-2026",
        "url": "https://example.invalid/semantica/internal/metric-graph-hybrid-2026",
        "note": "Applies to hybrid reasoning thresholds.",
    },
    "governance_impact_suite": {
        "source_id": "governance_impact_suite",
        "title": "Semantica governance-impact benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-GOV-2026",
        "url": "https://example.invalid/semantica/internal/governance-impact-2026",
        "note": "Applies to decision drift, change coverage, and impact precision thresholds.",
    },
    "agentic_consistency_suite": {
        "source_id": "agentic_consistency_suite",
        "title": "Semantica agentic consistency benchmark notes",
        "citation_type": "internal_measurement",
        "identifier": "SEM-INT-AGENTIC-2026",
        "url": "https://example.invalid/semantica/internal/agentic-consistency-2026",
        "note": "Applies to cross-turn consistency, threshold stability, update detection, decision consistency, and trace buildability thresholds.",
    },
}

THRESHOLD_PROVENANCE: dict[str, str] = {
    "decision_accuracy_delta": "internal_decision_eval_2026",
    "hallucination_rate_delta": "internal_decision_eval_2026",
    "citation_groundedness": "internal_decision_eval_2026",
    "policy_compliance_rate": "internal_decision_eval_2026",
    "direct_lookup_hit_rate": "retrieval_benchmark_suite",
    "multi_hop_recall_2hop": "retrieval_benchmark_suite",
    "multi_hop_recall_3hop": "retrieval_benchmark_suite",
    "decision_precedent_mrr": "retrieval_benchmark_suite",
    "stale_context_injection_rate": "temporal_validity_suite",
    "future_context_injection_rate": "temporal_validity_suite",
    "temporal_precision": "temporal_validity_suite",
    "temporal_recall": "temporal_validity_suite",
    "temporal_rewriter_accuracy": "temporal_validity_suite",
    "causal_chain_recall": "causal_reasoning_suite",
    "causal_chain_precision": "causal_reasoning_suite",
    "policy_compliance_hit_rate": "internal_decision_eval_2026",
    "community_nmi": "kg_algorithms_suite",
    "link_predictor_auc": "kg_algorithms_suite",
    "explanation_completeness": "reasoning_quality_suite",
    "rete_inference_precision": "reasoning_quality_suite",
    "allen_interval_accuracy": "reasoning_quality_suite",
    "provenance_lineage_completeness": "w3c_prov_o",
    "checksum_integrity": "w3c_prov_o",
    "conflict_detection_recall": "conflict_resolution_suite",
    "conflict_detection_precision": "conflict_resolution_suite",
    "duplicate_detection_recall": "deepmatcher_dblp_acm",
    "duplicate_detection_precision": "deepmatcher_dblp_acm",
    "duplicate_detection_f1": "deepmatcher_dblp_acm",
    "semantic_coherence_delta": "embedding_quality_suite",
    "hash_fallback_stability": "embedding_quality_suite",
    "snapshot_fidelity": "change_management_suite",
    "version_diff_correctness": "change_management_suite",
    "skill_activation_rate": "internal_decision_eval_2026",
    "ner_f1": "semantic_extraction_suite",
    "relation_extraction_f1": "semantic_extraction_suite",
    "event_detection_recall": "semantic_extraction_suite",
    "kg_triplet_accuracy": "semantic_extraction_suite",
    "context_relevance_score": "context_quality_suite",
    "context_noise_ratio": "context_quality_suite",
    "signal_to_context_ratio": "context_quality_suite",
    "redundancy_score": "context_quality_suite",
    "graph_triple_retrieval_rate": "graph_integrity_suite",
    "graph_relation_type_coverage": "graph_integrity_suite",
    "multi_hop_recall_4hop": "hotpotqa_benchmark_suite",
    "hotpotqa_bridge_recall": "hotpotqa_benchmark_suite",
    "hotpotqa_comparison_recall": "hotpotqa_benchmark_suite",
    "abductive_cause_accuracy": "causal_reasoning_suite",
    "abductive_effect_accuracy": "causal_reasoning_suite",
    "deductive_chain_recall": "causal_reasoning_suite",
    "entity_linker_precision": "entity_linking_suite",
    "entity_linker_recall": "entity_linking_suite",
    "graph_validator_false_positive_rate": "entity_linking_suite",
    "ses_composite": "semantic_layer_exactness_suite",
    "ses_domain_minimum": "semantic_layer_exactness_suite",
    "metric_exactness_at_1": "semantic_layer_exactness_suite",
    "dimension_conformance_rate": "semantic_layer_exactness_suite",
    "metric_alias_resolution_rate": "semantic_layer_exactness_suite",
    "metric_node_storage_fidelity": "semantic_layer_exactness_suite",
    "semantic_layer_coverage": "semantic_layer_exactness_suite",
    "hybrid_recall": "metric_graph_hybrid_suite",
    "policy_metric_compliance": "metric_graph_hybrid_suite",
    "causal_root_accuracy": "metric_graph_hybrid_suite",
    "metric_policy_linkage_rate": "metric_graph_hybrid_suite",
    "hybrid_graph_coverage": "metric_graph_hybrid_suite",
    "metric_change_impact_score": "governance_impact_suite",
    "decision_drift_rate": "governance_impact_suite",
    "change_type_coverage": "governance_impact_suite",
    "impact_precision": "governance_impact_suite",
    "cross_turn_metric_consistency": "agentic_consistency_suite",
    "threshold_stability_rate": "agentic_consistency_suite",
    "explicit_update_detection_rate": "agentic_consistency_suite",
    "decision_consistency_rate": "agentic_consistency_suite",
    "trace_buildability_rate": "agentic_consistency_suite",
}

_SOURCE_REQUIRED_FIELDS = ("source_id", "title", "citation_type", "identifier", "url", "note")


def _validate_source_record(source: Mapping[str, Any], *, source_id: str) -> None:
    missing = [field for field in _SOURCE_REQUIRED_FIELDS if field not in source]
    if missing:
        raise KeyError(f"threshold source '{source_id}' is missing fields: {', '.join(missing)}")

    for field in _SOURCE_REQUIRED_FIELDS:
        value = source[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"threshold source '{source_id}' field '{field}' must be a non-empty string")

    if source["source_id"] != source_id:
        raise ValueError(
            f"threshold source '{source_id}' has mismatched source_id '{source['source_id']}'"
        )


def get_threshold_source_id(threshold_name: str) -> str:
    try:
        return THRESHOLD_PROVENANCE[threshold_name]
    except KeyError as exc:
        raise KeyError(f"Unknown threshold provenance key: {threshold_name}") from exc


def get_threshold_source(threshold_name: str) -> ThresholdSource:
    source_id = get_threshold_source_id(threshold_name)
    try:
        source = THRESHOLD_SOURCE_REGISTRY[source_id]
    except KeyError as exc:
        raise KeyError(
            f"threshold provenance source '{source_id}' is missing for '{threshold_name}'"
        ) from exc

    _validate_source_record(source, source_id=source_id)
    return source


def iter_threshold_provenance() -> Iterator[tuple[str, str, ThresholdSource]]:
    for threshold_name in sorted(THRESHOLD_PROVENANCE):
        yield threshold_name, get_threshold_source_id(threshold_name), get_threshold_source(threshold_name)


def iter_threshold_sources() -> Iterator[ThresholdSource]:
    for source_id in sorted(THRESHOLD_SOURCE_REGISTRY):
        source = THRESHOLD_SOURCE_REGISTRY[source_id]
        _validate_source_record(source, source_id=source_id)
        yield source
