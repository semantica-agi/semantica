"""
Temporal Query Rewriter

Extracts temporal references from natural-language queries so that downstream
components (e.g. :class:`~semantica.context.context_retriever.TemporalGraphRetriever`)
can perform **deterministic** temporal filtering instead of asking the LLM to
do it.

Separation of concerns
-----------------------
* **This module** — extracts ``at_time``, ``start_time``, ``end_time``, and
  ``temporal_intent`` from query text and produces a cleaned ``rewritten_query``
  with the temporal phrase stripped out.
* **TemporalGraphRetriever** — uses the extracted parameters to call
  ``reconstruct_at_time()`` on the retrieved subgraph.

This module never calls ``reconstruct_at_time()``.

Usage::

    from semantica.kg import TemporalQueryRewriter

    rewriter = TemporalQueryRewriter()                # no LLM — regex only
    result = rewriter.rewrite("which suppliers were certified before the 2021 merger?")
    # result.temporal_intent == "before"
    # result.at_time == datetime(2021, 1, 1, tzinfo=utc)  (start of year)
    # result.rewritten_query == "which suppliers were certified?"

    # With an LLM for higher accuracy on free-form phrasing:
    from semantica.llms import Groq
    llm = Groq(model="llama-3.1-8b-instant")
    rewriter = TemporalQueryRewriter(llm_provider=llm)
    result = rewriter.rewrite("what interactions were known in Q2 2022?")
    # result.temporal_intent == "during"
    # result.start_time / result.end_time == Q2 2022 bounds
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from .temporal_normalizer import TemporalNormalizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TemporalQueryResult:
    """
    Output of :meth:`TemporalQueryRewriter.rewrite`.

    Attributes:
        rewritten_query: Original query with the temporal phrase removed and
            whitespace normalised. Identical to the input query when no
            temporal phrase is found.
        at_time: Point-in-time bound for intents ``"at"``, ``"during"``,
            ``"before"``, and ``"after"``. For ``"before"`` / ``"after"``
            this is the bounding moment. ``None`` for ``"between"`` (use
            ``start_time`` / ``end_time``) and when no temporal phrase is
            found.
        start_time: Lower bound for ``"between"`` queries. ``None`` otherwise.
        end_time: Upper bound for ``"between"`` queries. ``None`` otherwise.
        temporal_intent: One of ``"before"``, ``"after"``, ``"at"``,
            ``"during"``, ``"between"``, or ``None`` when no temporal phrase
            was detected.
        confidence: Extraction confidence in ``[0.0, 1.0]``. Regex-only
            extractions return ``0.85``; LLM-backed extractions propagate
            the LLM's self-reported confidence or default to ``0.75``.
    """

    rewritten_query: str
    at_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    temporal_intent: Optional[str] = None
    confidence: float = 0.0

    def has_temporal_context(self) -> bool:
        """Return ``True`` when any temporal parameter was extracted.

        Example:
            >>> from semantica.kg import TemporalQueryRewriter
            >>> rw = TemporalQueryRewriter()
            >>> result = rw.rewrite("suppliers certified before 2021")
            >>> result.has_temporal_context()
            True
            >>> rw.rewrite("list all suppliers").has_temporal_context()
            False
        """
        return self.temporal_intent is not None


# ---------------------------------------------------------------------------
# Regex-based fallback extractor
# ---------------------------------------------------------------------------

# Maps leading keyword → temporal_intent
_INTENT_PREFIXES: list[Tuple[str, str]] = [
    # "between … and …"  handled separately
    (r"\bbetween\b", "between"),
    (r"\bprior\s+to\b", "before"),
    (r"\bbefore\b", "before"),
    (r"\buntil\b", "before"),
    (r"\bup\s+to\b", "before"),
    (r"\bafter\b", "after"),
    (r"\bsince\b", "after"),
    (r"\bfollowing\b", "after"),
    (r"\bduring\b", "during"),
    (r"\bin\b", "during"),
    (r"\bwithin\b", "during"),
    (r"\bas\s+of\b", "at"),
    (r"\bat\b", "at"),
    (r"\bon\b", "at"),
]

# Captures a temporal phrase after an intent keyword
_TEMPORAL_PHRASE_RE = re.compile(
    r"""
    \b
    (?P<intent_kw>
        between | prior\s+to | before | until | up\s+to |
        after | since | following |
        during | in | within |
        as\s+of | at | on
    )
    \b
    \s+
    (?P<phrase>
        # "between X and Y"
        (?:
            (?:the\s+)?
            [\w\s,\-/]+ (?:\s+and\s+[\w\s,\-/]+)?
        )
        |
        # simple phrase: "Q1 2022", "2021 merger", "June 2020"
        [\w][\w\s,\-/]*?
    )
    (?=\s*[?.,;!]|\s*$|\s+(?:and\b|\bor\b|\bthat\b|\bwhere\b|\bwho\b|\bwhich\b|\bwhen\b))
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "between X and Y" extractor
_BETWEEN_RE = re.compile(
    r"\bbetween\s+(?P<start>[\w][\w\s\-,/]*?)\s+and\s+(?P<end>[\w][\w\s\-,/]*?)"
    r"(?=\s*[?.,;!]|\s*$|\s+(?:and\b|\bor\b|\bthat\b|\bwhere\b|\bwho\b|\bwhich\b|\bwhen\b))",
    re.IGNORECASE,
)


