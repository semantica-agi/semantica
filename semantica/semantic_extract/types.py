"""
Shared semantic extraction data types.

These lightweight dataclasses live outside the extractor implementations so
method dispatchers and extractors can share result models without import cycles.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Provenance vocabulary for Entity.confidence, recorded under
# metadata[CONFIDENCE_SOURCE_KEY]. Producers must use these constants so the
# vocabulary stays greppable and typo-proof.
CONFIDENCE_SOURCE_KEY = "confidence_source"
CONFIDENCE_SOURCE_MODEL = "model"  # score produced by the extraction backend
CONFIDENCE_SOURCE_HEURISTIC = "heuristic"  # filled by EntityConfidenceScorer
CONFIDENCE_SOURCE_TYPE_SIMILARITY = "type_similarity"  # from entity_types weighting
CONFIDENCE_SOURCE_UNAVAILABLE = "unavailable"  # backend exposes no score

# Degradation-trace vocabulary, recorded under metadata[EXTRACTION_TRACE_KEY].
# When an LLM stage fails and the pipeline degrades to a fallback (or returns
# un-enhanced originals), the failure is recorded in-band on the returned
# items, e.g. "llm:failed(ProcessingError)->pattern:ok". A log line alone is
# not enough: the returned data must say the result is degraded. The key is
# only stamped when a degradation actually happened; clean runs carry no key.
EXTRACTION_TRACE_KEY = "extraction_trace"


def stamp_extraction_trace(items, trace: str) -> None:
    """Record a degradation event in-band on *items*' metadata.

    Appends to an existing trace (joined with "; ") instead of overwriting
    it, so a failure recorded by an earlier stage (e.g. LLM enhancement on a
    relation that is later converted to a triplet) is preserved.
    """
    for item in items:
        metadata = item.metadata
        if metadata is None:
            metadata = item.metadata = {}
        existing = metadata.get(EXTRACTION_TRACE_KEY)
        metadata[EXTRACTION_TRACE_KEY] = f"{existing}; {trace}" if existing else trace


@dataclass
class Entity:
    """Entity representation.

    ``confidence`` is ``None`` when no confidence measurement is available
    (e.g. the extraction backend does not expose per-entity probabilities).
    ``None`` is distinct from any numeric score: it means "unknown", not
    "certain". Producers record where a score came from under
    ``metadata[CONFIDENCE_SOURCE_KEY]``, using the ``CONFIDENCE_SOURCE_*``
    constants above.
    """

    text: str
    label: str
    start_char: int
    end_char: int
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def meets_confidence_threshold(
    confidence: Optional[float], threshold: float
) -> bool:
    """Return True if a confidence value passes a minimum threshold.

    Unknown confidence (``None``) passes: absence of a measurement is not
    evidence of low confidence, and entities must not be silently dropped
    just because their backend exposes no probabilities.
    """
    return confidence is None or confidence >= threshold


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
