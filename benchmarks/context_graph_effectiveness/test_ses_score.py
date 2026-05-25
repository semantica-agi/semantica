from __future__ import annotations

import pytest

from benchmarks.context_graph_effectiveness.reporting import (
    coverage_summary,
    make_track_report,
    require_reportable,
)
from benchmarks.context_graph_effectiveness.thresholds import get_threshold
from benchmarks.context_graph_effectiveness.metrics import normalize_decision_label
from benchmarks.context_graph_effectiveness.test_agentic_consistency import (
    _build_turn_graph,
    _extract_metric_def,
)
from benchmarks.context_graph_effectiveness.test_deduplication_quality import _evaluate_pairs
from benchmarks.context_graph_effectiveness.test_decision_intelligence import (
    _baseline_predict_decision,
    _structured_predict_decision,
)
from benchmarks.context_graph_effectiveness.test_retrieval import _aggregate_metrics
from benchmarks.context_graph_effectiveness.test_semantic_extraction import (
    _entity_span_f1,
    _extract_gold_entities_from_bio,
)
from benchmarks.context_graph_effectiveness.test_semantic_metric_exactness import (
    _flat_text_predict,
    _graph_predict,
    _no_semantic_layer_predict,
)


def _retrieval_component(retrieval_eval_dataset: dict) -> dict:
    measurable = [
        record for record in retrieval_eval_dataset["records"] if record["query_type"] != "no_match"
    ]
    hybrid = _aggregate_metrics(measurable, "hybrid")
    return {
        "metric": hybrid["hit@1"],
        "sample_size": len(measurable),
    }


def _decision_component(decision_dataset: dict) -> dict:
    records = decision_dataset["records"]
    gold = [record["ground_truth_decision"] for record in records]
    baseline = [_baseline_predict_decision(record)[0] for record in records]
    contextual = [_structured_predict_decision(record)[0] for record in records]
    correct = sum(1 for expected, predicted in zip(gold, contextual) if expected.lower() in predicted.lower())
    baseline_correct = sum(1 for expected, predicted in zip(gold, baseline) if expected.lower() in predicted.lower())
    return {
        "metric": correct / len(records),
        "baseline": baseline_correct / len(records),
        "sample_size": len(records),
    }


def _dedup_component(dedup_dblp_acm_dataset: dict) -> dict:
    _, _, f1 = _evaluate_pairs(dedup_dblp_acm_dataset, limit=250)
    return {
        "metric": f1,
        "sample_size": min(len(dedup_dblp_acm_dataset["pairs"]), 250),
    }


def _semantic_metric_component(jaffle_shop_dataset: dict) -> dict:
    metrics = jaffle_shop_dataset["metrics"]
    queries = jaffle_shop_dataset["nl_queries"]
    structured = sum(
        1 for query in queries if _graph_predict(query["query"], metrics) == query["governed_metric"]
    ) / len(queries)
    baseline = sum(
        1 for query in queries if _flat_text_predict(query["query"], metrics) == query["governed_metric"]
    ) / len(queries)
    no_sl = sum(
        1 for query in queries if _no_semantic_layer_predict(query["query"]) == query["governed_metric"]
    ) / len(queries)
    return {
        "metric": structured,
        "baseline": max(baseline, no_sl),
        "sample_size": len(queries),
    }


def _agentic_consistency_component(agentic_traces_dataset: dict, jaffle_shop_dataset: dict) -> dict:
    traces = agentic_traces_dataset["traces"]
    jaffle_metrics = {metric["name"]: metric for metric in jaffle_shop_dataset["metrics"]}
    consistent = 0
    total = 0
    for trace in traces:
        turns = [
            turn for turn in trace["turns"]
            if turn.get("expected_metric") and "updated_expression" not in turn
        ]
        if len(turns) < 2:
            continue
        metric_name = turns[0]["expected_metric"]
        base_def = jaffle_metrics.get(metric_name, {})
        expressions = [
            _extract_metric_def(_build_turn_graph(turn, base_def), metric_name).get("expression", "")
            for turn in turns
        ]
        if len(set(expression for expression in expressions if expression)) <= 1:
            consistent += 1
        total += 1
    return {
        "metric": consistent / max(total, 1),
        "sample_size": total,
    }


def _semantic_extraction_component(semantic_extract_dataset: dict) -> dict | None:
    ner_mod = pytest.importorskip("semantica.semantic_extract.ner_extractor")
    extractor = ner_mod.NERExtractor(method="pattern")
    f1_scores = []
    for record in semantic_extract_dataset["ner"]["records"][:20]:
        gold_entities = _extract_gold_entities_from_bio(record.get("tokens", []), record.get("ner_tags", []))
        if not gold_entities:
            continue
        extracted = extractor.extract(record["text"])
        extracted_texts = {
            getattr(entity, "text", "").lower()
            for entity in (extracted if isinstance(extracted, list) else [])
            if getattr(entity, "text", "")
        }
        gold_texts = {entity[0] for entity in gold_entities}
        f1_scores.append(_entity_span_f1(extracted_texts, gold_texts))
    if not f1_scores:
        return None
    return {
        "metric": sum(f1_scores) / len(f1_scores),
        "sample_size": len(f1_scores),
    }


