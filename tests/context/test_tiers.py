"""
Unit tests for trust tiers (semantica.context.tiers).

Covers tier ordering, the corroboration-led thresholds, the degradation rules
for missing or unusable confidence, the placeholder confidence values that
count as absent, and the tolerance for messy inputs.
"""

import json
import unittest

from semantica.context.tiers import TierCalculator, TrustTier


class TestTrustTierOrdering(unittest.TestCase):
    """TrustTier ordering helpers used by min_tier filtering."""

    def test_rank_increases_with_trust(self):
        self.assertLess(TrustTier.QUARANTINE.rank, TrustTier.BRONZE.rank)
        self.assertLess(TrustTier.BRONZE.rank, TrustTier.SILVER.rank)
        self.assertLess(TrustTier.SILVER.rank, TrustTier.GOLD.rank)

    def test_meets_is_inclusive(self):
        self.assertTrue(TrustTier.GOLD.meets(TrustTier.GOLD))
        self.assertTrue(TrustTier.GOLD.meets(TrustTier.QUARANTINE))
        self.assertFalse(TrustTier.BRONZE.meets(TrustTier.SILVER))

    def test_meets_rejects_non_tier(self):
        with self.assertRaises(TypeError):
            TrustTier.GOLD.meets("gold")

    def test_values_are_stable_strings(self):
        self.assertEqual(TrustTier.GOLD.value, "gold")
        self.assertEqual(TrustTier.SILVER.value, "silver")
        self.assertEqual(TrustTier.BRONZE.value, "bronze")
        self.assertEqual(TrustTier.QUARANTINE.value, "quarantine")

    def test_downgrade_steps_down_one_tier(self):
        self.assertIs(TrustTier.GOLD.downgrade(), TrustTier.SILVER)
        self.assertIs(TrustTier.SILVER.downgrade(), TrustTier.BRONZE)
        self.assertIs(TrustTier.BRONZE.downgrade(), TrustTier.QUARANTINE)

    def test_downgrade_floors_at_quarantine(self):
        self.assertIs(TrustTier.QUARANTINE.downgrade(), TrustTier.QUARANTINE)


class TestTierCalculatorThresholds(unittest.TestCase):
    """Corroboration count sets the tier; confidence adjusts it."""

    def setUp(self):
        self.calculator = TierCalculator()

    def test_multiple_sources_with_usable_confidence_is_gold(self):
        self.assertIs(self.calculator.calculate(3, 0.9), TrustTier.GOLD)

    def test_source_count_at_gold_threshold_is_gold(self):
        self.assertIs(self.calculator.calculate(2, 0.7), TrustTier.GOLD)

    def test_confidence_below_threshold_downgrades_gold(self):
        self.assertIs(self.calculator.calculate(2, 0.69), TrustTier.SILVER)

    def test_single_source_with_usable_confidence_is_silver(self):
        self.assertIs(self.calculator.calculate(1, 0.9), TrustTier.SILVER)

    def test_single_source_with_weak_confidence_is_bronze(self):
        self.assertIs(self.calculator.calculate(1, 0.5), TrustTier.BRONZE)

    def test_no_sources_with_usable_confidence_is_bronze(self):
        self.assertIs(self.calculator.calculate(0, 0.9), TrustTier.BRONZE)

    def test_no_sources_and_no_confidence_is_quarantine(self):
        self.assertIs(self.calculator.calculate(0, None), TrustTier.QUARANTINE)

    def test_no_sources_with_weak_confidence_is_quarantine(self):
        self.assertIs(self.calculator.calculate(0, 0.2), TrustTier.QUARANTINE)

    def test_many_sources_with_weak_confidence_is_silver(self):
        self.assertIs(self.calculator.calculate(5, 0.3), TrustTier.SILVER)

    def test_confidence_is_optional(self):
        self.assertIs(self.calculator.calculate(3), TrustTier.SILVER)


class TestMissingConfidenceDegradation(unittest.TestCase):
    """Absent confidence degrades a tier rather than defaulting high."""

    def setUp(self):
        self.calculator = TierCalculator()

    def test_missing_confidence_downgrades_gold(self):
        self.assertIs(self.calculator.calculate(2, None), TrustTier.SILVER)

    def test_missing_confidence_downgrades_silver(self):
        self.assertIs(self.calculator.calculate(1, None), TrustTier.BRONZE)

    def test_missing_confidence_does_not_earn_bronze(self):
        # No corroboration and no confidence is quarantine, not bronze.
        self.assertIs(self.calculator.calculate(0, None), TrustTier.QUARANTINE)

    def test_missing_confidence_never_yields_gold(self):
        for count in (2, 5, 50):
            self.assertIsNot(self.calculator.calculate(count, None), TrustTier.GOLD)

    def test_degradation_can_be_disabled(self):
        calculator = TierCalculator(missing_confidence_degrades=False)
        self.assertIs(calculator.calculate(2, None), TrustTier.GOLD)
        self.assertIs(calculator.calculate(0, None), TrustTier.QUARANTINE)


