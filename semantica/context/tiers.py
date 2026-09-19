"""
Trust Tiers for Graph Facts

Retrieval results carry a relevance score but no evidence-quality signal, so a
fact corroborated by three ingested sources and a singleton extracted at low
confidence arrive at the agent looking identical. This module grades a fact
into a discrete trust tier using signals that already exist inside semantica:

    - Corroboration count: how many sources back the entity, as reported by
      ProvenanceManager.get_all_sources.
    - Extraction confidence: the value graph_builder persisted on the node via
      getattr(item, "confidence", 1.0).

Tiers are derived on demand at retrieval time and never persisted, so they stay
accurate as source sets evolve and existing storage layouts are untouched.

Algorithms Used:

    - Primary signal: corroboration count. Confidence alone cannot separate
      "1.0 because it was earned" from "1.0 because nothing set it": the
      extraction dataclasses in semantic_extract.types default confidence to
      1.0, and graph_builder falls back to 1.0 for objects that lack the
      attribute, so a stored 1.0 usually means the fact was never scored.
    - Secondary signal: extraction confidence, used to keep or downgrade the
      tier produced by corroboration. Values listed in treat_as_missing are
      treated as absent, which by default covers that 1.0 placeholder.
    - Missing confidence degrades the tier instead of defaulting high, so
      absent data is never trusted as if it had been measured.

Tiers:

    - gold: multiple independent sources plus usable confidence.
    - silver: partial support, a single source, or a higher band pulled down
      by absent or low confidence.
    - bronze: no corroboration at all, held up only by usable confidence.
    - quarantine: no corroboration and no usable confidence; needs review.

Example:
    >>> from semantica.context.tiers import TierCalculator, TrustTier
    >>> calculator = TierCalculator()
    >>> calculator.calculate(3, 0.9) is TrustTier.GOLD
    True
    >>> calculator.calculate(0, None) is TrustTier.QUARANTINE
    True
"""

import math
from enum import Enum
from typing import Any, Iterable, Optional


class TrustTier(Enum):
    """
    Evidence-quality tier for a retrieved graph fact.

    Members are ordered from least to most trustworthy. Values are stable
    strings so a tier can be written straight into RetrievedContext.metadata
    for downstream consumers, while ordering is exposed through rank and meets
    rather than through the value type.
    """

    QUARANTINE = "quarantine"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"

    @property
    def rank(self) -> int:
        """
        Return the position of this tier in the trust ordering.

        Returns:
            Integer rank: 0 for quarantine through 3 for gold.
        """
        return _TIER_RANKS[self]

    def meets(self, minimum: "TrustTier") -> bool:
        """
        Return whether this tier is at least as trustworthy as minimum.

        Args:
            minimum: Lowest acceptable tier.

        Returns:
            True when this tier ranks at or above minimum.

        Raises:
            TypeError: If minimum is not a TrustTier.

        Example:
            >>> TrustTier.GOLD.meets(TrustTier.SILVER)
            True
            >>> TrustTier.BRONZE.meets(TrustTier.SILVER)
            False
        """
        if not isinstance(minimum, TrustTier):
            raise TypeError(
                f"minimum must be a TrustTier, got {type(minimum).__name__}"
            )
        return self.rank >= minimum.rank

    def downgrade(self) -> "TrustTier":
        """
        Return the next lower tier, flooring at quarantine.

        Used when a secondary signal (extraction confidence) is missing or
        unusable, so the corroboration-based tier cannot be kept as it stands.

        Returns:
            The tier one step less trustworthy, or quarantine at the floor.

        Example:
            >>> TrustTier.GOLD.downgrade()
            <TrustTier.SILVER: 'silver'>
            >>> TrustTier.QUARANTINE.downgrade() is TrustTier.QUARANTINE
            True
        """
        if self is TrustTier.GOLD:
            return TrustTier.SILVER
        if self is TrustTier.SILVER:
            return TrustTier.BRONZE
        return TrustTier.QUARANTINE


_TIER_RANKS = {
    TrustTier.QUARANTINE: 0,
    TrustTier.BRONZE: 1,
    TrustTier.SILVER: 2,
    TrustTier.GOLD: 3,
}

# Stored confidence that means "never scored" rather than "scored perfectly".
# semantic_extract.types.Entity defaults confidence to 1.0 and graph_builder
# keeps 1.0 for objects without the attribute, so the value is not evidence.
_DEFAULT_TREAT_AS_MISSING = frozenset({1.0})


