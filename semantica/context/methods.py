"""
Context Retrieval and Search Methods.

Provides high-level functional APIs for global Map-Reduce retrieval, DRIFT
hybrid search, and unified context retrieval, with registration into the
context method registry.
"""

from typing import Any, List, Optional, Union

from ..kg.community_hierarchy import CommunityHierarchy
from ..kg.community_summarizer import CommunityReport
from ..utils.logging import get_logger
from .context_retriever import ContextRetriever, RetrievedContext
from .drift_search import DriftSearchEngine, DriftSearchResult
from .global_retriever import GlobalGraphRetriever, GlobalSearchResult
from .registry import method_registry

logger = get_logger("context_methods")


def retrieve_global(
    query: str,
    reports: Optional[
        Union[
            List[Union[CommunityReport, dict]],
            dict,
        ]
    ] = None,
    hierarchy: Optional[CommunityHierarchy] = None,
    llm: Optional[Any] = None,
    level: Optional[int] = None,
    max_context_tokens: int = 4000,
    min_relevance_score: float = 0.0,
    **kwargs: Any,
) -> GlobalSearchResult:
    """
    Execute global hierarchical GraphRAG retrieval over community reports.

    Args:
        query: Natural language query string.
        reports: Community reports collection or mapping.
        hierarchy: Optional hierarchical community structure.
        llm: LLM client or callable for Map and Reduce phases.
        level: Coarsening level to query.
        max_context_tokens: Maximum token budget.
        min_relevance_score: Minimum relevance threshold (0.0 - 10.0).
        **kwargs: Additional options for GlobalGraphRetriever.

    Returns:
        GlobalSearchResult with synthesized answer, key points, and citations.
    """
    retriever = GlobalGraphRetriever(
        reports=reports,
        hierarchy=hierarchy,
        llm=llm,
        max_context_tokens=max_context_tokens,
        min_relevance_score=min_relevance_score,
        **kwargs,
    )
    return retriever.search(
        query,
        level=level,
        min_relevance_score=min_relevance_score,
        **kwargs,
    )


def retrieve_drift(
    query: str,
    knowledge_graph: Optional[Any] = None,
    reports: Optional[
        Union[
            List[Union[CommunityReport, dict]],
            dict,
        ]
    ] = None,
    hierarchy: Optional[CommunityHierarchy] = None,
    llm: Optional[Any] = None,
    max_depth: int = 2,
    drift_threshold: float = 0.35,
    **kwargs: Any,
) -> DriftSearchResult:
    """
    Execute DRIFT hybrid search combining global framing and local graph exploration.

    Args:
        query: Natural language search query.
        knowledge_graph: Knowledge graph store or dictionary.
        reports: Community reports collection or mapping.
        hierarchy: Optional hierarchical community structure.
        llm: LLM client or callable for reasoning and synthesis.
        max_depth: Entity traversal depth limit.
        drift_threshold: Minimum alignment score for pruning graph drift.
        **kwargs: Additional options for DriftSearchEngine.

    Returns:
        DriftSearchResult with answer, verified contexts, citations, and metrics.
    """
    engine = DriftSearchEngine(
        knowledge_graph=knowledge_graph,
        reports=reports,
        hierarchy=hierarchy,
        llm=llm,
        max_depth=max_depth,
        drift_threshold=drift_threshold,
        **kwargs,
    )
    return engine.search(
        query,
        max_depth=max_depth,
        drift_threshold=drift_threshold,
        **kwargs,
    )


def retrieve_context(
    query: str,
    retriever: Optional[ContextRetriever] = None,
    mode: str = "local",
    max_results: int = 5,
    **kwargs: Any,
) -> List[RetrievedContext]:
    """
    Unified context retrieval supporting local, global, drift, and hybrid modes.

    Args:
        query: Search query string.
        retriever: ContextRetriever instance (created if not provided).
        mode: Retrieval mode ('local', 'global', 'drift', 'hybrid').
        max_results: Maximum number of contexts to return.
        **kwargs: Additional options passed to retriever.

    Returns:
        List of RetrievedContext objects.
    """
    if retriever is None:
        retriever = ContextRetriever(**kwargs)
    return retriever.retrieve(
        query, max_results=max_results, mode=mode, **kwargs
    )


# Functional aliases
global_search = retrieve_global
drift_search = retrieve_drift

# Pre-register in semantica.context method registry
method_registry.register(
    "retrieval",
    "global",
    retrieve_global,
    metadata={
        "description": "Global Map-Reduce retrieval across community reports",
        "parameters": ["query", "reports", "hierarchy", "llm", "level"],
    },
    capabilities=["map_reduce", "dynamic_levels", "citations"],
)

method_registry.register(
    "retrieval",
    "drift",
    retrieve_drift,
    metadata={
        "description": "DRIFT hybrid global-local retrieval engine",
        "parameters": ["query", "knowledge_graph", "reports", "llm"],
    },
    capabilities=["directed_reasoning", "drift_pruning", "dual_attribution"],
)

method_registry.register(
    "retrieval",
    "context",
    retrieve_context,
    metadata={
        "description": "Unified context retriever dispatcher",
        "parameters": ["query", "retriever", "mode", "max_results"],
    },
    capabilities=["multi_mode", "hybrid", "ranking"],
)

method_registry.register(
    "global_retrieval",
    "default",
    retrieve_global,
    metadata={"description": "Default global GraphRAG retrieval"},
    capabilities=["map_reduce", "level_promotion"],
)

method_registry.register(
    "drift_search",
    "default",
    retrieve_drift,
    metadata={"description": "Default DRIFT hybrid search"},
    capabilities=["thematic_framing", "iterative_deepening"],
)
