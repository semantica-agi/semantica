# Core Module Usage Guide

This comprehensive guide demonstrates how to use the core orchestration module for framework initialization, knowledge base construction, pipeline execution, configuration management, lifecycle management, and plugin system integration.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Semantica Class](#semantica-class)
3. [ConfigManager](#configmanager)
4. [Config Class](#config-class)
5. [LifecycleManager](#lifecyclemanager)
6. [PluginRegistry](#pluginregistry)
7. [MethodRegistry](#methodregistry)
8. [Orchestration Methods](#orchestration-methods)
9. [Convenience Functions](#convenience-functions)
10. [Configuration](#configuration)
11. [Advanced Examples](#advanced-examples)
12. [Best Practices](#best-practices)

## Basic Usage

### Quick Start

```python
from semantica.core import Semantica

# Initialize framework
framework = Semantica()
framework.initialize()

# Build knowledge base from documents
result = framework.build_knowledge_base(
    sources=["doc1.pdf", "doc2.docx"],
    embeddings=True,
    graph=True
)

# Check system status
status = framework.get_status()
print(f"System state: {status['state']}")

# Shutdown gracefully
framework.shutdown()
```

### Using Convenience Functions

```python
from semantica.core import build
from semantica.core.methods import build_knowledge_base

# Using module-level convenience function
result = build(
    sources=["doc1.pdf"],
    extract_entities=True,
    extract_relations=True,
    embeddings=True,
    graph=True
)

# Using methods directly
result = build_knowledge_base(
    sources=["doc1.pdf", "doc2.docx"],
    method="default",
    embeddings=True,
    graph=True
)
```

## Semantica Class

The main framework class that coordinates all components and provides a unified API.

### Initialization

```python
from semantica.core import Semantica, Config

# Initialize with default configuration
framework = Semantica()

# Initialize with configuration dictionary
config_dict = {
    "llm_provider": {"name": "openai", "model": "gpt-4o-mini"},
    "processing": {"batch_size": 32}
}
framework = Semantica(config=config_dict)

# Initialize with Config object
from semantica.core import ConfigManager
config_manager = ConfigManager()
config = config_manager.load_from_dict(config_dict)
framework = Semantica(config=config)
```

### Methods

#### `initialize()`

Initialize all framework components, load plugins, and prepare the system for processing.

```python
framework = Semantica()
framework.initialize()

# Check if initialization was successful
status = framework.get_status()
if status['state'] == 'ready':
    print("Framework initialized successfully")
```

**Raises:**
- `ConfigurationError`: If configuration is invalid
- `SemanticaError`: If initialization fails

#### `build_knowledge_base()`

Build knowledge base from various data sources.

```python
# Basic usage
result = framework.build_knowledge_base(
    sources=["doc1.pdf", "doc2.docx"]
)

# With options
result = framework.build_knowledge_base(
    sources=["doc1.pdf", "https://example.com/doc.html"],
    embeddings=True,
    graph=True,
    pipeline={"extract": {"entities": True, "relations": True}},
    fail_fast=False
)

# Access results
kg = result["knowledge_graph"]
embeddings = result["embeddings"]
stats = result["statistics"]
print(f"Processed {stats['sources_processed']} sources")
```

**Parameters:**
- `sources`: List of data sources (files, URLs, streams)
- `embeddings`: Whether to generate embeddings (default: True)
- `graph`: Whether to build knowledge graph (default: True)
- `pipeline`: Custom pipeline configuration dictionary
- `fail_fast`: Whether to stop on first error (default: False)

**Returns:**
Dictionary containing:
- `knowledge_graph`: Knowledge graph data
- `embeddings`: Embedding vectors
- `results`: Processing results
- `statistics`: Processing statistics
- `metadata`: Processing metadata

**Raises:**
- `ProcessingError`: If processing fails

#### `run_pipeline()`

Execute a processing pipeline.

```python
# Using pipeline configuration dictionary
pipeline_config = {
    "steps": ["parse", "extract", "normalize"]
}

result = framework.run_pipeline(
    pipeline=pipeline_config,
    data="sample text data"
)

# Access results
output = result["output"]
metrics = result["metrics"]
print(f"Execution time: {metrics.get('execution_time', 0)}s")
```

**Parameters:**
- `pipeline`: Pipeline object or configuration dictionary
- `data`: Input data for pipeline

**Returns:**
Dictionary containing:
- `success`: Whether execution succeeded
- `output`: Pipeline output data
- `metrics`: Performance metrics
- `metadata`: Processing metadata

**Raises:**
- `ProcessingError`: If pipeline execution fails

#### `get_status()`

Get system health and status.

```python
status = framework.get_status()

# Access status information
print(f"System state: {status['state']}")
print(f"Healthy components: {status['health']['healthy_components']}")

# Check module status
for name, module_status in status['modules'].items():
    print(f"{name}: {module_status['status']}")

# Check plugin status
for name, plugin_status in status['plugins'].items():
    print(f"{name}: loaded={plugin_status['loaded']}")
```

**Returns:**
Dictionary containing:
- `state`: System state (uninitialized, ready, running, stopped, error)
- `health`: Health summary with component statuses
- `modules`: Module status information
- `plugins`: Plugin status information
- `config`: Configuration status

#### `shutdown()`

Shutdown the framework gracefully.

```python
# Graceful shutdown (default)
framework.shutdown(graceful=True)

# Force shutdown
framework.shutdown(graceful=False)
```

**Parameters:**
- `graceful`: Whether to shutdown gracefully (default: True)

## ConfigManager

Configuration management system for loading, validating, and merging configurations.

### Methods

#### `load_from_file()`

Load configuration from YAML or JSON file.

```python
from semantica.core import ConfigManager

manager = ConfigManager()

# Load from YAML file
config = manager.load_from_file("config.yaml")

# Load from JSON file
config = manager.load_from_file("config.json")

# Load without validation
config = manager.load_from_file("config.yaml", validate=False)
```

**Parameters:**
- `file_path`: Path to configuration file (YAML or JSON)
- `validate`: Whether to validate configuration after loading (default: True)

**Returns:**
- `Config`: Loaded configuration object

**Raises:**
- `ConfigurationError`: If file cannot be loaded or is invalid

#### `load_from_dict()`

Load configuration from dictionary.

```python
config_dict = {
    "llm_provider": {"name": "openai"},
    "processing": {"batch_size": 64}
}

config = manager.load_from_dict(config_dict)
```

**Parameters:**
- `config_dict`: Dictionary of configuration values
- `validate`: Whether to validate configuration after loading (default: True)

**Returns:**
- `Config`: Configuration object

**Raises:**
- `ConfigurationError`: If configuration is invalid

#### `merge_configs()`

Merge multiple configurations.

```python
config1 = manager.load_from_file("base_config.yaml")
config2 = manager.load_from_file("override_config.yaml")
config3 = manager.load_from_dict({"processing": {"batch_size": 128}})

# Later configurations take priority
merged = manager.merge_configs(config1, config2, config3)
```

**Parameters:**
- `*configs`: Configuration objects to merge
- `validate`: Whether to validate merged configuration (default: True)

**Returns:**
- `Config`: Merged configuration

**Raises:**
- `ConfigurationError`: If no configurations provided or merged config is invalid

#### `get_config()`

Get current configuration.

```python
current_config = manager.get_config()
if current_config:
    batch_size = current_config.get("processing.batch_size")
```

**Returns:**
- `Optional[Config]`: Current configuration or None if not loaded

#### `set_config()`

Set current configuration.

```python
config = manager.load_from_file("config.yaml")
manager.set_config(config, validate=True)
```

**Parameters:**
- `config`: Configuration object to set
- `validate`: Whether to validate configuration (default: True)

#### `reload()`

Reload configuration from file.

```python
# Reload from last loaded file
config = manager.reload()

# Reload from specific file
config = manager.reload("config.yaml")
```

**Parameters:**
- `file_path`: Optional path to configuration file (uses last loaded file if None)

**Returns:**
- `Config`: Reloaded configuration

## Config Class

Configuration data class with validation and nested access.

### Methods

#### `get()`

Get nested configuration value by key path.

```python
from semantica.core import Config

config = Config(config_dict={"processing": {"batch_size": 32}})

# Get nested value
batch_size = config.get("processing.batch_size", default=16)

# Get with default
timeout = config.get("processing.timeout", default=30)
```

**Parameters:**
- `key_path`: Dot-separated key path (e.g., "processing.batch_size")
- `default`: Default value if key not found

**Returns:**
- Configuration value or default

#### `set()`

Set nested configuration value by key path.

```python
config.set("processing.batch_size", 64)
config.set("llm_provider.model", "gpt-4o-mini")
```

**Parameters:**
- `key_path`: Dot-separated key path
- `value`: Value to set

#### `update()`

Update configuration with new values.

```python
# Merge updates
config.update({
    "processing": {"batch_size": 128},
    "quality": {"min_confidence": 0.9}
}, merge=True)

# Replace (don't merge)
config.update({
    "processing": {"batch_size": 128}
}, merge=False)
```

**Parameters:**
- `updates`: Dictionary of updates
- `merge`: Whether to merge nested dictionaries (default: True)

#### `validate()`

Validate configuration settings.

```python
try:
    config.validate()
    print("Configuration is valid")
except ConfigurationError as e:
    print(f"Validation failed: {e}")
```

**Raises:**
- `ConfigurationError`: If configuration is invalid with detailed error messages

#### `to_dict()`

Convert configuration to dictionary.

```python
config_dict = config.to_dict()
print(config_dict["processing"]["batch_size"])
```

**Returns:**
- Dictionary representation of configuration

## LifecycleManager

System lifecycle management with hooks and health monitoring.

### Methods

#### `startup()`

Execute startup sequence with registered hooks.

```python
from semantica.core import LifecycleManager

manager = LifecycleManager()

# Register startup hooks
def init_database():
    print("Initializing database...")

def init_cache():
    print("Initializing cache...")

manager.register_startup_hook(init_database, priority=10)
manager.register_startup_hook(init_cache, priority=20)

# Execute startup (hooks run in priority order)
manager.startup()
```

**Raises:**
- `SemanticaError`: If startup fails

#### `shutdown()`

Execute shutdown sequence with registered hooks.

```python
def cleanup_database():
    print("Cleaning up database...")

manager.register_shutdown_hook(cleanup_database, priority=10)

# Graceful shutdown (continues even if hooks fail)
manager.shutdown(graceful=True)

# Force shutdown (stops on first error)
manager.shutdown(graceful=False)
```

**Parameters:**
- `graceful`: Whether to shutdown gracefully (default: True)

**Raises:**
- `SemanticaError`: If shutdown fails and graceful=False

#### `register_startup_hook()`

Register a startup hook.

```python
def my_startup_hook():
    # Your initialization code
    pass

# Lower priority = earlier execution
manager.register_startup_hook(my_startup_hook, priority=50)
```

**Parameters:**
- `hook_fn`: Function to call during startup (no arguments)
- `priority`: Hook priority (lower = earlier execution, default: 50)

#### `register_shutdown_hook()`

Register a shutdown hook.

```python
def my_shutdown_hook():
    # Your cleanup code
    pass

manager.register_shutdown_hook(my_shutdown_hook, priority=50)
```

**Parameters:**
- `hook_fn`: Function to call during shutdown (no arguments)
- `priority`: Hook priority (lower = earlier execution, default: 50)

#### `register_component()`

Register a component for health monitoring.

```python
class DatabaseConnection:
    def health_check(self):
        return {"healthy": True, "message": "Connected"}

db = DatabaseConnection()
manager.register_component("database", db)
```

**Parameters:**
- `name`: Component name
- `component`: Component instance

#### `health_check()`

Perform comprehensive system health check.

```python
health_results = manager.health_check()

for component_name, status in health_results.items():
    if status.healthy:
        print(f"{component_name}: ✓ {status.message}")
    else:
        print(f"{component_name}: ✗ {status.message}")
```

**Returns:**
- Dictionary mapping component names to `HealthStatus` objects

#### `get_health_summary()`

Get summary of system health.

```python
summary = manager.get_health_summary()

print(f"Total components: {summary['total_components']}")
print(f"Healthy: {summary['healthy_components']}")
print(f"Unhealthy: {summary['unhealthy_components']}")
print(f"System healthy: {summary['is_healthy']}")
```

**Returns:**
- Dictionary with health summary information

#### `get_state()`

Get current system state.

```python
state = manager.get_state()
print(f"Current state: {state.value}")  # uninitialized, ready, running, etc.
```

**Returns:**
- `SystemState`: Current system state enum

#### `is_ready()` / `is_running()`

Check system state.

```python
if manager.is_ready():
    print("System is ready")

if manager.is_running():
    print("System is running")
```

## PluginRegistry

Plugin registry and management system for dynamic plugin discovery and loading.

### Methods

#### `register_plugin()`

Manually register a plugin.

```python
from semantica.core import PluginRegistry

registry = PluginRegistry()

class MyPlugin:
    def initialize(self):
        print("Plugin initialized")
    
    def execute(self, data):
        return {"result": "processed"}

registry.register_plugin(
    plugin_name="my_plugin",
    plugin_class=MyPlugin,
    version="1.0.0",
    description="My custom plugin",
    author="John Doe",
    dependencies=["base_plugin"],
    capabilities=["processing", "transformation"]
)
```

**Parameters:**
- `plugin_name`: Name of the plugin
- `plugin_class`: Plugin class to register
- `version`: Plugin version (default: "1.0.0")
- `**metadata`: Additional plugin metadata

**Raises:**
- `ValidationError`: If plugin is invalid

#### `load_plugin()`

Load and initialize a plugin.

```python
# Auto-discover and load
registry = PluginRegistry(plugin_paths=["./plugins"])

# Load with configuration
plugin = registry.load_plugin(
    "my_plugin",
    api_key="xxx",
    host="localhost",
    port=8080
)

# Dependencies are automatically loaded first
plugin = registry.load_plugin("dependent_plugin")
```

**Parameters:**
- `plugin_name`: Name of the plugin to load
- `**config`: Plugin configuration passed to plugin constructor

**Returns:**
- Loaded and initialized plugin instance

**Raises:**
- `ConfigurationError`: If plugin not found, dependencies missing, or initialization fails

#### `unload_plugin()`

Unload a plugin.

```python
registry.unload_plugin("my_plugin")
```

**Parameters:**
- `plugin_name`: Name of plugin to unload

**Raises:**
- `ConfigurationError`: If plugin not loaded

#### `list_plugins()`

List all available plugins.

```python
plugins = registry.list_plugins()

for plugin_info in plugins:
    print(f"Name: {plugin_info['name']}")
    print(f"Version: {plugin_info['version']}")
    print(f"Loaded: {plugin_info['loaded']}")
    print(f"Dependencies: {plugin_info['dependencies']}")
```

**Returns:**
- List of plugin information dictionaries

#### `get_plugin_info()`

Get information about a specific plugin.

```python
info = registry.get_plugin_info("my_plugin")
print(f"Description: {info['description']}")
print(f"Author: {info['author']}")
print(f"Capabilities: {info['capabilities']}")
```

**Parameters:**
- `plugin_name`: Name of plugin

**Returns:**
- Dictionary with plugin information

**Raises:**
- `ConfigurationError`: If plugin not found

#### `is_plugin_loaded()`

Check if a plugin is loaded.

```python
if registry.is_plugin_loaded("my_plugin"):
    print("Plugin is loaded")
```

**Returns:**
- `bool`: True if plugin is loaded

#### `get_loaded_plugin()`

Get loaded plugin instance.

```python
plugin = registry.get_loaded_plugin("my_plugin")
if plugin:
    result = plugin.execute(data)
```

**Returns:**
- Plugin instance or None if not loaded

## MethodRegistry

Registry for custom orchestration methods.

### Methods

#### `register()`

Register a custom orchestration method.

```python
from semantica.core import method_registry

def custom_kb_builder(sources, **kwargs):
    # Custom knowledge base building logic
    return {"knowledge_graph": {}, "embeddings": []}

method_registry.register("knowledge_base", "custom", custom_kb_builder)
```

**Parameters:**
- `task`: Task type ("pipeline", "knowledge_base", "orchestration", "lifecycle")
- `name`: Method name
- `method_func`: Method function

#### `get()`

Get method by task and name.

```python
method = method_registry.get("knowledge_base", "custom")
if method:
    result = method(sources=["doc.pdf"])
```

**Parameters:**
- `task`: Task type
- `name`: Method name

**Returns:**
- Method function or None

#### `list_all()`

List all registered methods.

```python
# List all methods
all_methods = method_registry.list_all()
# Returns: {"knowledge_base": ["default", "custom"], "pipeline": ["default"]}

# List methods for specific task
kb_methods = method_registry.list_all("knowledge_base")
# Returns: {"knowledge_base": ["default", "custom"]}
```

**Parameters:**
- `task`: Optional task type to filter by

**Returns:**
- Dictionary mapping task types to method names

#### `unregister()`

Unregister a method.

```python
method_registry.unregister("knowledge_base", "custom")
```

**Parameters:**
- `task`: Task type
- `name`: Method name

#### `clear()`

Clear all registered methods.

```python
# Clear all methods
method_registry.clear()

# Clear methods for specific task
method_registry.clear("knowledge_base")
```

**Parameters:**
- `task`: Optional task type to clear (clears all if None)

## Orchestration Methods

Convenience functions for common orchestration tasks.

### `build_knowledge_base()`

Build knowledge base from data sources.

```python
from semantica.core.methods import build_knowledge_base

# Default method
result = build_knowledge_base(
    sources=["doc1.pdf", "doc2.docx"],
    method="default"
)

# Minimal method (no embeddings or graph)
result = build_knowledge_base(
    sources=["doc.pdf"],
    method="minimal"
)

# Full method (all features enabled)
result = build_knowledge_base(
    sources=["doc.pdf"],
    method="full",
    embeddings=True,
    graph=True
)

# With custom configuration
config = {"llm_provider": {"name": "openai"}}
result = build_knowledge_base(
    sources=["doc.pdf"],
    config=config,
    embeddings=True
)
```

**Parameters:**
- `sources`: Single source or list of sources
- `method`: Knowledge base construction method (default: "default")
- `config`: Optional configuration object or dictionary
- `**kwargs`: Additional options

**Returns:**
- Dictionary with knowledge base data

### `run_pipeline()`

Execute a processing pipeline.

```python
from semantica.core.methods import run_pipeline

result = run_pipeline(
    pipeline={"steps": ["parse", "extract"]},
    data="sample text",
    method="default"
)
```

**Parameters:**
- `pipeline`: Pipeline object or configuration dictionary
- `data`: Input data for pipeline
- `method`: Pipeline execution method (default: "default")
- `config`: Optional configuration object or dictionary
- `**kwargs`: Additional pipeline options

**Returns:**
- Dictionary with pipeline results

### `initialize_framework()`

Initialize Semantica framework.

```python
from semantica.core.methods import initialize_framework

# Default initialization
framework = initialize_framework()

# Minimal initialization (no plugins)
framework = initialize_framework(method="minimal")

# Full initialization
framework = initialize_framework(method="full", config=config_dict)
```

**Parameters:**
- `config`: Optional configuration object or dictionary
- `method`: Initialization method (default: "default")
- `**kwargs`: Additional initialization options

**Returns:**
- Initialized `Semantica` framework instance

### `get_status()`

Get system status.

```python
from semantica.core.methods import get_status

# Default status
status = get_status(framework=my_framework)

# Summary status
status = get_status(framework=my_framework, method="summary")

# Detailed status
status = get_status(framework=my_framework, method="detailed")
```

**Parameters:**
- `framework`: Optional Semantica framework instance (creates new if None)
- `method`: Status retrieval method (default: "default")
- `**kwargs`: Additional options

**Returns:**
- Dictionary with system status

### `get_orchestration_method()`

Get orchestration method by task and name.

```python
from semantica.core.methods import get_orchestration_method

method = get_orchestration_method("knowledge_base", "custom")
if method:
    result = method(sources=["doc.pdf"])
```

**Parameters:**
- `task`: Task type
- `name`: Method name

**Returns:**
- Method function or None

### `list_available_methods()`

List all available orchestration methods.

```python
from semantica.core.methods import list_available_methods

# List all methods
all_methods = list_available_methods()

# List methods for specific task
kb_methods = list_available_methods("knowledge_base")
```

**Parameters:**
- `task`: Optional task type to filter by

**Returns:**
- Dictionary mapping task types to method names

## Convenience Functions

### Module-level `build()` Function

Convenience function for building knowledge bases.

```python
from semantica.core import build

result = build(
    sources=["doc1.pdf", "doc2.docx"],
    extract_entities=True,
    extract_relations=True,
    embeddings=True,
    graph=True
)
```

**Parameters:**
- `sources`: Input source or list of sources
- `extract_entities`: Whether to extract named entities (default: True)
- `extract_relations`: Whether to extract relationships (default: True)
- `embeddings`: Whether to generate embeddings (default: True)
- `graph`: Whether to build knowledge graph (default: True)
- `**options`: Additional processing options

**Returns:**
- Dictionary with knowledge base data

## Configuration

### Environment Variables

Configuration can be loaded from environment variables with `SEMANTICA_` prefix:

```bash
export SEMANTICA_PROCESSING_BATCH_SIZE=64
export SEMANTICA_LLM_PROVIDER_MODEL=gpt-4
export SEMANTICA_QUALITY_MIN_CONFIDENCE=0.8
```

### YAML Configuration File

```yaml
llm_provider:
  name: openai
  model: gpt-4
  api_key: ${OPENAI_API_KEY}

embedding_model:
  name: openai
  model: text-embedding-ada-002

processing:
  batch_size: 32
  max_workers: 4

quality:
  min_confidence: 0.7

logging:
  level: INFO

plugins:
  my_plugin:
    enabled: true
    config_key: config_value
```

### JSON Configuration File

```json
{
  "llm_provider": {
    "name": "openai",
    "model": "gpt-4o-mini"
  },
  "processing": {
    "batch_size": 32
  }
}
```

### Loading Configuration

```python
from semantica.core import ConfigManager

manager = ConfigManager()

# Load from file
config = manager.load_from_file("config.yaml")

# Load from dictionary
config = manager.load_from_dict({"processing": {"batch_size": 64}})

# Use with framework
from semantica.core import Semantica
framework = Semantica(config=config)
```

## Advanced Examples

### Custom Plugin Development

```python
from semantica.core import PluginRegistry

class CustomProcessor:
    def initialize(self):
        print("Custom processor initialized")
    
    def execute(self, data):
        # Process data
        return {"processed": True, "data": data}

# Register plugin
registry = PluginRegistry()
registry.register_plugin(
    plugin_name="custom_processor",
    plugin_class=CustomProcessor,
    version="1.0.0",
    description="Custom data processor",
    capabilities=["processing"]
)

# Load and use
processor = registry.load_plugin("custom_processor")
result = processor.execute("sample data")
```

### Custom Orchestration Method

```python
from semantica.core import method_registry
from semantica.core import Semantica

def fast_kb_builder(sources, **kwargs):
    """Fast knowledge base builder with minimal processing."""
    framework = Semantica()
    framework.initialize()
    
    try:
        result = framework.build_knowledge_base(
            sources=sources,
            embeddings=False,  # Skip embeddings for speed
            graph=True,
            **kwargs
        )
        return result
    finally:
        framework.shutdown()

# Register custom method
method_registry.register("knowledge_base", "fast", fast_kb_builder)

# Use custom method
from semantica.core.methods import build_knowledge_base
result = build_knowledge_base(sources=["doc.pdf"], method="fast")
```

### Lifecycle Hooks

```python
from semantica.core import LifecycleManager

manager = LifecycleManager()

# Register startup hooks with priorities
def init_logging():
    print("Initializing logging...")

def init_database():
    print("Initializing database...")

def init_cache():
    print("Initializing cache...")

manager.register_startup_hook(init_logging, priority=10)  # Runs first
manager.register_startup_hook(init_database, priority=20)  # Runs second
manager.register_startup_hook(init_cache, priority=30)    # Runs third

# Register shutdown hooks
def cleanup_cache():
    print("Cleaning up cache...")

def cleanup_database():
    print("Cleaning up database...")

manager.register_shutdown_hook(cleanup_cache, priority=10)   # Runs first
manager.register_shutdown_hook(cleanup_database, priority=20)  # Runs second

# Execute lifecycle
manager.startup()
# ... do work ...
manager.shutdown(graceful=True)
```

### Component Health Monitoring

```python
from semantica.core import LifecycleManager

class DatabaseComponent:
    def __init__(self):
        self.connected = False
    
    def connect(self):
        self.connected = True
    
    def health_check(self):
        return {
            "healthy": self.connected,
            "message": "Connected" if self.connected else "Not connected"
        }

manager = LifecycleManager()

# Register component
db = DatabaseComponent()
db.connect()
manager.register_component("database", db)

# Check health
health = manager.health_check()
for name, status in health.items():
    print(f"{name}: {status.healthy} - {status.message}")

# Get health summary
summary = manager.get_health_summary()
print(f"System healthy: {summary['is_healthy']}")
```

### Configuration Merging

```python
from semantica.core import ConfigManager

manager = ConfigManager()

# Load base configuration
base_config = manager.load_from_file("base_config.yaml")

# Load environment-specific overrides
dev_config = manager.load_from_file("dev_config.yaml")

# Load runtime overrides
runtime_config = manager.load_from_dict({
    "processing": {"batch_size": 128}
})

# Merge (later configs override earlier ones)
merged = manager.merge_configs(base_config, dev_config, runtime_config)

# Use merged configuration
from semantica.core import Semantica
framework = Semantica(config=merged)
```

## Best Practices

1. **Always Initialize**: Always call `initialize()` after creating a `Semantica` instance before using it.

2. **Graceful Shutdown**: Always call `shutdown(graceful=True)` in a `finally` block to ensure proper cleanup.

3. **Configuration Management**: Use `ConfigManager` for loading and managing configurations. Prefer YAML files for complex configurations.

4. **Error Handling**: Wrap framework operations in try-except blocks to handle `ConfigurationError` and `ProcessingError` appropriately.

5. **Health Monitoring**: Register components with `LifecycleManager` for health monitoring and use `health_check()` regularly.

6. **Plugin Development**: Follow the plugin interface (must have `initialize()` and `execute()` methods) when creating custom plugins.

7. **Method Registration**: Use `MethodRegistry` for extensibility. Register custom methods for knowledge base building, pipeline execution, etc.

8. **Hook Priorities**: Use appropriate priorities for lifecycle hooks. Lower numbers execute first.

9. **Configuration Validation**: Always validate configurations using `config.validate()` before using them.

10. **Resource Cleanup**: Ensure all resources are properly cleaned up in shutdown hooks.

### Example: Complete Workflow

```python
from semantica.core import Semantica, ConfigManager

# 1. Load configuration
config_manager = ConfigManager()
config = config_manager.load_from_file("config.yaml")

# 2. Initialize framework
framework = Semantica(config=config)

try:
    # 3. Initialize all components
    framework.initialize()
    
    # 4. Check system health
    status = framework.get_status()
    if not status['health']['is_healthy']:
        print("Warning: Some components are unhealthy")
    
    # 5. Build knowledge base
    result = framework.build_knowledge_base(
        sources=["doc1.pdf", "doc2.docx"],
        embeddings=True,
        graph=True
    )
    
    # 6. Process results
    print(f"Processed {result['statistics']['sources_processed']} sources")
    print(f"Knowledge graph has {len(result['knowledge_graph'].get('entities', []))} entities")
    
    # 7. Run pipeline
    pipeline_result = framework.run_pipeline(
        pipeline={"steps": ["extract", "normalize"]},
        data="sample text"
    )
    
finally:
    # 8. Always shutdown gracefully
    framework.shutdown(graceful=True)
```

This completes the comprehensive usage guide for the core module. All classes, methods, and their usage patterns are documented with examples.
