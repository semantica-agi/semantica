"""
KnowledgeGraph dataclass — canonical in-memory representation.

This is the formal type produced by the Semantica KG pipeline and consumed
by visualizers, exporters, and other downstream components.  It is a thin,
immutable-friendly wrapper around three plain collections so that isinstance
checks, type hints, and IDEs can surface the type rather than relying on
bare dicts.

Keeping this in its own file avoids circular imports between the kg and
visualization sub-packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class KnowledgeGraph:
    """
    Canonical in-memory knowledge graph.

    Attributes:
        entities:      List of entity dicts with at minimum ``id`` and ``type`` keys.
        relationships: List of relationship dicts with at minimum ``source``,
                       ``target``, and ``type`` keys.
        metadata:      Arbitrary graph-level metadata (e.g. build timestamps,
                       entity-resolution flags).
    """

    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of entities (mirrors the most common 'size' query)."""
        return len(self.entities)

    def __bool__(self) -> bool:
        return bool(self.entities or self.relationships)