@pytest.fixture(scope="module")
def ses_report(
    retrieval_eval_dataset,
    decision_dataset,
    dedup_dblp_acm_dataset,
    jaffle_shop_dataset,
    agentic_traces_dataset,
    semantic_extract_dataset,
):
    components = {
        "retrieval_hit_rate": _retrieval_component(retrieval_eval_dataset),
        "decision_accuracy": _decision_component(decision_dataset),
        "duplicate_detection_f1": _dedup_component(dedup_dblp_acm_dataset),
        "semantic_metric_exactness": _semantic_metric_component(jaffle_shop_dataset),
        "cross_turn_metric_consistency": _agentic_consistency_component(
            agentic_traces_dataset,
            jaffle_shop_dataset,
        ),
    }
    extraction_component = _semantic_extraction_component(semantic_extract_dataset)
    if extraction_component is not None:
        components["ner_f1"] = extraction_component

    required_components = {
        "retrieval_hit_rate",
        "decision_accuracy",
        "duplicate_detection_f1",
        "semantic_metric_exactness",
        "cross_turn_metric_consistency",
    }
    available_components = {
        name: payload["metric"] for name, payload in components.items() if payload is not None
    }
    if missing := sorted(required_components - set(available_components)):
        raise AssertionError(f"SES required components missing: {', '.join(missing)}")

    # SES_v2 = 0.7 * ContextGraphScore + 0.3 * SemanticLayerScore
    # Pillar 1 — Context Graph components
    _CG = {"retrieval_hit_rate", "decision_accuracy", "duplicate_detection_f1", "ner_f1"}
    # Pillar 2 — Semantic Layer components
    _SL = {"semantic_metric_exactness", "cross_turn_metric_consistency"}

    cg_vals = [v for k, v in available_components.items() if k in _CG]
    sl_vals = [v for k, v in available_components.items() if k in _SL]
    cg_score = sum(cg_vals) / len(cg_vals) if cg_vals else 0.0
    sl_score = sum(sl_vals) / len(sl_vals) if sl_vals else 0.0
    ses_value = 0.7 * cg_score + 0.3 * sl_score
    domain_scores = {
        domain: sum(
            1.0
            for record in rows
            if normalize_decision_label(_structured_predict_decision(record)[0])
            == normalize_decision_label(record["ground_truth_decision"])
        ) / len(rows)
        for domain, rows in {
            key: value
            for key, value in {
                domain: [
                    record for record in decision_dataset["records"] if record["domain"] == domain
                ]
                for domain in {record["domain"] for record in decision_dataset["records"]}
            }.items()
        }.items()
    }
    report = make_track_report(
        name="ses_composite",
        sample_size=len(available_components),
        metrics={
            "ses_composite": ses_value,
            "ses_domain_minimum": min(domain_scores.values()),
        },
        slices={
            "components": components,
            "domains": domain_scores,
        },
        coverage=coverage_summary(
            executed=len(available_components),
            eligible=len(components),
            required=len(required_components),
        ),
        metadata={
            "required_components": sorted(required_components),
            # This is the offline CI estimate (8 components, no real-LLM tracks).
            # The canonical full SES_v2 is reported only by the weekly
            # benchmark_real_llm.yml run that includes real-LLM tracks.
            # Expected offline range: 0.68–0.74.
            "ses_label": "SES_v2_offline",
            "ses_offline_range": [0.68, 0.74],
            "full_ses_v2_source": "benchmark_real_llm.yml (weekly)",
        },
    )
    require_reportable(
        report,
        min_sample_size=len(required_components),
        min_executed_ratio=len(required_components) / max(len(components), 1),
        required_metrics=("ses_composite", "ses_domain_minimum"),
    )
    return report


class TestSESCompositeScore:
    def test_ses_component_coverage_is_sufficient(self, ses_report):
        assert ses_report["coverage"]["meets_required_coverage"] is True
        assert set(ses_report["metadata"]["required_components"]) <= set(ses_report["slices"]["components"])

    def test_ses_above_baseline(self, ses_report):
        assert ses_report["ses_composite"] >= get_threshold("ses_composite")

    def test_ses_domain_breakdown(self, ses_report):
        assert ses_report["ses_domain_minimum"] >= get_threshold("ses_domain_minimum")

    def test_ses_regression_guard(self, ses_report):
        assert ses_report["ses_composite"] >= 0.50

    def test_ses_report_structure(self, ses_report):
        assert isinstance(ses_report, dict)
        assert "ses_composite" in ses_report
        assert "components" in ses_report["slices"]
        assert 0.0 <= ses_report["ses_composite"] <= 1.0
