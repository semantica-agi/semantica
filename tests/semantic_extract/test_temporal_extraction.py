"""
Tests for temporal metadata extraction (Issue #400).

Covers:
  - extract_temporal_bounds=True/False flag on extract_relations_llm()
  - TemporalNormalizer: relative dates, partial dates, ambiguity, domain phrases,
    custom phrase map
  - Full pipeline: extract → normalize → BiTemporalFact

All LLM calls are mocked. No real API keys required. Suite runs in < 5 s.
"""

import os
import sys
import unittest
import warnings
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ── Mock optional heavyweight dependencies before any semantica import ──────
_MOCKED_MODULES = [
    "spacy",
    "instructor",
    "openai",
    "groq",
    "sentence_transformers",
    "transformers",
]
_original_modules = {k: sys.modules.get(k) for k in _MOCKED_MODULES}

for k in _MOCKED_MODULES:
    sys.modules.setdefault(k, MagicMock())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from semantica.semantic_extract.methods import extract_relations_llm  # noqa: E402

for _key, _original in _original_modules.items():
    if _original is None:
        sys.modules.pop(_key, None)
    else:
        sys.modules[_key] = _original

from semantica.semantic_extract.ner_extractor import Entity  # noqa: E402
from semantica.semantic_extract.schemas import (  # noqa: E402
    RelationsResponse,
    RelationsWithTemporalResponse,
)
from semantica.kg.temporal_normalizer import TemporalNormalizer  # noqa: E402
from semantica.utils.exceptions import TemporalAmbiguityWarning  # noqa: E402

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_entities():
    return [
        Entity(text="Apple", label="ORG", start_char=0, end_char=5),
        Entity(text="Beats", label="ORG", start_char=15, end_char=20),
    ]


def _ref_date():
    return datetime(2025, 6, 15, tzinfo=timezone.utc)


# ============================================================================
# Part 1 – extract_relations_llm() temporal flag
# ============================================================================


