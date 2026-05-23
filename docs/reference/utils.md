---
title: "Utils Module"
description: "Shared utilities for logging, validation, error handling, progress tracking, and common operations."
icon: "wrench"
---

`semantica.utils` provides shared infrastructure used throughout Semantica. Most users won't call it directly, but its APIs are available when you need fine-grained control over logging, validation, progress tracking, or error handling.

## What You Get

- **Logging** — structured logging with `@log_performance` decorator and quality metrics
- **Validation** — `validate_entity`, `validate_config` with a typed `ValidationError`
- **Progress tracking** — `track_progress` wraps any iterable with console, Jupyter, or file output
- **Helper functions** — `clean_text`, `hash_data`, `safe_filename`
- **Exception hierarchy** — `SemanticaError` → `ValidationError`, `ProcessingError`

## Logging

```python
from semantica.utils import setup_logging, get_logger, log_performance

setup_logging(level="INFO")   # "DEBUG" | "INFO" | "WARNING" | "ERROR"
logger = get_logger(__name__)

@log_performance
def process_data(data):
    logger.info(f"Processing {len(data)} items")
    # Decorator automatically logs function name, duration, and any exception
```

Configure via environment variables:

```bash
export SEMANTICA_LOG_LEVEL=DEBUG
export SEMANTICA_LOG_FORMAT=json     # "json" | "text"
export SEMANTICA_PROGRESS_BAR=true
```

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
- **Jupyter** — notebook-compatible widget
- **File** — write progress to a log file

## Helper Functions

```python
from semantica.utils import clean_text, hash_data, safe_filename

# Normalize whitespace and strip control characters
clean  = clean_text("  Hello   World  ")   # → "Hello World"

# Deterministic SHA-256 hash of any serializable object
uid    = hash_data({"key": "value"})        # → hex digest string

# Sanitize a string for use as a filename
fname  = safe_filename("My File?.txt")      # → "My_File_.txt"
```

## Exception Hierarchy

```python
from semantica.utils import SemanticaError, ValidationError, ProcessingError

try:
    run_pipeline(data)
except ValidationError as e:
    # Input data did not pass schema validation
    logger.error(f"Validation failed: {e}")
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

<CardGroup cols={2}>
  <Card title="Core" icon="gear" href="core">
    Framework orchestration that uses Utils internally.
  </Card>
  <Card title="Pipeline" icon="arrows-turn-to-dots" href="pipeline">
    Uses ProgressTracker for per-step tracking.
  </Card>
</CardGroup>
