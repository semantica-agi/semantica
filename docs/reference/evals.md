---
title: "Evals Module"
description: "Evaluation framework for measuring Knowledge Graph quality, extraction accuracy, and pipeline performance."
icon: "chart-line"
---

`semantica.evals` provides a comprehensive evaluation framework for measuring extraction accuracy, graph quality, and pipeline performance. Use it to benchmark extractors, validate pipeline output, and track quality regressions across runs.

<Warning>
  **Coming Soon** — This module is currently in active development. Documentation will be expanded in the next release.
</Warning>

## Planned Capabilities

The Evals module will cover five evaluation areas:

| Area | What It Measures |
| ---- | ---------------- |
| **KG Quality** | Completeness, consistency, schema compliance, coverage metrics |
| **Extraction Accuracy** | NER precision / recall / F1, relation extraction metrics |
| **Pipeline Performance** | Throughput (docs/sec), latency per step, error rates |
| **Deduplication** | Merge accuracy, false positive / negative rates |
| **Reasoning** | Inference correctness, rule coverage, derivation depth |

## Scope

- **Offline evaluation** — compare against gold-standard annotated datasets
- **Regression tracking** — compare pipeline runs across commits or config changes
- **Live monitoring** — record quality metrics during production pipeline runs
- **Benchmark suites** — standard NER, RE, and KG construction benchmarks

<CardGroup cols={2}>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Extraction module to evaluate.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    Graph quality assessment.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Pipeline performance metrics.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Deduplication accuracy evaluation.
  </Card>
</CardGroup>
