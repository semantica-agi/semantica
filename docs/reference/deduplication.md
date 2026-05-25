---
title: "Deduplication Module"
description: "Entity deduplication v1/v2 — similarity scoring, blocking, merging, and cluster-based batch processing."
icon: "copy"
---

`semantica.deduplication` detects and merges duplicate entities across sources to produce a clean, single-source-of-truth knowledge graph. **v2 strategies** (`blocking_v2`, `hybrid_v2`, `semantic_v2`) are up to **7x faster** than v1 with fine-grained result control.

## Exported Classes

| Class | Role |
| --- | --- |
| `DuplicateDetector` | Pairwise and batch detection with configurable strategy and threshold |
| `EntityMerger` | Merge duplicate groups with per-property merge policies (`KEEP_FIRST`, `UNION`, `VOTING`, ...) |
| `SimilarityCalculator` | Levenshtein, Jaro-Winkler, cosine, Jaccard, and embedding similarity |
| `ClusterBuilder` | Union-Find and hierarchical clustering for large-scale batch deduplication |
| `PropertyMergeRule` | Enum of merge policies used by `EntityMerger` |
| `MergeStrategyManager` | Manage and apply named merge strategies across entity types |
| `detect_duplicates()` | Quick function: `detect_duplicates(entities, method="semantic_v2")` |
| `merge_entities()` | Quick function: `merge_entities(entities, duplicates, method="union")` |

**Available `method=` values:**

| Method | Speed | Notes |
| --- | --- | --- |
| `exact` | Fastest | Exact string match only |
| `fuzzy` | Fast | Levenshtein + Jaro-Winkler |
| `semantic` | Moderate | Embedding cosine similarity |
| `blocking_v2` | Fast | Sorted neighborhood blocking (v2) |
| `hybrid_v2` | Balanced | Blocking + multi-feature scoring (v2) |
| `semantic_v2` | Best accuracy | Embedding + structural features, up to 7× faster than v1 |

## DuplicateDetector

Find duplicate entity pairs with configurable strategies and result filtering:

```python
from semantica.deduplication import DuplicateDetector

detector = DuplicateDetector(similarity_threshold=0.85)
duplicates = detector.detect_duplicates(entities)

for dup in duplicates:
    print(f"{dup.entity_a} ≈ {dup.entity_b}  ({dup.similarity:.2f})")
```

Fine-grained control over strategy, thresholds, and result size:

```python
duplicates = detector.detect_duplicates(
    entities,
    strategy="semantic_v2",    # see strategies table below
    min_similarity=0.85,        # minimum score to consider a match
    top_k_per_entity=3,         # max candidates per entity
    max_results=100,            # total result cap
    sort_by="similarity",       # "similarity" | "entity_id" | "cluster_size"
)
```

### Detection Strategies

| Strategy | Algorithm | Speed | Accuracy |
| -------- | --------- | ----- | -------- |
| `jaro_winkler` | String similarity (v1) | Fast | Medium |
| `blocking_v2` | Blocking + Jaro-Winkler (v2) | Very fast | Medium |
| `hybrid_v2` | Blocking + semantic + string (v2) | Fast | High |
| `semantic_v2` | Embedding similarity (v2) | Medium | Highest |

<Note>
  **v0.5.0 fix:** `DuplicateDetector` no longer produces duplicate definition errors when the same entity appears in multiple sources with identical definitions.
</Note>

## EntityMerger

Merges detected duplicate groups into canonical entities, preserving provenance:

```python
from semantica.deduplication import EntityMerger

merger = EntityMerger()
merged_entities = merger.merge_duplicates(
    entities,
    strategy="keep_most_complete",  # see strategies table below
    preserve_provenance=True,        # keep source references after merge
)
```

### Merge Strategies

| Strategy | Behavior |
| -------- | -------- |
| `keep_first` | Keep the first entity in each duplicate group |
| `keep_last` | Keep the most recently seen entity |
| `keep_most_complete` | Keep the entity with the most non-null properties |
| `union` | Merge all properties — non-conflicting fields combined |
| `voting` | Most common property value wins |

Fine-grained per-property merge rules:

```python
from semantica.deduplication import EntityMerger, PropertyMergeRule

merger = EntityMerger(
    property_rules={
        "name":        PropertyMergeRule.KEEP_FIRST,
        "aliases":     PropertyMergeRule.UNION,
        "description": PropertyMergeRule.KEEP_LONGEST,
    }
)
```

## SimilarityCalculator

Compute multi-factor similarity scores between entity pairs:

```python
from semantica.deduplication import SimilarityCalculator

calc = SimilarityCalculator()

score = calc.calculate_similarity(entity_a, entity_b)
# → SimilarityResult(score=0.91, components={...})

print(score.score)                    # overall score 0.0–1.0
print(score.components["label"])      # label similarity
print(score.components["embedding"])  # semantic similarity
print(score.components["property"])   # property overlap
```

Individual string and vector metrics:

```python
lev  = calc.levenshtein("Apple Inc.", "Apple Inc")
jaro = calc.jaro_winkler("Steve Jobs", "Steven Jobs")
cos  = calc.cosine_similarity(embedding_a, embedding_b)
jacc = calc.jaccard({"founded", "tech"}, {"founded", "technology"})
```

## ClusterBuilder

Build entity clusters for large-scale batch deduplication:

```python
from semantica.deduplication import ClusterBuilder

builder = ClusterBuilder(algorithm="union_find")  # or "hierarchical"
result = builder.build_clusters(entities, similarity_threshold=0.85)

print(f"Clusters: {len(result.clusters)}")
for cluster in result.clusters:
    print(f"  [{cluster.id}] {cluster.members} — cohesion: {cluster.cohesion:.2f}")
```

## Blocking Strategies

Blocking reduces the O(n²) pairwise comparison problem to a manageable candidate set:

```python
detector = DuplicateDetector(
    blocking_strategy="token",     # "token" | "phonetic" | "ngram"
    blocking_threshold=0.6,
    similarity_threshold=0.85
)
```

## Custom Similarity Functions

Register domain-specific similarity logic:

```python
from semantica.deduplication import method_registry

def drug_name_similarity(entity_a, entity_b):
    # Match drug names by active compound
    return score  # 0.0 to 1.0

method_registry.register("similarity", "drug_name", drug_name_similarity)

detector = DuplicateDetector(similarity_method="drug_name")
```

## Convenience Functions

```python
from semantica.deduplication import detect_duplicates, merge_entities, calculate_similarity

# Quick detection
duplicates = detect_duplicates(entities, method="semantic_v2", similarity_threshold=0.85)

# Quick merge
merged = merge_entities(entities, duplicates, method="keep_most_complete")

# Quick similarity
score = calculate_similarity(entity_a, entity_b, method="hybrid_v2")
```

<CardGroup cols={2}>
  <Card title="Conflicts" icon="triangle-exclamation" href="conflicts">
    Detect value conflicts between non-duplicate entities.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    GraphBuilder uses deduplication during construction.
  </Card>
  <Card title="Normalize" icon="broom" href="normalize">
    Normalize entity names before deduplication.
  </Card>
  <Card title="Provenance" icon="link" href="provenance">
    Track merged entity lineage.
  </Card>
</CardGroup>