class TestTemporalExtractionFlag(unittest.TestCase):

    def setUp(self):
        from semantica.semantic_extract.methods import _result_cache

        _result_cache.clear()

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_extract_temporal_bounds_true_adds_four_fields(self, mock_create):
        """With extract_temporal_bounds=True all four temporal keys appear."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsWithTemporalResponse(
            relations=[
                {
                    "subject": "Apple",
                    "predicate": "acquired",
                    "object": "Beats",
                    "confidence": 0.97,
                    "valid_from": "2014-05-01",
                    "valid_until": None,
                    "temporal_confidence": 0.90,
                    "temporal_source_text": "May 2014",
                }
            ]
        )
        mock_create.return_value = mock_prov

        rels = extract_relations_llm(
            "Apple acquired Beats in May 2014.",
            _make_entities(),
            provider="openai",
            extract_temporal_bounds=True,
        )

        self.assertEqual(len(rels), 1)
        meta = rels[0].metadata
        self.assertIn("valid_from", meta)
        self.assertIn("valid_until", meta)
        self.assertIn("temporal_confidence", meta)
        self.assertIn("temporal_source_text", meta)
        self.assertEqual(meta["valid_from"], "2014-05-01")
        self.assertIsNone(meta["valid_until"])
        self.assertAlmostEqual(meta["temporal_confidence"], 0.90, places=2)
        self.assertEqual(meta["temporal_source_text"], "May 2014")

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_extract_temporal_bounds_false_output_identical(self, mock_create):
        """With extract_temporal_bounds=False (default) no temporal keys appear."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsResponse(
            relations=[
                {
                    "subject": "Apple",
                    "predicate": "acquired",
                    "object": "Beats",
                    "confidence": 0.97,
                }
            ]
        )
        mock_create.return_value = mock_prov

        rels = extract_relations_llm(
            "Apple acquired Beats.",
            _make_entities(),
            provider="openai",
        )

        self.assertEqual(len(rels), 1)
        meta = rels[0].metadata
        self.assertNotIn("valid_from", meta)
        self.assertNotIn("valid_until", meta)
        self.assertNotIn("temporal_confidence", meta)
        self.assertNotIn("temporal_source_text", meta)

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_no_temporal_signal_returns_zero_confidence_and_null_dates(
        self, mock_create
    ):
        """When LLM returns no temporal signal, confidence=0.0 and dates are null."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsWithTemporalResponse(
            relations=[
                {
                    "subject": "Apple",
                    "predicate": "owns",
                    "object": "Beats",
                    "confidence": 0.95,
                    "valid_from": None,
                    "valid_until": None,
                    "temporal_confidence": 0.0,
                    "temporal_source_text": None,
                }
            ]
        )
        mock_create.return_value = mock_prov

        rels = extract_relations_llm(
            "Apple owns Beats.",
            _make_entities(),
            provider="openai",
            extract_temporal_bounds=True,
        )

        meta = rels[0].metadata
        self.assertIsNone(meta["valid_from"])
        self.assertIsNone(meta["valid_until"])
        self.assertEqual(meta["temporal_confidence"], 0.0)
        self.assertIsNone(meta["temporal_source_text"])

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_low_temporal_confidence_logs_warning(self, mock_create):
        """temporal_confidence < 0.5 with non-null date logs a WARNING."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsWithTemporalResponse(
            relations=[
                {
                    "subject": "Apple",
                    "predicate": "partnered_with",
                    "object": "Beats",
                    "confidence": 0.80,
                    "valid_from": "recently",
                    "valid_until": None,
                    "temporal_confidence": 0.35,
                    "temporal_source_text": "recently",
                }
            ]
        )
        mock_create.return_value = mock_prov

        with self.assertLogs("semantica", level="WARNING") as cm:
            extract_relations_llm(
                "Apple recently partnered with Beats.",
                _make_entities(),
                provider="openai",
                extract_temporal_bounds=True,
            )
        self.assertTrue(any("Low temporal confidence" in line for line in cm.output))

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_correct_schema_used_when_temporal_true(self, mock_create):
        """generate_typed is called with RelationsWithTemporalResponse."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsWithTemporalResponse(
            relations=[]
        )
        mock_create.return_value = mock_prov

        extract_relations_llm(
            "Some text.",
            _make_entities(),
            provider="openai",
            extract_temporal_bounds=True,
        )

        call_kwargs = mock_prov.generate_typed.call_args[1]
        self.assertIs(call_kwargs["schema"], RelationsWithTemporalResponse)

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_correct_schema_used_when_temporal_false(self, mock_create):
        """generate_typed is called with RelationsResponse when flag=False."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsResponse(relations=[])
        mock_create.return_value = mock_prov

        extract_relations_llm(
            "Some text.",
            _make_entities(),
            provider="openai",
        )

        call_kwargs = mock_prov.generate_typed.call_args[1]
        self.assertIs(call_kwargs["schema"], RelationsResponse)


# ============================================================================
# Part 2 – TemporalNormalizer: relative dates
# ============================================================================


