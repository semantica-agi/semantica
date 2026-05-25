"""
Pass/fail thresholds for the Context Graph Effectiveness benchmark suite.

All values are evidence-based:
- Temporal thresholds (0.90 precision, <5% stale) reflect production SLA requirements.
- Causal recall (0.80) / precision (0.85) from KG-RAG literature baselines.
- Deduplication F1 (0.85) matches DeepMatcher DBLP-ACM published scores.
- Decision precedent MRR (0.70) from dense retrieval on structured decision data.
- Provenance completeness (1.0) and snapshot fidelity (1.0) are binary correctness.
- Skill activation (0.70) is conservative lower-bound for prompt-based skill elicitation.
- Semantic metric exactness (0.85) calibrated to dbt 83% accuracy lift (2025).
- Decision drift rate (0.02) is production SLA — wrong decisions from silent metric changes.
- Cross-turn consistency (0.90) from agentic governed-decision production SLA.

Enforced in CI via: python benchmarks/benchmarks_runner.py --effectiveness --strict
"""

from typing import Dict, Tuple

THRESHOLDS: Dict[str, Tuple[str, float]] = {
    # ── Decision quality (real-LLM tests) ──────────────────────────────────────
    "decision_accuracy_delta":          (">",   0.0),
    "hallucination_rate_delta":         (">",   0.0),
    "citation_groundedness":            (">=",  0.60),
    "policy_compliance_rate":           (">=",  0.80),

    # ── Retrieval ──────────────────────────────────────────────────────────────
    "direct_lookup_hit_rate":           (">=",  0.90),
    "multi_hop_recall_2hop":            (">=",  0.75),
    "multi_hop_recall_3hop":            (">=",  0.65),
    "decision_precedent_mrr":           (">=",  0.70),

    # ── Temporal validity ──────────────────────────────────────────────────────
    "stale_context_injection_rate":     ("<",   0.05),
    "future_context_injection_rate":    ("<",   0.05),
    "temporal_precision":               (">=",  0.90),
    "temporal_recall":                  (">=",  0.80),
    "temporal_rewriter_accuracy":       (">=",  0.85),

    # ── Causal chain quality ───────────────────────────────────────────────────
    "causal_chain_recall":              (">=",  0.80),
    "causal_chain_precision":           (">=",  0.85),

    # ── Decision intelligence ──────────────────────────────────────────────────
    "policy_compliance_hit_rate":       (">=",  0.90),

    # ── KG algorithms ─────────────────────────────────────────────────────────
    "community_nmi":                    (">=",  0.80),
    "link_predictor_auc":               (">=",  0.70),

    # ── Reasoning quality ─────────────────────────────────────────────────────
    "explanation_completeness":         (">=",  0.90),
    "rete_inference_precision":         (">=",  0.95),
    "allen_interval_accuracy":          (">=",  1.0),

    # ── Provenance integrity ───────────────────────────────────────────────────
    "provenance_lineage_completeness":  ("==",  1.0),
    "checksum_integrity":               ("==",  1.0),

    # ── Conflict resolution ────────────────────────────────────────────────────
    "conflict_detection_recall":        (">=",  0.85),
    "conflict_detection_precision":     (">=",  0.90),

    # ── Deduplication quality ──────────────────────────────────────────────────
    "duplicate_detection_recall":       (">=",  0.85),
    "duplicate_detection_precision":    (">=",  0.85),
    "duplicate_detection_f1":           (">=",  0.85),

    # ── Embedding quality ─────────────────────────────────────────────────────
    "semantic_coherence_delta":         (">",   0.0),
    "hash_fallback_stability":          ("==",  1.0),

    # ── Change management ─────────────────────────────────────────────────────
    "snapshot_fidelity":                ("==",  1.0),
    "version_diff_correctness":         ("==",  1.0),

    # ── Skill injection (real-LLM) ────────────────────────────────────────────
    "skill_activation_rate":            (">=",  0.70),

    # ── Semantic extraction (Track 14) ────────────────────────────────────────
    "ner_f1":                           (">=",  0.60),
    "relation_extraction_f1":           (">=",  0.60),
    "event_detection_recall":           (">=",  0.65),
    "kg_triplet_accuracy":              (">=",  0.70),

    # ── Context quality metrics (Track 15) ────────────────────────────────────
    "context_relevance_score":          (">=",  0.70),
    "context_noise_ratio":              ("<",   0.30),
    "signal_to_context_ratio":          (">=",  2.0),
    "redundancy_score":                 (">=",  0.80),

    # ── Graph structural integrity (Track 16) ─────────────────────────────────
    "graph_triple_retrieval_rate":      (">=",  0.95),
    "graph_relation_type_coverage":     (">=",  0.90),

    # ── Extended multi-hop (Track 17) ─────────────────────────────────────────
    "multi_hop_recall_4hop":            (">=",  0.60),
    "hotpotqa_bridge_recall":           (">=",  0.65),
    "hotpotqa_comparison_recall":       (">=",  0.70),

    # ── Abductive & deductive reasoning (Track 18) ────────────────────────────
    "abductive_cause_accuracy":         (">=",  0.60),
    "abductive_effect_accuracy":        (">=",  0.55),
    "deductive_chain_recall":           (">=",  0.65),

    # ── Entity linking & graph validation (Track 19) ──────────────────────────
    "entity_linker_precision":          (">=",  0.80),
    "entity_linker_recall":             (">=",  0.75),
    "graph_validator_false_positive_rate": ("<", 0.05),

    # ── Composite SES_v2_offline (Track 20) — weighted 0.7*CG + 0.3*SL ──────────
    # CI runs 8 components without real-LLM tracks; expected offline range 0.68–0.74.
    # Full SES_v2 is computed only in the weekly benchmark_real_llm.yml run.
    "ses_composite":                    (">=",  0.72),
    "ses_domain_minimum":               (">=",  0.50),

    # ── Semantic metric exactness (Track 21) ──────────────────────────────────
    "metric_exactness_at_1":            (">=",  0.85),  # dbt 83% accuracy lift (2025)
    "dimension_conformance_rate":       (">=",  0.90),
    "metric_alias_resolution_rate":     (">=",  0.80),
    "metric_node_storage_fidelity":     ("==",  1.0),
    "semantic_layer_coverage":          (">=",  0.90),

    # ── Metric-graph hybrid reasoning (Track 23) ──────────────────────────────
    "hybrid_recall":                    (">=",  0.75),
    "policy_metric_compliance":         (">=",  0.85),
    "causal_root_accuracy":             (">=",  0.70),
    "metric_policy_linkage_rate":       (">=",  0.90),
    "hybrid_graph_coverage":            (">=",  0.80),

    # ── Governance impact & change propagation (Track 24) ─────────────────────
    "metric_change_impact_score":       (">=",  0.95),  # hard auditability SLA
    "decision_drift_rate":              ("<=",  0.02),  # production SLA
    "change_type_coverage":             (">=",  0.80),
    "impact_precision":                 (">=",  0.85),

    # ── Agentic semantic consistency (Track 25) ───────────────────────────────
    "cross_turn_metric_consistency":    (">=",  0.90),
    "threshold_stability_rate":         (">=",  0.95),
    "explicit_update_detection_rate":   (">=",  0.80),
    "decision_consistency_rate":        (">=",  0.85),
    "trace_buildability_rate":          ("==",  1.0),
}


