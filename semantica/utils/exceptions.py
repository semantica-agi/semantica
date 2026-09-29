"""
Exception Handling Module

This module provides comprehensive exception handling for the Semantica framework,
including a custom exception hierarchy, error context management, and exception
handling utilities for robust error reporting and debugging.

Key Features:
    - Custom exception hierarchy with base SemanticaError class
    - Specialized exception types (ValidationError, ProcessingError, ConfigurationError, QualityError)
    - Error context and debugging information
    - Exception serialization and formatting
    - Exception handling utilities with recovery support
    - Error code management

Main Classes:
    - SemanticaError: Base exception class for all framework errors
    - ValidationError: Exception for data validation failures
    - ProcessingError: Exception for data processing failures
    - ConfigurationError: Exception for configuration validation failures
    - QualityError: Exception for data quality validation failures

Example Usage:
    >>> from semantica.utils import ValidationError, ProcessingError
    >>> try:
    ...     if not is_valid:
    ...         raise ValidationError("Invalid data format", field="name", value=value)
    ... except ValidationError as e:
    ...     print(f"Error: {e}, Code: {e.error_code}")
    >>> 
    >>> from semantica.utils import handle_exception, format_exception
    >>> try:
    ...     process_data(data)
    ... except Exception as e:
    ...     error_info = handle_exception(e, context={"stage": "processing"})
    ...     formatted = format_exception(e, include_traceback=True)

Author: Semantica Contributors
License: MIT
"""

from __future__ import annotations

import sys
import traceback
from typing import Any, Dict, Optional


class SemanticaError(Exception):
    """
    Base exception class for all Semantica framework errors.

    Provides base error handling with:
    - Error context and debugging information
    - Error chaining and propagation
    - Error reporting and logging
    """

    def __init__(
        self, message: str, context: Optional[Dict[str, Any]] = None, **details: Any
    ):
        """
        Initialize Semantica error.

        Args:
            message: Error message
            context: Error context dictionary
            **details: Additional error details as keyword arguments
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.details = details
        self.error_code = self.details.get("error_code", "SEM000")

        # Capture stack trace
        _, _, self.traceback = sys.exc_info()

    def __str__(self) -> str:
        """Return formatted error message with context."""
        parts = [self.message]

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: {context_str}")

        if self.details:
            details_str = ", ".join(
                f"{k}={v}" for k, v in self.details.items() if k != "error_code"
            )
            if details_str:
                parts.append(f"Details: {details_str}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        """Return detailed representation of the error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"context={self.context}, "
            f"error_code={self.error_code}, "
            f"details={self.details})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary format for serialization.

        Returns:
            Dictionary containing error information
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "details": self.details,
        }


class ValidationError(SemanticaError):
    """
    Exception raised for data validation errors.

    Handles data validation failures with:
    - Validation context and details
    - Validation error reporting
    - Validation error recovery support
    """

    def __init__(
        self,
        message: str,
        validation_context: Optional[Dict[str, Any]] = None,
        **details: Any,
    ):
        """
        Initialize validation error.

        Args:
            message: Validation error message
            validation_context: Validation context dictionary
            **details: Additional validation details
        """
        super().__init__(
            message, context=validation_context, error_code="SEM001", **details
        )
        self.validation_context = validation_context or {}
        self.field = details.get("field")
        self.value = details.get("value")
        self.constraint = details.get("constraint")


class TemporalValidationError(ValidationError):
    """
    Exception raised for invalid temporal values or inconsistent temporal state.
    """

    def __init__(
        self,
        message: str,
        temporal_context: Optional[Dict[str, Any]] = None,
        **details: Any,
    ):
        super().__init__(message, validation_context=temporal_context, **details)
        self.error_code = "SEM001T"


class TemporalAmbiguityWarning(UserWarning):
    """
    Warning raised when a temporal expression is ambiguous and cannot be
    resolved without additional locale or context information.

    Example: "03/04/2022" is ambiguous without knowing whether day-first or
    month-first ordering applies. Use ``warnings.catch_warnings()`` to handle.
    """

    pass


class PartialIngestionWarning(UserWarning):
    """
    Warning raised when a directory ingestion completes but one or more files
    could not be processed.

    The successfully ingested files are still returned by
    ``FileIngestor.ingest_directory()``.  This warning carries the count of
    failures and the list of failed paths so callers can decide whether the
    partial result is acceptable.

    Example::

        import warnings
        from semantica.ingest import FileIngestor
        from semantica.utils.exceptions import PartialIngestionWarning

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", PartialIngestionWarning)
            files = FileIngestor().ingest_directory("./docs")
        if caught:
            print(caught[0].message)
    """

    pass