def _map_intent_keyword(kw: str) -> str:
    kw_lower = kw.lower().strip()
    if kw_lower in ("before", "until", "up to", "prior to"):
        return "before"
    if kw_lower in ("after", "since", "following"):
        return "after"
    if kw_lower in ("during", "in", "within"):
        return "during"
    if kw_lower in ("as of", "at", "on"):
        return "at"
    return "at"


def _strip_phrase(query: str, matched_text: str) -> str:
    """Remove *matched_text* from *query* and tidy up residual whitespace."""
    cleaned = query.replace(matched_text, " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([?.,;!])", r"\1", cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TemporalQueryRewriter:
    """
    Extract temporal intent from natural-language queries.

    Two operating modes:

    **Regex-only** (default, no LLM required)
        Handles common structured phrasings — ``"before 2021"``,
        ``"between Q1 and Q3 2022"``, ``"as of 2023-06-01"``, etc.
        All datetime resolution is delegated to
        :class:`~semantica.kg.temporal_normalizer.TemporalNormalizer`
        (deterministic, zero LLM calls).

    **LLM-assisted** (``llm_provider`` kwarg)
        Uses a small LLM call to extract the temporal phrase and intent for
        free-form phrasing.  Datetime resolution is still performed by
        :class:`~semantica.kg.temporal_normalizer.TemporalNormalizer` so the
        result is always deterministic given the same phrase text.

    .. warning::
        This class never calls ``reconstruct_at_time()``.  It is a pure
        parameter-extraction step; the actual temporal filtering is always
        performed by
        :class:`~semantica.context.context_retriever.TemporalGraphRetriever`.
    """

    _LLM_EXTRACTION_PROMPT = (
        "Extract the temporal reference from this query and return ONLY valid JSON "
        "with these exact keys:\n"
        '  "temporal_phrase": the verbatim temporal expression (or null),\n'
        '  "temporal_intent": one of "before", "after", "at", "during", "between", or null,\n'
        '  "confidence": a float between 0 and 1.\n\n'
        "Query: {query}\n\nJSON:"
    )

    def __init__(
        self,
        llm_provider: Optional[Any] = None,
        reference_date: Optional[datetime] = None,
    ):
        """
        Args:
            llm_provider: Optional LLM provider (any object with a
                ``generate(prompt: str) -> str`` method).  When ``None``,
                regex-only extraction is used.
            reference_date: Reference date for relative phrases like
                ``"last year"``.  Defaults to ``datetime.now(utc)`` at
                construction time.

        Example:
            >>> from semantica.kg import TemporalQueryRewriter
            >>> # Regex-only (no LLM dependency)
            >>> rw = TemporalQueryRewriter()

            >>> # LLM-assisted — handles free-form phrasings like "the 2021 merger"
            >>> from semantica.llms import Groq
            >>> llm = Groq(model="llama-3.1-8b-instant")
            >>> rw_llm = TemporalQueryRewriter(llm_provider=llm)
        """
        self._llm = llm_provider
        self._normalizer = TemporalNormalizer(
            reference_date=reference_date or datetime.now(timezone.utc)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rewrite(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> TemporalQueryResult:
        """
        Extract temporal context from *query* and return a cleaned query.

        Args:
            query: The raw user query.
            context: Optional dict of additional context (e.g. domain hint).
                Currently unused; reserved for future domain-specific rules.

        Returns:
            :class:`TemporalQueryResult` with extracted parameters and the
            cleaned ``rewritten_query``.

        Example:
            >>> from semantica.kg import TemporalQueryRewriter
            >>> rw = TemporalQueryRewriter()

            >>> # "before" intent — single bound
            >>> r = rw.rewrite("which suppliers were certified before 2021?")
            >>> r.temporal_intent
            'before'
            >>> r.at_time.year
            2021
            >>> r.rewritten_query
            'which suppliers were certified?'

            >>> # "between" intent — range
            >>> r = rw.rewrite("revenue between Q1 2022 and Q3 2022")
            >>> r.temporal_intent
            'between'
            >>> r.start_time is not None and r.end_time is not None
            True

            >>> # No temporal phrase — passthrough
            >>> r = rw.rewrite("list all active suppliers")
            >>> r.temporal_intent is None
            True
            >>> r.rewritten_query
            'list all active suppliers'
        """
        if self._llm is not None:
            result = self._llm_rewrite(query)
            if result is not None:
                return result
        return self._regex_rewrite(query)

    # ------------------------------------------------------------------
    # Internal: LLM path
    # ------------------------------------------------------------------

    def _llm_rewrite(self, query: str) -> Optional[TemporalQueryResult]:
        """
        Ask the LLM to extract the temporal phrase + intent.

        Falls back to ``None`` (triggering the regex path) if the LLM call
        fails or produces unparseable output.
        """
        prompt = self._LLM_EXTRACTION_PROMPT.format(query=query)
        try:
            raw = self._llm.generate(prompt)
            data = self._parse_json(raw)
        except Exception as exc:
            logger.debug("LLM extraction failed (%s); falling back to regex.", exc)
            return None

        phrase: Optional[str] = data.get("temporal_phrase")
        intent: Optional[str] = data.get("temporal_intent")
        confidence: float = float(data.get("confidence", 0.75))

        if not phrase or not intent:
            return TemporalQueryResult(
                rewritten_query=query,
                temporal_intent=None,
                confidence=confidence,
            )

        at_time, start_time, end_time = self._resolve_phrase(phrase, intent)
        rewritten = _strip_phrase(query, phrase)

        return TemporalQueryResult(
            rewritten_query=rewritten,
            at_time=at_time,
            start_time=start_time,
            end_time=end_time,
            temporal_intent=intent,
            confidence=confidence,
        )

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Extract JSON object from raw LLM output (tolerates trailing prose)."""
        # Find first '{' … '}' block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in LLM output")
        return json.loads(text[start:end])

    # ------------------------------------------------------------------
    # Internal: regex path
    # ------------------------------------------------------------------

    def _regex_rewrite(self, query: str) -> TemporalQueryResult:
        """Regex-based extraction — no LLM calls."""
        # 1. Try "between X and Y" first (most specific)
        between_m = _BETWEEN_RE.search(query)
        if between_m:
            start_phrase = between_m.group("start").strip()
            end_phrase = between_m.group("end").strip()
            start_time = self._normalize_single(start_phrase, prefer="start")
            end_time = self._normalize_single(end_phrase, prefer="end")
            if start_time is not None or end_time is not None:
                rewritten = _strip_phrase(query, between_m.group(0))
                return TemporalQueryResult(
                    rewritten_query=rewritten,
                    start_time=start_time,
                    end_time=end_time,
                    temporal_intent="between",
                    confidence=0.85,
                )

        # 2. Generic intent + phrase
        m = _TEMPORAL_PHRASE_RE.search(query)
        if m:
            intent_kw = m.group("intent_kw")
            phrase = m.group("phrase").strip()
            intent = _map_intent_keyword(intent_kw)

            at_time, start_time, end_time = self._resolve_phrase(phrase, intent)
            if at_time is not None or start_time is not None or end_time is not None:
                rewritten = _strip_phrase(query, m.group(0))
                return TemporalQueryResult(
                    rewritten_query=rewritten,
                    at_time=at_time,
                    start_time=start_time,
                    end_time=end_time,
                    temporal_intent=intent,
                    confidence=0.85,
                )

        # 3. No temporal phrase found
        return TemporalQueryResult(
            rewritten_query=query,
            temporal_intent=None,
            confidence=1.0,
        )

    # ------------------------------------------------------------------
    # Internal: phrase → datetime resolution
    # ------------------------------------------------------------------

    # Matches a 4-digit year as fallback when the full phrase can't be normalized
    _YEAR_IN_PHRASE = re.compile(r"\b(\d{4})\b")

    def _resolve_phrase(
        self,
        phrase: str,
        intent: str,
    ) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime]]:
        """
        Resolve *phrase* to datetime bounds via :class:`TemporalNormalizer`.

        Returns ``(at_time, start_time, end_time)`` according to *intent*:

        * ``"before"`` / ``"after"`` / ``"at"`` / ``"during"`` → only ``at_time``
          is populated (``start_time`` / ``end_time`` are ``None``).
        * ``"between"`` → only ``start_time`` / ``end_time`` are populated.

        When the full phrase cannot be normalized (e.g. ``"the 2021 merger"``)
        the method extracts the first 4-digit year as a fallback and retries.
        """
        try:
            norm_start, norm_end = self._normalizer.normalize(phrase)
        except Exception:
            # Fallback: extract first 4-digit year from phrase and retry
            year_m = self._YEAR_IN_PHRASE.search(phrase)
            if year_m:
                try:
                    norm_start, norm_end = self._normalizer.normalize(year_m.group(1))
                except Exception:
                    return None, None, None
            else:
                return None, None, None

        if intent == "between":
            return None, norm_start, norm_end

        # For all point-in-time intents use the start of the resolved interval
        # as the bounding datetime ("before 2021" → before 2021-01-01).
        at_time = norm_start
        return at_time, None, None

    def _normalize_single(
        self, phrase: str, prefer: str = "start"
    ) -> Optional[datetime]:
        """Normalize *phrase* to a single datetime (start or end of interval)."""
        try:
            start, end = self._normalizer.normalize(phrase)
            return start if prefer == "start" else end
        except Exception:
            return None
