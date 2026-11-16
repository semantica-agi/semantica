"""Regression tests for semantica-agi/semantica #2274.

When an LLM stage in the triplet-extraction pipeline fails (timeout, 400,
parse error) the failure used to be swallowed: the pipeline degraded to the
next method and the run completed "successfully" with fewer, lower-quality
triplets and nothing in the returned data indicating the degradation — only a
``logger.error``/``logger.warning`` line buried in console output.

The fix records the degradation in-band: every returned triplet carries
``metadata["extraction_trace"]`` describing the method chain, e.g.
``"llm:failed(ProcessingError)->pattern:ok"``. The same shape is applied to
the LLM-enhancement swallow (``LLMExtraction.enhance_relations`` /
``enhance_entities``): items returned after a failed enhancement carry
``metadata["extraction_trace"] = "llm_enhancement:failed(<ExcClass>)"``.

The trace is stamped ONLY when a degradation actually happened; a clean run
carries no ``extraction_trace`` key. Fallback behaviour itself is unchanged:
partial results are still returned, they are now labelled.
"""

import pytest
from unittest.mock import MagicMock

from semantica.semantic_extract.llm_extraction import LLMExtraction
from semantica.semantic_extract.methods import extract_triplets_pattern
from semantica.semantic_extract.relation_extractor import RelationExtractor
from semantica.semantic_extract.triplet_extractor import TripletExtractor
from semantica.semantic_extract.types import Entity, Relation
from semantica.utils.exceptions import ProcessingError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(text, label="ORG", confidence=0.9):
    return Entity(
        text=text,
        label=label,
        start_char=0,
        end_char=len(text),
        confidence=confidence,
        metadata={},
    )


def _make_relation(subj, pred, obj, confidence=0.9):
    return Relation(
        subject=_make_entity(subj),
        predicate=pred,
        object=_make_entity(obj, "PERSON"),
        confidence=confidence,
        context="",
        metadata={},
    )


def _make_failing_llm_extraction() -> LLMExtraction:
    extractor = LLMExtraction.__new__(LLMExtraction)
    extractor.provider_name = "openai"
    extractor.model = "gpt-4"
    extractor.temperature = None
    extractor.config = {}

    from semantica.utils.logging import get_logger

    extractor.logger = get_logger("test_llm_failure_trace")
    from semantica.utils.progress_tracker import get_progress_tracker

    extractor.progress_tracker = get_progress_tracker()
    extractor.progress_tracker.enabled = False

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.generate_typed.side_effect = TimeoutError("Request timed out.")
    extractor.provider = mock_provider
    return extractor


def _extractor_with_methods(monkeypatch, llm_behaviour):
    """TripletExtractor whose ``llm`` method raises/fails per *llm_behaviour*.

    ``llm_behaviour`` is a callable ``(text, **kwargs) -> List[Triplet]`` used
    for the ``llm`` method; every other method resolves to the real builtin.
    """
    import semantica.semantic_extract.methods as methods_mod

    real_get = methods_mod.get_triplet_method

    def fake_get(name):
        if name == "llm":
            return llm_behaviour
        return real_get(name)

    monkeypatch.setattr(methods_mod, "get_triplet_method", fake_get)
    return TripletExtractor()


# ---------------------------------------------------------------------------
# Extractor fallback chain — issue repro shape
# ---------------------------------------------------------------------------


