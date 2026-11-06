"""
Logging Utilities Module

This module provides comprehensive logging utilities for the Semantica framework,
including structured logging, log rotation, performance metrics, error logging,
and data quality tracking with configurable output destinations and formats.

Key Features:
    - Structured logging with configurable levels and formats
    - Console and file output with rotation support
    - Performance logging with execution time and metrics
    - Error logging with context and traceback support
    - Data quality metrics logging and threshold alerts
    - Execution time decorator for automatic function timing

Main Functions:
    - setup_logging: Setup logging configuration for framework
    - get_logger: Get logger instance for specified name
    - log_performance: Log performance metrics for function execution
    - log_error: Log error with context and details
    - log_data_quality: Log data quality metrics and statistics
    - log_execution_time: Decorator to log function execution time

Example Usage:
    >>> from semantica.utils import setup_logging, get_logger
    >>> logger = setup_logging(level="INFO", file="app.log")
    >>> module_logger = get_logger(__name__)
    >>> module_logger.info("Processing started")
    >>> 
    >>> from semantica.utils import log_performance, log_error
    >>> log_performance("process_data", 2.5, memory_usage=1024*1024*100)
    >>> try:
    ...     process_data()
    ... except Exception as e:
    ...     log_error(e, context={"stage": "processing"}, include_traceback=True)
    >>> 
    >>> from semantica.utils import log_execution_time
    >>> @log_execution_time
    ... def my_function():
    ...     # Function implementation
    ...     pass

Author: Semantica Contributors
License: MIT
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .constants import DEFAULT_CONFIG


def setup_logging(config: Optional[Dict[str, Any]] = None, **kwargs) -> logging.Logger:
    """
    Setup logging configuration for Semantica framework.

    Configures logging levels, formats, and output destinations.
    Supports file rotation and console output.

    Args:
        config: Logging configuration dictionary. If None, uses DEFAULT_CONFIG.
        **kwargs: Additional logging options:
            - level: Logging level (default: from config or INFO)
            - format: Log format string
            - file: Log file path
            - console: Enable console output to stderr (default: True)
            - rotation: Enable file rotation (default: True)
            - max_bytes: Maximum file size for rotation
            - backup_count: Number of backup files to keep

    Returns:
        Configured root logger instance
    """
    # Merge config with defaults
    if config is None:
        config = DEFAULT_CONFIG.get("logging", {})

    config = {**config, **kwargs}

    # Get configuration values
    level = config.get("level", "INFO")
    format_str = config.get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_file = config.get("file", "semantica.log")
    console_enabled = config.get("console", True)
    rotation_enabled = config.get("rotation", True)
    max_bytes = config.get("max_bytes", 10485760)  # 10MB
    backup_count = config.get("backup_count", 5)

    # Convert level string to logging level
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger("semantica")
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(format_str)

    # Console handler
    if console_enabled:
        # stderr, so a command's own output on stdout (e.g. `--json`) stays clean.
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if rotation_enabled:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
        else:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")

        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False

    return root_logger


def get_logger(
    name: str, level: Optional[Union[str, int]] = None, **options: Any
) -> logging.Logger:
    """
    Get logger instance for specified name.

    Creates or retrieves a logger with the specified name.
    If level is provided, sets the logger level.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (string or logging constant)
        **options: Additional logger options:
            - propagate: Whether to propagate to parent logger (default: True)
            - format: Custom format string

    Returns:
        Logger instance
    """
    logger = logging.getLogger(f"semantica.{name}")

    # Set level if provided
    if level is not None:
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(level)

    # Configure propagation
    if "propagate" in options:
        logger.propagate = options["propagate"]

    # Add custom handler if format specified
    if "format" in options:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(options["format"]))
        logger.addHandler(handler)

    return logger


def log_performance(func_name: str, execution_time: float, **metrics: Any) -> None:
    """
    Log performance metrics for function execution.

    Logs function execution time and additional performance metrics.
    Tracks performance trends and can trigger alerts.

    Args:
        func_name: Name of function being logged
        execution_time: Function execution time in seconds
        **metrics: Additional performance metrics:
            - memory_usage: Memory usage in bytes
            - input_size: Size of input data
            - output_size: Size of output data
            - cache_hit: Whether cache was hit
            - level: Logging level (default: INFO)
    """
    logger = get_logger("performance")
    level = metrics.pop("level", logging.INFO)

    # Build log message
    message_parts = [f"Function: {func_name}", f"Execution Time: {execution_time:.4f}s"]

    if "memory_usage" in metrics:
        memory_mb = metrics["memory_usage"] / (1024 * 1024)
        message_parts.append(f"Memory: {memory_mb:.2f}MB")

    if "input_size" in metrics:
        message_parts.append(f"Input Size: {metrics['input_size']}")

    if "output_size" in metrics:
        message_parts.append(f"Output Size: {metrics['output_size']}")

    if "cache_hit" in metrics:
        message_parts.append(f"Cache: {'HIT' if metrics['cache_hit'] else 'MISS'}")

    message = " | ".join(message_parts)

    # Log additional metrics as extra data
    extra_metrics = {
        k: v
        for k, v in metrics.items()
        if k not in ["memory_usage", "input_size", "output_size", "cache_hit", "level"]
    }

    if extra_metrics:
        logger.log(level, message, extra={"metrics": extra_metrics})
    else:
        logger.log(level, message)


def log_error(
    error: Exception, context: Optional[Dict[str, Any]] = None, **details: Any
) -> None:
    """
    Log error with context and details.

    Logs error information with context and details for debugging.
    Can handle error escalation if configured.

    Args:
        error: Error/Exception to log
        context: Error context dictionary
        **details: Additional error details:
            - level: Logging level (default: ERROR)
            - include_traceback: Include full traceback (default: True)
            - escalate: Whether to escalate error (default: False)
    """
    logger = get_logger("error")
    level = details.pop("level", logging.ERROR)
    include_traceback = details.pop("include_traceback", True)
    escalate = details.pop("escalate", False)

    # Build error message
    error_type = type(error).__name__
    error_message = str(error)
    message = f"{error_type}: {error_message}"

    # Add context information
    log_data = {
        "error_type": error_type,
        "error_message": error_message,
        "context": context or {},
        "details": details,
    }

    # Include traceback if requested
    if include_traceback and hasattr(error, "__traceback__"):
        import traceback

        log_data["traceback"] = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    # Add error code if available
    if hasattr(error, "error_code"):
        log_data["error_code"] = error.error_code

    # Log error
    logger.log(level, message, extra=log_data)

    # Handle escalation
    if escalate:
        logger.critical(f"ESCALATED: {message}", extra=log_data)


def log_data_quality(quality_metrics: Dict[str, Any], **options: Any) -> None:
    """
    Log data quality metrics and statistics.

    Logs quality metrics, tracks quality trends, and can generate alerts
    when quality thresholds are not met.

    Args:
        quality_metrics: Quality metrics dictionary:
            - score: Overall quality score
            - completeness: Completeness score
            - accuracy: Accuracy score
            - consistency: Consistency score
            - validity: Validity score
            - timeliness: Timeliness score
        **options: Additional logging options:
            - level: Logging level (default: INFO)
            - threshold: Quality threshold (default: 0.7)
            - alert_on_threshold: Alert if below threshold (default: True)
            - generate_report: Generate quality report (default: False)
    """
    logger = get_logger("quality")
    level = options.get("level", logging.INFO)
    threshold = options.get("threshold", 0.7)
    alert_on_threshold = options.get("alert_on_threshold", True)
    generate_report = options.get("generate_report", False)

    # Extract quality scores
    overall_score = quality_metrics.get("score", quality_metrics.get("overall_score"))

    # Build log message
    message_parts = [f"Quality Score: {overall_score:.3f}"]

    # Add individual metrics
    metric_names = ["completeness", "accuracy", "consistency", "validity", "timeliness"]
    for metric in metric_names:
        if metric in quality_metrics:
            message_parts.append(
                f"{metric.capitalize()}: {quality_metrics[metric]:.3f}"
            )

    message = " | ".join(message_parts)

    # Log quality metrics
    logger.log(level, message, extra={"quality_metrics": quality_metrics})

    # Alert if below threshold
    if alert_on_threshold and overall_score is not None and overall_score < threshold:
        logger.warning(
            f"Quality score {overall_score:.3f} below threshold {threshold}",
            extra={"quality_metrics": quality_metrics, "threshold": threshold},
        )

    # Generate report if requested
    if generate_report:
        report = {
            "timestamp": datetime.now().isoformat(),
            "quality_metrics": quality_metrics,
            "threshold": threshold,
            "status": "PASS"
            if (overall_score and overall_score >= threshold)
            else "FAIL",
        }
        logger.info("Quality Report", extra={"report": report})


# Performance decorator for easy function timing
def log_execution_time(func):
    """
    Decorator to log function execution time.

    Usage:
        @log_execution_time
        def my_function():
            ...
    """
    import functools
    import time

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger("performance")
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            log_performance(func.__name__, execution_time, **{"success": True})

            return result
        except Exception as e:
            execution_time = time.time() - start_time

            log_performance(
                func.__name__, execution_time, **{"success": False, "error": str(e)}
            )

            raise

    return wrapper
