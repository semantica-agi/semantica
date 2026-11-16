"""
Main Orchestrator Module

The Semantica orchestrator coordinates all framework components and manages
the overall execution flow.

This module provides the main entry point for the Semantica framework, handling:
- Framework initialization and lifecycle management
- Knowledge base construction from various data sources
- Pipeline execution and resource management
- Plugin system coordination
- System health monitoring

Example Usage:
    >>> from semantica.core import Semantica
    >>> framework = Semantica()
    >>> result = framework.build_knowledge_base(
    ...     sources=["doc1.pdf", "doc2.docx"],
    ...     embeddings=True,
    ...     graph=True
    ... )

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger, log_execution_time
from ..utils.progress_tracker import get_progress_tracker
from .config_manager import Config, ConfigManager
from .lifecycle import LifecycleManager
from .plugin_registry import PluginRegistry


class Semantica:
    """
    Main Semantica framework class.

    This is the primary entry point for using the framework. It coordinates
    all modules and provides a unified API for semantic processing.

    Attributes:
        config: Configuration object
        config_manager: Configuration management system
        plugin_registry: Plugin management system
        lifecycle_manager: Lifecycle management

    Methods:
        initialize(): Initialize all framework components
        build_knowledge_base(): Build knowledge base from sources
        run_pipeline(): Execute processing pipeline
        get_status(): Get system health and status
    """

    def __init__(
        self, config: Optional[Union[Config, Dict[str, Any]]] = None, **kwargs
    ):
        """
        Initialize Semantica framework.

        Args:
            config: Configuration object or dict
            **kwargs: Additional configuration parameters
        """
        self.logger = get_logger("semantica")
        self.config_manager = ConfigManager()

        # Load configuration
        if isinstance(config, Config):
            self.config = config
        elif isinstance(config, dict):
            self.config = self.config_manager.load_from_dict(config)
        else:
            # Load from kwargs or defaults
            self.config = self.config_manager.load_from_dict(kwargs or {})

        # Initialize core components
        self.lifecycle_manager = LifecycleManager()
        self.plugin_registry = PluginRegistry()

        # Register lifecycle manager with itself
        self.lifecycle_manager.register_component(
            "lifecycle_manager", self.lifecycle_manager
        )
        self.lifecycle_manager.register_component(
            "plugin_registry", self.plugin_registry
        )
        self.lifecycle_manager.register_component("config_manager", self.config_manager)

        # Configure global provenance storage path if specified
        try:
            # Config.get() already resolves dotted paths against nested dicts
            # (see get_nested_value), so this single lookup covers both
            # top-level and config.provenance={"storage_path": ...} shapes.
            prov_storage_path = self.config.get("provenance.storage_path")
            if prov_storage_path:
                from ..provenance import ProvenanceManager
                ProvenanceManager.set_default_storage_path(prov_storage_path)
        except Exception as e:
            self.logger.warning(f"Failed to configure provenance storage: {e}")

        # Module placeholders (to be initialized)
        self._modules: Dict[str, Any] = {}
        self._initialized: bool = False

        # Initialize progress tracker (automatic, zero configuration)
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.info("Semantica framework initialized")

    @property
    def embedding_generator(self) -> Any:
        """
        Get the framework's embedding generator.

        Returns:
            EmbeddingGenerator instance
        """
        if "embedding_generator" not in self._modules:
            try:
                from ..embeddings import EmbeddingGenerator
                self._modules["embedding_generator"] = EmbeddingGenerator(
                    config=self.config.get("embedding", {})
                )
            except (ImportError, OSError) as e:
                self.logger.warning(f"Could not import EmbeddingGenerator: {e}")
                raise ProcessingError(f"Embeddings module not available: {e}")
        return self._modules["embedding_generator"]

    @property
    def reasoner(self) -> Any:
        """
        Get the framework's graph reasoner.

        Returns:
            GraphReasoner instance
        """
        if "reasoner" not in self._modules:
            try:
                from ..reasoning import GraphReasoner
                self._modules["reasoner"] = GraphReasoner(config=self.config)
            except (ImportError, OSError) as e:
                self.logger.warning(f"Could not import GraphReasoner: {e}")
                raise ProcessingError(f"Reasoning module not available: {e}")
        return self._modules["reasoner"]

    @property
    def graph_builder(self) -> Any:
        """
        Get the framework's knowledge graph builder.

        Returns:
            GraphBuilder instance
        """
        if "graph_builder" not in self._modules:
            try:
                from ..kg import GraphBuilder
                self._modules["graph_builder"] = GraphBuilder(
                    config=self.config.get("kg", {})
                )
            except (ImportError, OSError) as e:
                self.logger.warning(f"Could not import GraphBuilder: {e}")
                raise ProcessingError(f"KG module not available: {e}")
        return self._modules["graph_builder"]

    @property
    def document_parser(self) -> Any:
        """
        Get the framework's document parser.

        Returns:
            DocumentParser instance
        """
        if "document_parser" not in self._modules:
            try:
                from ..parse import DocumentParser
                self._modules["document_parser"] = DocumentParser(
                    config=self.config.get("parse", {})
                )
            except (ImportError, OSError) as e:
                self.logger.warning(f"Could not import DocumentParser: {e}")
                raise ProcessingError(f"Parse module not available: {e}")
        return self._modules["document_parser"]

    @property
    def file_ingestor(self) -> Any:
        """
        Get the framework's file ingestor.

        Returns:
            FileIngestor instance
        """
        if "file_ingestor" not in self._modules:
            try:
                from ..ingest import FileIngestor
                self._modules["file_ingestor"] = FileIngestor(
                    config=self.config.get("ingest", {})
                )
            except (ImportError, OSError) as e:
                self.logger.warning(f"Could not import FileIngestor: {e}")
                raise ProcessingError(f"Ingest module not available: {e}")
        return self._modules["file_ingestor"]

    @property
    def pipeline_builder(self) -> Any:
        """
        Get the framework's pipeline builder.

        Returns:
            PipelineBuilder instance
        """
        if "pipeline_builder" not in self._modules:
            try:
                from ..pipeline import PipelineBuilder
                self._modules["pipeline_builder"] = PipelineBuilder(
                    config=self.config.get("pipeline", {})
                )
            except (ImportError, OSError) as e:
                self.logger.warning(f"Could not import PipelineBuilder: {e}")
                raise ProcessingError(f"Pipeline module not available: {e}")
        return self._modules["pipeline_builder"]

    @log_execution_time
    def initialize(self) -> None:
        """
        Initialize all framework components.

        This method sets up all modules, loads plugins, and prepares
        the system for processing.

        Raises:
            ConfigurationError: If configuration is invalid
            SemanticaError: If initialization fails
        """
        try:
            self.logger.info("Initializing Semantica framework")

            # Validate configuration
            self.config.validate()

            # Register startup hooks
            self._register_startup_hooks()

            # Execute startup sequence
            self.lifecycle_manager.startup()

            # Initialize modules
            self._initialize_modules()

            # Load plugins if configured
            if self.config.get("plugins", {}):
                self._load_plugins()

            # Run health checks
            health_summary = self.lifecycle_manager.get_health_summary()
            if not health_summary["is_healthy"]:
                self.logger.warning(
                    "Some components are unhealthy",
                    extra={"health_summary": health_summary},
                )

            self._initialized = True
            self.logger.info("Semantica framework initialization completed")

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise

    def _ensure_initialized(self) -> None:
        """Ensure framework is initialized (lazy initialization)."""
        if not self._initialized:
            self.initialize()

    @log_execution_time
    def build_knowledge_base(
        self, sources: List[Union[str, Path]], **kwargs
    ) -> Dict[str, Any]:
        """
        Build knowledge base from data sources.

        This is a high-level method that orchestrates the complete
        knowledge base construction process.

        Args:
            sources: List of data sources (files, URLs, streams)
            **kwargs: Additional processing options:
                - pipeline: Custom pipeline configuration
                - pipeline_id: Optional pipeline ID for progress tracking
                - embeddings: Whether to generate embeddings
                - graph: Whether to build knowledge graph
                - normalize: Whether to normalize data

        Returns:
            Dictionary containing:
                - knowledge_graph: Knowledge graph data
                - embeddings: Embedding vectors
                - metadata: Processing metadata
                - statistics: Processing statistics

        Raises:
            ProcessingError: If processing fails
        """
        # Auto-initialize if not already initialized
        self._ensure_initialized()

        # Extract or generate pipeline_id
        pipeline_id = kwargs.get("pipeline_id")
        if not pipeline_id:
            # Generate a unique pipeline ID
            import uuid
            pipeline_id = f"kb_build_{uuid.uuid4().hex[:8]}"

        # Start overall progress tracking
        overall_tracking_id = self.progress_tracker.start_tracking(
            module="core",
            submodule="Semantica",
            message=f"Building knowledge base from {len(sources)} sources",
            pipeline_id=pipeline_id,
        )

        try:
            self.logger.info(f"Building knowledge base from {len(sources)} sources")

            # Validate sources
            validated_sources = self._validate_sources(sources)

            # Create processing pipeline
            pipeline_config = kwargs.get("pipeline", {})
            pipeline = self._create_pipeline(pipeline_config)
            
            # Register pipeline modules for progress tracking
            if hasattr(pipeline, 'steps') and pipeline.steps:
                module_list = []
                module_order = {}
                for idx, step in enumerate(pipeline.steps):
                    module_name = getattr(step, 'module', None) or getattr(step, 'name', None) or str(step)
                    if module_name and module_name not in module_list:
                        module_list.append(module_name)
                        module_order[module_name] = idx
                
                if module_list:
                    self.progress_tracker.register_pipeline_modules(
                        pipeline_id=pipeline_id,
                        module_list=module_list,
                        module_order=module_order
                    )

            # Process sources
            results = []
            total_sources = len(validated_sources)
            update_interval = max(1, total_sources // 20)  # Update every 5%
            
            for idx, source in enumerate(validated_sources, 1):
                try:
                    # Track file processing
                    file_str = str(source)
                    file_tracking_id = self.progress_tracker.start_tracking(
                        file=file_str,
                        module="core",
                        submodule="build_knowledge_base",
                        message=f"Processing {Path(file_str).name if file_str else 'source'}",
                        pipeline_id=pipeline_id,
                    )
                    try:
                        result = self.run_pipeline(pipeline, source)
                        results.append(result)
                        self.progress_tracker.stop_tracking(
                            file_tracking_id, status="completed"
                        )
                    except Exception as e:
                        self.progress_tracker.stop_tracking(
                            file_tracking_id, status="failed", message=str(e)
                        )
                        self.logger.error(f"Failed to process source {source}: {e}")
                        if kwargs.get("fail_fast", False):
                            raise ProcessingError(
                                f"Failed to process source {source}: {e}"
                            )
                    
                    # Update overall progress
                    if idx % update_interval == 0 or idx == total_sources:
                        self.progress_tracker.update_progress(
                            overall_tracking_id,
                            processed=idx,
                            total=total_sources,
                            message=f"Processing sources... {idx}/{total_sources}"
                        )
                except Exception as e:
                    self.logger.error(f"Failed to process source {source}: {e}")
                    if kwargs.get("fail_fast", False):
                        raise ProcessingError(f"Failed to process source {source}: {e}")

            # Build knowledge graph if requested
            knowledge_graph = None
            if kwargs.get("graph", True):
                knowledge_graph = self._build_knowledge_graph(results)

            # Generate embeddings if requested
            embeddings = None
            if kwargs.get("embeddings", True):
                embeddings = self._generate_embeddings(results)

            # Compile statistics
            statistics = {
                "sources_processed": len(results),
                "sources_total": len(sources),
                "success_rate": len([r for r in results if r.get("success")])
                / len(results)
                if results
                else 0.0,
            }

            # Stop overall tracking
            self.progress_tracker.stop_tracking(
                overall_tracking_id,
                status="completed",
                message=f"Processed {len(results)} sources",
            )

            # Clear pipeline context when complete
            self.progress_tracker.clear_pipeline_context(pipeline_id)

            # Show summary
            self.progress_tracker.show_summary()

            return {
                "knowledge_graph": knowledge_graph,
                "embeddings": embeddings,
                "results": results,
                "statistics": statistics,
                "metadata": {
                    "sources": validated_sources,
                    "pipeline": pipeline_config,
                    "pipeline_id": pipeline_id,
                },
            }

        except Exception as e:
            self.progress_tracker.stop_tracking(
                overall_tracking_id, status="failed", message=str(e)
            )
            # Clear pipeline context on failure
            self.progress_tracker.clear_pipeline_context(pipeline_id)
            self.logger.error(f"Failed to build knowledge base: {e}")
            raise ProcessingError(f"Failed to build knowledge base: {e}")

    @log_execution_time
    def run_pipeline(
        self, pipeline: Union[Dict[str, Any], Any], data: Any
    ) -> Dict[str, Any]:
        """
        Execute a processing pipeline.

        Args:
            pipeline: Pipeline object or configuration dictionary
            data: Input data for pipeline

        Returns:
            Dictionary containing:
                - output: Pipeline output data
                - metadata: Processing metadata
                - metrics: Performance metrics

        Raises:
            ProcessingError: If pipeline execution fails
        """
        pipeline_tracking_id = None
        try:
            self.logger.info("Executing processing pipeline")

            pipeline_tracking_id = self.progress_tracker.start_tracking(
                file=str(data) if isinstance(data, (str, Path)) else None,
                module="pipeline",
                submodule="ExecutionEngine",
                message="Executing pipeline",
            )

            if isinstance(pipeline, dict):
                pipeline = self._create_pipeline_from_dict(pipeline)

            execution_engine = None
            execution_result = None

            try:
                from ..pipeline import ExecutionEngine, Pipeline

                if isinstance(pipeline, Pipeline):
                    execution_engine = ExecutionEngine()
            except (ImportError, OSError):
                execution_engine = None

            if execution_engine is None and not hasattr(pipeline, "execute"):
                raise ProcessingError(
                    "Pipeline must be a Pipeline object or have execute() method"
                )

            resources = self._allocate_resources(pipeline)

            try:
                if execution_engine is not None:
                    execution_result = execution_engine.execute_pipeline(
                        pipeline, data
                    )
                    success = execution_result.success
                    output = execution_result.output
                    metrics = execution_result.metrics
                else:
                    output = pipeline.execute(data)
                    metrics = self._collect_metrics(pipeline)
                    success = True

                if pipeline_tracking_id:
                    self.progress_tracker.stop_tracking(
                        pipeline_tracking_id, status="completed"
                    )

                return {
                    "success": success,
                    "output": output,
                    "metrics": metrics,
                    "metadata": {
                        "pipeline": str(pipeline),
                        "resources": resources,
                    },
                }

            finally:
                self._release_resources(resources)

        except Exception as e:
            if pipeline_tracking_id:
                self.progress_tracker.stop_tracking(
                    pipeline_tracking_id, status="failed", message=str(e)
                )
            self.logger.error(f"Pipeline execution failed: {e}")
            raise ProcessingError(f"Pipeline execution failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get system health and status.

        Returns:
            Dictionary containing:
                - state: System state
                - health: Health summary
                - modules: Module status
                - plugins: Plugin status
                - metrics: System metrics
        """
        health_summary = self.lifecycle_manager.get_health_summary()

        # Get module status
        module_status = {}
        for name, module in self._modules.items():
            module_status[name] = {
                "initialized": module is not None,
                "status": "ready" if module else "not_initialized",
            }

        # Get plugin status
        plugin_status = {}
        try:
            plugins = self.plugin_registry.list_plugins()
            for plugin_info in plugins:
                plugin_status[plugin_info.get("name", "unknown")] = {
                    "loaded": plugin_info.get("loaded", False),
                    "version": plugin_info.get("version", "unknown"),
                }
        except Exception as e:
            self.logger.warning(f"Failed to get plugin status: {e}")

        return {
            "state": self.lifecycle_manager.get_state().value,
            "health": health_summary,
            "modules": module_status,
            "plugins": plugin_status,
            "config": {
                "loaded": self.config is not None,
                "validated": True,  # Assuming validated if initialized
            },
        }

    def shutdown(self, graceful: bool = True) -> None:
        """
        Shutdown the framework.

        Args:
            graceful: Whether to shutdown gracefully (default: True)
        """
        self.logger.info("Shutting down Semantica framework")
        self.lifecycle_manager.shutdown(graceful=graceful)
        self.logger.info("Semantica framework shutdown completed")

    def _register_startup_hooks(self) -> None:
        """
        Register framework startup hooks.

        This method registers all framework-level startup hooks that execute
        during initialization. Hooks are registered with specific priorities
        to ensure correct execution order.

        Registered Hooks:
            - Config validation (priority 10): Validates configuration before other operations
            - Module initialization (priority 30): Initializes framework modules
        """

        # Register config validation hook (high priority - runs first)
        def validate_config_hook():
            """Validate configuration during startup."""
            self.config.validate()

        self.lifecycle_manager.register_startup_hook(validate_config_hook, priority=10)

        # Register module initialization hook (lower priority - runs after validation)
        def initialize_modules_hook():
            """Initialize framework modules during startup."""
            self._initialize_modules()

        self.lifecycle_manager.register_startup_hook(
            initialize_modules_hook, priority=30
        )

    def _initialize_modules(self) -> None:
        """
        Initialize framework modules.

        This method attempts to import and verify availability of key framework
        modules. It's called during startup to ensure modules are ready for use.
        Import failures are logged but don't stop initialization (modules may be optional).

        Modules Checked:
            - GraphBuilder: Knowledge graph construction
            - PipelineBuilder: Processing pipeline creation
            - FileIngestor: File ingestion capabilities
            - DocumentParser: Document parsing capabilities
        """
        try:
            # Import key modules to verify they're available
            # These imports don't create instances, just verify module availability
            from ..ingest import FileIngestor  # noqa: F401
            from ..kg import GraphBuilder  # noqa: F401
            from ..parse import DocumentParser  # noqa: F401
            from ..pipeline import PipelineBuilder  # noqa: F401

            self.logger.debug("Framework modules verified and available")
        except (ImportError, OSError) as e:
            # Log but don't fail - modules may be optional or not installed
            self.logger.warning(
                f"Some framework modules could not be imported: {e}. "
                "They may be optional or not installed."
            )

    def _load_plugins(self) -> None:
        """
        Load configured plugins from configuration.

        This method reads the plugin configuration from the framework config
        and loads each plugin using the plugin registry. Plugin loading failures
        are logged but don't stop the initialization process.

        Configuration Format:
            plugins:
                plugin_name:
                    config_key: config_value
                    ...
        """
        plugins_config = self.config.get("plugins", {})

        if not plugins_config:
            self.logger.debug("No plugins configured")
            return

        self.logger.info(f"Loading {len(plugins_config)} configured plugin(s)")

        for plugin_name, plugin_config in plugins_config.items():
            try:
                # Load plugin with its configuration
                self.plugin_registry.load_plugin(plugin_name, **plugin_config)
                self.logger.info(f"Successfully loaded plugin: {plugin_name}")
            except Exception as e:
                # Log error but continue loading other plugins
                self.logger.error(
                    f"Failed to load plugin '{plugin_name}': {e}. "
                    "Continuing with other plugins."
                )

    def _validate_sources(
        self, sources: List[Union[str, Path]]
    ) -> List[Union[str, Path]]:
        """
        Validate and filter data sources.

        This method checks if sources exist (for file paths) or are valid URLs.
        Invalid sources are logged as warnings but don't stop processing.

        Args:
            sources: List of source paths or URLs to validate

        Returns:
            List of validated sources

        Raises:
            ProcessingError: If no valid sources are found
        """
        validated_sources = []

        for source in sources:
            # Convert string to Path for easier handling
            source_path = Path(source) if isinstance(source, str) else source

            # Check if source is valid:
            # 1. File path exists on filesystem
            # 2. URL starts with http:// or https://
            is_valid_file = source_path.exists()
            is_valid_url = isinstance(source, str) and source.startswith(
                ("http://", "https://")
            )

            if is_valid_file or is_valid_url:
                validated_sources.append(source)
            else:
                self.logger.warning(
                    f"Source not found or invalid: {source}. " "Skipping this source."
                )

        # Ensure we have at least one valid source
        if not validated_sources:
            error_msg = (
                f"No valid sources provided. "
                f"Checked {len(sources)} source(s), all were invalid."
            )
            raise ProcessingError(error_msg)

        return validated_sources

    def _create_pipeline(self, pipeline_config: Dict[str, Any]) -> Any:
        """
        Create processing pipeline from configuration.

        This method creates a pipeline instance from the provided configuration.
        The actual pipeline creation is delegated to the pipeline module.

        Args:
            pipeline_config: Pipeline configuration dictionary

        Returns:
            Pipeline object or configuration dict (if pipeline module not available)
        """
        try:
            # Build each pipeline on a fresh builder. PipelineBuilder keeps the
            # steps it is given, so reusing the cached one would add a second
            # "default_step" on the next call and fail validation. Handlers
            # registered on the shared builder are carried over.
            from ..pipeline import PipelineBuilder

            shared_builder = self.pipeline_builder
            builder = PipelineBuilder(config=dict(self.config.get("pipeline", {})))
            builder.step_registry.update(shared_builder.step_registry)

            if not pipeline_config:
                builder.add_step("default_step", "default")
                return builder.build("default_pipeline")

            steps_config = pipeline_config.get("steps")

            if isinstance(steps_config, list) and steps_config and isinstance(
                steps_config[0], str
            ):
                converted_steps = [
                    {"name": name, "type": name, "config": {}}
                    for name in steps_config
                ]
                normalized_config: Dict[str, Any] = {
                    "name": pipeline_config.get("name", "default_pipeline"),
                    "steps": converted_steps,
                }
                if "parallelism" in pipeline_config:
                    normalized_config["parallelism"] = pipeline_config["parallelism"]
                return builder.build_pipeline(normalized_config)

            if "steps" in pipeline_config:
                return builder.build_pipeline(pipeline_config)

            builder.add_step("default_step", "default")
            return builder.build("default_pipeline")
        except (ImportError, OSError, ProcessingError):
            self.logger.debug("Pipeline module not available, using config directly")
            return pipeline_config

    def _create_pipeline_from_dict(self, pipeline_dict: Dict[str, Any]) -> Any:
        """
        Create pipeline object from dictionary configuration.

        Args:
            pipeline_dict: Dictionary containing pipeline configuration

        Returns:
            Pipeline object or dict if pipeline module not available
        """
        return self._create_pipeline(pipeline_dict)

    def _build_knowledge_graph(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build knowledge graph from processing results.

        This method extracts entities and relationships from processing results
        and constructs a knowledge graph structure.

        Args:
            results: List of processing results containing entities and relationships

        Returns:
            Dictionary containing knowledge graph structure
        """
        try:
            # Extract entities and relationships from results
            graph_sources = []
            for result in results:
                if isinstance(result, dict):
                    source_data = {}
                    if "entities" in result:
                        source_data["entities"] = result["entities"]
                    if "relationships" in result:
                        source_data["relationships"] = result["relationships"]
                    if source_data:
                        graph_sources.append(source_data)

            if not graph_sources:
                self.logger.warning("No entities or relationships found in results")
                return {"entities": [], "relationships": [], "metadata": {}}

            # Track knowledge graph building
            kg_tracking_id = self.progress_tracker.start_tracking(
                module="kg",
                submodule="GraphBuilder",
                message="Building knowledge graph",
            )

            try:
                # Build knowledge graph using the lazy property
                knowledge_graph = self.graph_builder.build(graph_sources)
                self.progress_tracker.stop_tracking(kg_tracking_id, status="completed")
                return knowledge_graph
            except Exception as e:
                self.progress_tracker.stop_tracking(
                    kg_tracking_id, status="failed", message=str(e)
                )
                raise

        except (ImportError, OSError, ProcessingError):
            self.logger.warning("KG module not available, returning placeholder")
            return {"status": "placeholder", "results": results}

    def _generate_embeddings(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate embeddings from processing results.

        This method extracts text content from processing results and generates
        embeddings using the embeddings module.

        Args:
            results: List of processing results containing text content

        Returns:
            Dictionary containing generated embeddings
        """
        try:
            # Extract text content from results
            texts_to_embed = []
            for result in results:
                if isinstance(result, dict):
                    # Try to find text content in various possible keys
                    text = (
                        result.get("text")
                        or result.get("content")
                        or result.get("output", {}).get("text")
                        if isinstance(result.get("output"), dict)
                        else None
                    )
                    if text:
                        texts_to_embed.append(text)

            if not texts_to_embed:
                self.logger.warning("No text content found in results for embedding")
                return {"embeddings": [], "metadata": {}}

            # Track embedding generation
            embed_tracking_id = self.progress_tracker.start_tracking(
                module="embeddings",
                submodule="EmbeddingGenerator",
                message=f"Generating embeddings for {len(texts_to_embed)} texts",
            )

            try:
                # Generate embeddings using the lazy property
                embeddings_result = self.embedding_generator.process_batch(texts_to_embed)
                self.progress_tracker.stop_tracking(
                    embed_tracking_id,
                    status="completed",
                    message=f"Generated {embeddings_result.get('success_count', 0)} embeddings",
                )

                return {
                    "embeddings": embeddings_result["embeddings"],
                    "metadata": {
                        "total_texts": len(texts_to_embed),
                        "successful": embeddings_result["success_count"],
                        "failed": embeddings_result["failure_count"],
                    },
                }
            except Exception as e:
                self.progress_tracker.stop_tracking(
                    embed_tracking_id, status="failed", message=str(e)
                )
                raise

        except (ImportError, OSError, ProcessingError):
            self.logger.warning(
                "Embeddings module not available, returning placeholder"
            )
            return {"status": "placeholder", "results": results}

    def _allocate_resources(self, pipeline: Any) -> Dict[str, Any]:
        """
        Allocate resources for pipeline execution.

        This method prepares and allocates necessary resources (connections,
        memory, etc.) for pipeline execution. Currently returns a placeholder
        but can be extended for actual resource management.

        Args:
            pipeline: Pipeline object that will be executed

        Returns:
            Dictionary containing resource allocation information:
                - allocated: Whether resources were successfully allocated
                - resources: List of allocated resource references (optional)
        """
        # Placeholder for resource allocation logic
        # Can be extended to allocate database connections, file handles, etc.
        return {"allocated": True, "resources": []}

    def _release_resources(self, resources: Dict[str, Any]) -> None:
        """
        Release allocated resources safely.

        This method ensures all resources (connections, files, etc.) are properly
        closed and cleaned up, even if errors occur during cleanup.

        Args:
            resources: Dictionary containing resource references to release
        """
        if not resources:
            return

        # Release database/network connections
        connections = resources.get("connections", [])
        for connection in connections:
            try:
                if hasattr(connection, "close"):
                    connection.close()
                    self.logger.debug("Closed connection resource")
            except Exception as e:
                self.logger.warning(f"Error closing connection: {e}")

        # Release file handles
        file_handles = resources.get("files", [])
        for file_handle in file_handles:
            try:
                if hasattr(file_handle, "close"):
                    file_handle.close()
                    self.logger.debug("Closed file resource")
            except Exception as e:
                self.logger.warning(f"Error closing file: {e}")

        # Clear resource dictionary to prevent reuse
        resources.clear()
        self.logger.debug("All resources released")

    def _collect_metrics(self, pipeline: Any) -> Dict[str, Any]:
        """
        Collect performance metrics from pipeline execution.

        This method gathers execution metrics such as execution time, memory usage,
        and other performance indicators from the pipeline.

        Args:
            pipeline: Pipeline object that was executed

        Returns:
            Dictionary containing performance metrics
        """
        metrics = {"execution_time": 0.0, "memory_usage": 0, "cpu_usage": 0.0}

        # Try to get metrics from pipeline if it has them
        try:
            if hasattr(pipeline, "get_metrics"):
                pipeline_metrics = pipeline.get_metrics()
                metrics.update(pipeline_metrics)
        except Exception as e:
            self.logger.debug(f"Pipeline metrics not available: {e}")

        # Try to get system metrics using psutil (optional dependency)
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            metrics["memory_usage"] = memory_info.rss  # Resident Set Size in bytes

            # Get CPU usage (non-blocking)
            try:
                cpu_percent = process.cpu_percent(interval=0.1)
                metrics["cpu_usage"] = cpu_percent
            except Exception:
                # CPU percent may not be available immediately
                pass

        except (ImportError, OSError):
            # psutil not available, use basic metrics
            self.logger.debug("psutil not available, using basic metrics")
        except Exception as e:
            self.logger.debug(f"Error collecting system metrics: {e}")

        return metrics
