"""
Shared semantic extraction data types.

These lightweight dataclasses live outside the extractor implementations so
method dispatchers and extractors can share result models without import cycles.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Entity:
    """Entity representation."""

    text: str
    label: str
    start_char: int
    end_char: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relation:
    """Relation representation."""

    subject: Entity
    predicate: str
    object: Entity
    confidence: float = 1.0
    context: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Triplet:
    """RDF triplet representation."""

    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get attribute value like a dictionary."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Get item like a dictionary."""
        return getattr(self, key)
