---
title: "Utils Module"
description: "Shared utilities for logging, validation, error handling, progress tracking, and common operations."
icon: "wrench"
---

`semantica.utils` provides shared infrastructure used throughout Semantica. Most users won't call it directly, but its APIs are available when you need fine-grained control over logging, validation, progress tracking, or error handling.

## Exported Classes

| Name | Type | Role |
| --- | --- | --- |
| `setup_logging` | function | Configure root logger — `level`, `format` (`"json"` or `"text"`) |
| `get_logger` | function | Get a named logger instance |
| `log_performance` | decorator | Logs function name, duration, and any exception |
| `validate_entity` | function | Validate entity dict structure — raises `ValidationError` on failure |
| `validate_config` | function | Validate config dict against schema — raises `ValidationError` on failure |
| `ProgressTracker` | class | Class-based progress tracker with ETA and step callbacks |
| `track_progress` | function | Wrap any iterable with a live progress bar |
| `clean_text` | function | Normalize whitespace and strip control characters |
| `hash_data` | function | Deterministic SHA-256 hash of any serializable object |
| `SemanticaError` | exception | Base exception for all Semantica errors |
| `ValidationError` | exception | Raised when input fails validation |
| `ProcessingError` | exception | Raised during extraction, graph build, or pipeline step |

## What You Get

<CardGroup cols={2}>
  <Card title="Logging" icon="scroll">
    Structured logging with `@log_performance` decorator and quality metrics via environment variables.
  </Card>
  <Card title="Validation" icon="shield-check">
    `validate_entity` and `validate_config` with a typed `ValidationError` carrying field and value context.
  </Card>
  <Card title="Progress Tracking" icon="bars-progress">
    `track_progress` wraps any iterable — auto-detects console vs Jupyter for the right renderer.
  </Card>
  <Card title="Helper Functions" icon="wrench">
    `clean_text`, `hash_data`, `safe_filename`, and nested dict utilities used throughout the framework.
  </Card>
  <Card title="Exception Hierarchy" icon="triangle-exclamation">
    `SemanticaError` → `ValidationError`, `ProcessingError` — typed exceptions for targeted recovery.
  </Card>
  <Card title="File Utilities" icon="file">
    `read_json_file` with `ProcessingError` on failure — no boilerplate try/except around JSON I/O.
  </Card>
</CardGroup>

## Logging

<Steps>
  <Step title="Initialize logging at application startup">
    ```python
    from semantica.utils import setup_logging, get_logger

    setup_logging(level="INFO")   # "DEBUG" | "INFO" | "WARNING" | "ERROR"
    logger = get_logger(__name__)
    ```
  </Step>
  <Step title="Instrument expensive functions with the performance decorator">
    ```python
    from semantica.utils import log_performance, log_execution_time

    @log_performance
    def process_data(data):
        logger.info(f"Processing {len(data)} items")
        # Logs function name, duration, and any exception automatically

    @log_execution_time
    def expensive_step(data):
        ...
    # Logs: "expensive_step completed in 2.34s"
    ```
  </Step>
  <Step title="Configure via environment variables">
    ```bash
    export SEMANTICA_LOG_LEVEL=DEBUG
    export SEMANTICA_LOG_FORMAT=json     # "json" | "text"
    export SEMANTICA_PROGRESS_BAR=true
    ```
  </Step>
</Steps>

## Validation

```python
from semantica.utils import validate_entity, validate_config, ValidationError

# Validate an entity dict
try:
    validate_entity({"id": "1", "type": "PERSON", "text": "Alice"})
except ValidationError as e:
    print(f"Invalid entity: {e.message}")
    print(f"  Field:   {e.field}")
    print(f"  Value:   {e.value}")

# Validate a configuration dict
try:
    validate_config(config)
except ValidationError as e:
    print(f"Invalid config: {e}")
```

| Function | Description |
| -------- | ----------- |
| `validate_entity(data)` | Check entity dict has required fields and correct types |
| `validate_config(cfg)` | Check configuration dict against schema |

## Progress Tracking

```python
from semantica.utils import track_progress

# Wraps any iterable — auto-detects console vs Jupyter
for item in track_progress(items, desc="Processing documents"):
    process(item)
```