class TestExtractionTraceOnLlmFallback:
    """#2274: LLM stage fails -> pattern fallback must be visible in-band."""

    def test_llm_failure_then_pattern_success_is_traced(self, monkeypatch):
        """Pattern results are returned AND carry the llm failure in metadata."""

        def failing_llm(text, **kwargs):
            raise ProcessingError("Typed generation failed: Request timed out.")

        extractor = _extractor_with_methods(monkeypatch, failing_llm)
        entities = [_make_entity("Alpha"), _make_entity("Beta")]
        relations = [_make_relation("Alpha", "connected_to", "Beta")]

        triplets = extractor.extract_triplets(
            "Alpha is connected to Beta.",
            entities=entities,
            relations=relations,
            method=["llm", "pattern"],
        )

        assert len(triplets) > 0
        assert all(
            t.metadata.get("extraction_trace")
            == "llm:failed(ProcessingError)->pattern:ok"
            for t in triplets
        ), "fallback triplets must record the llm failure in-band"

    def test_first_method_succeeds_later_failure_not_traced(self, monkeypatch):
        """Qodo #2278 review: a failure AFTER the producer must not be stamped.

        With method=["pattern", "llm"], pattern succeeds and the llm call
        raises afterwards. The returned triplets came from pattern alone, so
        no ``extraction_trace`` key may appear: stamping
        ``"llm:failed(...)->pattern:ok"`` would reverse execution order and
        blame the result on a failure that did not cause it.
        """

        def failing_llm(text, **kwargs):
            raise ProcessingError("Typed generation failed: Request timed out.")

        extractor = _extractor_with_methods(monkeypatch, failing_llm)
        entities = [_make_entity("Alpha"), _make_entity("Beta")]
        relations = [_make_relation("Alpha", "connected_to", "Beta")]

        triplets = extractor.extract_triplets(
            "Alpha is connected to Beta.",
            entities=entities,
            relations=relations,
            method=["pattern", "llm"],
        )

        assert len(triplets) > 0
        assert all("extraction_trace" not in t.metadata for t in triplets), (
            "a failure after the first successful method did not produce "
            "these triplets and must not be stamped on them"
        )

    def test_only_failures_before_producer_are_traced(self, monkeypatch):
        """Failures before the producer stay; failures after it are dropped."""

        def failing_method(text, **kwargs):
            raise ProcessingError("Typed generation failed: Request timed out.")

        import semantica.semantic_extract.methods as methods_mod

        real_get = methods_mod.get_triplet_method

        def fake_get(name):
            if name in ("llm", "rules"):
                return failing_method
            return real_get(name)

        monkeypatch.setattr(methods_mod, "get_triplet_method", fake_get)
        extractor = TripletExtractor()
        entities = [_make_entity("Alpha"), _make_entity("Beta")]
        relations = [_make_relation("Alpha", "connected_to", "Beta")]

        triplets = extractor.extract_triplets(
            "Alpha is connected to Beta.",
            entities=entities,
            relations=relations,
            method=["llm", "pattern", "rules"],
        )

        assert len(triplets) > 0
        assert all(
            t.metadata.get("extraction_trace")
            == "llm:failed(ProcessingError)->pattern:ok"
            for t in triplets
        ), "only the failure preceding the producer belongs in the trace"

    def test_clean_run_carries_no_trace(self, monkeypatch):
        """When no method fails, no extraction_trace key is stamped."""

        def working_llm(text, **kwargs):
            return extract_triplets_pattern(text, **kwargs)

        extractor = _extractor_with_methods(monkeypatch, working_llm)
        entities = [_make_entity("Alpha"), _make_entity("Beta")]
        relations = [_make_relation("Alpha", "connected_to", "Beta")]

        triplets = extractor.extract_triplets(
            "Alpha is connected to Beta.",
            entities=entities,
            relations=relations,
            method=["llm", "pattern"],
        )

        assert len(triplets) > 0
        assert all("extraction_trace" not in t.metadata for t in triplets)

    def test_all_methods_fail_falls_back_to_relations_with_trace(self, monkeypatch):
        """Every method fails -> relation conversion still runs, traced."""

        def failing_llm(text, **kwargs):
            raise ProcessingError("Typed generation failed: Request timed out.")

        import semantica.semantic_extract.methods as methods_mod

        real_get = methods_mod.get_triplet_method

        def fake_get(name):
            if name in ("llm", "pattern"):
                return failing_llm
            return real_get(name)

        monkeypatch.setattr(methods_mod, "get_triplet_method", fake_get)
        extractor = TripletExtractor()
        entities = [_make_entity("Alpha"), _make_entity("Beta")]
        relations = [_make_relation("Alpha", "connected_to", "Beta")]

        triplets = extractor.extract_triplets(
            "Alpha is connected to Beta.",
            entities=entities,
            relations=relations,
            method=["llm", "pattern"],
        )

        assert len(triplets) > 0
        # Relation-conversion formats the predicate as a URI.
        assert triplets[0].predicate.endswith("connected_to")
        assert all(
            t.metadata.get("extraction_trace")
            == "llm:failed(ProcessingError)->pattern:failed(ProcessingError)->relations:ok"
            for t in triplets
        )


