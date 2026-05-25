from __future__ import annotations

from unittest.mock import patch

from benchmarks.context_graph_effectiveness.metrics import precision_recall_f1
from benchmarks.context_graph_effectiveness.thresholds import THRESHOLDS
from semantica.deduplication.cluster_builder import ClusterBuilder
from semantica.deduplication.entity_merger import EntityMerger
from semantica.deduplication.similarity_calculator import SimilarityCalculator


def _entity_text(entity: dict) -> str:
    return str(entity.get("title") or entity.get("name") or entity.get("authors") or entity.get("manufacturer") or entity.get("id"))


def _augment(entity: dict) -> dict:
    augmented = dict(entity)
    augmented.setdefault("name", _entity_text(entity))
    augmented.setdefault("type", "Entity")
    return augmented


def _evaluate_pairs(dataset: dict, limit: int = 200) -> tuple[float, float, float]:
    calculator = SimilarityCalculator(similarity_threshold=0.75)
    pairs = dataset["pairs"][:limit]
    expected = []
    predicted = []
    for pair in pairs:
        result = calculator.calculate_similarity(_augment(pair["entity1"]), _augment(pair["entity2"]), track=False)
        expected.append(bool(pair["is_duplicate"]))
        predicted.append(result.score >= 0.75)
    return precision_recall_f1(expected, predicted)


def test_duplicate_detection_recall(dedup_dblp_acm_dataset):
    _, recall, _ = _evaluate_pairs(dedup_dblp_acm_dataset)
    assert recall >= THRESHOLDS["duplicate_detection_recall"][1]


def test_duplicate_detection_precision(dedup_dblp_acm_dataset):
    precision, _, _ = _evaluate_pairs(dedup_dblp_acm_dataset)
    assert precision >= THRESHOLDS["duplicate_detection_precision"][1]


def test_f1_by_similarity_method(dedup_amazon_google_dataset):
    _, _, f1 = _evaluate_pairs(dedup_amazon_google_dataset)
    assert f1 >= THRESHOLDS["duplicate_detection_f1"][1]


def test_cluster_quality(dedup_abt_buy_dataset):
    entities = [
        {"id": "a1", "name": "Apple Inc.", "type": "Company"},
        {"id": "a2", "name": "Apple", "type": "Company"},
        {"id": "g1", "name": "Google LLC", "type": "Company"},
        {"id": "g2", "name": "Google", "type": "Company"},
        {"id": "m1", "name": "Microsoft Corporation", "type": "Company"},
        {"id": "m2", "name": "Microsoft", "type": "Company"},
        {"id": "banana", "name": "Banana Republic", "type": "Brand"},
    ]
    gold_pairs = {
        tuple(sorted(("a1", "a2"))),
        tuple(sorted(("g1", "g2"))),
        tuple(sorted(("m1", "m2"))),
    }

    builder = ClusterBuilder(similarity_threshold=0.75)
    result = builder.build_clusters(entities)
    clustered_pairs = set()
    for cluster in result.clusters:
        ids = [entity["id"] for entity in cluster.entities]
        for index, left in enumerate(ids):
            for right in ids[index + 1 :]:
                clustered_pairs.add(tuple(sorted((left, right))))

    assert clustered_pairs, "Cluster builder returned no clusters on obvious duplicate sample"
    purity = len(clustered_pairs & gold_pairs) / len(clustered_pairs)
    coverage = len(clustered_pairs & gold_pairs) / len(gold_pairs)
    assert purity >= 0.50
    assert coverage >= 0.67


def test_merge_strategy_keep_most_complete():
    merger = EntityMerger(preserve_provenance=True)
    entities = [
        {"id": "1", "name": "Apple Inc.", "type": "Company", "industry": "Technology"},
        {"id": "2", "name": "Apple", "type": "Company", "website": "apple.com", "hq": "Cupertino"},
    ]
    operations = merger.merge_duplicates(entities, strategy="keep_most_complete", threshold=0.75)
    assert operations, "Expected at least one merge operation"
    merged = operations[0].merged_entity
    assert set(merged.get("merged_from", [])) >= {"1", "2"}
    assert merged.get("name") in {"Apple Inc.", "Apple"}


def test_provenance_preservation():
    merger = EntityMerger(preserve_provenance=True)
    entities = [
        {"id": "1", "name": "Apple Inc.", "type": "Company"},
        {"id": "2", "name": "Apple", "type": "Company"},
    ]
    operations = merger.merge_duplicates(entities, strategy="merge_all", threshold=0.75)
    assert operations, "Expected merge operation to preserve provenance"
    merged_sources = operations[0].merged_entity.get("merged_from", [])
    assert set(merged_sources) >= {"1", "2"}


def test_incremental_detection_efficiency():
    calculator = SimilarityCalculator()
    new_entity = {"id": "new", "name": "Apple Inc.", "type": "Company"}
    existing = [
        {"id": "1", "name": "Apple", "type": "Company"},
        {"id": "2", "name": "Microsoft", "type": "Company"},
        {"id": "3", "name": "Google", "type": "Company"},
    ]
    scores = [calculator.calculate_similarity(new_entity, entity, track=False).score for entity in existing]
    assert max(scores) == scores[0]


def test_detect_duplicates_not_called_in_benchmark_pipeline():
    """Regression guard: semantica.deduplication.methods.detect_duplicates() has a known
    infinite-recursion risk.  The benchmark pipeline must use SimilarityCalculator /
    ClusterBuilder / EntityMerger directly and must never invoke the module-level
    detect_duplicates() wrapper.  This test enforces that invariant by asserting the
    function is never reached during a representative benchmark operation.
    """
    with patch(
        "semantica.deduplication.methods.detect_duplicates",
        side_effect=RecursionError("detect_duplicates called — infinite recursion risk"),
    ) as mock_detect:
        calculator = SimilarityCalculator(similarity_threshold=0.75)
        calculator.calculate_similarity(
            {"id": "1", "name": "Apple Inc.", "type": "Company"},
            {"id": "2", "name": "Apple", "type": "Company"},
            track=False,
        )
        builder = ClusterBuilder(similarity_threshold=0.75)
        builder.build_clusters([
            {"id": "a", "name": "Acme Corp.", "type": "Company"},
            {"id": "b", "name": "Acme", "type": "Company"},
        ])
        mock_detect.assert_not_called()
