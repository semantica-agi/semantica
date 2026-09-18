import unittest

from semantica.normalize.language_detector import (
    LANGDETECT_AVAILABLE,
    UNKNOWN_LANGUAGE,
    LanguageDetector,
)


class TestLanguageDetector(unittest.TestCase):
    def setUp(self):
        self.detector = LanguageDetector()

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_language(self):
        # English
        self.assertEqual(
            self.detector.detect("This is a simple English sentence."), "en"
        )
        # French
        self.assertEqual(
            self.detector.detect("Ceci est une phrase française simple."), "fr"
        )
        # German
        self.assertEqual(
            self.detector.detect("Dies ist ein einfacher deutscher Satz."), "de"
        )

    def test_detect_short_text_returns_default(self):
        # Below-threshold input returns the configured default language
        self.assertEqual(self.detector.detect("Hi"), "en")

    def test_configured_default_language_is_returned_for_short_text(self):
        # default_language is returned whenever detection is skipped;
        # UNKNOWN_LANGUAGE can be passed explicitly for an out-of-band signal
        detector_unknown = LanguageDetector(default_language=UNKNOWN_LANGUAGE)
        self.assertEqual(detector_unknown.detect("Hi"), UNKNOWN_LANGUAGE)

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_with_confidence(self):
        lang, conf = self.detector.detect_with_confidence(
            "This is definitely an English sentence."
        )
        self.assertEqual(lang, "en")
        self.assertGreater(conf, 0.5)

    def test_default_min_text_length_preserved(self):
        # Backward compatibility: default threshold stays at 10
        self.assertEqual(self.detector.min_text_length, 10)
        self.assertEqual(self.detector.detect("Short txt"), "en")

    def test_short_text_fallback_has_zero_confidence(self):
        # Fallback can be distinguished from a genuine detection via 0.0 confidence
        lang, conf = self.detector.detect_with_confidence("Hi")
        self.assertEqual((lang, conf), ("en", 0.0))
        self.assertEqual(
            self.detector.detect_multiple("Hi"), [("en", 0.0)]
        )

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_short_non_latin_text_with_configured_threshold(self):
        # 9 stripped chars: below the default threshold, falls back to default
        text = "你好，这是中文文本"
        self.assertEqual(self.detector.detect(text), "en")

        # A configured threshold lets short CJK text reach the detector
        detector = LanguageDetector(min_text_length=5)
        self.assertTrue(detector.detect(text).startswith("zh"))

        lang, conf = detector.detect_with_confidence(text)
        self.assertTrue(lang.startswith("zh"))
        self.assertGreater(conf, 0.5)

        languages = detector.detect_multiple(text)
        self.assertTrue(languages[0][0].startswith("zh"))

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_min_text_length_per_call_override(self):
        text = "你好，这是中文文本"
        self.assertEqual(self.detector.detect(text), "en")
        self.assertTrue(
            self.detector.detect(text, min_text_length=5).startswith("zh")
        )

    def test_min_text_length_still_guards_empty_text(self):
        detector = LanguageDetector(min_text_length=0)
        self.assertEqual(detector.detect(""), "en")
        self.assertEqual(
            detector.detect_with_confidence(""), ("en", 0.0)
        )

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_min_text_length_zero_allows_nonempty_short_text(self):
        # min_text_length=0 disables the length guard for non-empty input:
        # the text reaches langdetect and a real language code is returned.
        # We verify detection actually ran by checking the confidence is > 0.0
        # rather than asserting the specific language (detection is non-deterministic).
        detector = LanguageDetector(min_text_length=0)
        result = detector.detect("Hi")
        self.assertIsInstance(result, str)
        self.assertNotEqual(result, detector.default_language)

        # detect_multiple likewise runs and returns a non-zero confidence
        langs = detector.detect_multiple("Hi")
        self.assertTrue(len(langs) > 0)
        self.assertGreater(langs[0][1], 0.0)

    def test_invalid_min_text_length_degrades_to_fallback(self):
        # Invalid values must not raise TypeError during the length check
        for invalid in (None, "abc", object()):
            detector = LanguageDetector(min_text_length=invalid)
            self.assertEqual(detector.min_text_length, 10)
            self.assertEqual(detector.detect("Hi"), "en")

        # Invalid per-call override falls back to the instance value
        detector = LanguageDetector(min_text_length=3)
        self.assertEqual(
            detector.detect("Hi", min_text_length=None), "en"
        )

        # Numeric-ish values are coerced; negatives clamp to zero
        self.assertEqual(LanguageDetector(min_text_length="5").min_text_length, 5)
        self.assertEqual(LanguageDetector(min_text_length=-1).min_text_length, 0)
        self.assertEqual(LanguageDetector(min_text_length=2.9).min_text_length, 2)

    def test_detect_batch_respects_min_text_length(self):
        # Batch APIs forward **options to detect/detect_with_confidence,
        # so min_text_length overrides must work at both constructor and
        # per-call level for detect_batch and detect_batch_with_confidence.
        cjk = "你好，这是中文文本"  # 9 stripped chars, below the default threshold of 10
        mixed = [cjk, cjk]

        # Default threshold blocks CJK text -> all fallbacks
        self.assertEqual(
            self.detector.detect_batch(mixed),
            ["en", "en"],
        )
        self.assertEqual(
            self.detector.detect_batch_with_confidence(mixed),
            [("en", 0.0), ("en", 0.0)],
        )

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_batch_min_text_length_constructor_override(self):
        cjk = "你好，这是中文文本"
        mixed = [cjk, cjk]

        # Constructor-level threshold lets CJK text through
        detector = LanguageDetector(min_text_length=5)
        results = detector.detect_batch(mixed)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.startswith("zh") for r in results))

        conf_results = detector.detect_batch_with_confidence(mixed)
        self.assertEqual(len(conf_results), 2)
        self.assertTrue(all(lang.startswith("zh") for lang, _ in conf_results))
        self.assertTrue(all(conf > 0.5 for _, conf in conf_results))

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_batch_min_text_length_per_call_override(self):
        cjk = "你好，这是中文文本"
        mixed = [cjk, cjk]

        # Per-call override on a default-threshold detector
        results = self.detector.detect_batch(mixed, min_text_length=5)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.startswith("zh") for r in results))

        conf_results = self.detector.detect_batch_with_confidence(
            mixed, min_text_length=5
        )
        self.assertEqual(len(conf_results), 2)
        self.assertTrue(all(lang.startswith("zh") for lang, _ in conf_results))

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_uses_detect_langs_not_detect(self):
        # The PR refactored detect() to delegate to detect_multiple(), which
        # calls detect_langs() rather than the top-level langdetect.detect().
        # This test pins that contract: detect() must return detect_langs()[0].lang,
        # not an independent call to langdetect.detect().
        #
        # We mock detect_langs at the module level used by language_detector so the
        # test is deterministic and does not depend on the non-deterministic
        # langdetect profile selection.
        from unittest.mock import MagicMock, patch

        fake_lang = MagicMock()
        fake_lang.lang = "de"
        fake_lang.prob = 0.99

        detector = LanguageDetector(min_text_length=5)
        target = "semantica.normalize.language_detector.detect_langs"
        with patch(target, return_value=[fake_lang]) as mock_detect_langs:
            result = detector.detect("Hello world this is text")

        mock_detect_langs.assert_called_once()
        self.assertEqual(result, "de")

        # detect_with_confidence must use the same path: it returns
        # (fake_lang.lang, fake_lang.prob) because 0.99 >= min_confidence 0.5
        with patch(target, return_value=[fake_lang]):
            lang, conf = detector.detect_with_confidence("Hello world this is text")
        self.assertEqual(lang, "de")
        self.assertAlmostEqual(conf, 0.99)

    def test_detect_language_wrapper_does_not_mutate_global_config(self):
        from semantica.normalize.config import normalize_config
        from semantica.normalize.methods import detect_language

        original = dict(normalize_config.get_method_config("language"))
        normalize_config.set_method_config("language", default_language="en")
        try:
            detect_language("Hi", min_text_length=1)
            self.assertNotIn(
                "min_text_length",
                normalize_config.get_method_config("language"),
            )
        finally:
            normalize_config.set_method_config("language", **original)

    def test_unknown_option_names_are_reported_not_swallowed(self):
        from unittest.mock import patch

        detector = LanguageDetector(min_text_length=5)
        with patch.object(detector, "logger") as mock_logger:
            # Typo'd option name: must warn instead of silently ignoring
            detector.detect("Hi", min_text_len=1)
            detector.detect("Hi", min_text_len=1)

        warnings = [
            call.args[0] for call in mock_logger.warning.call_args_list
        ]
        self.assertEqual(len(warnings), 1)  # once per name, not per call
        self.assertIn("min_text_len", warnings[0])

        # Valid option names must not warn (threshold high enough that the
        # guard short-circuits before any langdetect call can log)
        with patch.object(detector, "logger") as mock_logger:
            detector.detect("Hi", min_text_length=100)
        mock_logger.warning.assert_not_called()

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_apis_share_one_semantic_core(self):
        # detect() and detect_with_confidence() delegate to detect_multiple(),
        # so all three must agree on the same input.
        text = "Ceci est une phrase française simple."
        top_lang, top_conf = self.detector.detect_multiple(text, top_n=1)[0]
        self.assertEqual(self.detector.detect(text), top_lang)
        lang, conf = self.detector.detect_with_confidence(text)
        self.assertEqual(lang, top_lang)
        self.assertGreater(conf, 0.5)

    def test_detect_apis_consistent_below_threshold(self):
        # All three APIs must agree when the guard short-circuits: same
        # fallback language and the same 0.0 sentinel confidence.
        text = "Hi"  # len=2, below default threshold of 10
        self.assertEqual(self.detector.detect(text), "en")
        self.assertEqual(
            self.detector.detect_with_confidence(text), ("en", 0.0)
        )
        self.assertEqual(
            self.detector.detect_multiple(text), [("en", 0.0)]
        )

    @unittest.skipUnless(LANGDETECT_AVAILABLE, "langdetect is not installed")
    def test_detect_ignores_min_confidence_detect_with_confidence_applies_it(self):
        # detect() returns the best-matching language regardless of
        # min_confidence; detect_with_confidence() substitutes the fallback
        # when the top confidence is below the threshold.  This tests the
        # behavioral split between the two APIs.
        text = "Ceci est une phrase française simple."
        # A min_confidence just above what langdetect actually returns forces
        # detect_with_confidence() to fall back, while detect() is unaffected.
        detector = LanguageDetector(min_confidence=0.9999999)

        # detect() returns the raw winner regardless of the threshold
        top_lang = detector.detect(text)
        self.assertNotEqual(top_lang, UNKNOWN_LANGUAGE)

        # detect_with_confidence() applies the threshold: confidence fell
        # short, so the fallback language is returned.  The confidence is the
        # real observed score (not 0.0, which is reserved for the length-guard
        # path) — we only verify the structural invariants here since
        # langdetect's probability is non-deterministic across calls.
        lang, conf = detector.detect_with_confidence(text)
        self.assertEqual(lang, detector.default_language)
        self.assertGreater(conf, 0.0)       # real score, not the 0.0 sentinel
        self.assertLess(conf, 0.9999999)    # below the configured threshold

    def test_get_language_name(self):
        self.assertEqual(self.detector.get_language_name("en"), "English")
        self.assertEqual(self.detector.get_language_name("fr"), "French")
        self.assertEqual(
            self.detector.get_language_name(UNKNOWN_LANGUAGE), "Unknown"
        )
        self.assertEqual(self.detector.get_language_name("xx"), "XX")


if __name__ == "__main__":
    unittest.main()