class TestInputHandling(unittest.TestCase):
    """Messy inputs must not raise or inflate a tier."""

    def setUp(self):
        self.calculator = TierCalculator()

    def test_none_count_is_treated_as_zero(self):
        self.assertIs(self.calculator.calculate(None, 0.9), TrustTier.BRONZE)

    def test_negative_count_is_treated_as_zero(self):
        self.assertIs(self.calculator.calculate(-4, 0.9), TrustTier.BRONZE)

    def test_non_numeric_count_is_treated_as_zero(self):
        self.assertIs(self.calculator.calculate("many", 0.9), TrustTier.BRONZE)

    def test_numeric_string_count_is_accepted(self):
        self.assertIs(self.calculator.calculate("3", 0.9), TrustTier.GOLD)

    def test_float_count_is_truncated(self):
        self.assertIs(self.calculator.calculate(2.9, 0.9), TrustTier.GOLD)
        self.assertIs(self.calculator.calculate(1.5, 0.9), TrustTier.SILVER)

    def test_unusable_confidence_downgrades(self):
        self.assertIs(self.calculator.calculate(2, "high"), TrustTier.SILVER)

    def test_nan_confidence_downgrades(self):
        tier = self.calculator.calculate(2, float("nan"))
        self.assertIs(tier, TrustTier.SILVER)

    def test_infinite_confidence_downgrades(self):
        self.assertIs(self.calculator.calculate(2, float("inf")), TrustTier.SILVER)
        self.assertIs(self.calculator.calculate(2, float("-inf")), TrustTier.SILVER)

    def test_infinite_count_is_treated_as_zero(self):
        self.assertIs(self.calculator.calculate(float("inf"), 0.9), TrustTier.BRONZE)
        self.assertIs(self.calculator.calculate(float("-inf"), 0.9), TrustTier.BRONZE)

    def test_nan_count_is_treated_as_zero(self):
        self.assertIs(
            self.calculator.calculate(float("nan"), 0.5), TrustTier.QUARANTINE
        )

    def test_confidence_above_one_is_still_usable(self):
        self.assertIs(self.calculator.calculate(2, 1.4), TrustTier.GOLD)


class TestTierCalculatorConfiguration(unittest.TestCase):
    """Thresholds are configurable but invalid ones are rejected."""

    def test_gold_threshold_must_be_positive(self):
        with self.assertRaises(ValueError):
            TierCalculator(min_corroboration_for_gold=0)

    def test_min_confidence_must_be_a_probability(self):
        with self.assertRaises(ValueError):
            TierCalculator(min_confidence=1.5)
        with self.assertRaises(ValueError):
            TierCalculator(min_confidence=-0.1)

    def test_lower_gold_threshold_promotes_single_source(self):
        calculator = TierCalculator(min_corroboration_for_gold=1)
        self.assertIs(calculator.calculate(1, 0.9), TrustTier.GOLD)

    def test_lower_min_confidence_keeps_weaker_confidence(self):
        calculator = TierCalculator(min_confidence=0.5)
        self.assertIs(calculator.calculate(1, 0.6), TrustTier.SILVER)
        self.assertIs(calculator.calculate(1, 0.4), TrustTier.BRONZE)


class TestMetadataFriendly(unittest.TestCase):
    """Tier values are ready to drop into RetrievedContext.metadata."""

    def test_tier_value_is_json_serialisable(self):
        tier = TierCalculator().calculate(3, 0.9)
        payload = json.dumps({"trust_tier": tier.value})
        self.assertEqual(payload, '{"trust_tier": "gold"}')


class TestTreatAsMissing(unittest.TestCase):
    """Placeholder confidence is handled as absent, not as a perfect score."""

    def setUp(self):
        self.calculator = TierCalculator()

    def test_answer_placeholder_cannot_earn_gold(self):
        for count in (2, 5, 50):
            self.assertIsNot(self.calculator.calculate(count, 1.0), TrustTier.GOLD)

    def test_answer_placeholder_downgrades_gold(self):
        self.assertIs(self.calculator.calculate(2, 1.0), TrustTier.SILVER)

    def test_integer_one_is_also_a_placeholder(self):
        # The dataclass default can arrive as int 1 depending on the source.
        self.assertIs(self.calculator.calculate(2, 1), TrustTier.SILVER)

    def test_placeholder_without_corroboration_is_quarantine(self):
        self.assertIs(self.calculator.calculate(0, 1.0), TrustTier.QUARANTINE)

    def test_earned_confidence_is_not_treated_as_missing(self):
        # 0.9 is the value the issue discusses; the repo default is 1.0, so
        # 0.9 stays usable unless it is configured as a placeholder.
        self.assertIs(self.calculator.calculate(2, 0.9), TrustTier.GOLD)

    def test_default_placeholder_is_exposed(self):
        self.assertEqual(self.calculator.treat_as_missing, frozenset({1.0}))

    def test_substitution_can_be_disabled(self):
        calculator = TierCalculator(treat_as_missing=())
        self.assertIs(calculator.calculate(2, 1.0), TrustTier.GOLD)

    def test_additional_placeholders_can_be_configured(self):
        calculator = TierCalculator(treat_as_missing=[0.9, 1.0])
        self.assertIs(calculator.calculate(2, 0.9), TrustTier.SILVER)
        self.assertIs(calculator.calculate(2, 1.0), TrustTier.SILVER)
        self.assertIs(calculator.calculate(2, 0.95), TrustTier.GOLD)

    def test_degradation_flag_applies_to_placeholders(self):
        calculator = TierCalculator(missing_confidence_degrades=False)
        self.assertIs(calculator.calculate(2, 1.0), TrustTier.GOLD)
        self.assertIs(calculator.calculate(0, 1.0), TrustTier.QUARANTINE)

    def test_placeholder_outside_probability_range_is_rejected(self):
        with self.assertRaises(ValueError):
            TierCalculator(treat_as_missing=[1.5])

    def test_non_numeric_placeholder_is_rejected(self):
        with self.assertRaises(ValueError):
            TierCalculator(treat_as_missing=["high"])

    def test_non_iterable_placeholder_is_rejected(self):
        with self.assertRaises(TypeError):
            TierCalculator(treat_as_missing=1.0)


if __name__ == "__main__":
    unittest.main()
