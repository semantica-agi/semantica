"""
Provenance Tracking Module for Semantica

Provides audit-grade provenance tracking for high-stakes domains requiring
complete traceability (blue finance, healthcare, legal, pharma).

This module consolidates and enhances provenance tracking from:
- kg.ProvenanceTracker (entity/relationship tracking)
- split.ProvenanceTracker (chunk tracking)
- conflicts.SourceTracker (source tracking)

Key Features:
    - W3C PROV-O compliant tracking
    - End-to-end lineage (doc → chunk → entity → KG → query → response)
    - Bridge axiom translation chains (L1 → L2 → L3)
    - Audit-grade source tracking (DOI + page + quote)
    - Zero breaking changes (opt-in only)
    - No new dependencies (stdlib only)

Example Usage:
    >>> # Enable provenance tracking
    >>> from semantica.semantic_extract import NERExtractor
    >>> ner = NERExtractor(provenance=True)
    >>> entities = ner.extract("Steve Jobs founded Apple.")
    >>> 
    >>> # Trace lineage
    >>> from semantica.provenance import ProvenanceManager
    >>> prov_mgr = ProvenanceManager()
    >>> lineage = prov_mgr.get_lineage(entities[0].id)
    >>> 
    >>> # Track with source details
    >>> prov_mgr.track_entity(
    ...     entity_id="entity_1",
    ...     source="DOI:10.1371/journal.pone.0023601",
    ...     source_location="Figure 2",
    ...     source_quote="Total fish biomass increased by 463%...",
    ...     confidence=0.92
    ... )

Author: Semantica Contributors
License: MIT
"""

from .schemas import (
    ProvenanceEntry,
    SourceReference,
    AgentRecord,
    ActivityRecord,
    Invalidation,
)
from .storage import ProvenanceStorage, InMemoryStorage, SQLiteStorage
from .manager import ProvenanceManager, default_storage_path, storage_path_from_env
from .integrity import compute_checksum, verify_checksum

__all__ = [
    # Core schemas
    "ProvenanceEntry",
    "SourceReference",
    "AgentRecord",
    "ActivityRecord",
    "Invalidation",

    # Storage backends
    "ProvenanceStorage",
    "InMemoryStorage",
    "SQLiteStorage",
    
    # Manager
    "ProvenanceManager",
    "default_storage_path",
    "storage_path_from_env",
    
    # Utilities
    "compute_checksum",
    "verify_checksum",
]

__version__ = "1.0.0"
__author__ = "Semantica Team"
__description__ = "Audit-Grade Provenance Tracking for Semantica"
