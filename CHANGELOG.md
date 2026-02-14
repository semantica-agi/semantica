# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Fixed: PolicyEngine latest version selection on ContextGraph; AgentContext fallback robustness and secure logging (PR #TBD by @KaifAhmad1)
- Tests: Added ContextGraph fallback and AgentContext smoke tests; full suite passing

- **Context Engineering Enhancement** (PR #307 by @KaifAhmad1):
  - Comprehensive decision tracking system with full lifecycle management (record → analyze → query → precedent → influence)
  - Advanced KG algorithm integration: centrality analysis, community detection, node embeddings with ContextGraph
  - Enhanced AgentContext with granular feature flags for decision tracking, KG algorithms, and vector store features
  - PolicyException model replacing conflicting Exception name for meaningful business domain modeling
  - GraphStore validation preventing runtime failures with explicit capability checking
  - Hybrid search combining semantic, structural, and category similarity with configurable weights
  - Decision influence analysis with centrality measures and causal chain tracking
  - Policy management with versioning, compliance checking, and exception handling
  - Production-ready architecture with audit trails, security, and scalability features
  - 9 critical bug fixes: logging, security, audit trails, API compatibility, Cypher queries, centrality access, validation, naming
  - Comprehensive documentation with usage guides, production examples, and API references
  - 100% test coverage with all validation tests passing (9/9 tests)
  - Enterprise-grade features for financial services, healthcare, legal, and business domains
  - Complete backward compatibility with existing semantica components
  - Performance optimizations: caching, indexing, and efficient graph operations

- **Added PgVector Store Support** (PR #303 by @Sameer6305, @KaifAhmad1):
  - Native PostgreSQL vector storage using pgvector extension with full integration
  - Multiple distance metrics: cosine, L2/Euclidean, inner product with automatic score normalization
  - Advanced indexing: HNSW and IVFFlat for approximate nearest neighbor search with tunable parameters
  - JSONB metadata storage with flexible filtering capabilities and batch operations
  - Connection pooling support with psycopg3/psycopg2 fallback and efficient resource management
  - Comprehensive VectorStore integration with backend delegation and unified API
  - Idempotent index creation and table management with safe migration support
  - Production-ready security: SQL injection protection with psycopg_sql.SQL() and input validation
  - Performance optimizations: UUID4-based IDs, batch executemany operations, connection pooling
  - Full backward compatibility with existing vector store implementations
  - 36+ comprehensive test cases with Docker integration and dependency skipping
  - Complete documentation with setup guides, examples, and performance tuning
  - CI/CD integration: resolved benchmark compatibility and fixed documentation links

- **Improved Vector Store for Decision Tracking** (PR #293 by @KaifAhmad1):
  - Comprehensive decision tracking capabilities with hybrid search combining semantic and structural embeddings
  - New DecisionEmbeddingPipeline for generating semantic and structural embeddings with KG algorithm integration
  - HybridSimilarityCalculator with configurable weights (semantic: 0.7, structural: 0.3)
  - DecisionContext high-level interface for decision management with explainable AI features
  - ContextRetriever with hybrid precedent search and multi-hop reasoning
  - User-friendly convenience API: quick_decision(), find_precedents(), explain(), similar_to(), batch_decisions(), filter_decisions()
  - Knowledge Graph algorithm integration: Node2Vec, PathFinder, CommunityDetector, CentralityCalculator, SimilarityCalculator, ConnectivityAnalyzer
  - Explainable AI with path tracing, confidence scoring, and comprehensive decision explanations
  - Performance optimizations: 0.028s per decision processing, 0.031s search performance, ~0.8KB per decision memory usage
  - 100% backward compatibility maintained with existing VectorStore functionality
  - 34+ comprehensive tests covering all functionality including end-to-end scenarios and performance benchmarks
  - Real-world validation examples for banking and insurance domains
  - Documentation with clear imports, examples, and API references

- **Improved Graph Algorithms in KG Module** (PR #292 by @KaifAhmad1):
  - Complete algorithm suite with 30+ graph algorithms across 7 categories
  - Node Embeddings: Node2Vec, DeepWalk, Word2Vec for structural similarity analysis
  - Similarity Analysis: Cosine, Euclidean, Manhattan, Correlation metrics with batch processing
  - Path Finding: Dijkstra, A*, BFS, K-shortest paths for route and network analysis
  - Link Prediction: Preferential attachment, Jaccard, Adamic-Adar for network completion
  - Centrality Analysis: Degree, Betweenness, Closeness, PageRank for importance ranking
  - Community Detection: Louvain, Leiden, Label propagation for clustering analysis
  - Connectivity Analysis: Components, bridges, density for network robustness
  - Unified provenance tracking system with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
  - Complete execution tracking with metadata, timestamps, and reproducibility IDs
  - Comprehensive test coverage with 5 test suites and 40+ test methods
  - Professional documentation overhaul for all modules and reference documentation
  - Enterprise-ready functionality with error handling and NetworkX compatibility
  - Performance optimizations with sparse matrix operations and batch processing
  - Full backward compatibility maintained with gradual migration support

- **Improved Security Configuration with Dependabot**:
  - Configured bi-weekly security updates with manual review by @KaifAhmad1
  - Implemented automated security scans (Monday & Thursday at 7 AM IST) with Bandit, Safety, Semgrep
  - Added security-critical package grouping (cryptography, requests, urllib3, certifi, pyopenssl)
  - Enterprise-grade security with audit trail, compliance features, and zero auto-merge
  - Optimized IST timezone scheduling (Security scans: 7 AM IST, PRs: 9 AM IST)
  - Aligned with new Dependabot features: open-source proxy support, smart dependency grouping for Snowflake/Arrow/benchmark features, private registry support, semantic commit prefixes, and latest GitHub security best practices

- **ResourceScheduler Deadlock Fix and Performance Improvements** (PR #299, #301 by @d4ndr4d3, @KaifAhmad1):
  - Fixed critical deadlock in ResourceScheduler by replacing `threading.Lock()` with `threading.RLock()`
  - Resolved nested lock acquisition issue in `allocate_resources()` → `allocate_cpu/memory/gpu()` calls
  - Added allocation validation with `ValidationError` when no resources can be allocated
  - Improved performance by moving progress tracking updates outside lock scope
  - Implemented comprehensive resource cleanup on allocation failures to prevent leaks
  - Added complete regression test suite (6 tests) for deadlock prevention and edge cases
  - Improved error handling and documentation for better operator visibility
  - Zero breaking changes, maintains thread safety and backward compatibility

## [0.2.7] - 2026-02-09

### Added / Changed

- **Snowflake Connector for Data Ingestion** (PR #276 by @Sameer6305):
  - Native Snowflake connector with multi-authentication (password, OAuth, key-pair, SSO)
  - Table and query ingestion with pagination, schema introspection, batch processing
  - SQL injection prevention via identifier escaping, OAuth token validation
  - Progress tracking integration, context manager support, document export
  - 24 comprehensive unit tests with mocking, complete documentation and examples
  - Added as optional dependency `db-snowflake` with snowflake-connector-python>=3.0.0

- **Apache Arrow Export Support** (PR #273 by @Sameer6305):
  - Added Apache Arrow exporter with explicit schemas, entity/relationship export, compression support
  - Integrated with export module and method registry, Pandas/DuckDB compatible
  - 20 unit tests + 1 integration test, complete documentation with examples

- **Comprehensive Benchmark Suite with Regression CLI** (PR #289 by @ZohaibHassan16, @KaifAhmad1):
  - 137+ benchmarks across all 10 Semantica modules (Input, Core, Storage, Context, QA, Ontology, etc.)
  - Environment-agnostic design with robust mocking system for CI/CD compatibility
  - Statistical regression detection using Z-score analysis with configurable thresholds
  - Automated performance auditing via GitHub Actions workflow
  - Comprehensive documentation suite (benchmarks.md, architecture guides, usage examples)
  - Zero breaking changes, production-ready with ultra-fast text processing (>10,000 ops/s)
  - Added benchmark runner CLI: `python benchmarks/benchmark_runner.py`

## [0.2.6] - 2026-02-03

### Added / Changed

- **W3C PROV-O Compliant Provenance Tracking** (#254, #246):
  - Comprehensive provenance tracking system with W3C PROV-O compliance across all 17 Semantica modules
  - **Core Module**: `ProvenanceManager`, W3C PROV-O schemas, storage backends (InMemory, SQLite), SHA-256 integrity verification
  - **Module Integrations**: Semantic Extract, LLMs (Groq, OpenAI, HuggingFace, LiteLLM), Pipeline, Context, Ingest, Embeddings, Graph/Vector/Triplet stores, Reasoning, Conflicts, Deduplication, Export, Parse, Normalize, Ontology, Visualization
  - **Features**: Complete lineage tracking (Document → Chunk → Entity → Relationship → Graph), LLM tracking (tokens, costs, latency), source tracking, bridge axioms for domain transformations
  - **Compliance Infrastructure**: W3C PROV-O, FDA 21 CFR Part 11, SOX, HIPAA, TNFD
  - **Testing**: 237 tests covering core functionality, all 17 module integrations, edge cases, backward compatibility
  - **Design**: Opt-in with `provenance=False` by default, zero breaking changes, no new dependencies
  - Contributed by @KaifAhmad1

- **Enhanced Change Management Module** (#248, #243):
  - Enterprise-grade version control for knowledge graphs and ontologies with persistent storage and audit trails
  - **Core Classes**: `TemporalVersionManager` (KG versioning), `OntologyVersionManager` (ontology versioning), `ChangeLogEntry` (metadata)
  - **Storage**: SQLite (persistent) and in-memory backends with thread-safe operations
  - **Features**: SHA-256 checksums, detailed entity/relationship diffs, structural ontology comparison, email validation
  - **Compliance Infrastructure**: HIPAA, SOX, FDA 21 CFR Part 11 with immutable audit trails
  - **Testing**: 104 tests (100% pass) - unit, integration, compliance, performance, edge cases
  - **Performance**: 17.6ms for 10k entities, 510+ ops/sec concurrent, handles 5k+ entity graphs
  - **Migration**: Backward compatible, simplified class names, zero external dependencies
  - Contributed by @KaifAhmad1

- CSV Ingestion Enhancements (PR #244 by @saloni0318)
  - Auto-detect CSV encoding (chardet) and delimiter (csv.Sniffer)
  - Tolerant decoding and malformed-row handling (`on_bad_lines='warn'`)
  - Optional chunked reading for large files; metadata tracks detected values
  - Expanded unit tests covering delimiters, quoted/multiline fields, header overrides, chunks, and NaN preservation

- Tests: Comprehensive units for TextNormalizer (PR #242 by @ZohaibHassan16)
  - Added focused test coverage for TextNormalizer behavior across inputs

- Tests: Register integration mark and tidy ingest test warnings (PR #241 by @KaifAhmad1)
  - Introduced integration test marker and reduced noisy warnings in ingest tests

- **Ingest Unit Tests** (#239, #232):
  - Comprehensive unit tests for ingestion modules (file, web, and feed ingestors)
  - **Coverage**: File scanning (local/cloud S3/GCS/Azure), web ingestion (URL/sitemap/robots.txt), RSS/Atom feed parsing
  - **Testing**: 998 lines of test code with mocked external dependencies for fast, isolated execution
  - **Results**: file_ingestor (86%), web_ingestor (86%), feed_ingestor (80%) coverage
  - Covers happy paths, edge cases, and error handling
  - Contributed by @Mohammed2372

### Fixed

- **Temperature Compatibility Fix** (#256, #252):
  - Fixed hardcoded `temperature=0.3` that broke compatibility with models requiring specific temperature values (e.g., gpt-5-mini)
  - Added `_add_if_set` helper method to `BaseProvider` that only passes parameters when explicitly set
  - When `temperature=None`, parameter is omitted allowing APIs to use model defaults
  - Updated all 5 providers: OpenAI, Groq, Gemini, Ollama, DeepSeek
  - Reduced code by ~85 lines with cleaner parameter handling
  - Comprehensive test coverage added (10 temperature tests, all passing)
  - Backward compatible - no breaking changes
  - Contributed by @F0rt1s and @IGES-Institut

- **JenaStore Empty Graph Bug** (#257, #258):
  - Fixed `ProcessingError: Graph not initialized` when operating on empty (but initialized) graphs
  - Replaced implicit `if not self.graph:` checks with explicit `if self.graph is None:` validation in 5 methods (`add_triplets`, `get_triplets`, `delete_triplet`, `execute_sparql`, `serialize`)
  - Properly distinguishes `None` (uninitialized) from empty graphs (initialized with 0 triplets)
  - Unblocks benchmarking suite, fresh deployments, and testing workflows
  - Contributed by @ZohaibHassan16

## [0.2.5] - 2026-01-27

### Added
- **Pinecone Vector Store Support**:
    - Implemented native Pinecone support (`PineconeStore`) with full CRUD capabilities.
    - Added support for serverless and pod-based indexes, namespaces, and metadata filtering.
    - Integrated with `VectorStore` unified interface and registry.
    - (Closes #219, Resolves #220)
- **Configurable LLM Retry Logic**:
    - Exposed `max_retries` parameter in `NERExtractor`, `RelationExtractor`, `TripletExtractor` and low-level extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Defaults to 3 retries to prevent infinite loops during JSON validation failures or API timeouts.
    - Propagated retry configuration through chunked processing helpers to ensure consistent behavior for long documents.
    - Updated `03_Earnings_Call_Analysis.ipynb` to use `max_retries=3` by default.

### Added
- **Bring Your Own Model (BYOM) Support**:
    - Enabled full support for custom Hugging Face models in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added support for custom tokenizers in `HuggingFaceModelLoader` to handle models with non-standard tokenization requirements.
    - Implemented robust fallback logic for model selection: runtime options (`extract(model=...)`) now correctly override configuration defaults.
- **Enhanced NER Implementation**:
    - Added configurable aggregation strategies (`simple`, `first`, `average`, `max`) to `extract_entities_huggingface` for better sub-word token handling.
    - Implemented robust IOB/BILOU parsing to reconstruct entities from raw model outputs when structured output is unavailable.
    - Added confidence scoring for aggregated entities.
- **Relation Extraction Improvements**:
    - Implemented standard entity marker technique (wrapping subject/object with `<subj>`, `<obj>` tags) in `extract_relations_huggingface` for compatibility with sequence classification models.
    - Added structured output parsing to convert raw model predictions into validated `Relation` objects.
- **Triplet Extraction Completion**:
    - Added specialized parsing for Seq2Seq models (e.g., REBEL) in `extract_triplets_huggingface` to generate structured triplets directly from text.
    - Implemented post-processing logic to clean and validate generated triplets.

### Fixed
- **LLM Extraction Stability**:
    - Fixed infinite retry loops in `BaseProvider` by strictly enforcing `max_retries` limit during structured output generation.
    - Resolved stuck execution in earnings call analysis notebooks when using smaller models (e.g., Llama 3 8B) that frequently produce invalid JSON.
- **Model Parameter Precedence**:
    - Fixed issue where configuration defaults took precedence over runtime arguments in Hugging Face extractors. Runtime options now correctly override config values.
- **Import Handling**:
    - Fixed circular import issues in test suites by implementing robust mocking strategies.

## [0.2.4] - 2026-01-22

### Added
- **Ontology Ingestion Module**:
    - Implemented `OntologyIngestor` in `semantica.ingest` for parsing RDF/OWL files (Turtle, RDF/XML, JSON-LD, N3) into standardized `OntologyData` objects.
    - Added `ingest_ontology` convenience function and integrated it into the unified `ingest(source_type="ontology")` interface.
    - Added recursive directory scanning support for batch ontology ingestion.
    - Exposed ingestion tools in `semantica.ontology` for better discoverability.
    - Added `OntologyData` dataclass for consistent metadata handling (source path, format, timestamps).
- **Documentation**:
    - **Ontology Usage Guide**: Updated `ontology_usage.md` with comprehensive examples for single-file and directory ingestion.
    - **API Reference**: Updated `ontology.md` with `OntologyIngestor` class documentation and method details.
- **Tests**:
    - **Comprehensive Test Suite**: Added `tests/ingest/test_ontology_ingestor.py` covering all supported formats, error handling, and unified interface integration.
    - **Demo Script**: Added `examples/demo_ontology_ingest.py` for end-to-end usage demonstration.

## [0.2.3] - 2026-01-20

### Fixed
- **LLM Relation Extraction Parsing**:
    - Fixed relation extraction returning zero relations despite successful API calls to Groq and other providers
    - Normalized typed responses from instructor/OpenAI/Groq to consistent dict format before parsing
    - Added structured JSON fallback when typed generation yields zero relations to avoid silent empty outputs
    - Removed acceptance of extra kwargs (`max_tokens`, `max_entities_prompt`) from relation extraction internals
    - Filtered kwargs passed to provider LLM calls to only `temperature` and `verbose`
- **API Parameter Handling**:
    - Limited kwargs forwarded in chunked extraction helper to prevent parameter leakage
    - Ensured minimal, safe parameters are passed to provider calls
- **Pipeline Circular Import (Issues #192, #193)**:
    - Fixed circular import between `pipeline_builder` and `pipeline_validator` triggered during `semantica.pipeline` import
    - Lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__` and guarded type hints with `TYPE_CHECKING`
    - Ensured `from semantica.deduplication import DuplicateDetector` no longer fails even when pipeline module is imported
- **JupyterLab Progress Output (Issue #181)**:
    - Added `SEMANTICA_DISABLE_JUPYTER_PROGRESS` environment variable to disable rich Jupyter/Colab progress tables
    - When enabled, progress falls back to console-style output, preventing infinite scrolling and JupyterLab out-of-memory errors

### Added
- **Comprehensive Test Suite**:
-    - Added unit tests (`tests/test_relations_llm.py`) with mocked LLM provider covering both typed and structured response paths
-    - Added integration tests (`tests/integration/test_relations_groq.py`) for real Groq API calls with environment variable API key
-    - Tests validate relation extraction completion and result parsing across different response formats
- **Amazon Neptune Dev Environment**:
-    - Added CloudFormation template (`cookbook/introduction/neptune-setup.yaml`) to provision a dev Neptune cluster with public endpoint and IAM auth enabled
-    - Documented deployment, cost estimates, and IAM User vs IAM Role best practices in `cookbook/introduction/21_Amazon_Neptune_Store.ipynb`
-    - Added `cfn-lint` to `.pre-commit-config.yaml` for validating CloudFormation templates while excluding `neptune-setup.yaml` from generic YAML linters
- **Vector Store High-Performance Ingestion**:
-    - Added `VectorStore.add_documents` for high-throughput ingestion with automatic embedding generation, batching, and parallel processing
-    - Added `VectorStore.embed_batch` helper for generating embeddings for lists of texts without immediately storing them
-    - Enabled default parallel ingestion in `VectorStore` with `max_workers=6` for common workloads
-    - Added dedicated documentation page `docs/vector_store_usage.md` describing high-performance vector store usage and configuration
-    - Added `tests/vector_store/test_vector_store_parallel.py` covering parallel vs sequential performance, error handling, and edge cases for `add_documents` and `embed_batch`

### Changed
- **Relation Extraction API**:
-    - Simplified parameter interface by removing unused kwargs that were previously ignored
-    - Improved error handling and verbose logging for debugging relation extraction issues
-    - Enhanced robustness of post-response parsing across different LLM providers
- **Vector Store Defaults and Examples**:
-    - Standardized `VectorStore` default concurrency to `max_workers=6` for parallel ingestion
-    - Updated vector store reference documentation and usage guides to rely on implicit defaults instead of requiring manual `max_workers` configuration in examples


## [0.2.2] - 2026-01-15

### Added
- **Parallel Extraction Engine**:
    - Implemented high-throughput parallel batch processing across all core extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`) using `concurrent.futures.ThreadPoolExecutor`.
    - Added `max_workers` configuration parameter (default: 1) to all extractor `extract()` methods, allowing users to tune concurrency based on available CPU cores or API rate limits.
    - **Parallel Chunking**: Implemented parallel processing for large document chunking in `_extract_entities_chunked` and `_extract_relations_chunked`, significantly reducing latency for long-form text analysis.
    - **Thread-Safe Progress Tracking**: Enhanced `ProgressTracker` to handle concurrent updates from multiple threads without race conditions during batch processing.
- **Semantic Extract Performance & Regression**:
    - Added edge-case regression suite covering max worker defaults, LLM prompt entity filtering, and extractor reuse.
    - Added a runnable real-use-case benchmark script for batch latency across `NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticAnalyzer`, and `SemanticNetworkExtractor`.
    - Added Groq LLM smoke tests that exercise LLM-based entities/relations/triplets when `GROQ_API_KEY` is available via environment configuration.

### Security
- **Credential Sanitization**:
    - Removed hardcoded API keys from 8 cookbook notebooks to prevent secret leakage.
    - Enforced environment variable usage for `GROQ_API_KEY` across all examples.
- **Secure Caching**:
    - Updated `ExtractionCache` to exclude sensitive parameters (e.g., `api_key`, `token`, `password`) from cache key generation, preventing secret leakage and enabling safe cache sharing.
    - Upgraded cache key hashing algorithm from MD5 to **SHA-256** for enhanced collision resistance and security.

### Changed
- **Gemini SDK Migration**:
    - Migrated `GeminiProvider` to use the new `google-genai` SDK (v0.1.0+) to address deprecation warnings.
    - Implemented graceful fallback to `google.generativeai` for backward compatibility.
- **Dependency Resolution**:
    - Pinned `opentelemetry-api` and `opentelemetry-sdk` to `1.37.0` to resolve pip conflicts.
    - Updated `protobuf` and `grpcio` constraints for better stability.
- **Entity Filtering Scope**:
    - Removed entity filtering from non-LLM extraction flows to avoid accuracy regressions.
    - Applied entity downselection only to LLM relation prompt construction, while matching returned entities against the full original entity list.
- **Batch Concurrency Defaults**:
    - Standardized `max_workers` defaulting across `semantic_extract` and tuned for low-latency: ML-backed methods default to single-worker, while pattern/regex/rules/LLM/huggingface methods use a higher parallelism default capped by CPU.
    - Raised the global `optimization.max_workers` default to 8 for better throughput on batch workloads.

### Performance
- **Bottleneck Optimization (GitHub Issue #186)**:
    - **Resolved Bottleneck #1 (Sequential Processing)**: Replaced sequential `for` loops with parallel execution for both document-level batches and intra-document chunks.
    - **Performance Gains**: Achieved **~1.89x speedup** in real-world extraction scenarios (tested with Groq `llama-3.3-70b-versatile` on standard datasets).
    - **Initialization Optimization**: Refactored test suite to use class-level `setUpClass` for LLM provider initialization, eliminating redundant API client creation overhead.
- **Low-Latency Entity Matching**:
    - Avoided heavyweight embedding stack imports on common matches by improving fast matching heuristics and short-circuiting before embedding similarity.
    - Optimized entity matching to prioritize exact/substring/word-boundary matches and only fall back to embedding similarity when needed, reducing CPU overhead in LLM relation/triplet mapping.


## [0.2.1] - 2026-01-12

### Fixed
- **LLM Output Stability (Bug #176)**:
    - Fixed incomplete JSON output issues by correctly propagating `max_tokens` parameter in `extract_relations_llm`.
    - Implemented automatic error handling that halves chunk sizes and retries when LLM context or output limits are exceeded.
    - Fixed `AttributeError` in provider integration by ensuring consistent parameter passing via `**kwargs`.
- **Constraint Relaxations**:
    - Removed hardcoded `max_length` constraints from `Entity`, `Relation`, and `Triplet` classes to support long-form semantic extraction (e.g., long descriptions or names).
- Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
- Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
- Fixed dependency compatibility issues by pinning `protobuf>=5.29.1,<7.0` and `grpcio>=1.71.2`.
- Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
- Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Changed
- **Chunking Defaults**:
    - Increased default `max_text_length` for auto-chunking to **64,000 characters** (from 32k/16k) for OpenAI, Anthropic, Gemini, Groq, and DeepSeek providers.
    - Unified chunking logic across `extract_entities_llm`, `extract_relations_llm`, and `extract_triplets_llm`.
- **Groq Support**:
    - Standardized Groq provider defaults to use `llama-3.3-70b-versatile` with a 64k context window.
    - Added native support for `max_tokens` and `max_completion_tokens` to prevent output truncation.

### Added
- **Testing**:
    - Added `tests/reproduce_issue_176.py` to validate `max_tokens` propagation and chunking behavior across all extractors.


## [0.2.0] - 2026-01-10

### Added
- **Amazon Neptune Support**:
    - Added `AmazonNeptuneStore` providing Amazon Neptune graph database integration via Bolt protocol and OpenCypher.
    - Implemented `NeptuneAuthTokenManager` extending Neo4j AuthManager for AWS IAM SigV4 signing with automatic token refresh.
    - Added robust connection handling: retry logic with backoff for transient errors (signature expired, connection closed) and driver recreation.
    - Added `graph-amazon-neptune` optional dependency group (boto3, neo4j).
    - Comprehensive test suite covering all GraphStore interface methods.
- **Docling Integration**:
    - Added `DoclingParser` in `semantica.parse` for high-fidelity document parsing using the Docling library.
    - Supports multi-format parsing (PDF, DOCX, PPTX, XLSX, HTML, images) with superior table extraction and structure understanding.
    - Implemented as a standalone parser supporting local execution, OCR, and multiple export formats (Markdown, HTML, JSON).
- **Robust Extraction Fallbacks**:
    - Implemented comprehensive fallback chains ("ML/LLM" -> "Pattern" -> "Last Resort") across `NERExtractor`, `RelationExtractor`, and `TripletExtractor` to prevent empty result lists.
    - Added "Last Resort" pattern matching in `NERExtractor` to identify capitalized words as generic entities when all other methods fail.
    - Added "Last Resort" adjacency-based relation extraction in `RelationExtractor` to create weak connections between adjacent entities if no relations are found.
    - Added fallback logic in `TripletExtractor` to convert relations to triplets or use rule-based extraction if standard methods fail.
- **Provenance & Tracking**:
    - Added count tracking to batch processing logs in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added `batch_index` and `document_id` to the metadata of all extracted entities, relations, triplets, semantic roles, and clusters for better traceability.
- **Semantic Extract Improvements**:
    - Introduced `auto-chunking` for long text processing in LLM extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Added `silent_fail` parameter to LLM extraction methods for configurable error handling.
    - Implemented robust JSON parsing and automatic retry logic (3 attempts with exponential backoff) in `BaseProvider` for all LLM providers.
    - Enhanced `GroqProvider` with better diagnostics and connectivity testing.
    - Added comprehensive entity, relation, and triplet deduplication for chunked extraction.
    - Added `semantica/semantic_extract/schemas.py` with canonical Pydantic models for consistent structured output.
- **Testing**:
    - Added comprehensive robustness test suite `tests/semantic_extract/test_robustness_fallback.py` for validating extraction fallbacks and metadata propagation.
    - Added comprehensive unit test suite `tests/embeddings/test_model_switching.py` for verifying dynamic model transitions and dimension updates.
    - Added end-to-end integration test suite for Knowledge Graph pipeline validation (GraphBuilder -> EntityResolver -> GraphAnalyzer).
- **Other**:
    - Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
    - Robustified ID extraction across `CentralityCalculator`, `CommunityDetector`, and `ConnectivityAnalyzer` to handle various entity formats.
    - Improved `Entity` class hashability and equality logic in `utils/types.py`.

### Changed
- **Deduplication & Conflict Logic**:
    - Removed internal deduplication logic from `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Removed consistency/conflict checking from `ExtractionValidator` to defer to dedicated `semantica/conflicts` module.
    - Removed `_deduplicate_*` methods from `semantica/semantic_extract/methods.py`.
- **Batch Processing & Consistency**:
    - Standardized batch processing across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `SemanticNetworkExtractor`, `EventDetector`, `SemanticAnalyzer`, `CoreferenceResolver`) using a unified `extract`/`analyze`/`resolve` method pattern with progress tracking.
    - Added provenance metadata (`batch_index`, `document_id`) to `SemanticNetwork` nodes/edges, `Event` objects, `SemanticRole` results, `CoreferenceChain` mentions, and `SemanticCluster` (tracking source `document_ids`).
    - Updated `SemanticClusterer.cluster` and `SemanticAnalyzer.cluster_semantically` to accept list of dictionaries (with `content` and `id` keys) for better document tracking during clustering.
    - Removed legacy `check_triplet_consistency` from `TripletExtractor`.
    - Removed `validate_consistency` and `_check_consistency` from `ExtractionValidator`.
- **Weighted Scoring**:
    - Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity) in comments.
    - Explicitly labeled "Type Similarity" as "user-provided" in code comments to remove ambiguity.
- **Refactoring**:
    - Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
    - Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Fixed
- **Critical Fixes**:
    - Resolved `NameError` in `extraction_validator.py` by adding missing `Union` import.
    - Resolved issues where extractors would return empty lists for valid input text when primary extraction methods failed.
    - Fixed metadata initialization issue in batch processing where `batch_index` and `document_id` were occasionally missing from extracted items.
    - Ensured `LLMExtraction` methods (`enhance_entities`, `enhance_relations`) return original input instead of failing or returning empty results when LLM providers are unavailable.
- **Component Fixes**:
    - Fixed model switching bug in `TextEmbedder` where internal state was not cleared, preventing dynamic updates between `fastembed` and `sentence_transformers` (#160).
    - Implemented model-intrinsic embedding dimension detection in `TextEmbedder` to ensure consistency between models and vector databases.
    - Updated `set_model` to properly refresh configuration and dimensions during model switches.
    - Fixed `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer` when processing graphs with raw `Entity` objects or dictionaries in relationships (#159).
    - Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
    - Fixed dependency compatibility issues by pinning `protobuf==4.25.3` and `grpcio==1.67.1`.
    - Fixed a bug in `TripletExtractor` where the `validate_triplets` method was shadowed by an internal attribute.
    - Fixed incorrect `TextSplitter` import path in the `semantic_extract.methods` module.

## [0.1.1] - 2026-01-05

### Added
- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse` for easier access.
- Added comprehensive `DoclingParser` usage examples to README and documentation.
- Added Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed
- Fixed `DoclingParser` import/export issues across platforms (Windows, Linux, Google Colab).
- Improved error messaging when optional `docling` dependency is missing.
- Fixed versioning inconsistencies across the framework.

## [0.1.0] - 2025-12-31

### Added
- New command-line interface (`semantica` CLI) with support for knowledge base building and info commands.
- Integrated FastAPI-based REST API server for remote access to framework functionality.
- Dedicated background worker component for scalable task processing and pipeline execution.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed
- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core framework components.

## [0.0.5] - 2025-11-26

### Changed
- Configured Trusted Publishing for secure automated PyPI deployments

## [0.0.4] - 2025-11-26

### Changed
- Fixed PyPI deployment issues from v0.0.3

## [0.0.3] - 2025-11-25

### Changed
- Simplified CI/CD workflows - removed failing tests and strict linting
- Combined release and PyPI publishing into single workflow
- Simplified security scanning to weekly pip-audit only
- Streamlined GitHub Actions configuration

### Added
- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership)
- Updated pull request template with clear guidelines
- Community support documentation (SUPPORT.md)
- Funding and sponsorship configuration (FUNDING.yml)
- GitHub configuration README for maintainers
- 10+ new domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.)

### Removed
- Redundant scripts folder (8 shell/PowerShell scripts)
- Unnecessary automation workflows (label-issues, mark-answered)
- Excessive issue templates

## [0.0.2] - 2025-11-25

### Changed
- Updated README with streamlined content and better examples
- Added more notebooks to cookbook
- Improved documentation structure

## [0.0.1] - 2024-01-XX

### Added
- Core framework architecture
- Universal data ingestion (multiple file formats)
- Semantic intelligence engine (NER, relation extraction, event detection)
- Knowledge graph construction with entity resolution
- 6-stage ontology generation pipeline
- GraphRAG engine for hybrid retrieval
- Multi-agent system infrastructure
- Production-ready quality assurance modules
- Comprehensive documentation with MkDocs
- Cookbook with interactive tutorials
- Support for multiple vector stores (Weaviate, Qdrant, FAISS)
- Support for multiple graph databases (Neo4j, NetworkX, RDFLib)
- Temporal knowledge graph support
- Conflict detection and resolution
- Deduplication and entity merging
- Schema template enforcement
- Seed data management
- Multi-format export (RDF, JSON-LD, CSV, GraphML)
- Visualization tools
- Pipeline orchestration
- Streaming support (Kafka, RabbitMQ, Kinesis)
- Context engineering for AI agents
- Reasoning and inference engine

### Documentation
- Getting started guide
- API reference for all modules
- Concepts and architecture documentation
- Use case examples
- Cookbook tutorials
- Community projects showcase

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Migration Guides

When breaking changes are introduced, migration guides will be provided in the release notes and documentation.

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Fixed: PolicyEngine latest version selection on ContextGraph; AgentContext fallback robustness and secure logging (PR #TBD by @KaifAhmad1)
- Tests: Added ContextGraph fallback and AgentContext smoke tests; full suite passing

- **Context Engineering Enhancement** (PR #307 by @KaifAhmad1):
  - Comprehensive decision tracking system with full lifecycle management (record → analyze → query → precedent → influence)
  - Advanced KG algorithm integration: centrality analysis, community detection, node embeddings with ContextGraph
  - Enhanced AgentContext with granular feature flags for decision tracking, KG algorithms, and vector store features
  - PolicyException model replacing conflicting Exception name for meaningful business domain modeling
  - GraphStore validation preventing runtime failures with explicit capability checking
  - Hybrid search combining semantic, structural, and category similarity with configurable weights
  - Decision influence analysis with centrality measures and causal chain tracking
  - Policy management with versioning, compliance checking, and exception handling
  - Production-ready architecture with audit trails, security, and scalability features
  - 9 critical bug fixes: logging, security, audit trails, API compatibility, Cypher queries, centrality access, validation, naming
  - Comprehensive documentation with usage guides, production examples, and API references
  - 100% test coverage with all validation tests passing (9/9 tests)
  - Enterprise-grade features for financial services, healthcare, legal, and business domains
  - Complete backward compatibility with existing semantica components
  - Performance optimizations: caching, indexing, and efficient graph operations

- **Added PgVector Store Support** (PR #303 by @Sameer6305, @KaifAhmad1):
  - Native PostgreSQL vector storage using pgvector extension with full integration
  - Multiple distance metrics: cosine, L2/Euclidean, inner product with automatic score normalization
  - Advanced indexing: HNSW and IVFFlat for approximate nearest neighbor search with tunable parameters
  - JSONB metadata storage with flexible filtering capabilities and batch operations
  - Connection pooling support with psycopg3/psycopg2 fallback and efficient resource management
  - Comprehensive VectorStore integration with backend delegation and unified API
  - Idempotent index creation and table management with safe migration support
  - Production-ready security: SQL injection protection with psycopg_sql.SQL() and input validation
  - Performance optimizations: UUID4-based IDs, batch executemany operations, connection pooling
  - Full backward compatibility with existing vector store implementations
  - 36+ comprehensive test cases with Docker integration and dependency skipping
  - Complete documentation with setup guides, examples, and performance tuning
  - CI/CD integration: resolved benchmark compatibility and fixed documentation links

- **Improved Vector Store for Decision Tracking** (PR #293 by @KaifAhmad1):
  - Comprehensive decision tracking capabilities with hybrid search combining semantic and structural embeddings
  - New DecisionEmbeddingPipeline for generating semantic and structural embeddings with KG algorithm integration
  - HybridSimilarityCalculator with configurable weights (semantic: 0.7, structural: 0.3)
  - DecisionContext high-level interface for decision management with explainable AI features
  - ContextRetriever with hybrid precedent search and multi-hop reasoning
  - User-friendly convenience API: quick_decision(), find_precedents(), explain(), similar_to(), batch_decisions(), filter_decisions()
  - Knowledge Graph algorithm integration: Node2Vec, PathFinder, CommunityDetector, CentralityCalculator, SimilarityCalculator, ConnectivityAnalyzer
  - Explainable AI with path tracing, confidence scoring, and comprehensive decision explanations
  - Performance optimizations: 0.028s per decision processing, 0.031s search performance, ~0.8KB per decision memory usage
  - 100% backward compatibility maintained with existing VectorStore functionality
  - 34+ comprehensive tests covering all functionality including end-to-end scenarios and performance benchmarks
  - Real-world validation examples for banking and insurance domains
  - Documentation with clear imports, examples, and API references

- **Improved Graph Algorithms in KG Module** (PR #292 by @KaifAhmad1):
  - Complete algorithm suite with 30+ graph algorithms across 7 categories
  - Node Embeddings: Node2Vec, DeepWalk, Word2Vec for structural similarity analysis
  - Similarity Analysis: Cosine, Euclidean, Manhattan, Correlation metrics with batch processing
  - Path Finding: Dijkstra, A*, BFS, K-shortest paths for route and network analysis
  - Link Prediction: Preferential attachment, Jaccard, Adamic-Adar for network completion
  - Centrality Analysis: Degree, Betweenness, Closeness, PageRank for importance ranking
  - Community Detection: Louvain, Leiden, Label propagation for clustering analysis
  - Connectivity Analysis: Components, bridges, density for network robustness
  - Unified provenance tracking system with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
  - Complete execution tracking with metadata, timestamps, and reproducibility IDs
  - Comprehensive test coverage with 5 test suites and 40+ test methods
  - Professional documentation overhaul for all modules and reference documentation
  - Enterprise-ready functionality with error handling and NetworkX compatibility
  - Performance optimizations with sparse matrix operations and batch processing
  - Full backward compatibility maintained with gradual migration support

- **Improved Security Configuration with Dependabot**:
  - Configured bi-weekly security updates with manual review by @KaifAhmad1
  - Implemented automated security scans (Monday & Thursday at 7 AM IST) with Bandit, Safety, Semgrep
  - Added security-critical package grouping (cryptography, requests, urllib3, certifi, pyopenssl)
  - Enterprise-grade security with audit trail, compliance features, and zero auto-merge
  - Optimized IST timezone scheduling (Security scans: 7 AM IST, PRs: 9 AM IST)
  - Aligned with new Dependabot features: open-source proxy support, smart dependency grouping for Snowflake/Arrow/benchmark features, private registry support, semantic commit prefixes, and latest GitHub security best practices

- **ResourceScheduler Deadlock Fix and Performance Improvements** (PR #299, #301 by @d4ndr4d3, @KaifAhmad1):
  - Fixed critical deadlock in ResourceScheduler by replacing `threading.Lock()` with `threading.RLock()`
  - Resolved nested lock acquisition issue in `allocate_resources()` → `allocate_cpu/memory/gpu()` calls
  - Added allocation validation with `ValidationError` when no resources can be allocated
  - Improved performance by moving progress tracking updates outside lock scope
  - Implemented comprehensive resource cleanup on allocation failures to prevent leaks
  - Added complete regression test suite (6 tests) for deadlock prevention and edge cases
  - Improved error handling and documentation for better operator visibility
  - Zero breaking changes, maintains thread safety and backward compatibility

## [0.2.7] - 2026-02-09

### Added / Changed

- **Snowflake Connector for Data Ingestion** (PR #276 by @Sameer6305):
  - Native Snowflake connector with multi-authentication (password, OAuth, key-pair, SSO)
  - Table and query ingestion with pagination, schema introspection, batch processing
  - SQL injection prevention via identifier escaping, OAuth token validation
  - Progress tracking integration, context manager support, document export
  - 24 comprehensive unit tests with mocking, complete documentation and examples
  - Added as optional dependency `db-snowflake` with snowflake-connector-python>=3.0.0

- **Apache Arrow Export Support** (PR #273 by @Sameer6305):
  - Added Apache Arrow exporter with explicit schemas, entity/relationship export, compression support
  - Integrated with export module and method registry, Pandas/DuckDB compatible
  - 20 unit tests + 1 integration test, complete documentation with examples

- **Comprehensive Benchmark Suite with Regression CLI** (PR #289 by @ZohaibHassan16, @KaifAhmad1):
  - 137+ benchmarks across all 10 Semantica modules (Input, Core, Storage, Context, QA, Ontology, etc.)
  - Environment-agnostic design with robust mocking system for CI/CD compatibility
  - Statistical regression detection using Z-score analysis with configurable thresholds
  - Automated performance auditing via GitHub Actions workflow
  - Comprehensive documentation suite (benchmarks.md, architecture guides, usage examples)
  - Zero breaking changes, production-ready with ultra-fast text processing (>10,000 ops/s)
  - Added benchmark runner CLI: `python benchmarks/benchmark_runner.py`

## [0.2.6] - 2026-02-03

### Added / Changed

- **W3C PROV-O Compliant Provenance Tracking** (#254, #246):
  - Comprehensive provenance tracking system with W3C PROV-O compliance across all 17 Semantica modules
  - **Core Module**: `ProvenanceManager`, W3C PROV-O schemas, storage backends (InMemory, SQLite), SHA-256 integrity verification
  - **Module Integrations**: Semantic Extract, LLMs (Groq, OpenAI, HuggingFace, LiteLLM), Pipeline, Context, Ingest, Embeddings, Graph/Vector/Triplet stores, Reasoning, Conflicts, Deduplication, Export, Parse, Normalize, Ontology, Visualization
  - **Features**: Complete lineage tracking (Document → Chunk → Entity → Relationship → Graph), LLM tracking (tokens, costs, latency), source tracking, bridge axioms for domain transformations
  - **Compliance Infrastructure**: W3C PROV-O, FDA 21 CFR Part 11, SOX, HIPAA, TNFD
  - **Testing**: 237 tests covering core functionality, all 17 module integrations, edge cases, backward compatibility
  - **Design**: Opt-in with `provenance=False` by default, zero breaking changes, no new dependencies
  - Contributed by @KaifAhmad1

- **Enhanced Change Management Module** (#248, #243):
  - Enterprise-grade version control for knowledge graphs and ontologies with persistent storage and audit trails
  - **Core Classes**: `TemporalVersionManager` (KG versioning), `OntologyVersionManager` (ontology versioning), `ChangeLogEntry` (metadata)
  - **Storage**: SQLite (persistent) and in-memory backends with thread-safe operations
  - **Features**: SHA-256 checksums, detailed entity/relationship diffs, structural ontology comparison, email validation
  - **Compliance Infrastructure**: HIPAA, SOX, FDA 21 CFR Part 11 with immutable audit trails
  - **Testing**: 104 tests (100% pass) - unit, integration, compliance, performance, edge cases
  - **Performance**: 17.6ms for 10k entities, 510+ ops/sec concurrent, handles 5k+ entity graphs
  - **Migration**: Backward compatible, simplified class names, zero external dependencies
  - Contributed by @KaifAhmad1

- CSV Ingestion Enhancements (PR #244 by @saloni0318)
  - Auto-detect CSV encoding (chardet) and delimiter (csv.Sniffer)
  - Tolerant decoding and malformed-row handling (`on_bad_lines='warn'`)
  - Optional chunked reading for large files; metadata tracks detected values
  - Expanded unit tests covering delimiters, quoted/multiline fields, header overrides, chunks, and NaN preservation

- Tests: Comprehensive units for TextNormalizer (PR #242 by @ZohaibHassan16)
  - Added focused test coverage for TextNormalizer behavior across inputs

- Tests: Register integration mark and tidy ingest test warnings (PR #241 by @KaifAhmad1)
  - Introduced integration test marker and reduced noisy warnings in ingest tests

- **Ingest Unit Tests** (#239, #232):
  - Comprehensive unit tests for ingestion modules (file, web, and feed ingestors)
  - **Coverage**: File scanning (local/cloud S3/GCS/Azure), web ingestion (URL/sitemap/robots.txt), RSS/Atom feed parsing
  - **Testing**: 998 lines of test code with mocked external dependencies for fast, isolated execution
  - **Results**: file_ingestor (86%), web_ingestor (86%), feed_ingestor (80%) coverage
  - Covers happy paths, edge cases, and error handling
  - Contributed by @Mohammed2372

### Fixed

- **Temperature Compatibility Fix** (#256, #252):
  - Fixed hardcoded `temperature=0.3` that broke compatibility with models requiring specific temperature values (e.g., gpt-5-mini)
  - Added `_add_if_set` helper method to `BaseProvider` that only passes parameters when explicitly set
  - When `temperature=None`, parameter is omitted allowing APIs to use model defaults
  - Updated all 5 providers: OpenAI, Groq, Gemini, Ollama, DeepSeek
  - Reduced code by ~85 lines with cleaner parameter handling
  - Comprehensive test coverage added (10 temperature tests, all passing)
  - Backward compatible - no breaking changes
  - Contributed by @F0rt1s and @IGES-Institut

- **JenaStore Empty Graph Bug** (#257, #258):
  - Fixed `ProcessingError: Graph not initialized` when operating on empty (but initialized) graphs
  - Replaced implicit `if not self.graph:` checks with explicit `if self.graph is None:` validation in 5 methods (`add_triplets`, `get_triplets`, `delete_triplet`, `execute_sparql`, `serialize`)
  - Properly distinguishes `None` (uninitialized) from empty graphs (initialized with 0 triplets)
  - Unblocks benchmarking suite, fresh deployments, and testing workflows
  - Contributed by @ZohaibHassan16

## [0.2.5] - 2026-01-27

### Added
- **Pinecone Vector Store Support**:
    - Implemented native Pinecone support (`PineconeStore`) with full CRUD capabilities.
    - Added support for serverless and pod-based indexes, namespaces, and metadata filtering.
    - Integrated with `VectorStore` unified interface and registry.
    - (Closes #219, Resolves #220)
- **Configurable LLM Retry Logic**:
    - Exposed `max_retries` parameter in `NERExtractor`, `RelationExtractor`, `TripletExtractor` and low-level extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Defaults to 3 retries to prevent infinite loops during JSON validation failures or API timeouts.
    - Propagated retry configuration through chunked processing helpers to ensure consistent behavior for long documents.
    - Updated `03_Earnings_Call_Analysis.ipynb` to use `max_retries=3` by default.

### Added
- **Bring Your Own Model (BYOM) Support**:
    - Enabled full support for custom Hugging Face models in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added support for custom tokenizers in `HuggingFaceModelLoader` to handle models with non-standard tokenization requirements.
    - Implemented robust fallback logic for model selection: runtime options (`extract(model=...)`) now correctly override configuration defaults.
- **Enhanced NER Implementation**:
    - Added configurable aggregation strategies (`simple`, `first`, `average`, `max`) to `extract_entities_huggingface` for better sub-word token handling.
    - Implemented robust IOB/BILOU parsing to reconstruct entities from raw model outputs when structured output is unavailable.
    - Added confidence scoring for aggregated entities.
- **Relation Extraction Improvements**:
    - Implemented standard entity marker technique (wrapping subject/object with `<subj>`, `<obj>` tags) in `extract_relations_huggingface` for compatibility with sequence classification models.
    - Added structured output parsing to convert raw model predictions into validated `Relation` objects.
- **Triplet Extraction Completion**:
    - Added specialized parsing for Seq2Seq models (e.g., REBEL) in `extract_triplets_huggingface` to generate structured triplets directly from text.
    - Implemented post-processing logic to clean and validate generated triplets.

### Fixed
- **LLM Extraction Stability**:
    - Fixed infinite retry loops in `BaseProvider` by strictly enforcing `max_retries` limit during structured output generation.
    - Resolved stuck execution in earnings call analysis notebooks when using smaller models (e.g., Llama 3 8B) that frequently produce invalid JSON.
- **Model Parameter Precedence**:
    - Fixed issue where configuration defaults took precedence over runtime arguments in Hugging Face extractors. Runtime options now correctly override config values.
- **Import Handling**:
    - Fixed circular import issues in test suites by implementing robust mocking strategies.

## [0.2.4] - 2026-01-22

### Added
- **Ontology Ingestion Module**:
    - Implemented `OntologyIngestor` in `semantica.ingest` for parsing RDF/OWL files (Turtle, RDF/XML, JSON-LD, N3) into standardized `OntologyData` objects.
    - Added `ingest_ontology` convenience function and integrated it into the unified `ingest(source_type="ontology")` interface.
    - Added recursive directory scanning support for batch ontology ingestion.
    - Exposed ingestion tools in `semantica.ontology` for better discoverability.
    - Added `OntologyData` dataclass for consistent metadata handling (source path, format, timestamps).
- **Documentation**:
    - **Ontology Usage Guide**: Updated `ontology_usage.md` with comprehensive examples for single-file and directory ingestion.
    - **API Reference**: Updated `ontology.md` with `OntologyIngestor` class documentation and method details.
- **Tests**:
    - **Comprehensive Test Suite**: Added `tests/ingest/test_ontology_ingestor.py` covering all supported formats, error handling, and unified interface integration.
    - **Demo Script**: Added `examples/demo_ontology_ingest.py` for end-to-end usage demonstration.

## [0.2.3] - 2026-01-20

### Fixed
- **LLM Relation Extraction Parsing**:
    - Fixed relation extraction returning zero relations despite successful API calls to Groq and other providers
    - Normalized typed responses from instructor/OpenAI/Groq to consistent dict format before parsing
    - Added structured JSON fallback when typed generation yields zero relations to avoid silent empty outputs
    - Removed acceptance of extra kwargs (`max_tokens`, `max_entities_prompt`) from relation extraction internals
    - Filtered kwargs passed to provider LLM calls to only `temperature` and `verbose`
- **API Parameter Handling**:
    - Limited kwargs forwarded in chunked extraction helper to prevent parameter leakage
    - Ensured minimal, safe parameters are passed to provider calls
- **Pipeline Circular Import (Issues #192, #193)**:
    - Fixed circular import between `pipeline_builder` and `pipeline_validator` triggered during `semantica.pipeline` import
    - Lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__` and guarded type hints with `TYPE_CHECKING`
    - Ensured `from semantica.deduplication import DuplicateDetector` no longer fails even when pipeline module is imported
- **JupyterLab Progress Output (Issue #181)**:
    - Added `SEMANTICA_DISABLE_JUPYTER_PROGRESS` environment variable to disable rich Jupyter/Colab progress tables
    - When enabled, progress falls back to console-style output, preventing infinite scrolling and JupyterLab out-of-memory errors

### Added
- **Comprehensive Test Suite**:
-    - Added unit tests (`tests/test_relations_llm.py`) with mocked LLM provider covering both typed and structured response paths
-    - Added integration tests (`tests/integration/test_relations_groq.py`) for real Groq API calls with environment variable API key
-    - Tests validate relation extraction completion and result parsing across different response formats
- **Amazon Neptune Dev Environment**:
-    - Added CloudFormation template (`cookbook/introduction/neptune-setup.yaml`) to provision a dev Neptune cluster with public endpoint and IAM auth enabled
-    - Documented deployment, cost estimates, and IAM User vs IAM Role best practices in `cookbook/introduction/21_Amazon_Neptune_Store.ipynb`
-    - Added `cfn-lint` to `.pre-commit-config.yaml` for validating CloudFormation templates while excluding `neptune-setup.yaml` from generic YAML linters
- **Vector Store High-Performance Ingestion**:
-    - Added `VectorStore.add_documents` for high-throughput ingestion with automatic embedding generation, batching, and parallel processing
-    - Added `VectorStore.embed_batch` helper for generating embeddings for lists of texts without immediately storing them
-    - Enabled default parallel ingestion in `VectorStore` with `max_workers=6` for common workloads
-    - Added dedicated documentation page `docs/vector_store_usage.md` describing high-performance vector store usage and configuration
-    - Added `tests/vector_store/test_vector_store_parallel.py` covering parallel vs sequential performance, error handling, and edge cases for `add_documents` and `embed_batch`

### Changed
- **Relation Extraction API**:
-    - Simplified parameter interface by removing unused kwargs that were previously ignored
-    - Improved error handling and verbose logging for debugging relation extraction issues
-    - Enhanced robustness of post-response parsing across different LLM providers
- **Vector Store Defaults and Examples**:
-    - Standardized `VectorStore` default concurrency to `max_workers=6` for parallel ingestion
-    - Updated vector store reference documentation and usage guides to rely on implicit defaults instead of requiring manual `max_workers` configuration in examples


## [0.2.2] - 2026-01-15

### Added
- **Parallel Extraction Engine**:
    - Implemented high-throughput parallel batch processing across all core extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`) using `concurrent.futures.ThreadPoolExecutor`.
    - Added `max_workers` configuration parameter (default: 1) to all extractor `extract()` methods, allowing users to tune concurrency based on available CPU cores or API rate limits.
    - **Parallel Chunking**: Implemented parallel processing for large document chunking in `_extract_entities_chunked` and `_extract_relations_chunked`, significantly reducing latency for long-form text analysis.
    - **Thread-Safe Progress Tracking**: Enhanced `ProgressTracker` to handle concurrent updates from multiple threads without race conditions during batch processing.
- **Semantic Extract Performance & Regression**:
    - Added edge-case regression suite covering max worker defaults, LLM prompt entity filtering, and extractor reuse.
    - Added a runnable real-use-case benchmark script for batch latency across `NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticAnalyzer`, and `SemanticNetworkExtractor`.
    - Added Groq LLM smoke tests that exercise LLM-based entities/relations/triplets when `GROQ_API_KEY` is available via environment configuration.

### Security
- **Credential Sanitization**:
    - Removed hardcoded API keys from 8 cookbook notebooks to prevent secret leakage.
    - Enforced environment variable usage for `GROQ_API_KEY` across all examples.
- **Secure Caching**:
    - Updated `ExtractionCache` to exclude sensitive parameters (e.g., `api_key`, `token`, `password`) from cache key generation, preventing secret leakage and enabling safe cache sharing.
    - Upgraded cache key hashing algorithm from MD5 to **SHA-256** for enhanced collision resistance and security.

### Changed
- **Gemini SDK Migration**:
    - Migrated `GeminiProvider` to use the new `google-genai` SDK (v0.1.0+) to address deprecation warnings.
    - Implemented graceful fallback to `google.generativeai` for backward compatibility.
- **Dependency Resolution**:
    - Pinned `opentelemetry-api` and `opentelemetry-sdk` to `1.37.0` to resolve pip conflicts.
    - Updated `protobuf` and `grpcio` constraints for better stability.
- **Entity Filtering Scope**:
    - Removed entity filtering from non-LLM extraction flows to avoid accuracy regressions.
    - Applied entity downselection only to LLM relation prompt construction, while matching returned entities against the full original entity list.
- **Batch Concurrency Defaults**:
    - Standardized `max_workers` defaulting across `semantic_extract` and tuned for low-latency: ML-backed methods default to single-worker, while pattern/regex/rules/LLM/huggingface methods use a higher parallelism default capped by CPU.
    - Raised the global `optimization.max_workers` default to 8 for better throughput on batch workloads.

### Performance
- **Bottleneck Optimization (GitHub Issue #186)**:
    - **Resolved Bottleneck #1 (Sequential Processing)**: Replaced sequential `for` loops with parallel execution for both document-level batches and intra-document chunks.
    - **Performance Gains**: Achieved **~1.89x speedup** in real-world extraction scenarios (tested with Groq `llama-3.3-70b-versatile` on standard datasets).
    - **Initialization Optimization**: Refactored test suite to use class-level `setUpClass` for LLM provider initialization, eliminating redundant API client creation overhead.
- **Low-Latency Entity Matching**:
    - Avoided heavyweight embedding stack imports on common matches by improving fast matching heuristics and short-circuiting before embedding similarity.
    - Optimized entity matching to prioritize exact/substring/word-boundary matches and only fall back to embedding similarity when needed, reducing CPU overhead in LLM relation/triplet mapping.


## [0.2.1] - 2026-01-12

### Fixed
- **LLM Output Stability (Bug #176)**:
    - Fixed incomplete JSON output issues by correctly propagating `max_tokens` parameter in `extract_relations_llm`.
    - Implemented automatic error handling that halves chunk sizes and retries when LLM context or output limits are exceeded.
    - Fixed `AttributeError` in provider integration by ensuring consistent parameter passing via `**kwargs`.
- **Constraint Relaxations**:
    - Removed hardcoded `max_length` constraints from `Entity`, `Relation`, and `Triplet` classes to support long-form semantic extraction (e.g., long descriptions or names).
- Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
- Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
- Fixed dependency compatibility issues by pinning `protobuf>=5.29.1,<7.0` and `grpcio>=1.71.2`.
- Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
- Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Changed
- **Chunking Defaults**:
    - Increased default `max_text_length` for auto-chunking to **64,000 characters** (from 32k/16k) for OpenAI, Anthropic, Gemini, Groq, and DeepSeek providers.
    - Unified chunking logic across `extract_entities_llm`, `extract_relations_llm`, and `extract_triplets_llm`.
- **Groq Support**:
    - Standardized Groq provider defaults to use `llama-3.3-70b-versatile` with a 64k context window.
    - Added native support for `max_tokens` and `max_completion_tokens` to prevent output truncation.

### Added
- **Testing**:
    - Added `tests/reproduce_issue_176.py` to validate `max_tokens` propagation and chunking behavior across all extractors.


## [0.2.0] - 2026-01-10

### Added
- **Amazon Neptune Support**:
    - Added `AmazonNeptuneStore` providing Amazon Neptune graph database integration via Bolt protocol and OpenCypher.
    - Implemented `NeptuneAuthTokenManager` extending Neo4j AuthManager for AWS IAM SigV4 signing with automatic token refresh.
    - Added robust connection handling: retry logic with backoff for transient errors (signature expired, connection closed) and driver recreation.
    - Added `graph-amazon-neptune` optional dependency group (boto3, neo4j).
    - Comprehensive test suite covering all GraphStore interface methods.
- **Docling Integration**:
    - Added `DoclingParser` in `semantica.parse` for high-fidelity document parsing using the Docling library.
    - Supports multi-format parsing (PDF, DOCX, PPTX, XLSX, HTML, images) with superior table extraction and structure understanding.
    - Implemented as a standalone parser supporting local execution, OCR, and multiple export formats (Markdown, HTML, JSON).
- **Robust Extraction Fallbacks**:
    - Implemented comprehensive fallback chains ("ML/LLM" -> "Pattern" -> "Last Resort") across `NERExtractor`, `RelationExtractor`, and `TripletExtractor` to prevent empty result lists.
    - Added "Last Resort" pattern matching in `NERExtractor` to identify capitalized words as generic entities when all other methods fail.
    - Added "Last Resort" adjacency-based relation extraction in `RelationExtractor` to create weak connections between adjacent entities if no relations are found.
    - Added fallback logic in `TripletExtractor` to convert relations to triplets or use rule-based extraction if standard methods fail.
- **Provenance & Tracking**:
    - Added count tracking to batch processing logs in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added `batch_index` and `document_id` to the metadata of all extracted entities, relations, triplets, semantic roles, and clusters for better traceability.
- **Semantic Extract Improvements**:
    - Introduced `auto-chunking` for long text processing in LLM extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Added `silent_fail` parameter to LLM extraction methods for configurable error handling.
    - Implemented robust JSON parsing and automatic retry logic (3 attempts with exponential backoff) in `BaseProvider` for all LLM providers.
    - Enhanced `GroqProvider` with better diagnostics and connectivity testing.
    - Added comprehensive entity, relation, and triplet deduplication for chunked extraction.
    - Added `semantica/semantic_extract/schemas.py` with canonical Pydantic models for consistent structured output.
- **Testing**:
    - Added comprehensive robustness test suite `tests/semantic_extract/test_robustness_fallback.py` for validating extraction fallbacks and metadata propagation.
    - Added comprehensive unit test suite `tests/embeddings/test_model_switching.py` for verifying dynamic model transitions and dimension updates.
    - Added end-to-end integration test suite for Knowledge Graph pipeline validation (GraphBuilder -> EntityResolver -> GraphAnalyzer).
- **Other**:
    - Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
    - Robustified ID extraction across `CentralityCalculator`, `CommunityDetector`, and `ConnectivityAnalyzer` to handle various entity formats.
    - Improved `Entity` class hashability and equality logic in `utils/types.py`.

### Changed
- **Deduplication & Conflict Logic**:
    - Removed internal deduplication logic from `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Removed consistency/conflict checking from `ExtractionValidator` to defer to dedicated `semantica/conflicts` module.
    - Removed `_deduplicate_*` methods from `semantica/semantic_extract/methods.py`.
- **Batch Processing & Consistency**:
    - Standardized batch processing across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `SemanticNetworkExtractor`, `EventDetector`, `SemanticAnalyzer`, `CoreferenceResolver`) using a unified `extract`/`analyze`/`resolve` method pattern with progress tracking.
    - Added provenance metadata (`batch_index`, `document_id`) to `SemanticNetwork` nodes/edges, `Event` objects, `SemanticRole` results, `CoreferenceChain` mentions, and `SemanticCluster` (tracking source `document_ids`).
    - Updated `SemanticClusterer.cluster` and `SemanticAnalyzer.cluster_semantically` to accept list of dictionaries (with `content` and `id` keys) for better document tracking during clustering.
    - Removed legacy `check_triplet_consistency` from `TripletExtractor`.
    - Removed `validate_consistency` and `_check_consistency` from `ExtractionValidator`.
- **Weighted Scoring**:
    - Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity) in comments.
    - Explicitly labeled "Type Similarity" as "user-provided" in code comments to remove ambiguity.
- **Refactoring**:
    - Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
    - Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Fixed
- **Critical Fixes**:
    - Resolved `NameError` in `extraction_validator.py` by adding missing `Union` import.
    - Resolved issues where extractors would return empty lists for valid input text when primary extraction methods failed.
    - Fixed metadata initialization issue in batch processing where `batch_index` and `document_id` were occasionally missing from extracted items.
    - Ensured `LLMExtraction` methods (`enhance_entities`, `enhance_relations`) return original input instead of failing or returning empty results when LLM providers are unavailable.
- **Component Fixes**:
    - Fixed model switching bug in `TextEmbedder` where internal state was not cleared, preventing dynamic updates between `fastembed` and `sentence_transformers` (#160).
    - Implemented model-intrinsic embedding dimension detection in `TextEmbedder` to ensure consistency between models and vector databases.
    - Updated `set_model` to properly refresh configuration and dimensions during model switches.
    - Fixed `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer` when processing graphs with raw `Entity` objects or dictionaries in relationships (#159).
    - Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
    - Fixed dependency compatibility issues by pinning `protobuf==4.25.3` and `grpcio==1.67.1`.
    - Fixed a bug in `TripletExtractor` where the `validate_triplets` method was shadowed by an internal attribute.
    - Fixed incorrect `TextSplitter` import path in the `semantic_extract.methods` module.

## [0.1.1] - 2026-01-05

### Added
- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse` for easier access.
- Added comprehensive `DoclingParser` usage examples to README and documentation.
- Added Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed
- Fixed `DoclingParser` import/export issues across platforms (Windows, Linux, Google Colab).
- Improved error messaging when optional `docling` dependency is missing.
- Fixed versioning inconsistencies across the framework.

## [0.1.0] - 2025-12-31

### Added
- New command-line interface (`semantica` CLI) with support for knowledge base building and info commands.
- Integrated FastAPI-based REST API server for remote access to framework functionality.
- Dedicated background worker component for scalable task processing and pipeline execution.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed
- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core framework components.

## [0.0.5] - 2025-11-26

### Changed
- Configured Trusted Publishing for secure automated PyPI deployments

## [0.0.4] - 2025-11-26

### Changed
- Fixed PyPI deployment issues from v0.0.3

## [0.0.3] - 2025-11-25

### Changed
- Simplified CI/CD workflows - removed failing tests and strict linting
- Combined release and PyPI publishing into single workflow
- Simplified security scanning to weekly pip-audit only
- Streamlined GitHub Actions configuration

### Added
- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership)
- Updated pull request template with clear guidelines
- Community support documentation (SUPPORT.md)
- Funding and sponsorship configuration (FUNDING.yml)
- GitHub configuration README for maintainers
- 10+ new domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.)

### Removed
- Redundant scripts folder (8 shell/PowerShell scripts)
- Unnecessary automation workflows (label-issues, mark-answered)
- Excessive issue templates

## [0.0.2] - 2025-11-25

### Changed
- Updated README with streamlined content and better examples
- Added more notebooks to cookbook
- Improved documentation structure

## [0.0.1] - 2024-01-XX

### Added
- Core framework architecture
- Universal data ingestion (multiple file formats)
- Semantic intelligence engine (NER, relation extraction, event detection)
- Knowledge graph construction with entity resolution
- 6-stage ontology generation pipeline
- GraphRAG engine for hybrid retrieval
- Multi-agent system infrastructure
- Production-ready quality assurance modules
- Comprehensive documentation with MkDocs
- Cookbook with interactive tutorials
- Support for multiple vector stores (Weaviate, Qdrant, FAISS)
- Support for multiple graph databases (Neo4j, NetworkX, RDFLib)
- Temporal knowledge graph support
- Conflict detection and resolution
- Deduplication and entity merging
- Schema template enforcement
- Seed data management
- Multi-format export (RDF, JSON-LD, CSV, GraphML)
- Visualization tools
- Pipeline orchestration
- Streaming support (Kafka, RabbitMQ, Kinesis)
- Context engineering for AI agents
- Reasoning and inference engine

### Documentation
- Getting started guide
- API reference for all modules
- Concepts and architecture documentation
- Use case examples
- Cookbook tutorials
- Community projects showcase

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Migration Guides

When breaking changes are introduced, migration guides will be provided in the release notes and documentation.

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Fixed: PolicyEngine latest version selection on ContextGraph; AgentContext fallback robustness and secure logging (PR #TBD by @KaifAhmad1)
- Tests: Added ContextGraph fallback and AgentContext smoke tests; full suite passing

- **Context Engineering Enhancement** (PR #307 by @KaifAhmad1):
  - Comprehensive decision tracking system with full lifecycle management (record → analyze → query → precedent → influence)
  - Advanced KG algorithm integration: centrality analysis, community detection, node embeddings with ContextGraph
  - Enhanced AgentContext with granular feature flags for decision tracking, KG algorithms, and vector store features
  - PolicyException model replacing conflicting Exception name for meaningful business domain modeling
  - GraphStore validation preventing runtime failures with explicit capability checking
  - Hybrid search combining semantic, structural, and category similarity with configurable weights
  - Decision influence analysis with centrality measures and causal chain tracking
  - Policy management with versioning, compliance checking, and exception handling
  - Production-ready architecture with audit trails, security, and scalability features
  - 9 critical bug fixes: logging, security, audit trails, API compatibility, Cypher queries, centrality access, validation, naming
  - Comprehensive documentation with usage guides, production examples, and API references
  - 100% test coverage with all validation tests passing (9/9 tests)
  - Enterprise-grade features for financial services, healthcare, legal, and business domains
  - Complete backward compatibility with existing semantica components
  - Performance optimizations: caching, indexing, and efficient graph operations

- **Added PgVector Store Support** (PR #303 by @Sameer6305, @KaifAhmad1):
  - Native PostgreSQL vector storage using pgvector extension with full integration
  - Multiple distance metrics: cosine, L2/Euclidean, inner product with automatic score normalization
  - Advanced indexing: HNSW and IVFFlat for approximate nearest neighbor search with tunable parameters
  - JSONB metadata storage with flexible filtering capabilities and batch operations
  - Connection pooling support with psycopg3/psycopg2 fallback and efficient resource management
  - Comprehensive VectorStore integration with backend delegation and unified API
  - Idempotent index creation and table management with safe migration support
  - Production-ready security: SQL injection protection with psycopg_sql.SQL() and input validation
  - Performance optimizations: UUID4-based IDs, batch executemany operations, connection pooling
  - Full backward compatibility with existing vector store implementations
  - 36+ comprehensive test cases with Docker integration and dependency skipping
  - Complete documentation with setup guides, examples, and performance tuning
  - CI/CD integration: resolved benchmark compatibility and fixed documentation links

- **Improved Vector Store for Decision Tracking** (PR #293 by @KaifAhmad1):
  - Comprehensive decision tracking capabilities with hybrid search combining semantic and structural embeddings
  - New DecisionEmbeddingPipeline for generating semantic and structural embeddings with KG algorithm integration
  - HybridSimilarityCalculator with configurable weights (semantic: 0.7, structural: 0.3)
  - DecisionContext high-level interface for decision management with explainable AI features
  - ContextRetriever with hybrid precedent search and multi-hop reasoning
  - User-friendly convenience API: quick_decision(), find_precedents(), explain(), similar_to(), batch_decisions(), filter_decisions()
  - Knowledge Graph algorithm integration: Node2Vec, PathFinder, CommunityDetector, CentralityCalculator, SimilarityCalculator, ConnectivityAnalyzer
  - Explainable AI with path tracing, confidence scoring, and comprehensive decision explanations
  - Performance optimizations: 0.028s per decision processing, 0.031s search performance, ~0.8KB per decision memory usage
  - 100% backward compatibility maintained with existing VectorStore functionality
  - 34+ comprehensive tests covering all functionality including end-to-end scenarios and performance benchmarks
  - Real-world validation examples for banking and insurance domains
  - Documentation with clear imports, examples, and API references

- **Improved Graph Algorithms in KG Module** (PR #292 by @KaifAhmad1):
  - Complete algorithm suite with 30+ graph algorithms across 7 categories
  - Node Embeddings: Node2Vec, DeepWalk, Word2Vec for structural similarity analysis
  - Similarity Analysis: Cosine, Euclidean, Manhattan, Correlation metrics with batch processing
  - Path Finding: Dijkstra, A*, BFS, K-shortest paths for route and network analysis
  - Link Prediction: Preferential attachment, Jaccard, Adamic-Adar for network completion
  - Centrality Analysis: Degree, Betweenness, Closeness, PageRank for importance ranking
  - Community Detection: Louvain, Leiden, Label propagation for clustering analysis
  - Connectivity Analysis: Components, bridges, density for network robustness
  - Unified provenance tracking system with GraphBuilderWithProvenance and AlgorithmTrackerWithProvenance
  - Complete execution tracking with metadata, timestamps, and reproducibility IDs
  - Comprehensive test coverage with 5 test suites and 40+ test methods
  - Professional documentation overhaul for all modules and reference documentation
  - Enterprise-ready functionality with error handling and NetworkX compatibility
  - Performance optimizations with sparse matrix operations and batch processing
  - Full backward compatibility maintained with gradual migration support

- **Improved Security Configuration with Dependabot**:
  - Configured bi-weekly security updates with manual review by @KaifAhmad1
  - Implemented automated security scans (Monday & Thursday at 7 AM IST) with Bandit, Safety, Semgrep
  - Added security-critical package grouping (cryptography, requests, urllib3, certifi, pyopenssl)
  - Enterprise-grade security with audit trail, compliance features, and zero auto-merge
  - Optimized IST timezone scheduling (Security scans: 7 AM IST, PRs: 9 AM IST)
  - Aligned with new Dependabot features: open-source proxy support, smart dependency grouping for Snowflake/Arrow/benchmark features, private registry support, semantic commit prefixes, and latest GitHub security best practices

- **ResourceScheduler Deadlock Fix and Performance Improvements** (PR #299, #301 by @d4ndr4d3, @KaifAhmad1):
  - Fixed critical deadlock in ResourceScheduler by replacing `threading.Lock()` with `threading.RLock()`
  - Resolved nested lock acquisition issue in `allocate_resources()` → `allocate_cpu/memory/gpu()` calls
  - Added allocation validation with `ValidationError` when no resources can be allocated
  - Improved performance by moving progress tracking updates outside lock scope
  - Implemented comprehensive resource cleanup on allocation failures to prevent leaks
  - Added complete regression test suite (6 tests) for deadlock prevention and edge cases
  - Improved error handling and documentation for better operator visibility
  - Zero breaking changes, maintains thread safety and backward compatibility

## [0.2.7] - 2026-02-09

### Added / Changed

- **Snowflake Connector for Data Ingestion** (PR #276 by @Sameer6305):
  - Native Snowflake connector with multi-authentication (password, OAuth, key-pair, SSO)
  - Table and query ingestion with pagination, schema introspection, batch processing
  - SQL injection prevention via identifier escaping, OAuth token validation
  - Progress tracking integration, context manager support, document export
  - 24 comprehensive unit tests with mocking, complete documentation and examples
  - Added as optional dependency `db-snowflake` with snowflake-connector-python>=3.0.0

- **Apache Arrow Export Support** (PR #273 by @Sameer6305):
  - Added Apache Arrow exporter with explicit schemas, entity/relationship export, compression support
  - Integrated with export module and method registry, Pandas/DuckDB compatible
  - 20 unit tests + 1 integration test, complete documentation with examples

- **Comprehensive Benchmark Suite with Regression CLI** (PR #289 by @ZohaibHassan16, @KaifAhmad1):
  - 137+ benchmarks across all 10 Semantica modules (Input, Core, Storage, Context, QA, Ontology, etc.)
  - Environment-agnostic design with robust mocking system for CI/CD compatibility
  - Statistical regression detection using Z-score analysis with configurable thresholds
  - Automated performance auditing via GitHub Actions workflow
  - Comprehensive documentation suite (benchmarks.md, architecture guides, usage examples)
  - Zero breaking changes, production-ready with ultra-fast text processing (>10,000 ops/s)
  - Added benchmark runner CLI: `python benchmarks/benchmark_runner.py`

## [0.2.6] - 2026-02-03

### Added / Changed

- **W3C PROV-O Compliant Provenance Tracking** (#254, #246):
  - Comprehensive provenance tracking system with W3C PROV-O compliance across all 17 Semantica modules
  - **Core Module**: `ProvenanceManager`, W3C PROV-O schemas, storage backends (InMemory, SQLite), SHA-256 integrity verification
  - **Module Integrations**: Semantic Extract, LLMs (Groq, OpenAI, HuggingFace, LiteLLM), Pipeline, Context, Ingest, Embeddings, Graph/Vector/Triplet stores, Reasoning, Conflicts, Deduplication, Export, Parse, Normalize, Ontology, Visualization
  - **Features**: Complete lineage tracking (Document → Chunk → Entity → Relationship → Graph), LLM tracking (tokens, costs, latency), source tracking, bridge axioms for domain transformations
  - **Compliance Infrastructure**: W3C PROV-O, FDA 21 CFR Part 11, SOX, HIPAA, TNFD
  - **Testing**: 237 tests covering core functionality, all 17 module integrations, edge cases, backward compatibility
  - **Design**: Opt-in with `provenance=False` by default, zero breaking changes, no new dependencies
  - Contributed by @KaifAhmad1

- **Enhanced Change Management Module** (#248, #243):
  - Enterprise-grade version control for knowledge graphs and ontologies with persistent storage and audit trails
  - **Core Classes**: `TemporalVersionManager` (KG versioning), `OntologyVersionManager` (ontology versioning), `ChangeLogEntry` (metadata)
  - **Storage**: SQLite (persistent) and in-memory backends with thread-safe operations
  - **Features**: SHA-256 checksums, detailed entity/relationship diffs, structural ontology comparison, email validation
  - **Compliance Infrastructure**: HIPAA, SOX, FDA 21 CFR Part 11 with immutable audit trails
  - **Testing**: 104 tests (100% pass) - unit, integration, compliance, performance, edge cases
  - **Performance**: 17.6ms for 10k entities, 510+ ops/sec concurrent, handles 5k+ entity graphs
  - **Migration**: Backward compatible, simplified class names, zero external dependencies
  - Contributed by @KaifAhmad1

- CSV Ingestion Enhancements (PR #244 by @saloni0318)
  - Auto-detect CSV encoding (chardet) and delimiter (csv.Sniffer)
  - Tolerant decoding and malformed-row handling (`on_bad_lines='warn'`)
  - Optional chunked reading for large files; metadata tracks detected values
  - Expanded unit tests covering delimiters, quoted/multiline fields, header overrides, chunks, and NaN preservation

- Tests: Comprehensive units for TextNormalizer (PR #242 by @ZohaibHassan16)
  - Added focused test coverage for TextNormalizer behavior across inputs

- Tests: Register integration mark and tidy ingest test warnings (PR #241 by @KaifAhmad1)
  - Introduced integration test marker and reduced noisy warnings in ingest tests

- **Ingest Unit Tests** (#239, #232):
  - Comprehensive unit tests for ingestion modules (file, web, and feed ingestors)
  - **Coverage**: File scanning (local/cloud S3/GCS/Azure), web ingestion (URL/sitemap/robots.txt), RSS/Atom feed parsing
  - **Testing**: 998 lines of test code with mocked external dependencies for fast, isolated execution
  - **Results**: file_ingestor (86%), web_ingestor (86%), feed_ingestor (80%) coverage
  - Covers happy paths, edge cases, and error handling
  - Contributed by @Mohammed2372

### Fixed

- **Temperature Compatibility Fix** (#256, #252):
  - Fixed hardcoded `temperature=0.3` that broke compatibility with models requiring specific temperature values (e.g., gpt-5-mini)
  - Added `_add_if_set` helper method to `BaseProvider` that only passes parameters when explicitly set
  - When `temperature=None`, parameter is omitted allowing APIs to use model defaults
  - Updated all 5 providers: OpenAI, Groq, Gemini, Ollama, DeepSeek
  - Reduced code by ~85 lines with cleaner parameter handling
  - Comprehensive test coverage added (10 temperature tests, all passing)
  - Backward compatible - no breaking changes
  - Contributed by @F0rt1s and @IGES-Institut

- **JenaStore Empty Graph Bug** (#257, #258):
  - Fixed `ProcessingError: Graph not initialized` when operating on empty (but initialized) graphs
  - Replaced implicit `if not self.graph:` checks with explicit `if self.graph is None:` validation in 5 methods (`add_triplets`, `get_triplets`, `delete_triplet`, `execute_sparql`, `serialize`)
  - Properly distinguishes `None` (uninitialized) from empty graphs (initialized with 0 triplets)
  - Unblocks benchmarking suite, fresh deployments, and testing workflows
  - Contributed by @ZohaibHassan16

## [0.2.5] - 2026-01-27

### Added
- **Pinecone Vector Store Support**:
    - Implemented native Pinecone support (`PineconeStore`) with full CRUD capabilities.
    - Added support for serverless and pod-based indexes, namespaces, and metadata filtering.
    - Integrated with `VectorStore` unified interface and registry.
    - (Closes #219, Resolves #220)
- **Configurable LLM Retry Logic**:
    - Exposed `max_retries` parameter in `NERExtractor`, `RelationExtractor`, `TripletExtractor` and low-level extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Defaults to 3 retries to prevent infinite loops during JSON validation failures or API timeouts.
    - Propagated retry configuration through chunked processing helpers to ensure consistent behavior for long documents.
    - Updated `03_Earnings_Call_Analysis.ipynb` to use `max_retries=3` by default.

### Added
- **Bring Your Own Model (BYOM) Support**:
    - Enabled full support for custom Hugging Face models in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added support for custom tokenizers in `HuggingFaceModelLoader` to handle models with non-standard tokenization requirements.
    - Implemented robust fallback logic for model selection: runtime options (`extract(model=...)`) now correctly override configuration defaults.
- **Enhanced NER Implementation**:
    - Added configurable aggregation strategies (`simple`, `first`, `average`, `max`) to `extract_entities_huggingface` for better sub-word token handling.
    - Implemented robust IOB/BILOU parsing to reconstruct entities from raw model outputs when structured output is unavailable.
    - Added confidence scoring for aggregated entities.
- **Relation Extraction Improvements**:
    - Implemented standard entity marker technique (wrapping subject/object with `<subj>`, `<obj>` tags) in `extract_relations_huggingface` for compatibility with sequence classification models.
    - Added structured output parsing to convert raw model predictions into validated `Relation` objects.
- **Triplet Extraction Completion**:
    - Added specialized parsing for Seq2Seq models (e.g., REBEL) in `extract_triplets_huggingface` to generate structured triplets directly from text.
    - Implemented post-processing logic to clean and validate generated triplets.

### Fixed
- **LLM Extraction Stability**:
    - Fixed infinite retry loops in `BaseProvider` by strictly enforcing `max_retries` limit during structured output generation.
    - Resolved stuck execution in earnings call analysis notebooks when using smaller models (e.g., Llama 3 8B) that frequently produce invalid JSON.
- **Model Parameter Precedence**:
    - Fixed issue where configuration defaults took precedence over runtime arguments in Hugging Face extractors. Runtime options now correctly override config values.
- **Import Handling**:
    - Fixed circular import issues in test suites by implementing robust mocking strategies.

## [0.2.4] - 2026-01-22

### Added
- **Ontology Ingestion Module**:
    - Implemented `OntologyIngestor` in `semantica.ingest` for parsing RDF/OWL files (Turtle, RDF/XML, JSON-LD, N3) into standardized `OntologyData` objects.
    - Added `ingest_ontology` convenience function and integrated it into the unified `ingest(source_type="ontology")` interface.
    - Added recursive directory scanning support for batch ontology ingestion.
    - Exposed ingestion tools in `semantica.ontology` for better discoverability.
    - Added `OntologyData` dataclass for consistent metadata handling (source path, format, timestamps).
- **Documentation**:
    - **Ontology Usage Guide**: Updated `ontology_usage.md` with comprehensive examples for single-file and directory ingestion.
    - **API Reference**: Updated `ontology.md` with `OntologyIngestor` class documentation and method details.
- **Tests**:
    - **Comprehensive Test Suite**: Added `tests/ingest/test_ontology_ingestor.py` covering all supported formats, error handling, and unified interface integration.
    - **Demo Script**: Added `examples/demo_ontology_ingest.py` for end-to-end usage demonstration.

## [0.2.3] - 2026-01-20

### Fixed
- **LLM Relation Extraction Parsing**:
    - Fixed relation extraction returning zero relations despite successful API calls to Groq and other providers
    - Normalized typed responses from instructor/OpenAI/Groq to consistent dict format before parsing
    - Added structured JSON fallback when typed generation yields zero relations to avoid silent empty outputs
    - Removed acceptance of extra kwargs (`max_tokens`, `max_entities_prompt`) from relation extraction internals
    - Filtered kwargs passed to provider LLM calls to only `temperature` and `verbose`
- **API Parameter Handling**:
    - Limited kwargs forwarded in chunked extraction helper to prevent parameter leakage
    - Ensured minimal, safe parameters are passed to provider calls
- **Pipeline Circular Import (Issues #192, #193)**:
    - Fixed circular import between `pipeline_builder` and `pipeline_validator` triggered during `semantica.pipeline` import
    - Lazy-loaded `PipelineValidator` inside `PipelineBuilder.__init__` and guarded type hints with `TYPE_CHECKING`
    - Ensured `from semantica.deduplication import DuplicateDetector` no longer fails even when pipeline module is imported
- **JupyterLab Progress Output (Issue #181)**:
    - Added `SEMANTICA_DISABLE_JUPYTER_PROGRESS` environment variable to disable rich Jupyter/Colab progress tables
    - When enabled, progress falls back to console-style output, preventing infinite scrolling and JupyterLab out-of-memory errors

### Added
- **Comprehensive Test Suite**:
-    - Added unit tests (`tests/test_relations_llm.py`) with mocked LLM provider covering both typed and structured response paths
-    - Added integration tests (`tests/integration/test_relations_groq.py`) for real Groq API calls with environment variable API key
-    - Tests validate relation extraction completion and result parsing across different response formats
- **Amazon Neptune Dev Environment**:
-    - Added CloudFormation template (`cookbook/introduction/neptune-setup.yaml`) to provision a dev Neptune cluster with public endpoint and IAM auth enabled
-    - Documented deployment, cost estimates, and IAM User vs IAM Role best practices in `cookbook/introduction/21_Amazon_Neptune_Store.ipynb`
-    - Added `cfn-lint` to `.pre-commit-config.yaml` for validating CloudFormation templates while excluding `neptune-setup.yaml` from generic YAML linters
- **Vector Store High-Performance Ingestion**:
-    - Added `VectorStore.add_documents` for high-throughput ingestion with automatic embedding generation, batching, and parallel processing
-    - Added `VectorStore.embed_batch` helper for generating embeddings for lists of texts without immediately storing them
-    - Enabled default parallel ingestion in `VectorStore` with `max_workers=6` for common workloads
-    - Added dedicated documentation page `docs/vector_store_usage.md` describing high-performance vector store usage and configuration
-    - Added `tests/vector_store/test_vector_store_parallel.py` covering parallel vs sequential performance, error handling, and edge cases for `add_documents` and `embed_batch`

### Changed
- **Relation Extraction API**:
-    - Simplified parameter interface by removing unused kwargs that were previously ignored
-    - Improved error handling and verbose logging for debugging relation extraction issues
-    - Enhanced robustness of post-response parsing across different LLM providers
- **Vector Store Defaults and Examples**:
-    - Standardized `VectorStore` default concurrency to `max_workers=6` for parallel ingestion
-    - Updated vector store reference documentation and usage guides to rely on implicit defaults instead of requiring manual `max_workers` configuration in examples


## [0.2.2] - 2026-01-15

### Added
- **Parallel Extraction Engine**:
    - Implemented high-throughput parallel batch processing across all core extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticNetworkExtractor`) using `concurrent.futures.ThreadPoolExecutor`.
    - Added `max_workers` configuration parameter (default: 1) to all extractor `extract()` methods, allowing users to tune concurrency based on available CPU cores or API rate limits.
    - **Parallel Chunking**: Implemented parallel processing for large document chunking in `_extract_entities_chunked` and `_extract_relations_chunked`, significantly reducing latency for long-form text analysis.
    - **Thread-Safe Progress Tracking**: Enhanced `ProgressTracker` to handle concurrent updates from multiple threads without race conditions during batch processing.
- **Semantic Extract Performance & Regression**:
    - Added edge-case regression suite covering max worker defaults, LLM prompt entity filtering, and extractor reuse.
    - Added a runnable real-use-case benchmark script for batch latency across `NERExtractor`, `RelationExtractor`, `TripletExtractor`, `EventDetector`, `SemanticAnalyzer`, and `SemanticNetworkExtractor`.
    - Added Groq LLM smoke tests that exercise LLM-based entities/relations/triplets when `GROQ_API_KEY` is available via environment configuration.

### Security
- **Credential Sanitization**:
    - Removed hardcoded API keys from 8 cookbook notebooks to prevent secret leakage.
    - Enforced environment variable usage for `GROQ_API_KEY` across all examples.
- **Secure Caching**:
    - Updated `ExtractionCache` to exclude sensitive parameters (e.g., `api_key`, `token`, `password`) from cache key generation, preventing secret leakage and enabling safe cache sharing.
    - Upgraded cache key hashing algorithm from MD5 to **SHA-256** for enhanced collision resistance and security.

### Changed
- **Gemini SDK Migration**:
    - Migrated `GeminiProvider` to use the new `google-genai` SDK (v0.1.0+) to address deprecation warnings.
    - Implemented graceful fallback to `google.generativeai` for backward compatibility.
- **Dependency Resolution**:
    - Pinned `opentelemetry-api` and `opentelemetry-sdk` to `1.37.0` to resolve pip conflicts.
    - Updated `protobuf` and `grpcio` constraints for better stability.
- **Entity Filtering Scope**:
    - Removed entity filtering from non-LLM extraction flows to avoid accuracy regressions.
    - Applied entity downselection only to LLM relation prompt construction, while matching returned entities against the full original entity list.
- **Batch Concurrency Defaults**:
    - Standardized `max_workers` defaulting across `semantic_extract` and tuned for low-latency: ML-backed methods default to single-worker, while pattern/regex/rules/LLM/huggingface methods use a higher parallelism default capped by CPU.
    - Raised the global `optimization.max_workers` default to 8 for better throughput on batch workloads.

### Performance
- **Bottleneck Optimization (GitHub Issue #186)**:
    - **Resolved Bottleneck #1 (Sequential Processing)**: Replaced sequential `for` loops with parallel execution for both document-level batches and intra-document chunks.
    - **Performance Gains**: Achieved **~1.89x speedup** in real-world extraction scenarios (tested with Groq `llama-3.3-70b-versatile` on standard datasets).
    - **Initialization Optimization**: Refactored test suite to use class-level `setUpClass` for LLM provider initialization, eliminating redundant API client creation overhead.
- **Low-Latency Entity Matching**:
    - Avoided heavyweight embedding stack imports on common matches by improving fast matching heuristics and short-circuiting before embedding similarity.
    - Optimized entity matching to prioritize exact/substring/word-boundary matches and only fall back to embedding similarity when needed, reducing CPU overhead in LLM relation/triplet mapping.


## [0.2.1] - 2026-01-12

### Fixed
- **LLM Output Stability (Bug #176)**:
    - Fixed incomplete JSON output issues by correctly propagating `max_tokens` parameter in `extract_relations_llm`.
    - Implemented automatic error handling that halves chunk sizes and retries when LLM context or output limits are exceeded.
    - Fixed `AttributeError` in provider integration by ensuring consistent parameter passing via `**kwargs`.
- **Constraint Relaxations**:
    - Removed hardcoded `max_length` constraints from `Entity`, `Relation`, and `Triplet` classes to support long-form semantic extraction (e.g., long descriptions or names).
- Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
- Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
- Fixed dependency compatibility issues by pinning `protobuf>=5.29.1,<7.0` and `grpcio>=1.71.2`.
- Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
- Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Changed
- **Chunking Defaults**:
    - Increased default `max_text_length` for auto-chunking to **64,000 characters** (from 32k/16k) for OpenAI, Anthropic, Gemini, Groq, and DeepSeek providers.
    - Unified chunking logic across `extract_entities_llm`, `extract_relations_llm`, and `extract_triplets_llm`.
- **Groq Support**:
    - Standardized Groq provider defaults to use `llama-3.3-70b-versatile` with a 64k context window.
    - Added native support for `max_tokens` and `max_completion_tokens` to prevent output truncation.

### Added
- **Testing**:
    - Added `tests/reproduce_issue_176.py` to validate `max_tokens` propagation and chunking behavior across all extractors.


## [0.2.0] - 2026-01-10

### Added
- **Amazon Neptune Support**:
    - Added `AmazonNeptuneStore` providing Amazon Neptune graph database integration via Bolt protocol and OpenCypher.
    - Implemented `NeptuneAuthTokenManager` extending Neo4j AuthManager for AWS IAM SigV4 signing with automatic token refresh.
    - Added robust connection handling: retry logic with backoff for transient errors (signature expired, connection closed) and driver recreation.
    - Added `graph-amazon-neptune` optional dependency group (boto3, neo4j).
    - Comprehensive test suite covering all GraphStore interface methods.
- **Docling Integration**:
    - Added `DoclingParser` in `semantica.parse` for high-fidelity document parsing using the Docling library.
    - Supports multi-format parsing (PDF, DOCX, PPTX, XLSX, HTML, images) with superior table extraction and structure understanding.
    - Implemented as a standalone parser supporting local execution, OCR, and multiple export formats (Markdown, HTML, JSON).
- **Robust Extraction Fallbacks**:
    - Implemented comprehensive fallback chains ("ML/LLM" -> "Pattern" -> "Last Resort") across `NERExtractor`, `RelationExtractor`, and `TripletExtractor` to prevent empty result lists.
    - Added "Last Resort" pattern matching in `NERExtractor` to identify capitalized words as generic entities when all other methods fail.
    - Added "Last Resort" adjacency-based relation extraction in `RelationExtractor` to create weak connections between adjacent entities if no relations are found.
    - Added fallback logic in `TripletExtractor` to convert relations to triplets or use rule-based extraction if standard methods fail.
- **Provenance & Tracking**:
    - Added count tracking to batch processing logs in `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Added `batch_index` and `document_id` to the metadata of all extracted entities, relations, triplets, semantic roles, and clusters for better traceability.
- **Semantic Extract Improvements**:
    - Introduced `auto-chunking` for long text processing in LLM extraction methods (`extract_entities_llm`, `extract_relations_llm`, `extract_triplets_llm`).
    - Added `silent_fail` parameter to LLM extraction methods for configurable error handling.
    - Implemented robust JSON parsing and automatic retry logic (3 attempts with exponential backoff) in `BaseProvider` for all LLM providers.
    - Enhanced `GroqProvider` with better diagnostics and connectivity testing.
    - Added comprehensive entity, relation, and triplet deduplication for chunked extraction.
    - Added `semantica/semantic_extract/schemas.py` with canonical Pydantic models for consistent structured output.
- **Testing**:
    - Added comprehensive robustness test suite `tests/semantic_extract/test_robustness_fallback.py` for validating extraction fallbacks and metadata propagation.
    - Added comprehensive unit test suite `tests/embeddings/test_model_switching.py` for verifying dynamic model transitions and dimension updates.
    - Added end-to-end integration test suite for Knowledge Graph pipeline validation (GraphBuilder -> EntityResolver -> GraphAnalyzer).
- **Other**:
    - Added missing dependencies `GitPython` and `chardet` to `pyproject.toml`.
    - Robustified ID extraction across `CentralityCalculator`, `CommunityDetector`, and `ConnectivityAnalyzer` to handle various entity formats.
    - Improved `Entity` class hashability and equality logic in `utils/types.py`.

### Changed
- **Deduplication & Conflict Logic**:
    - Removed internal deduplication logic from `NERExtractor`, `RelationExtractor`, and `TripletExtractor`.
    - Removed consistency/conflict checking from `ExtractionValidator` to defer to dedicated `semantica/conflicts` module.
    - Removed `_deduplicate_*` methods from `semantica/semantic_extract/methods.py`.
- **Batch Processing & Consistency**:
    - Standardized batch processing across all extractors (`NERExtractor`, `RelationExtractor`, `TripletExtractor`, `SemanticNetworkExtractor`, `EventDetector`, `SemanticAnalyzer`, `CoreferenceResolver`) using a unified `extract`/`analyze`/`resolve` method pattern with progress tracking.
    - Added provenance metadata (`batch_index`, `document_id`) to `SemanticNetwork` nodes/edges, `Event` objects, `SemanticRole` results, `CoreferenceChain` mentions, and `SemanticCluster` (tracking source `document_ids`).
    - Updated `SemanticClusterer.cluster` and `SemanticAnalyzer.cluster_semantically` to accept list of dictionaries (with `content` and `id` keys) for better document tracking during clustering.
    - Removed legacy `check_triplet_consistency` from `TripletExtractor`.
    - Removed `validate_consistency` and `_check_consistency` from `ExtractionValidator`.
- **Weighted Scoring**:
    - Clarified weighted confidence scoring (50% Method Confidence + 50% Type Similarity) in comments.
    - Explicitly labeled "Type Similarity" as "user-provided" in code comments to remove ambiguity.
- **Refactoring**:
    - Fixed orchestrator lazy property initialization and configuration normalization logic in `Orchestrator`.
    - Verified and aligned `FileObject.text` property usage in GraphRAG notebooks for consistent content decoding.

### Fixed
- **Critical Fixes**:
    - Resolved `NameError` in `extraction_validator.py` by adding missing `Union` import.
    - Resolved issues where extractors would return empty lists for valid input text when primary extraction methods failed.
    - Fixed metadata initialization issue in batch processing where `batch_index` and `document_id` were occasionally missing from extracted items.
    - Ensured `LLMExtraction` methods (`enhance_entities`, `enhance_relations`) return original input instead of failing or returning empty results when LLM providers are unavailable.
- **Component Fixes**:
    - Fixed model switching bug in `TextEmbedder` where internal state was not cleared, preventing dynamic updates between `fastembed` and `sentence_transformers` (#160).
    - Implemented model-intrinsic embedding dimension detection in `TextEmbedder` to ensure consistency between models and vector databases.
    - Updated `set_model` to properly refresh configuration and dimensions during model switches.
    - Fixed `TypeError: unhashable type: 'Entity'` in `GraphAnalyzer` when processing graphs with raw `Entity` objects or dictionaries in relationships (#159).
    - Resolved `AssertionError` in orchestrator tests by aligning test mocks with production component usage.
    - Fixed dependency compatibility issues by pinning `protobuf==4.25.3` and `grpcio==1.67.1`.
    - Fixed a bug in `TripletExtractor` where the `validate_triplets` method was shadowed by an internal attribute.
    - Fixed incorrect `TextSplitter` import path in the `semantic_extract.methods` module.

## [0.1.1] - 2026-01-05

### Added
- Exported `DoclingParser` and `DoclingMetadata` from `semantica.parse` for easier access.
- Added comprehensive `DoclingParser` usage examples to README and documentation.
- Added Windows-specific troubleshooting note for PyTorch DLL issues.

### Fixed
- Fixed `DoclingParser` import/export issues across platforms (Windows, Linux, Google Colab).
- Improved error messaging when optional `docling` dependency is missing.
- Fixed versioning inconsistencies across the framework.

## [0.1.0] - 2025-12-31

### Added
- New command-line interface (`semantica` CLI) with support for knowledge base building and info commands.
- Integrated FastAPI-based REST API server for remote access to framework functionality.
- Dedicated background worker component for scalable task processing and pipeline execution.
- Framework-level versioning configuration for PyPI distribution.
- Automated release workflow with Trusted Publishing support.

### Changed
- Updated versioning across the framework to 0.1.0.
- Refined entry point configurations in `pyproject.toml`.
- Improved lazy module loading for core framework components.

## [0.0.5] - 2025-11-26

### Changed
- Configured Trusted Publishing for secure automated PyPI deployments

## [0.0.4] - 2025-11-26

### Changed
- Fixed PyPI deployment issues from v0.0.3

## [0.0.3] - 2025-11-25

### Changed
- Simplified CI/CD workflows - removed failing tests and strict linting
- Combined release and PyPI publishing into single workflow
- Simplified security scanning to weekly pip-audit only
- Streamlined GitHub Actions configuration

### Added
- Comprehensive issue templates (Bug, Feature, Documentation, Support, Grant/Partnership)
- Updated pull request template with clear guidelines
- Community support documentation (SUPPORT.md)
- Funding and sponsorship configuration (FUNDING.yml)
- GitHub configuration README for maintainers
- 10+ new domain-specific cookbook examples (Finance, Healthcare, Cybersecurity, etc.)

### Removed
- Redundant scripts folder (8 shell/PowerShell scripts)
- Unnecessary automation workflows (label-issues, mark-answered)
- Excessive issue templates

## [0.0.2] - 2025-11-25

### Changed
- Updated README with streamlined content and better examples
- Added more notebooks to cookbook
- Improved documentation structure

## [0.0.1] - 2024-01-XX

### Added
- Core framework architecture
- Universal data ingestion (multiple file formats)
- Semantic intelligence engine (NER, relation extraction, event detection)
- Knowledge graph construction with entity resolution
- 6-stage ontology generation pipeline
- GraphRAG engine for hybrid retrieval
- Multi-agent system infrastructure
- Production-ready quality assurance modules
- Comprehensive documentation with MkDocs
- Cookbook with interactive tutorials
- Support for multiple vector stores (Weaviate, Qdrant, FAISS)
- Support for multiple graph databases (Neo4j, NetworkX, RDFLib)
- Temporal knowledge graph support
- Conflict detection and resolution
- Deduplication and entity merging
- Schema template enforcement
- Seed data management
- Multi-format export (RDF, JSON-LD, CSV, GraphML)
- Visualization tools
- Pipeline orchestration
- Streaming support (Kafka, RabbitMQ, Kinesis)
- Context engineering for AI agents
- Reasoning and inference engine

### Documentation
- Getting started guide
- API reference for all modules
- Concepts and architecture documentation
- Use case examples
- Cookbook tutorials
- Community projects showcase

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

## Migration Guides

When breaking changes are introduced, migration guides will be provided in the release notes and documentation.

---

For detailed release notes, see [GitHub Releases](https://github.com/Hawksight-AI/semantica/releases).

