"""
Date and Time Normalization Module

This module provides comprehensive date and time normalization capabilities
for the Semantica framework, enabling standardization of temporal data
across various formats and conventions.

Key Features:
    - Date format standardization (ISO8601, custom formats)
    - Time zone normalization and UTC conversion
    - Relative date processing ("yesterday", "3 days ago", etc.)
    - Temporal expression parsing (natural language dates)
    - Date range handling ("from X to Y")
    - Support for multiple calendar systems
    - Optional dateutil integration for advanced parsing

Main Classes:
    - DateNormalizer: Main date normalization coordinator
    - TimeZoneNormalizer: Time zone processing engine
    - RelativeDateProcessor: Relative date handling engine
    - TemporalExpressionParser: Temporal expression parser

Example Usage:
    >>> from semantica.normalize import DateNormalizer
    >>> normalizer = DateNormalizer()
    >>> normalized = normalizer.normalize_date("2023-01-15", format="ISO8601")
    >>> relative = normalizer.process_relative_date("3 days ago")

Author: Semantica Contributors
License: MIT
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

# Optional imports for date parsing
try:
    from dateutil import parser as date_parser
    from dateutil.relativedelta import relativedelta

    HAS_DATEUTIL = True
except (ImportError, OSError):
    HAS_DATEUTIL = False
    date_parser = None
    relativedelta = None


class DateNormalizer:
    """
    Date and time normalization coordinator.

    This class provides comprehensive date and time normalization capabilities,
    coordinating timezone normalization, relative date processing, and temporal
    expression parsing.

    Features:
        - Date and time format standardization
        - Multiple date format support
        - Timezone normalization and UTC conversion
        - Relative date processing
        - Temporal expression parsing
        - Date range handling

    Example Usage:
        >>> normalizer = DateNormalizer()
        >>> normalized = normalizer.normalize_date("2023-01-15", format="ISO8601")
        >>> relative = normalizer.process_relative_date("3 days ago")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize date normalizer.

        Sets up the normalizer with timezone normalizer, relative date processor,
        and temporal expression parser components.

        Args:
            config: Configuration dictionary (optional)
            **kwargs: Additional configuration options (merged into config)
        """
        self.logger = get_logger("date_normalizer")
        self.config = config or {}
        self.config.update(kwargs)

        self.timezone_normalizer = TimeZoneNormalizer(**self.config)
        self.relative_date_processor = RelativeDateProcessor(**self.config)
        self.temporal_parser = TemporalExpressionParser(**self.config)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Date normalizer initialized")

    def normalize_date(
        self, date_input: Any, format: str = "ISO8601", timezone: str = "UTC", **options
    ) -> str:
        """
        Normalize date to standard format.

        This method normalizes date input (string or datetime) to a standard
        format, handling timezone conversion and relative date expressions.

        Args:
            date_input: Date input - can be:
                - String (e.g., "2023-01-15", "yesterday")
                - datetime object
            format: Output format (default: "ISO8601"):
                - "ISO8601": ISO 8601 format (e.g., "2023-01-15T10:30:00")
                - "date": Date only (e.g., "2023-01-15")
                - Custom format string (strftime format)
            timezone: Target timezone (default: "UTC")
            **options: Additional normalization options (unused)

        Returns:
            str: Normalized date string in specified format

        Raises:
            ValidationError: If date input type is unsupported or parsing fails
        """
        if not date_input:
            return ""

        # Parse date input
        if isinstance(date_input, str):
            try:
                if HAS_DATEUTIL and date_parser:
                    dt = date_parser.parse(date_input)
                else:
                    # Fallback to basic parsing
                    dt = datetime.fromisoformat(date_input.replace("Z", "+00:00"))
            except Exception:
                # Try relative date processing
                dt = self.relative_date_processor.process_relative_expression(
                    date_input
                )
        elif isinstance(date_input, datetime):
            dt = date_input
        else:
            raise ValidationError(f"Unsupported date input type: {type(date_input)}")

        # Normalize timezone
        if timezone != "UTC":
            dt = self.timezone_normalizer.normalize_timezone(dt, timezone)
        else:
            dt = self.timezone_normalizer.convert_to_utc(dt)

        # Format output
        output_format = format
        if output_format == "ISO8601":
            return dt.isoformat()
        elif output_format == "date":
            return dt.date().isoformat()
        else:
            return dt.strftime(output_format)

    def normalize_time(self, time_input: Any, **options) -> str:
        """
        Normalize time to standard format.

        This method normalizes time input to ISO format (HH:MM:SS).

        Args:
            time_input: Time input - can be:
                - String (e.g., "10:30:00", "10:30 AM")
                - datetime object
            **options: Additional normalization options (unused)

        Returns:
            str: Normalized time string in ISO format (HH:MM:SS), or empty
                 string if parsing fails
        """
        if isinstance(time_input, str):
            try:
                if HAS_DATEUTIL and date_parser:
                    dt = date_parser.parse(time_input)
                else:
                    # Fallback parsing
                    dt = datetime.fromisoformat(time_input)
            except Exception:
                return ""
        elif isinstance(time_input, datetime):
            dt = time_input
        else:
            return ""

        return dt.time().isoformat()

    def process_relative_date(
        self, relative_expression: str, reference_date: Optional[datetime] = None
    ) -> datetime:
        """
        Process relative date expressions.

        This method processes relative date expressions like "yesterday",
        "3 days ago", "2 weeks from now", etc.

        Args:
            relative_expression: Relative date expression (e.g., "yesterday",
                                "3 days ago", "2 weeks from now")
            reference_date: Reference date for calculation (default: current
                           datetime)

        Returns:
            datetime: Calculated absolute date
        """
        return self.relative_date_processor.process_relative_expression(
            relative_expression, reference_date
        )

    def parse_temporal_expression(
        self, temporal_text: str, **context
    ) -> Dict[str, Any]:
        """
        Parse temporal expressions and references.

        This method parses natural language temporal expressions, extracting
        date, time, and range information.

        Args:
            temporal_text: Temporal expression text (e.g., "from January to
                          March", "last week")
            **context: Context information (optional)

        Returns:
            dict: Parsed temporal data containing:
                - date: Date string (if found)
                - time: Time string (if found)
                - range: Range dictionary with start/end (if found)
                - relative: Whether expression is relative (bool)
        """
        return self.temporal_parser.parse_temporal_expression(temporal_text, **context)


class TimeZoneNormalizer:
    """
    Time zone normalization engine.

    This class provides timezone conversion and normalization capabilities,
    handling UTC conversion, timezone abbreviations, and daylight saving
    time transitions.

    Features:
        - Timezone conversion and normalization
        - UTC conversion
        - Timezone abbreviation processing
        - Daylight saving time handling
        - ZoneInfo integration

    Example Usage:
        >>> tz_normalizer = TimeZoneNormalizer()
        >>> utc_dt = tz_normalizer.convert_to_utc(datetime_obj)
        >>> normalized = tz_normalizer.normalize_timezone(dt, "America/New_York")
    """

    def __init__(self, **config):
        """
        Initialize time zone normalizer.

        Sets up the normalizer with configuration options.

        Args:
            **config: Configuration options (currently unused)
        """
        self.logger = get_logger("timezone_normalizer")
        self.config = config

        self.logger.debug("Time zone normalizer initialized")

    def normalize_timezone(
        self, datetime_obj: datetime, target_timezone: str = "UTC"
    ) -> datetime:
        """
        Normalize datetime to target timezone.

        This method converts a datetime object to the specified timezone with
        ZoneInfo. If the conversion fails, the datetime comes back unconverted.

        Args:
            datetime_obj: Datetime object to normalize
            target_timezone: Target timezone string (e.g., "America/New_York",
                           "UTC", "Europe/London")

        Returns:
            datetime: Normalized datetime in target timezone
        """
        try:
            from zoneinfo import ZoneInfo

            target_tz = ZoneInfo(target_timezone)
            if datetime_obj.tzinfo is None:
                datetime_obj = datetime_obj.replace(tzinfo=timezone.utc)
            return datetime_obj.astimezone(target_tz)
        except Exception:
            # zoneinfo is always available (stdlib on 3.11+). This falls back on
            # any failure (an unknown, malformed or non-str timezone name, or a
            # conversion overflow) and returns the datetime unconverted; a naive
            # input may come back tagged UTC.
            return datetime_obj

    def convert_to_utc(
        self, datetime_obj: datetime, source_timezone: Optional[str] = None
    ) -> datetime:
        """
        Convert datetime to UTC.

        This method converts a datetime object to UTC timezone. If the datetime
        has no timezone info, it assumes UTC or uses the source_timezone if
        provided. Aware datetimes ignore source_timezone.

        Args:
            datetime_obj: Datetime object to convert
            source_timezone: Source timezone string (optional, used if datetime
                          has no timezone info)

        Returns:
            datetime: Datetime object in UTC timezone

        Raises:
            ValidationError: If source_timezone is unknown or invalid for a
                             naive datetime
        """
        if datetime_obj.tzinfo is None:
            if source_timezone:
                try:
                    source_tz = ZoneInfo(source_timezone)
                except (ZoneInfoNotFoundError, ValueError, TypeError) as e:
                    raise ValidationError(
                        f"Invalid source timezone: {source_timezone!r}"
                    ) from e
                datetime_obj = datetime_obj.replace(tzinfo=source_tz)
            else:
                datetime_obj = datetime_obj.replace(tzinfo=timezone.utc)

        return datetime_obj.astimezone(timezone.utc)

    def handle_dst_transitions(
        self, datetime_obj: datetime, timezone_str: str
    ) -> datetime:
        """
        Handle daylight saving time transitions.

        This method handles DST transitions by normalizing the datetime to
        the specified timezone, which automatically accounts for DST.

        Args:
            datetime_obj: Datetime object
            timezone_str: Timezone string (e.g., "America/New_York")

        Returns:
            datetime: Adjusted datetime accounting for DST
        """
        return self.normalize_timezone(datetime_obj, timezone_str)


class RelativeDateProcessor:
    """
    Relative date processing engine.

    This class provides relative date expression processing, converting
    natural language relative dates (e.g., "yesterday", "3 days ago")
    into absolute datetime objects.

    Features:
        - Relative date expression processing
        - Natural language date parsing
        - Date arithmetic (days, weeks, months, years)
        - Support for common relative terms

    Example Usage:
        >>> processor = RelativeDateProcessor()
        >>> date = processor.process_relative_expression("3 days ago")
        >>> offset = processor.calculate_date_offset("2 weeks from now", ref_date)
    """

    def __init__(self, **config):
        """
        Initialize relative date processor.

        Sets up the processor with relative terms dictionary and configuration.

        Args:
            **config: Configuration options (currently unused)
        """
        self.logger = get_logger("relative_date_processor")
        self.config = config

        self.relative_terms = {
            "today": 0,
            "yesterday": -1,
            "tomorrow": 1,
            "now": 0,
        }

        self.logger.debug("Relative date processor initialized")

    def process_relative_expression(
        self, expression: str, reference_date: Optional[datetime] = None
    ) -> datetime:
        """
        Process relative date expression.

        This method processes relative date expressions like "yesterday",
        "3 days ago", "2 weeks from now", etc., converting them to absolute
        datetime objects.

        Args:
            expression: Relative date expression (e.g., "yesterday",
                      "3 days ago", "2 weeks from now")
            reference_date: Reference date for calculation (default: current
                           datetime)

        Returns:
            datetime: Calculated absolute date
        """
        if reference_date is None:
            reference_date = datetime.now()

        expression_lower = expression.lower().strip()

        # Check for relative terms
        if expression_lower in self.relative_terms:
            days = self.relative_terms[expression_lower]
            return reference_date + timedelta(days=days)

        # Parse patterns like "3 days ago", "2 weeks from now"
        pattern = r"(\d+)\s*(day|week|month|year)s?\s*(ago|from now|later)?"
        match = re.search(pattern, expression_lower)

        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            direction = match.group(3) or "ago"

            if unit == "day":
                delta = timedelta(days=amount)
            elif unit == "week":
                delta = timedelta(weeks=amount)
            elif unit == "month":
                if HAS_DATEUTIL and relativedelta:
                    delta = relativedelta(months=amount)
                else:
                    # Approximate month as 30 days
                    delta = timedelta(days=amount * 30)
            elif unit == "year":
                if HAS_DATEUTIL and relativedelta:
                    delta = relativedelta(years=amount)
                else:
                    # Approximate year as 365 days
                    delta = timedelta(days=amount * 365)
            else:
                delta = timedelta(days=amount)

            if direction in ["ago", "before"]:
                return reference_date - delta
            else:
                return reference_date + delta

        # Fallback: try to parse as absolute date
        try:
            if HAS_DATEUTIL and date_parser:
                return date_parser.parse(expression)
            else:
                # Basic ISO format parsing
                return datetime.fromisoformat(expression.replace("Z", "+00:00"))
        except Exception:
            return reference_date

    def calculate_date_offset(
        self, expression: str, reference_date: datetime
    ) -> datetime:
        """
        Calculate date offset from expression.

        This method calculates a date offset from a relative expression,
        using the provided reference date.

        Args:
            expression: Offset expression (e.g., "3 days ago",
                      "2 weeks from now")
            reference_date: Reference date for calculation

        Returns:
            datetime: Calculated date with offset applied
        """
        return self.process_relative_expression(expression, reference_date)

    def handle_relative_terms(self, term: str, reference_date: datetime) -> datetime:
        """
        Handle specific relative terms.

        This method processes specific relative terms like "today", "yesterday",
        "tomorrow", using the provided reference date.

        Args:
            term: Relative term (e.g., "today", "yesterday", "tomorrow")
            reference_date: Reference date for calculation

        Returns:
            datetime: Calculated date based on relative term
        """
        return self.process_relative_expression(term, reference_date)


class TemporalExpressionParser:
    """
    Temporal expression parsing engine.

    This class provides natural language temporal expression parsing,
    extracting date, time, and range information from text.

    Features:
        - Natural language temporal expression parsing
        - Date and time component extraction
        - Temporal range processing
        - Complex temporal reference handling

    Example Usage:
        >>> parser = TemporalExpressionParser()
        >>> result = parser.parse_temporal_expression("from January to March")
        >>> date_components = parser.extract_date_components("2023-01-15")
    """

    def __init__(self, **config):
        """
        Initialize temporal expression parser.

        Sets up the parser with configuration options.

        Args:
            **config: Configuration options (currently unused)
        """
        self.logger = get_logger("temporal_expression_parser")
        self.config = config

        self.logger.debug("Temporal expression parser initialized")

    def parse_temporal_expression(self, text: str, **context) -> Dict[str, Any]:
        """
        Parse temporal expression from text.

        This method parses natural language temporal expressions, extracting
        date, time, and range information.

        Args:
            text: Temporal expression text (e.g., "from January to March",
                 "last week", "2023-01-15")
            **context: Context information (optional)

        Returns:
            dict: Parsed temporal data containing:
                - date: Date string (if found)
                - time: Time string (if found)
                - range: Range dictionary with start/end (if found)
                - relative: Whether expression is relative (bool)
        """
        result = {"date": None, "time": None, "range": None, "relative": False}

        # Try to extract date components
        date_components = self.extract_date_components(text)
        if date_components:
            result.update(date_components)

        # Try to extract time components
        time_components = self.extract_time_components(text)
        if time_components:
            result.update(time_components)

        # Try to parse as range
        range_info = self.process_temporal_ranges(text)
        if range_info:
            result["range"] = range_info

        return result

    def extract_date_components(self, text: str) -> Dict[str, Any]:
        """
        Extract date components from text.

        This method extracts date components (year, month, day) from text
        using date parsing.

        Args:
            text: Input text containing date information

        Returns:
            dict: Date components containing:
                - date: Date string in ISO format
                - year: Year (int)
                - month: Month (int, 1-12)
                - day: Day (int, 1-31)
                Returns empty dict if parsing fails
        """
        try:
            if HAS_DATEUTIL and date_parser:
                dt = date_parser.parse(text, fuzzy=True)
            else:
                # Basic parsing
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return {
                "date": dt.date().isoformat(),
                "year": dt.year,
                "month": dt.month,
                "day": dt.day,
            }
        except Exception:
            return {}

    def extract_time_components(self, text: str) -> Dict[str, Any]:
        """
        Extract time components from text.

        This method extracts time components (hour, minute, second) from
        text using date parsing.

        Args:
            text: Input text containing time information

        Returns:
            dict: Time components containing:
                - time: Time string in ISO format (HH:MM:SS)
                - hour: Hour (int, 0-23)
                - minute: Minute (int, 0-59)
                - second: Second (int, 0-59)
                Returns empty dict if parsing fails
        """
        try:
            if HAS_DATEUTIL and date_parser:
                dt = date_parser.parse(text, fuzzy=True)
            else:
                # Basic parsing
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return {
                "time": dt.time().isoformat(),
                "hour": dt.hour,
                "minute": dt.minute,
                "second": dt.second,
            }
        except Exception:
            return {}

    def process_temporal_ranges(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Process temporal ranges and periods.

        This method extracts temporal ranges from text patterns like
        "from X to Y" or "between X and Y".

        Args:
            text: Input text containing temporal range (e.g., "from January
                 to March", "between 2023-01-01 and 2023-03-31")

        Returns:
            dict: Range information containing:
                - start: Start date string in ISO format
                - end: End date string in ISO format
            Returns None if no range is found
        """
        # Look for range patterns like "from X to Y", "between X and Y"
        range_patterns = [
            r"from\s+(.+?)\s+to\s+(.+?)",
            r"between\s+(.+?)\s+and\s+(.+?)",
        ]

        for pattern in range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if HAS_DATEUTIL and date_parser:
                        start = date_parser.parse(match.group(1))
                        end = date_parser.parse(match.group(2))
                    else:
                        # Basic parsing
                        start = datetime.fromisoformat(
                            match.group(1).replace("Z", "+00:00")
                        )
                        end = datetime.fromisoformat(
                            match.group(2).replace("Z", "+00:00")
                        )
                    return {"start": start.isoformat(), "end": end.isoformat()}
                except Exception:
                    continue

        return None