class TierCalculator:
    """
    Derive a trust tier from corroboration count and extraction confidence.

    Args:
        min_corroboration_for_gold: Number of corroborating sources required
            before a fact can reach gold (default: 2).
        min_confidence: Confidence at or above which the corroboration-based
            tier is kept; below it the tier is downgraded (default: 0.7).
        missing_confidence_degrades: Downgrade one tier when no confidence
            signal is available, instead of treating absent data as high
            confidence (default: True).
        treat_as_missing: Confidence values that carry no measurement and must
            therefore be handled as absent (default: 1.0). The extraction
            dataclasses in semantic_extract.types default confidence to 1.0 and
            graph_builder falls back to 1.0, so an unstored score is
            indistinguishable from a perfect one at the storage layer. Pass an
            empty iterable to disable the substitution, or add 0.9 to also
            treat the schema default as missing.

    Raises:
        ValueError: If min_corroboration_for_gold is below 1, min_confidence is
            outside [0.0, 1.0], or a treat_as_missing value is outside
            [0.0, 1.0].
        TypeError: If treat_as_missing is not iterable.

    Example:
        >>> TierCalculator().calculate(2, 0.8) is TrustTier.GOLD
        True
        >>> TierCalculator().calculate(2, None) is TrustTier.SILVER
        True
        >>> TierCalculator().calculate(2, 1.0) is TrustTier.SILVER
        True
    """

    def __init__(
        self,
        min_corroboration_for_gold: int = 2,
        min_confidence: float = 0.7,
        missing_confidence_degrades: bool = True,
        treat_as_missing: Optional[Iterable[Any]] = _DEFAULT_TREAT_AS_MISSING,
    ) -> None:
        if min_corroboration_for_gold < 1:
            raise ValueError("min_corroboration_for_gold must be at least 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be within [0.0, 1.0]")

        self.min_corroboration_for_gold = int(min_corroboration_for_gold)
        self.min_confidence = float(min_confidence)
        self.missing_confidence_degrades = bool(missing_confidence_degrades)
        self.treat_as_missing = self._normalize_treat_as_missing(treat_as_missing)

    def calculate(
        self,
        corroboration_count: Optional[int],
        confidence: Optional[float] = None,
    ) -> TrustTier:
        """
        Calculate the trust tier for a single fact.

        Corroboration count sets the tier, confidence keeps or downgrades it,
        and a complete absence of both signals yields quarantine. Confidence
        values configured in treat_as_missing count as absent, so a placeholder
        score cannot earn a high tier.

        Args:
            corroboration_count: Number of independent sources backing the
                fact. None, negatives and unusable values count as zero.
            confidence: Extraction confidence recorded for the fact, or None
                when no confidence signal is available.

        Returns:
            The TrustTier for the fact.

        Example:
            >>> calculator = TierCalculator()
            >>> calculator.calculate(3, 0.9) is TrustTier.GOLD
            True
            >>> calculator.calculate(1, 0.9) is TrustTier.SILVER
            True
            >>> calculator.calculate(3, None) is TrustTier.SILVER
            True
            >>> calculator.calculate(0, None) is TrustTier.QUARANTINE
            True
        """
        count = self._normalize_count(corroboration_count)
        confidence_is_missing = self._is_absent_confidence(confidence)
        has_usable_confidence = (
            self._is_usable_confidence(confidence) and not confidence_is_missing
        )

        if count >= self.min_corroboration_for_gold:
            tier = TrustTier.GOLD
        elif count >= 1:
            tier = TrustTier.SILVER
        elif has_usable_confidence:
            tier = TrustTier.BRONZE
        else:
            tier = TrustTier.QUARANTINE

        if confidence_is_missing:
            if self.missing_confidence_degrades:
                return tier.downgrade()
            return tier

        if has_usable_confidence:
            return tier

        return tier.downgrade()

    def _is_absent_confidence(self, confidence: Optional[float]) -> bool:
        """
        Return whether a confidence reading carries no measurement at all.

        None is always absent. A value listed in treat_as_missing is absent
        too, because the storage layer writes the same placeholder whether or
        not anything scored the fact.
        """
        if confidence is None:
            return True
        if not self.treat_as_missing:
            return False
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return False
        return value in self.treat_as_missing

    @staticmethod
    def _normalize_treat_as_missing(values: Iterable[Any]) -> frozenset:
        """Validate configured missing markers into a set of floats."""
        try:
            candidates = tuple(values)
        except TypeError as exc:
            raise TypeError(
                "treat_as_missing must be an iterable of confidence values"
            ) from exc

        normalized = set()
        for candidate in candidates:
            try:
                value = float(candidate)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "treat_as_missing values must be numbers, got " f"{candidate!r}"
                ) from exc
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    "treat_as_missing values must be within [0.0, 1.0], got "
                    f"{candidate!r}"
                )
            normalized.add(value)
        return frozenset(normalized)

    @staticmethod
    def _normalize_count(corroboration_count: Optional[int]) -> int:
        """Coerce a corroboration count into a non-negative integer."""
        if corroboration_count is None:
            return 0
        try:
            count = int(corroboration_count)
        except (TypeError, ValueError, OverflowError):
            return 0
        return max(0, count)

    def _is_usable_confidence(self, confidence: Optional[float]) -> bool:
        """Return whether confidence is a finite number at least
        min_confidence.

        Non-finite values (positive or negative infinity) are not real
        measurements, so they count as unusable rather than earning the top
        tier through the lower-bound comparison alone.
        """
        if confidence is None:
            return False
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(value):
            return False
        return value >= self.min_confidence