Supports:
- **Console** — tqdm progress bar with ETA
- **Jupyter** — notebook-compatible widget (auto-detected)
- **File** — write progress to a log file

## Helper Functions

```python
from semantica.utils import clean_text, hash_data, safe_filename

# Normalize whitespace and strip control characters
clean = clean_text("  Hello   World  ")     # → "Hello World"

# Deterministic SHA-256 hash of any JSON-serializable object
uid   = hash_data({"key": "value"})         # → hex digest string

# Sanitize a string for use as a filename
fname = safe_filename("My File?.txt")       # → "My_File_.txt"
```

## Nested Dict Utilities

Helper functions for deep configuration access — used extensively inside `Config` and `ConfigManager`:

```python
from semantica.utils import get_nested_value, set_nested_value, merge_dicts

config = {
    "processing": {"batch_size": 32, "max_workers": 4},
    "llm":        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
}

# Dot-notation read — returns default if key path is absent
batch = get_nested_value(config, "processing.batch_size", default=16)
# → 32

# Dot-notation write
set_nested_value(config, "processing.batch_size", 64)

# Deep merge — nested keys are merged recursively
base      = {"a": {"x": 1, "y": 2}, "b": 3}
overrides = {"a": {"y": 99, "z": 4}, "c": 5}
merged    = merge_dicts(base, overrides, deep=True)
# → {"a": {"x": 1, "y": 99, "z": 4}, "b": 3, "c": 5}
```

## Exception Hierarchy

<AccordionGroup>
  <Accordion title="Exception types and when they're raised">

```python
from semantica.utils import SemanticaError, ValidationError, ProcessingError

try:
    run_pipeline(data)
except ValidationError as e:
    # Input data did not pass schema validation
    logger.error(f"Validation failed at field '{e.field}': {e.message}")
except ProcessingError as e:
    # Failure during extraction or graph construction
    logger.error(f"Processing failed at step {e.step}: {e}")
except SemanticaError as e:
    # Catch-all for all Semantica framework errors
    logger.error(f"Framework error: {e}")
```

| Exception | When Raised |
| --------- | ----------- |
| `SemanticaError` | Base class — all framework errors inherit from this |
| `ValidationError` | Input data failed schema or type validation |
| `ProcessingError` | Failure during extraction, graph build, or pipeline step |

  </Accordion>
</AccordionGroup>

## File Utilities

```python
from semantica.utils import read_json_file

# Read and parse a JSON file — raises ProcessingError on failure
config = read_json_file("config.json")
```

## Tips and Common Pitfalls

<Warning>
  **Call `setup_logging(level="INFO")` once at application startup.** Without it, Semantica falls back to Python's root logger, which may be silent or misconfigured. Call it before importing other Semantica modules to capture initialization messages.
</Warning>

<Tip>
  **Use `@log_performance` on expensive functions.** The decorator logs function name, duration, and any raised exception automatically — no manual `time.time()` bookkeeping needed. Essential for profiling multi-step pipelines where one step is a hidden bottleneck.
</Tip>

<Tip>
  **`hash_data()` is deterministic across runs.** Given the same input dict (any JSON-serializable object), `hash_data()` always returns the same SHA-256 hex string — suitable as a cache key or idempotency token in pipeline steps.
</Tip>

<Tip>
  **Catch `SemanticaError` as the broadest exception net.** All framework errors inherit from `SemanticaError`, so `except SemanticaError` catches validation failures, processing errors, and everything in between. Use specific subclasses for targeted recovery logic.
</Tip>

<Tip>
  **`track_progress` auto-detects Jupyter.** In a terminal it renders a tqdm progress bar; in a Jupyter notebook it renders an interactive widget. You don't need to check the environment — the same call works in both.
</Tip>

<CardGroup cols={2}>
  <Card title="Core" icon="gear" href="core">
    Framework orchestration that uses Utils internally.
  </Card>
  <Card title="Pipeline" icon="arrows-turn-to-dots" href="pipeline">
    Uses ProgressTracker for per-step tracking.
  </Card>
</CardGroup>
