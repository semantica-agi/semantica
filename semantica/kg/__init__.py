"""
Knowledge Graph Management Module

This module provides comprehensive knowledge graph construction and management capabilities
for the Semantica framework, including temporal knowledge graph support for time-aware
knowledge representation, graph analytics, entity resolution, and provenance tracking.

Note: For conflict detection and resolution, use the semantica.conflicts module.
For deduplication, use the semantica.deduplication module.

Algorithms Used:

Knowledge Graph Construction:
    - Graph Building: Entity-relationship graph construction from multiple sources
    - Entity Resolution: Fuzzy string matching, exact matching, semantic similarity matching for duplicate detection
    - Temporal Graph Support: Time-aware edge creation with valid_from/valid_until timestamps
    - Temporal Granularity: Time normalization (second, minute, hour, day, week, month, year)
    - Entity Merging: Property aggregation, metadata merging, provenance tracking
    - Incremental Building: Batch processing for large graphs

Graph Analysis:
    - Degree Centrality: Normalized degree calculation (degree / (n-1)) for connectivity measure
    - Betweenness Centrality: Shortest path counting (BFS-based), path normalization by (n-1)*(n-2)/2
    - Closeness Centrality: Average distance calculation, (n-1) / sum of distances normalization
    - Eigenvector Centrality: Power iteration method, adjacency matrix eigenvalue computation, convergence tolerance
    - Community Detection: Louvain algorithm (greedy modularity optimization), Leiden algorithm (with refinement step)
    - Overlapping Communities: K-clique community detection, dense subgraph detection
    - Modularity Calculation: Q = (1/2m) * Σ(A_ij - k_i*k_j/2m) * δ(c_i, c_j)
    - Graph Connectivity: DFS-based connected component detection, component size analysis
    - Bridge Detection: Edge removal and connectivity change detection
    - Path Finding: BFS shortest path algorithm, all-pairs shortest paths computation
    - Graph Density: E / (n*(n-1)/2) calculation for undirected graphs
    - Structure Classification: Density-based classification (sparse, moderate, dense, disconnected)

Entity Resolution:
    - Duplicate Detection: Similarity-based grouping using threshold matching
    - Fuzzy Matching: String similarity algorithms (Levenshtein, Jaro-Winkler)
    - Semantic Matching: Embedding-based similarity for semantic entity matching
    - Entity Merging: Property conflict resolution, metadata aggregation
    - ID Normalization: Canonical ID assignment for merged entities


Temporal Operations:
    - Time-Point Queries: Temporal filtering using valid_from/valid_until comparison
    - Time-Range Queries: Interval overlap detection, union/intersection aggregation
    - Temporal Pattern Detection: Sequence detection, cycle detection, trend analysis
    - Graph Evolution Analysis: Time-series relationship counting, diversity metrics, stability measures
    - Temporal Path Finding: BFS with temporal validity constraints
    - Version Management: Snapshot creation, version comparison, timestamp-based versioning

Provenance Tracking:
    - Source Tracking: Multi-source entity tracking, timestamp recording
    - Lineage Retrieval: Complete provenance history reconstruction
    - Metadata Aggregation: Source metadata merging, temporal metadata tracking
    - Temporal Tracking: First seen, last updated timestamp management

Seed Management:
    - Data Normalization: Format conversion (list, dict, single entity), ID generation
    - Source Tracking: Source identifier assignment, metadata attachment
    - File Loading: JSON parsing, file-based seed data loading

Key Features:
    - Knowledge graph construction from multiple sources
    - Temporal knowledge graph support with time-aware edges
    - Entity resolution
    - Comprehensive graph analytics (centrality, communities, connectivity)
    - Temporal queries and pattern detection
    - Provenance tracking and lineage management
    - Method registry for extensibility
    - Configuration management with environment variables and config files

Main Classes:
    - GraphBuilder: Knowledge graph construction with temporal support
    - EntityResolver: Entity resolution and deduplication
    - GraphAnalyzer: Graph analytics with temporal evolution analysis
    - TemporalGraphQuery: Time-aware graph querying
    - TemporalPatternDetector: Temporal pattern detection
    - TemporalVersionManager: Temporal versioning and snapshots
    - ProvenanceTracker: Provenance tracking and management
    - CentralityCalculator: Centrality measures calculation
    - CommunityDetector: Community detection
    - ConnectivityAnalyzer: Connectivity analysis
    - SeedManager: Seed data management
    - MethodRegistry: Registry for custom KG methods
    - KGConfig: Configuration manager for KG module

Global Instances:
    - method_registry: Global MethodRegistry instance for registering custom methods
    - kg_config: Global KGConfig instance for configuration management

Example Usage:
    >>> from semantica.kg import GraphBuilder, GraphAnalyzer, CentralityCalculator
    >>> # Build knowledge graph
    >>> builder = GraphBuilder(merge_entities=True)
    >>> kg = builder.build(sources=[{"entities": [...], "relationships": [...]}])
    >>> # Analyze graph
    >>> analyzer = GraphAnalyzer()
    >>> analysis = analyzer.analyze_graph(kg)
    >>> # Calculate centrality
    >>> centrality_calc = CentralityCalculator()
    >>> degree_centrality = centrality_calc.calculate_degree_centrality(kg)

Author: Semantica Contributors
License: MIT
"""


from .centrality_calculator import CentralityCalculator
from .community_detector import CommunityDetector
from .config import KGConfig, kg_config
from .connectivity_analyzer import ConnectivityAnalyzer
from .entity_resolver import EntityResolver
from .graph_analyzer import GraphAnalyzer
from .graph_builder import GraphBuilder
from .graph_validator import GraphValidator
from .link_predictor import LinkPredictor
from .node_embeddings import NodeEmbedder
from .path_finder import PathFinder
from .kg_provenance import GraphBuilderWithProvenance, AlgorithmTrackerWithProvenance
from .provenance_tracker import ProvenanceTracker
from .registry import MethodRegistry, method_registry, AlgorithmRegistry, algorithm_registry
from .seed_manager import SeedManager
from .similarity_calculator import SimilarityCalculator
from .temporal_query import (
    TemporalGraphQuery,
    TemporalPatternDetector,
    TemporalVersionManager,
)
from .knowledge_graph import KnowledgeGraph
from .temporal_model import BiTemporalFact, TemporalBound
from .temporal_normalizer import TemporalNormalizer
from .temporal_query_rewriter import TemporalQueryRewriter, TemporalQueryResult

__all__ = [
    # Core Classes
    "KnowledgeGraph",
    "GraphBuilder",
    "GraphBuilderWithProvenance",
    "EntityResolver",
    "GraphAnalyzer",
    "GraphValidator",
    "TemporalGraphQuery",
    "TemporalPatternDetector",
    "TemporalVersionManager",
    "TemporalBound",
    "BiTemporalFact",
    "TemporalNormalizer",
    "TemporalQueryRewriter",
    "TemporalQueryResult",
    "AlgorithmTrackerWithProvenance",
    "ProvenanceTracker",
    # Enhanced Graph Algorithms
    "NodeEmbedder",
    "SimilarityCalculator",
    "PathFinder",
    "LinkPredictor",
    # Existing Analysis Classes
    "CentralityCalculator",
    "CommunityDetector",
    "ConnectivityAnalyzer",
    "SeedManager",
    # Registry and Configuration
    "MethodRegistry",
    "method_registry",
    "AlgorithmRegistry",
    "algorithm_registry",
    "KGConfig",
    "kg_config",
]
