---
title: "Pipeline Module"
description: "Pipeline DSL with parallel workers, retry policies, failure handling, and progress tracking."
icon: "gear"
---

`semantica.pipeline` lets you chain Semantica components into reproducible, fault-tolerant workflows with parallel execution and configurable error handling. Pipelines are serializable — save them to YAML and reload in any environment.

## What You Get

- **`Pipeline`** — chain steps with parallel workers, retry policies, and failure handlers
- **`PipelineBuilder`** — fluent DSL for building pipelines with a readable chain syntax
- **`RetryPolicy`** — fixed, linear, and exponential backoff with configurable max retries
- **`FailureHandler`** — skip, stop, or retry failed documents without halting the pipeline
- **Progress tracking** — console (tqdm), WebSocket streaming, or file logging

## Basic Pipeline

```python
from semantica.pipeline import Pipeline
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

pipeline = Pipeline()
pipeline.add_step("ingest",   FileIngestor())
pipeline.add_step("parse",    DocumentParser())
pipeline.add_step("extract",  NERExtractor(method="llm", llm_provider=llm))
pipeline.add_step("build_kg", GraphBuilder(merge_entities=True))

result = pipeline.run("data/")
kg = result.output
```

## Parallel Processing

Process documents concurrently across multiple workers:

```python
pipeline = Pipeline(workers=4)

pipeline.add_step("ingest",  FileIngestor())
pipeline.add_step("parse",   DocumentParser())
pipeline.add_step("extract", NERExtractor(), parallel=True, batch_size=10)
pipeline.add_step("build",   GraphBuilder())

result = pipeline.run("data/")
```

## Retry and Error Handling

Configure retry behavior and failure strategy independently:

```python
from semantica.pipeline import Pipeline, RetryPolicy, FailureHandler

retry = RetryPolicy(
    max_retries=3,
    backoff="exponential",   # "fixed" | "linear" | "exponential"
    initial_delay=1.0        # seconds before first retry
)

handler = FailureHandler(
    strategy="skip",         # "skip" | "stop" | "retry"
    log_failures=True        # write failed documents to error log
)

pipeline = Pipeline(retry_policy=retry, failure_handler=handler)
```

## Progress Tracking

```python
# Console progress bar (tqdm)
result = pipeline.run("data/", show_progress=True)

# WebSocket progress — stream to Knowledge Explorer
result = pipeline.run("data/", websocket_port=8080)

# Inspect results
print(f"Processed: {result.processed_count}")
print(f"Failed:    {result.failed_count}")
print(f"Duration:  {result.duration_seconds:.1f}s")
```

## Pipeline DSL

The `PipelineBuilder` provides a fluent chain syntax that reads as a data flow:

```python
from semantica.pipeline import PipelineBuilder

pipeline = (
    PipelineBuilder()
    .ingest(FileIngestor())
    .parse(DocumentParser())
    .normalize()
    .extract(NERExtractor(method="llm", llm_provider=llm))
    .extract_relations(RelationExtractor(method="llm", llm_provider=llm))
    .build_kg(merge_entities=True)
    .deduplicate(strategy="semantic_v2")
    .export(format="turtle", path="output.ttl")
    .build()
)

result = pipeline.run("data/")
```

## Save and Load Pipelines

Serialize a pipeline to YAML for reproducible runs across environments:

```python
# Save pipeline configuration
pipeline.save("pipeline_config.yaml")

# Load and run on any machine
pipeline = Pipeline.load("pipeline_config.yaml")
result = pipeline.run("data/")
```

## Pipeline Result

```python
@dataclass
class PipelineResult:
    output:           Any      # final step output (e.g., a KnowledgeGraph)
    processed_count:  int      # documents successfully processed
    failed_count:     int      # documents that failed after retries
    duration_seconds: float    # total wall-clock time
    step_metrics:     Dict     # per-step timing and counts
    errors:           List     # list of FailedDocument records
```

<CardGroup cols={2}>
  <Card title="Ingest" icon="database" href="ingest">
    First step in most pipelines.
  </Card>
  <Card title="Semantic Extract" icon="magnifying-glass" href="semantic_extract">
    Core extraction step.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    Graph construction step.
  </Card>
  <Card title="Export" icon="file-export" href="export">
    Final output step.
  </Card>
</CardGroup>
