---
title: "Evals Module"
description: "Evaluation framework for measuring Knowledge Graph quality, extraction accuracy, and pipeline performance — coming soon."
icon: "chart-line"
---

`semantica.evals` is planned as a comprehensive evaluation framework for measuring extraction accuracy, graph quality, and pipeline performance.

<Warning>
  **`semantica.evals` is not yet implemented.** The module exists as a placeholder (`__all__ = []`). No classes or functions are available for import. This page describes the planned API.
</Warning>

## Planned Features

When released, `semantica.evals` will provide:

| Planned Class | Role |
| --- | --- |
| `KGEvaluator` | Completeness, consistency, schema compliance, coverage, and orphan node detection |
| `ExtractionEvaluator` | NER precision / recall / F1 and relation extraction metrics against gold datasets |
| `PipelineBenchmark` | Throughput (docs/sec), per-step latency, peak memory, and error rate |
| `RegressionTracker` | Record runs and compare metrics across commits or config changes |
| `EvalReport` | Structured report: `{scores, regressions, recommendations}` |
| `DeduplicationEvaluator` | Merge precision, false positive / false negative rates |
| `ReasoningEvaluator` | Inference accuracy, rule coverage, and derivation depth |

## Current Workaround

Until `semantica.evals` ships, use `semantica.ontology.OntologyEvaluator` for ontology quality metrics:

```python
from semantica.ontology import OntologyEvaluator

evaluator = OntologyEvaluator()
report    = evaluator.evaluate(ontology, kg)
print(f"Coverage:     {report.coverage:.2%}")
print(f"Completeness: {report.completeness:.2%}")
```

<CardGroup cols={2}>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Extraction module.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    Graph quality assessment.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Pipeline performance metrics.
  </Card>
  <Card title="Ontology Evaluator" icon="sitemap" href="ontology">
    Available now for ontology quality metrics.
  </Card>
</CardGroup>
