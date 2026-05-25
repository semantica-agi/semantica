---
name: validate
description: Validate Semantica pipelines, extraction quality, graph schemas, and ontology consistency. Returns structured error/warning checklists. Uses PipelineValidator, PipelineBuilder.validate_pipeline(), GraphValidator, and OntologyValidator. Sub-commands: pipeline, step, dependencies, extraction, graph, ontology, performance.
---

# /semantica:validate

Validate pipeline and graph quality. Usage: `/semantica:validate <target> [options]`

`$ARGUMENTS` = target type + optional config or path.

---

## `pipeline [--config '<json>']`

Validate a full pipeline builder configuration.

```python
from semantica.pipeline.pipeline_builder import PipelineBuilder
from semantica.pipeline.pipeline_validator import PipelineValidator

builder = PipelineBuilder()
if config_json:
    import json
    builder.build_pipeline(json.loads(config_json))

# PipelineBuilder has its own quick validate
quick = builder.validate_pipeline()  # returns Dict

# PipelineValidator gives full ValidationResult(valid, errors, warnings)
# Does NOT raise — always returns a result object
validator = PipelineValidator()
result = validator.validate(builder)

# Also check inter-step dependencies
deps = validator.check_dependencies(builder)
```

Output:
```
Pipeline Validation:  VALID ✓  |  INVALID ✗
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Steps:    N registered
Valid:    M steps

Errors (K):
  ✗ [step_name] <error message>

Warnings (J):
  ⚠ [step_name] <warning message>

Dependencies:
  ✓ All dependencies resolved
  ✗ Step "<name>" depends on missing step "<dep>"

Result: <valid> — K errors, J warnings
```

---

## `step <step_name> [--type <type>] [--constraints '<json>']`

Validate a single pipeline step.

```python
from semantica.pipeline.pipeline_builder import PipelineBuilder
from semantica.pipeline.pipeline_validator import PipelineValidator
import json

builder = PipelineBuilder()
step = builder.get_step(step_name)

validator = PipelineValidator()
result = validator.validate_step(
    step=step,
    **json.loads(constraints_json) if constraints_json else {},
)
```

Output: same checklist format but scoped to a single step.

---

## `dependencies`

Check all inter-step dependency resolution for the active pipeline.

```python
from semantica.pipeline.pipeline_builder import PipelineBuilder
from semantica.pipeline.pipeline_validator import PipelineValidator

builder = PipelineBuilder()
validator = PipelineValidator()

deps = validator.check_dependencies(builder)
```

Output:
```
Dependency Graph:
  | Step | Depends On | Status |
  | step_A | — | ✓ |
  | step_B | step_A | ✓ |
  | step_C | step_X | ✗ MISSING |

Cycles detected: YES / NO
Missing steps:   [list]
```

---

## `extraction <file_path>`

Validate extraction quality for a file — entity confidence, relation density, coverage.

```python
from semantica.semantic_extract.extraction_validator import ExtractionValidator
from semantica.semantic_extract import (
    NamedEntityRecognizer,
    RelationExtractor,
)
from semantica.semantic_extract.cache import _result_cache

_result_cache.clear()  # prevent cross-invocation cache pollution

text = open(file_path).read()

ner = NamedEntityRecognizer()
rel = RelationExtractor()
entities = ner.extract(text)
relations = rel.extract(text)

validator = ExtractionValidator()
issues = validator.validate(entities, relations)
```

Output:
```
Extraction Validation: <file_path>
  Entities:    N extracted
  Relations:   M extracted
  Avg confidence: 0.83

Errors (K):
  ✗ <issue>

Warnings (J):
  ⚠ <warning>

Quality score: X/100
```

---

## `graph`

Check schema conformance, referential integrity, and structural health.

```python
from semantica.kg.graph_validator import GraphValidator
from semantica.context import ContextGraph

graph = ContextGraph()
validator = GraphValidator(graph)
result = validator.validate()
```

Output:
```
Graph Validation:
  Nodes:         N  |  Edges: M
  Node types:    K valid, J unknown
  
Referential integrity:
  ✗ Dangling edge: <source> → <missing target>

Schema conformance:
  ✗ Node "<id>" missing required property "<prop>"

Result: N errors, M warnings
```

---

## `ontology`

Validate ontology consistency and evaluate competency questions.

```python
from semantica.ontology import OntologyValidator

validator = OntologyValidator()
result = validator.validate()
cq_results = validator.evaluate_competency_questions()
```

Output:
```
Ontology Validation:
  Classes:      N
  Properties:   M
  Consistent:   YES ✓  |  NO ✗

Competency questions:
  ✓ "Can we find all instances of X?" — answered
  ✗ "Is Y a subclass of Z?" — failed: <reason>

Result: N consistency errors, M CQ failures
```

---

## `performance`

Validate pipeline performance characteristics — bottlenecks, parallelism, and resource use.

```python
from semantica.pipeline.pipeline_builder import PipelineBuilder
from semantica.pipeline.pipeline_validator import PipelineValidator

builder = PipelineBuilder()
pipeline = builder.build()
validator = PipelineValidator()

perf = validator.validate_performance(pipeline)
```

Output: step-by-step timing estimates, parallelism opportunities, and recommended parallelism level.