class TestTemporalNormalizerRelativeDates(unittest.TestCase):

    def setUp(self):
        self.ref = _ref_date()  # 2025-06-15
        self.tn = TemporalNormalizer(reference_date=self.ref)

    def test_last_year(self):
        result = self.tn.normalize("last year")
        self.assertIsNotNone(result)
        start, end = result
        self.assertEqual(start.year, 2024)
        self.assertEqual(start.month, 1)
        self.assertEqual(start.day, 1)
        self.assertEqual(end.year, 2024)
        self.assertEqual(end.month, 12)
        self.assertEqual(end.day, 31)

    def test_this_year(self):
        result = self.tn.normalize("this year")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2025)
        self.assertEqual(result[0].month, 1)
        self.assertEqual(result[1].month, 12)

    def test_three_months_ago(self):
        result = self.tn.normalize("three months ago")
        self.assertIsNotNone(result)
        # ref is 2025-06-15; three months ago → March 2025
        self.assertEqual(result[0].year, 2025)
        self.assertEqual(result[0].month, 3)

    def test_last_quarter(self):
        # ref is 2025-06-15 (Q2) → last quarter = Q1 2025
        result = self.tn.normalize("last quarter")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].month, 1)
        self.assertEqual(result[1].month, 3)
        self.assertEqual(result[0].year, 2025)

    def test_this_quarter(self):
        # ref is 2025-06-15 (Q2) → Q2 2025
        result = self.tn.normalize("this quarter")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].month, 4)
        self.assertEqual(result[1].month, 6)

    def test_last_month(self):
        # ref June 2025 → May 2025
        result = self.tn.normalize("last month")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].month, 5)
        self.assertEqual(result[0].year, 2025)

    def test_two_years_ago(self):
        result = self.tn.normalize("two years ago")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2023)
        self.assertEqual(result[1].year, 2023)

    def test_no_reference_date_raises_value_error(self):
        tn = TemporalNormalizer()
        with self.assertRaises(ValueError):
            tn.normalize("last year")

    def test_none_input_returns_none(self):
        self.assertIsNone(self.tn.normalize(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self.tn.normalize(""))

    def test_whitespace_string_returns_none(self):
        self.assertIsNone(self.tn.normalize("   "))


# ============================================================================
# Part 3 – TemporalNormalizer: partial / structured dates
# ============================================================================


class TestTemporalNormalizerPartialDates(unittest.TestCase):

    def setUp(self):
        self.tn = TemporalNormalizer(
            reference_date=datetime(2025, 3, 25, tzinfo=timezone.utc)
        )

    def test_year_only(self):
        result = self.tn.normalize("2021")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], datetime(2021, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(result[1], datetime(2021, 12, 31, tzinfo=timezone.utc))

    def test_month_year_word(self):
        result = self.tn.normalize("March 2022")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2022)
        self.assertEqual(result[0].month, 3)
        self.assertEqual(result[0].day, 1)
        self.assertEqual(result[1].day, 31)

    def test_month_year_word_abbreviated(self):
        result = self.tn.normalize("Dec 2023")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].month, 12)
        self.assertEqual(result[1].day, 31)

    def test_year_month_iso_partial(self):
        result = self.tn.normalize("2022-03")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2022)
        self.assertEqual(result[0].month, 3)
        self.assertEqual(result[0].day, 1)
        self.assertEqual(result[1].day, 31)

    def test_q1_2024(self):
        result = self.tn.normalize("Q1 2024")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], datetime(2024, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(result[1], datetime(2024, 3, 31, tzinfo=timezone.utc))

    def test_q2_2021(self):
        result = self.tn.normalize("Q2 2021")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], datetime(2021, 4, 1, tzinfo=timezone.utc))
        self.assertEqual(result[1], datetime(2021, 6, 30, tzinfo=timezone.utc))

    def test_q3_2023(self):
        result = self.tn.normalize("Q3 2023")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], datetime(2023, 7, 1, tzinfo=timezone.utc))
        self.assertEqual(result[1], datetime(2023, 9, 30, tzinfo=timezone.utc))

    def test_q4_2022(self):
        result = self.tn.normalize("Q4 2022")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], datetime(2022, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(result[1], datetime(2022, 12, 31, tzinfo=timezone.utc))

    def test_iso_full_date_returns_point(self):
        result = self.tn.normalize("2022-03-15")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2022)
        self.assertEqual(result[0].month, 3)
        self.assertEqual(result[0].day, 15)
        # Point interval: start == end
        self.assertEqual(result[0], result[1])

    def test_iso_datetime_with_z(self):
        result = self.tn.normalize("2022-03-15T00:00:00Z")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2022)

    def test_unparseable_returns_none(self):
        result = self.tn.normalize("sometime in the medieval period")
        self.assertIsNone(result)

    def test_none_returns_none(self):
        self.assertIsNone(self.tn.normalize(None))


# ============================================================================
# Part 4 – TemporalNormalizer: ambiguous formats
# ============================================================================


