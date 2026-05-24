---
title: "Core Module"
description: "Framework orchestration, lifecycle management, configuration, and plugin system."
icon: "gear"
---

`semantica.core` is the coordination layer for the framework. For most tasks you should use individual modules directly (`semantica.ingest`, `semantica.kg`, etc.). Reach for Core when you need application-level lifecycle management, centralized configuration, or a plugin registry.

## Exported Classes

```python
from semantica.core import (
    Semantica,       # orchestration class — coordinates full KG pipeline
    ConfigManager,   # YAML config loading, deep-merge, env var overrides
    LifecycleManager,# startup/shutdown state machine + health monitoring
    PluginRegistry,  # plugin discovery, registration, and loading
    method_registry, # global MethodRegistry instance for custom dispatch
)

# For custom build methods:
from semantica.core.methods import build_knowledge_base
```

## What You Get

- **`Semantica`** — orchestration class for coordinating complex multi-module workflows
- **`ConfigManager`** — unified config loading, merging, and validation with environment variable overrides
- **`LifecycleManager`** — startup/shutdown hooks and component health monitoring
- **`PluginRegistry`** — dynamic plugin discovery, registration, and loading
- **`method_registry`** — global `MethodRegistry` instance — register and dispatch custom orchestration methods

<Tip>
  **Use individual modules directly** for the vast majority of use cases. Use the `Semantica` orchestration class only when you need application-level lifecycle management or a plugin system.
</Tip>

## Semantica (Orchestration)

High-level entry point that coordinates the full KG construction pipeline:

```python
from semantica.core import Semantica, ConfigManager

config_manager = ConfigManager()
config = config_manager.load_from_file("config.yaml")

framework = Semantica(config=config)
framework.initialize()

try:
    result = framework.build_knowledge_base(
        sources=["doc1.pdf", "doc2.docx"],
        embeddings=True,
        graph=True,
    )
    status = framework.get_status()
    print(f"State: {status['state']}")
finally:
    framework.shutdown(graceful=True)
```

### Core Methods

| Method | Description |
| ------ | ----------- |
| `initialize()` | Initialize all framework components |
| `build_knowledge_base(sources, **kwargs)` | Orchestrate full KG construction pipeline |
| `run_pipeline(pipeline, data)` | Execute an existing `Pipeline` instance |
| `get_status()` | Return system health and current state |
| `shutdown(graceful=True)` | Graceful shutdown — waits for in-flight operations |

## ConfigManager

Centralized config loading with deep-merge and environment variable overrides:

```python
from semantica.core import ConfigManager

manager = ConfigManager()
config = manager.load_from_file("config.yaml")

# Merge base config with environment-specific overrides
merged = manager.merge_configs(
    manager.load_from_file("base.yaml"),
    manager.load_from_file("prod.yaml"),
)

# Nested key access with dot notation
batch_size = config.get("processing.batch_size", default=16)
config.set("processing.batch_size", 64)
config.validate()
```

### YAML Configuration

```yaml
llm_provider:
  name: openai
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}

processing:
  batch_size: 32
  max_workers: 4

quality:
  min_confidence: 0.7

logging:
  level: INFO
```

Environment variable overrides (prefix `SEMANTICA_`):

```bash
export SEMANTICA_PROCESSING_BATCH_SIZE=64
export SEMANTICA_LOG_LEVEL=DEBUG
```

## LifecycleManager

Manages framework state with a defined state machine and ordered startup/shutdown hooks:

**State machine:** `UNINITIALIZED` → `INITIALIZING` → `READY` → `RUNNING` → `STOPPING` → `STOPPED`

```python
from semantica.core import LifecycleManager

manager = LifecycleManager()

def init_db():
    print("Initializing database...")

def cleanup_db():
    print("Closing database connections...")

# Lower priority values run first during startup
# Higher priority values run first during shutdown
manager.register_startup_hook(init_db,     priority=10)
manager.register_shutdown_hook(cleanup_db, priority=10)

manager.startup()

# Component health monitoring
class DatabaseComponent:
    def health_check(self):
        return {"healthy": True, "message": "Connected"}

manager.register_component("database", DatabaseComponent())
summary = manager.get_health_summary()
# → {"database": {"healthy": True, "message": "Connected"}, ...}

manager.shutdown(graceful=True)
```

## PluginRegistry

Register custom components that participate in the full pipeline — provenance tracking, retry policies, and parallel execution included:

```python
from semantica.core import PluginRegistry

class MyPlugin:
    def initialize(self):
        print("Plugin initialized")

    def execute(self, data):
        return {"processed": True}

registry = PluginRegistry(plugin_paths=["./plugins"])
registry.register_plugin("my_plugin", MyPlugin, version="1.0.0")

plugin = registry.load_plugin("my_plugin", api_key="xxx")
result = plugin.execute("sample data")

for info in registry.list_plugins():
    print(f"{info['name']}: {info['version']}")
```

## MethodRegistry

Register custom orchestration methods and dispatch them by name:

```python
from semantica.core import method_registry
from semantica.core.methods import build_knowledge_base

def fast_kb_builder(sources, **kwargs):
    # Custom logic — skip embeddings for speed
    ...

method_registry.register("knowledge_base", "fast", fast_kb_builder)

result = build_knowledge_base(sources=["doc.pdf"], method="fast")
```

## When to Use Core vs. Individual Modules

| Scenario | Recommended Approach |
| -------- | -------------------- |
| Single extraction task | `from semantica.semantic_extract import NERExtractor` |
| Build a knowledge graph | `from semantica.kg import GraphBuilder` |
| Multi-step pipeline | `from semantica.pipeline import Pipeline` |
| App-level lifecycle + config | `from semantica.core import Semantica, ConfigManager` |
| Custom dispatch / plugins | `from semantica.core import method_registry, PluginRegistry` |

<Tip>
  Use `Semantica` and `LifecycleManager` only when building a long-running application (e.g. a FastAPI service) that needs ordered startup, health checks, and graceful shutdown. For scripts and notebooks, use individual modules directly.
</Tip>

<CardGroup cols={2}>
  <Card title="Pipeline" icon="arrows-turn-to-dots" href="pipeline">
    Pipeline execution and step orchestration.
  </Card>
  <Card title="Utils" icon="wrench" href="utils">
    Shared utilities used by Core internally.
  </Card>
  <Card title="Getting Started" icon="play" href="../getting-started">
    Learn the basics before using Core.
  </Card>
  <Card title="LLMs" icon="microchip" href="llms">
    Configure LLM providers via ConfigManager.
  </Card>
</CardGroup>