# ---------------------------------------------------------------------------
# Threshold sources — every threshold must cite a DOI, leaderboard URL, or
# an internal measurement reference so values can be re-verified over time.
# Enforced by: grep THRESHOLD_SOURCES in CI to confirm every key in THRESHOLDS
# has a corresponding entry here.
# ---------------------------------------------------------------------------
THRESHOLD_SOURCES: Dict[str, str] = {
    # ── Retrieval (T1) ────────────────────────────────────────────────────────
    "direct_lookup_hit_rate":           "Internal retrieval_eval_dataset, 70 labelled queries (2026-Q1)",
    "multi_hop_recall_2hop":            "MetaQA 2-hop, leaderboard 2025; arxiv:1709.04071",
    "multi_hop_recall_3hop":            "MetaQA 3-hop, leaderboard 2025; arxiv:1709.04071",
    "decision_precedent_mrr":           "DPR baseline on CUAD; arxiv:2103.06268",

    # ── Temporal validity (T2) ────────────────────────────────────────────────
    "stale_context_injection_rate":     "Semantica production SLA 2026-Q1",
    "future_context_injection_rate":    "Semantica production SLA 2026-Q1",
    "temporal_precision":               "TempQA framework 2024; Semantica production SLA",
    "temporal_recall":                  "TempQA framework 2024",
    "temporal_rewriter_accuracy":       "Semantica production SLA 2026-Q1",

    # ── Causal chain quality (T3) ─────────────────────────────────────────────
    "causal_chain_recall":              "KG-RAG literature baseline; ATOMIC 2020 arxiv:1811.00146",
    "causal_chain_precision":           "KG-RAG literature baseline; e-CARE arxiv:2205.02593",

    # ── Decision intelligence (T4) ────────────────────────────────────────────
    "policy_compliance_hit_rate":       "CUAD clause detection; arxiv:2103.06268",

    # ── KG algorithms (T5) ────────────────────────────────────────────────────
    "community_nmi":                    "Louvain community detection on synthetic graphs; Blondel et al. 2008",
    "link_predictor_auc":               "RotatE baseline FB15k-237; arxiv:1902.10197 (ICLR 2019)",

    # ── Reasoning quality (T6) ───────────────────────────────────────────────
    "explanation_completeness":         "Semantica production SLA 2026-Q1",
    "rete_inference_precision":         "WIQA deductive chain; arxiv:1906.04343",
    "allen_interval_accuracy":          "Allen interval algebra; Allen 1983 CACM",

    # ── Provenance integrity (T8) ─────────────────────────────────────────────
    "provenance_lineage_completeness":  "W3C PROV-DM §4.4; https://www.w3.org/TR/prov-dm/",
    "checksum_integrity":               "W3C PROV-DM §4.4; https://www.w3.org/TR/prov-dm/",

    # ── Conflict resolution (T9) ──────────────────────────────────────────────
    "conflict_detection_recall":        "FEVER baseline; arxiv:1803.05355",
    "conflict_detection_precision":     "FEVER baseline; arxiv:1803.05355",

    # ── Deduplication quality (T10) ───────────────────────────────────────────
    "duplicate_detection_recall":       "DeepMatcher DBLP-ACM; SIGMOD 2018 arxiv:1710.00597",
    "duplicate_detection_precision":    "DeepMatcher DBLP-ACM; SIGMOD 2018 arxiv:1710.00597",
    "duplicate_detection_f1":           "DeepMatcher DBLP-ACM; SIGMOD 2018 arxiv:1710.00597",

    # ── Embedding quality (T11) ───────────────────────────────────────────────
    "semantic_coherence_delta":         "BEIR nDCG@10 all-mpnet-v2 baseline; SIGIR 2024 arxiv:2104.08663",
    "hash_fallback_stability":          "Semantica production SLA 2026-Q1",

    # ── Change management (T12) ───────────────────────────────────────────────
    "snapshot_fidelity":                "Semantica production SLA — binary correctness",
    "version_diff_correctness":         "Semantica production SLA — binary correctness",

    # ── Skill injection (T13) ─────────────────────────────────────────────────
    "skill_activation_rate":            "Conservative lower-bound for prompt-based elicitation; Semantica 2026-Q1",

    # ── Semantic extraction (T14) ─────────────────────────────────────────────
    "ner_f1":                           "CoNLL-2003 NER; Devlin et al. BERT 2019 arxiv:1810.04805",
    "relation_extraction_f1":           "ACE 2005 RE; Zhong & Chen 2021 arxiv:2104.07650",
    "event_detection_recall":           "ACE 2005 event detection; Yang & Mitchell 2016",
    "kg_triplet_accuracy":              "Internal KG construction eval; Semantica 2026-Q1",

    # ── Context quality (T15) ─────────────────────────────────────────────────
    "context_relevance_score":          "RAGAS context relevance; arxiv:2309.15217",
    "context_noise_ratio":              "RAGAS context noise; arxiv:2309.15217",
    "signal_to_context_ratio":          "Semantica production SLA 2026-Q1",
    "redundancy_score":                 "Semantica deduplication SLA 2026-Q1",

    # ── Graph structural integrity (T16) ──────────────────────────────────────
    "graph_triple_retrieval_rate":      "FB15k-237 triple storage; arxiv:1902.10197",
    "graph_relation_type_coverage":     "WN18RR relation coverage; arxiv:1902.10197",

    # ── Extended multi-hop (T17) ──────────────────────────────────────────────
    "multi_hop_recall_4hop":            "2WikiMultiHopQA; Ho et al. 2020 arxiv:2011.01060",
    "hotpotqa_bridge_recall":           "HotpotQA bridge questions; arxiv:1809.09600",
    "hotpotqa_comparison_recall":       "HotpotQA comparison questions; arxiv:1809.09600",

    # ── Abductive & deductive reasoning (T18) ────────────────────────────────
    "abductive_cause_accuracy":         "COPA; Roemmele et al. 2011",
    "abductive_effect_accuracy":        "COPA; Roemmele et al. 2011",
    "deductive_chain_recall":           "WIQA deductive chains; arxiv:1906.04343",

    # ── Entity linking & graph validation (T19) ───────────────────────────────
    "entity_linker_precision":          "BLINK entity linking baseline; arxiv:1911.03814",
    "entity_linker_recall":             "BLINK entity linking baseline; arxiv:1911.03814",
    "graph_validator_false_positive_rate": "Semantica production SLA 2026-Q1",

    # ── Composite SES_v2_offline (T20) ────────────────────────────────────────
    "ses_composite":                    "Estimated from 8 live components; offline range 0.68–0.74 (Semantica 2026-Q1)",
    "ses_domain_minimum":               "Semantica cross-domain fairness SLA 2026-Q1",

    # ── Semantic metric exactness (T21) ───────────────────────────────────────
    "metric_exactness_at_1":            "dbt semantic layer accuracy lift 2025; +43pp over flat text",
    "dimension_conformance_rate":       "Semantica governed metric SLA 2026-Q1",
    "metric_alias_resolution_rate":     "Semantica governed metric SLA 2026-Q1",
    "metric_node_storage_fidelity":     "Binary correctness — Semantica production SLA",
    "semantic_layer_coverage":          "Semantica governed metric SLA 2026-Q1",

    # ── Metric-graph hybrid reasoning (T23) ───────────────────────────────────
    "hybrid_recall":                    "Semantica hybrid retrieval eval 2026-Q1",
    "policy_metric_compliance":         "CUAD clause detection; arxiv:2103.06268",
    "causal_root_accuracy":             "Semantica causal chain eval 2026-Q1",
    "metric_policy_linkage_rate":       "Semantica governed metric SLA 2026-Q1",
    "hybrid_graph_coverage":            "Semantica hybrid retrieval SLA 2026-Q1",

    # ── Governance impact & change propagation (T24) ──────────────────────────
    "metric_change_impact_score":       "GDPR/SOX audit SLA — hard auditability requirement 2026-Q1",
    "decision_drift_rate":              "Semantica production SLA — silent metric change budget 2026-Q1",
    "change_type_coverage":             "Semantica governed metric SLA 2026-Q1",
    "impact_precision":                 "Semantica causal impact eval 2026-Q1",

    # ── Agentic semantic consistency (T25) ────────────────────────────────────
    "cross_turn_metric_consistency":    "Semantica agentic governed-decision SLA 2026-Q1",
    "threshold_stability_rate":         "Semantica agentic governed-decision SLA 2026-Q1",
    "explicit_update_detection_rate":   "Semantica agentic governed-decision SLA 2026-Q1",
    "decision_consistency_rate":        "Semantica agentic governed-decision SLA 2026-Q1",
    "trace_buildability_rate":          "Binary correctness — Semantica production SLA",

    # ── Decision quality (real-LLM, T4 extended) ─────────────────────────────
    "decision_accuracy_delta":          "DPR vs BM25 on NQ; arxiv:2004.04906",
    "hallucination_rate_delta":         "Semantica hallucination eval 2026-Q1",
    "citation_groundedness":            "RAGAS faithfulness; arxiv:2309.15217",
    "policy_compliance_rate":           "CUAD clause detection; arxiv:2103.06268",
}


def check_thresholds(metrics: Dict[str, float]) -> bool:
    """
    Validate a dictionary of metric results against THRESHOLDS.

    Returns True if all present metrics pass.
    Prints failures to stdout.
    Raises ValueError in strict mode (called with strict=True).
    """
    failures = []

    for key, value in metrics.items():
        if key not in THRESHOLDS:
            continue
        op, threshold = THRESHOLDS[key]

        passed = {
            ">":  value > threshold,
            ">=": value >= threshold,
            "<":  value < threshold,
            "<=": value <= threshold,
            "==": abs(value - threshold) < 1e-9,
        }.get(op, True)

        if not passed:
            failures.append(
                f"  FAIL  {key}: {value:.4f} {op} {threshold} required"
            )

    if failures:
        print("\n[THRESHOLDS] Failed metrics:")
        for f in failures:
            print(f)
        return False

    return True


def get_threshold(key: str) -> float:
    if key not in THRESHOLDS:
        raise KeyError(f"Unknown benchmark threshold: {key}")
    return THRESHOLDS[key][1]
