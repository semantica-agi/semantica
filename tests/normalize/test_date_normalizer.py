import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from semantica.normalize.date_normalizer import (
    DateNormalizer,
    RelativeDateProcessor,
    TimeZoneNormalizer,
)
from semantica.utils.exceptions import ValidationError


class TestDateNormalizer(unittest.TestCase):
    def setUp(self):
        self.normalizer = DateNormalizer()

    def test_normalize_date_iso(self):
        # Test ISO8601 parsing
        self.assertEqual(
            self.normalizer.normalize_date("2023-01-01", format="date"), "2023-01-01"
        )
        self.assertEqual(
            self.normalizer.normalize_date("2023-01-01T12:00:00", format="ISO8601"),
            "2023-01-01T12:00:00+00:00",
        )

    def test_normalize_date_relative(self):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = cls(2024, 1, 2, 0, 30)
                return fixed if tz is None else fixed.replace(tzinfo=tz)

        with patch("semantica.normalize.date_normalizer.datetime", FixedDateTime):
            self.assertEqual(
                self.normalizer.normalize_date("today", format="date"),
                "2024-01-02",
            )

    def test_normalize_timezone(self):
        # Test timezone conversion
        # "2023-01-01T12:00:00+01:00" -> UTC should be "2023-01-01T11:00:00+00:00"
        normalized = self.normalizer.normalize_date(
            "2023-01-01T12:00:00+01:00", timezone="UTC"
        )
        self.assertEqual(normalized, "2023-01-01T11:00:00+00:00")

    def test_parse_temporal_expression(self):
        # Test range parsing
        result = self.normalizer.parse_temporal_expression(
            "from 2023-01-01 to 2023-01-31"
        )
        self.assertIsNotNone(result.get("range"))


class TestTimeZoneNormalizer(unittest.TestCase):
    def setUp(self):
        self.tz_normalizer = TimeZoneNormalizer()

    def test_normalize_timezone_obj(self):
        dt = datetime(2023, 1, 1, 12, 0, 0)
        # Assuming default is UTC if not specified or naive
        normalized = self.tz_normalizer.normalize_timezone(dt, "UTC")
        # Check offset instead of object identity
        self.assertEqual(
            normalized.tzinfo.utcoffset(normalized), timezone.utc.utcoffset(None)
        )

    def test_convert_to_utc_source_timezone_winter(self):
        dt = datetime(2026, 3, 1, 7, 30)
        self.assertEqual(
            self.tz_normalizer.convert_to_utc(dt, "America/New_York"),
            datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc),
        )

    def test_convert_to_utc_source_timezone_summer(self):
        dt = datetime(2026, 7, 1, 7, 30)
        self.assertEqual(
            self.tz_normalizer.convert_to_utc(dt, "America/New_York"),
            datetime(2026, 7, 1, 11, 30, tzinfo=timezone.utc),
        )

    def test_convert_to_utc_aware_ignores_source_timezone(self):
        dt = datetime(2026, 3, 1, 7, 30, tzinfo=timezone(timedelta(hours=2)))
        for source_timezone in ("America/New_York", "Nope/Zone"):
            with self.subTest(source_timezone=source_timezone):
                self.assertEqual(
                    self.tz_normalizer.convert_to_utc(dt, source_timezone),
                    datetime(2026, 3, 1, 5, 30, tzinfo=timezone.utc),
                )

    @unittest.skipUnless(hasattr(time, "tzset"), "time.tzset is not available")
    def test_convert_to_utc_unknown_timezone(self):
        # A non-UTC host zone, so a naive result read as local time would show up
        self.addCleanup(time.tzset)
        with patch.dict(os.environ, {"TZ": "Asia/Kolkata"}):
            time.tzset()
            with self.assertRaisesRegex(ValidationError, "Nope/Zone"):
                self.tz_normalizer.convert_to_utc(
                    datetime(2026, 3, 1, 7, 30), "Nope/Zone"
                )

    def test_convert_to_utc_invalid_timezone(self):
        for source_timezone in ("../etc", 123):
            with self.subTest(source_timezone=source_timezone):
                with self.assertRaises(ValidationError) as error:
                    self.tz_normalizer.convert_to_utc(
                        datetime(2026, 3, 1, 7, 30), source_timezone
                    )
                self.assertIn(repr(source_timezone), str(error.exception))

    def test_convert_to_utc_without_source_timezone(self):
        dt = datetime(2026, 3, 1, 7, 30)
        self.assertEqual(
            self.tz_normalizer.convert_to_utc(dt),
            datetime(2026, 3, 1, 7, 30, tzinfo=timezone.utc),
        )


class TestRelativeDateProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = RelativeDateProcessor()

    def test_process_relative_expression(self):
        # "3 days ago"
        dt = self.processor.process_relative_expression("3 days ago")
        self.assertIsInstance(dt, datetime)
        # Roughly check delta
        # Use datetime.now() since result is naive
        diff = datetime.now() - dt
        self.assertTrue(timedelta(days=2, hours=23) < diff < timedelta(days=3, hours=1))


if __name__ == "__main__":
    unittest.main()