class TestTemporalNormalizerAmbiguity(unittest.TestCase):

    def setUp(self):
        self.tn = TemporalNormalizer(
            reference_date=datetime(2025, 3, 25, tzinfo=timezone.utc)
        )

    def test_ambiguous_slash_date_raises_warning_and_returns_none(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = self.tn.normalize("03/04/2022")
        self.assertIsNone(result)
        ambig = [x for x in w if issubclass(x.category, TemporalAmbiguityWarning)]
        self.assertEqual(len(ambig), 1)
        self.assertIn("ambiguous", str(ambig[0].message).lower())

    def test_iso_hyphenated_date_not_flagged_as_ambiguous(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = self.tn.normalize("2022-03-04")
        ambig = [x for x in w if issubclass(x.category, TemporalAmbiguityWarning)]
        self.assertEqual(len(ambig), 0)
        self.assertIsNotNone(result)

    def test_ambiguous_date_does_not_raise_exception(self):
        # Must not raise, only warn
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.tn.normalize("01/12/2023")
        except Exception as e:
            self.fail(f"normalize() raised unexpectedly: {e}")


# ============================================================================
# Part 5 – TemporalNormalizer: domain phrase map
# ============================================================================


class TestTemporalNormalizerDomainPhrases(unittest.TestCase):

    def setUp(self):
        self.tn = TemporalNormalizer(
            reference_date=datetime(2025, 3, 25, tzinfo=timezone.utc)
        )

    def _assert_recognized(self, phrase):
        result = self.tn.normalize_phrase(phrase)
        self.assertIsNotNone(
            result, f"Expected phrase {phrase!r} to be recognized but got None"
        )
        return result

    # General / Policy
    def test_effective_date_recognized(self):
        r = self._assert_recognized("effective date")
        self.assertEqual(r["maps_to"], "valid_from")

    def test_effective_from_regex_recognized(self):
        r = self._assert_recognized("effective from")
        self.assertEqual(r["maps_to"], "valid_from")

    def test_effective_as_of_regex_recognized(self):
        r = self._assert_recognized("effective as of")
        self.assertEqual(r["maps_to"], "valid_from")

    def test_in_force_until_recognized(self):
        r = self._assert_recognized("in force until")
        self.assertEqual(r["maps_to"], "valid_until")

    def test_retroactive_to_recognized(self):
        r = self._assert_recognized("retroactive to")
        self.assertTrue(r.get("retroactive"))

    def test_sunset_clause_recognized(self):
        r = self._assert_recognized("sunset clause")
        self.assertEqual(r["maps_to"], "valid_until")

    # Healthcare / Drug Discovery
    def test_approval_date_recognized(self):
        r = self._assert_recognized("approval date")
        self.assertEqual(r["maps_to"], "valid_from")
        self.assertIn("Healthcare", r.get("domain", []))

    def test_expiry_date_recognized(self):
        r = self._assert_recognized("expiry date")
        self.assertEqual(r["maps_to"], "valid_until")

    def test_market_authorization_recognized(self):
        r = self._assert_recognized("market authorization")
        self.assertEqual(r["maps_to"], "valid_from")
        self.assertIn("Drug Discovery", r.get("domain", []))

    # Cybersecurity
    def test_incident_window_recognized(self):
        r = self._assert_recognized("incident window")
        self.assertIn("Cybersecurity", r.get("domain", []))

    def test_campaign_period_recognized(self):
        r = self._assert_recognized("campaign period")
        self.assertIn("Cybersecurity", r.get("domain", []))

    # Supply Chain
    def test_certification_valid_through_recognized(self):
        r = self._assert_recognized("certification valid through")
        self.assertEqual(r["maps_to"], "valid_until")
        self.assertIn("Supply Chain", r.get("domain", []))

    # Finance
    def test_trading_halt_recognized(self):
        r = self._assert_recognized("trading halt")
        self.assertIn("Finance", r.get("domain", []))

    # Energy
    def test_commissioned_date_recognized(self):
        r = self._assert_recognized("commissioned date")
        self.assertEqual(r["maps_to"], "valid_from")
        self.assertIn("Energy", r.get("domain", []))

    def test_decommissioned_date_recognized(self):
        r = self._assert_recognized("decommissioned date")
        self.assertEqual(r["maps_to"], "valid_until")
        self.assertIn("Energy", r.get("domain", []))

    def test_unrecognized_phrase_returns_none(self):
        result = self.tn.normalize_phrase("totally unknown phrase xyz")
        self.assertIsNone(result)


# ============================================================================
# Part 6 – TemporalNormalizer: custom phrase map
# ============================================================================


class TestTemporalNormalizerCustomPhraseMap(unittest.TestCase):

    def setUp(self):
        ref = datetime(2025, 3, 25, tzinfo=timezone.utc)
        self.tn = TemporalNormalizer(
            reference_date=ref,
            phrase_map={
                "fiscal year 2024": lambda r: (
                    datetime(2024, 4, 1, tzinfo=timezone.utc),
                    datetime(2025, 3, 31, tzinfo=timezone.utc),
                )
            },
        )

    def test_custom_phrase_resolved(self):
        result = self.tn.normalize("fiscal year 2024")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2024)
        self.assertEqual(result[0].month, 4)
        self.assertEqual(result[1].year, 2025)
        self.assertEqual(result[1].month, 3)

    def test_default_phrase_still_works_alongside_custom(self):
        result = self.tn.normalize("last year")
        self.assertIsNotNone(result)
        self.assertEqual(result[0].year, 2024)

    def test_custom_phrase_overrides_default_when_same_key(self):
        # Override "last year" to a custom sentinel
        sentinel_start = datetime(2000, 1, 1, tzinfo=timezone.utc)
        sentinel_end = datetime(2000, 12, 31, tzinfo=timezone.utc)
        tn = TemporalNormalizer(
            reference_date=datetime(2025, 3, 25, tzinfo=timezone.utc),
            phrase_map={"last year": lambda r: (sentinel_start, sentinel_end)},
        )
        result = tn.normalize("last year")
        self.assertEqual(result[0], sentinel_start)


# ============================================================================
# Part 7 – Full pipeline: extract → normalize → BiTemporalFact
# ============================================================================


class TestFullPipelineTemporalToBiTemporal(unittest.TestCase):

    def setUp(self):
        from semantica.semantic_extract.methods import _result_cache

        _result_cache.clear()

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_full_pipeline_explicit_date(self, mock_create):
        """extract_relations(temporal=True) → normalize → BiTemporalFact."""
        from semantica.kg.temporal_model import BiTemporalFact

        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsWithTemporalResponse(
            relations=[
                {
                    "subject": "Apple",
                    "predicate": "acquired",
                    "object": "Beats",
                    "confidence": 0.97,
                    "valid_from": "2014-05-01",
                    "valid_until": None,
                    "temporal_confidence": 0.90,
                    "temporal_source_text": "May 2014",
                }
            ]
        )
        mock_create.return_value = mock_prov

        entities = [
            Entity(text="Apple", label="ORG", start_char=0, end_char=5),
            Entity(text="Beats", label="ORG", start_char=15, end_char=20),
        ]
        rels = extract_relations_llm(
            "Apple acquired Beats in May 2014.",
            entities,
            provider="openai",
            extract_temporal_bounds=True,
        )
        self.assertEqual(len(rels), 1)

        meta = rels[0].metadata
        ref = datetime(2025, 3, 25, tzinfo=timezone.utc)
        tn = TemporalNormalizer(reference_date=ref)

        vf = tn.normalize(meta["valid_from"])
        vu = tn.normalize(meta["valid_until"])

        self.assertIsNotNone(vf)
        self.assertIsNone(vu)
        self.assertEqual(vf[0].year, 2014)
        self.assertEqual(vf[0].month, 5)
        self.assertEqual(vf[0].day, 1)

        # Feed into BiTemporalFact
        fact = BiTemporalFact.from_relationship(
            {
                "valid_from": "2014-05-01T00:00:00Z",
                "valid_until": None,
            }
        )
        self.assertIsNotNone(fact.valid_from)
        self.assertEqual(fact.valid_from.year, 2014)
        self.assertEqual(fact.valid_from.month, 5)

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_full_pipeline_quarter_expression(self, mock_create):
        """Pipeline with Q-expression normalizes to correct quarter bounds."""
        mock_prov = MagicMock()
        mock_prov.is_available.return_value = True
        mock_prov.generate_typed.return_value = RelationsWithTemporalResponse(
            relations=[
                {
                    "subject": "Apple",
                    "predicate": "supervised",
                    "object": "Beats",
                    "confidence": 0.85,
                    "valid_from": "Q2 2021",
                    "valid_until": "Q4 2021",
                    "temporal_confidence": 0.75,
                    "temporal_source_text": "between Q2 and Q4 2021",
                }
            ]
        )
        mock_create.return_value = mock_prov

        entities = [
            Entity(text="Apple", label="ORG", start_char=0, end_char=5),
            Entity(text="Beats", label="ORG", start_char=15, end_char=20),
        ]
        rels = extract_relations_llm(
            "Apple supervised Beats between Q2 and Q4 2021.",
            entities,
            provider="openai",
            extract_temporal_bounds=True,
        )
        meta = rels[0].metadata
        tn = TemporalNormalizer(
            reference_date=datetime(2025, 3, 25, tzinfo=timezone.utc)
        )

        vf = tn.normalize(meta["valid_from"])
        vu = tn.normalize(meta["valid_until"])

        self.assertEqual(vf[0], datetime(2021, 4, 1, tzinfo=timezone.utc))
        self.assertEqual(vf[1], datetime(2021, 6, 30, tzinfo=timezone.utc))
        self.assertEqual(vu[0], datetime(2021, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(vu[1], datetime(2021, 12, 31, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