# ---------------------------------------------------------------------------
# LLM enhancement swallow — same class, same shape
# ---------------------------------------------------------------------------


class TestEnhancementFailureTrace:
    """#2274: enhance_relations/enhance_entities swallow must be visible."""

    def test_enhance_relations_failure_is_traced(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]
        extractor = _make_failing_llm_extraction()
        result = extractor.enhance_relations("text", original)

        # Fallback behaviour unchanged: originals are still returned.
        assert len(result) == 1
        assert result[0].predicate == "founded_by"
        assert result[0].metadata.get("extraction_trace") == (
            "llm_enhancement:failed(TimeoutError)"
        )

    def test_enhance_entities_failure_is_traced(self):
        original = [_make_entity("Apple Inc.")]
        extractor = _make_failing_llm_extraction()
        result = extractor.enhance_entities("text", original)

        assert len(result) == 1
        assert result[0].label == "ORG"
        assert result[0].metadata.get("extraction_trace") == (
            "llm_enhancement:failed(TimeoutError)"
        )


# ---------------------------------------------------------------------------
# Trace propagation — Qodo #2278 review finding 2
# ---------------------------------------------------------------------------


class TestEntityTracePropagation:
    """#2274: an entity-enhancement failure must survive derived results.

    ``enhance_entities`` stamps the failure on the entities, but relations
    built from those entities (and triplets built from the relations) used to
    drop it: relation construction created fresh metadata, and the pattern
    triplet conversion copied only relation metadata. The derived results
    therefore looked clean although their inputs were never enhanced.
    """

    def _failed_enhanced_entities(self, text):
        """Entities for *text* after a failed LLM enhancement."""
        apple = Entity(
            text="Apple Inc.",
            label="ORG",
            start_char=text.index("Apple Inc."),
            end_char=text.index("Apple Inc.") + len("Apple Inc."),
            confidence=0.9,
            metadata={},
        )
        jobs = Entity(
            text="Steve Jobs",
            label="PERSON",
            start_char=text.index("Steve Jobs"),
            end_char=text.index("Steve Jobs") + len("Steve Jobs"),
            confidence=0.9,
            metadata={},
        )
        extractor = _make_failing_llm_extraction()
        return extractor.enhance_entities(text, [apple, jobs])

    def test_failed_enhancement_trace_survives_relations_and_triplets(self):
        text = "Apple Inc. was founded by Steve Jobs."
        entities = self._failed_enhanced_entities(text)
        assert all(
            e.metadata.get("extraction_trace") == "llm_enhancement:failed(TimeoutError)"
            for e in entities
        )

        relations = RelationExtractor(method="pattern").extract_relations(
            text, entities
        )
        founded_by = [r for r in relations if r.predicate == "founded_by"]
        assert len(founded_by) > 0, "pattern branch must find founded_by"
        assert all(
            r.metadata.get("extraction_trace") == "llm_enhancement:failed(TimeoutError)"
            for r in founded_by
        ), "relations built from un-enhanced entities must keep the trace"

        triplets = extract_triplets_pattern(text, entities, relations)
        assert len(triplets) > 0
        assert all(
            t.metadata.get("extraction_trace") == "llm_enhancement:failed(TimeoutError)"
            for t in triplets
        ), "triplets converted from traced relations must keep the trace"

    def test_failed_enhancement_trace_survives_entities_only_pattern(self):
        """Pattern triplets built straight from entities keep the trace."""
        text = "Alpha founded Beta"
        entities = [
            Entity(
                text="Alpha",
                label="ORG",
                start_char=0,
                end_char=5,
                confidence=0.9,
                metadata={},
            ),
            Entity(
                text="Beta",
                label="ORG",
                start_char=text.index("Beta"),
                end_char=text.index("Beta") + len("Beta"),
                confidence=0.9,
                metadata={},
            ),
        ]
        extractor = _make_failing_llm_extraction()
        entities = extractor.enhance_entities(text, entities)

        triplets = extract_triplets_pattern(text, entities, None)
        assert len(triplets) > 0
        assert all(
            t.metadata.get("extraction_trace") == "llm_enhancement:failed(TimeoutError)"
            for t in triplets
        ), "triplets built from un-enhanced entities must keep the trace"