class ProcessingError(SemanticaError):
    """
    Exception raised for data processing errors.

    Handles data processing failures with:
    - Processing context and details
    - Processing error reporting
    - Processing error recovery support
    """

    def __init__(
        self,
        message: str,
        processing_context: Optional[Dict[str, Any]] = None,
        **details: Any,
    ):
        """
        Initialize processing error.

        Args:
            message: Processing error message
            processing_context: Processing context dictionary
            **details: Additional processing details
        """
        super().__init__(
            message, context=processing_context, error_code="SEM002", **details
        )
        self.processing_context = processing_context or {}
        self.stage = details.get("stage")
        self.input_data = details.get("input_data")
        self.output_data = details.get("output_data")


class ConfigurationError(SemanticaError):
    """
    Exception raised for configuration errors.

    Handles configuration validation failures with:
    - Configuration context and details
    - Configuration error reporting
    - Configuration error recovery support
    """

    def __init__(
        self,
        message: str,
        config_context: Optional[Dict[str, Any]] = None,
        **details: Any,
    ):
        """
        Initialize configuration error.

        Args:
            message: Configuration error message
            config_context: Configuration context dictionary
            **details: Additional configuration details
        """
        super().__init__(
            message, context=config_context, error_code="SEM003", **details
        )
        self.config_context = config_context or {}
        self.config_key = details.get("config_key")
        self.config_value = details.get("config_value")
        self.expected_type = details.get("expected_type")


class QualityError(SemanticaError):
    """
    Exception raised for data quality errors.

    Handles data quality validation failures with:
    - Quality context and details
    - Quality error reporting
    - Quality error recovery support
    """

    def __init__(
        self,
        message: str,
        quality_context: Optional[Dict[str, Any]] = None,
        **details: Any,
    ):
        """
        Initialize quality error.

        Args:
            message: Quality error message
            quality_context: Quality context dictionary
            **details: Additional quality details
        """
        super().__init__(
            message, context=quality_context, error_code="SEM004", **details
        )
        self.quality_context = quality_context or {}
        self.quality_score = details.get("quality_score")
        self.threshold = details.get("threshold")
        self.metrics = details.get("metrics", {})


def handle_exception(
    exception: Exception, context: Optional[Dict[str, Any]] = None, **options: Any
) -> Dict[str, Any]:
    """
    Handle exception with context and options.

    Processes exception information and returns structured error data.

    Args:
        exception: Exception to handle
        context: Exception context dictionary
        **options: Additional handling options

    Returns:
        Dictionary containing exception handling results:
        - handled: Whether exception was handled
        - error_type: Type of error
        - message: Error message
        - context: Error context
        - traceback: Formatted traceback string
        - recovery: Recovery action if any
    """
    context = context or {}
    recovery_action = options.get("recovery_action", "log_and_continue")
    log_error = options.get("log_error", True)

    # Extract error information
    error_info = {
        "handled": True,
        "error_type": type(exception).__name__,
        "message": str(exception),
        "context": context,
        "traceback": None,
        "recovery": recovery_action,
    }

    # Add traceback if requested
    if options.get("include_traceback", True):
        error_info["traceback"] = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )

    # Add exception-specific details
    if isinstance(exception, SemanticaError):
        error_info["error_code"] = exception.error_code
        error_info["details"] = exception.details
        if hasattr(exception, "context"):
            error_info["context"].update(exception.context)

    # Log error if requested
    if log_error:
        # Import here to avoid circular dependency
        try:
            from .logging import log_error as log_err

            log_err(exception, context=context, **options)
        except (ImportError, OSError):
            # Fallback to print if logging not available
            print(f"Error: {error_info}")

    return error_info


def format_exception(exception: Exception, **options: Any) -> str:
    """
    Format exception for display and logging.

    Formats exception message with context and debugging information.

    Args:
        exception: Exception to format
        **options: Additional formatting options:
            - include_traceback: Include full traceback (default: False)
            - include_context: Include context information (default: True)
            - max_length: Maximum length of formatted string (default: None)

    Returns:
        Formatted exception string
    """
    parts = []

    # Add error type and message
    error_type = type(exception).__name__
    error_message = str(exception)
    parts.append(f"{error_type}: {error_message}")

    # Add exception-specific details
    if isinstance(exception, SemanticaError):
        if exception.error_code:
            parts.append(f"Error Code: {exception.error_code}")

        if options.get("include_context", True) and exception.context:
            context_str = ", ".join(f"{k}={v}" for k, v in exception.context.items())
            parts.append(f"Context: {context_str}")

        if exception.details:
            details_str = ", ".join(
                f"{k}={v}" for k, v in exception.details.items() if k != "error_code"
            )
            if details_str:
                parts.append(f"Details: {details_str}")

    # Add traceback if requested
    if options.get("include_traceback", False):
        tb_str = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        parts.append(f"\nTraceback:\n{tb_str}")

    formatted = "\n".join(parts)

    # Truncate if max_length specified
    max_length = options.get("max_length")
    if max_length and len(formatted) > max_length:
        formatted = formatted[:max_length] + "..."

    return formatted
