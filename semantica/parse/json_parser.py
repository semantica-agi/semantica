"""
JSON Document Parser Module

This module handles JSON file parsing for structured data extraction, supporting
nested structures, arrays, and various data types with validation and flattening.

Key Features:
    - JSON file and string parsing
    - Nested structure handling
    - Data type validation
    - Structure flattening
    - JSON path extraction
    - Large file processing

Main Classes:
    - JSONParser: JSON document parser
    - JSONData: Dataclass for JSON data representation

Example Usage:
    >>> from semantica.parse import JSONParser
    >>> parser = JSONParser()
    >>> data = parser.parse("data.json")
    >>> flattened = parser.parse("data.json", flatten=True)
    >>> values = parser.extract_values("data.json", "users")

Author: Semantica Contributors
License: MIT
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


@dataclass
class JSONData:
    """JSON data representation."""

    data: Any
    type: str  # object, array, string, number, boolean, null
    metadata: Dict[str, Any]


class JSONParser:
    """JSON document parser."""

    def __init__(self, **config):
        """
        Initialize JSON parser.

        Args:
            **config: Parser configuration
        """
        self.logger = get_logger("json_parser")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

    def parse(self, file_path: Union[str, Path], **options) -> JSONData:
        """
        Parse JSON file.

        Args:
            file_path: Path to JSON file or JSON string
            **options: Parsing options:
                - encoding: File encoding (default: 'utf-8')
                - flatten: Whether to flatten nested structures (default: False)
                - extract_paths: Whether to extract JSON paths (default: False)

        Returns:
            JSONData: Parsed JSON data
        """
        # Track JSON parsing
        file_path_obj = None
        if isinstance(file_path, Path) or (
            isinstance(file_path, str) and Path(file_path).exists()
        ):
            file_path_obj = Path(file_path)

        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path_obj) if file_path_obj else None,
            module="parse",
            submodule="JSONParser",
            message=f"JSON: {file_path_obj.name if file_path_obj else 'content'}",
        )

        try:
            encoding = options.get("encoding", "utf-8")

            # Check if input is a file path or JSON string
            if file_path_obj:
                if not file_path_obj.exists():
                    raise ValidationError(f"JSON file not found: {file_path_obj}")

                try:
                    with open(file_path_obj, "r", encoding=encoding) as f:
                        data = json.load(f)
                    source = str(file_path_obj)
                except json.JSONDecodeError as e:
                    raise ValidationError(f"Invalid JSON file: {e}")
            else:
                # Assume it's a JSON string
                try:
                    data = json.loads(file_path)
                    source = "string"
                except json.JSONDecodeError as e:
                    raise ValidationError(f"Invalid JSON string: {e}")

            # Determine data type
            data_type = self._determine_type(data)

            # Flatten if requested
            if options.get("flatten", False):
                data = self._flatten(data)

            # Extract paths if requested
            paths = None
            if options.get("extract_paths", False):
                paths = self._extract_paths(data)

            metadata = {"source": source, "type": data_type, "paths": paths}

            self.progress_tracker.stop_tracking(
                tracking_id, status="completed", message=f"Parsed JSON ({data_type})"
            )
            return JSONData(data=data, type=data_type, metadata=metadata)

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def parse_to_dict(self, file_path: Union[str, Path], **options) -> Dict[str, Any]:
        """
        Parse JSON to dictionary.

        Args:
            file_path: Path to JSON file or JSON string
            **options: Parsing options

        Returns:
            dict: Parsed JSON as dictionary
        """
        json_data = self.parse(file_path, **options)

        if json_data.type == "object":
            return json_data.data
        elif (
            json_data.type == "array"
            and len(json_data.data) > 0
            and isinstance(json_data.data[0], dict)
        ):
            # Return first element if array of objects
            return (
                json_data.data[0]
                if len(json_data.data) == 1
                else {"items": json_data.data}
            )
        else:
            return {"data": json_data.data}

    def parse_to_list(self, file_path: Union[str, Path], **options) -> List[Any]:
        """
        Parse JSON to list.

        Args:
            file_path: Path to JSON file or JSON string
            **options: Parsing options

        Returns:
            list: Parsed JSON as list
        """
        json_data = self.parse(file_path, **options)

        if json_data.type == "array":
            return json_data.data
        elif json_data.type == "object":
            return [json_data.data]
        else:
            return [json_data.data]

    def extract_values(
        self, file_path: Union[str, Path], key_path: str, **options
    ) -> List[Any]:
        """
        Extract values from JSON using key path.

        Args:
            file_path: Path to JSON file or JSON string
            key_path: Dot-separated key path (e.g., "user.name")
            **options: Parsing options

        Returns:
            list: Extracted values
        """
        json_data = self.parse(file_path, **options)
        return self._extract_by_path(json_data.data, key_path)

    def _determine_type(self, data: Any) -> str:
        """Determine JSON data type."""
        if isinstance(data, dict):
            return "object"
        elif isinstance(data, list):
            return "array"
        elif isinstance(data, str):
            return "string"
        elif isinstance(data, (int, float)):
            return "number"
        elif isinstance(data, bool):
            return "boolean"
        elif data is None:
            return "null"
        else:
            return "unknown"

    def _flatten(
        self, data: Any, parent_key: str = "", separator: str = "."
    ) -> Dict[str, Any]:
        """Flatten nested JSON structure."""
        items = []

        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{parent_key}{separator}{key}" if parent_key else key
                if isinstance(value, (dict, list)):
                    items.extend(self._flatten(value, new_key, separator).items())
                else:
                    items.append((new_key, value))
        elif isinstance(data, list):
            for idx, value in enumerate(data):
                new_key = f"{parent_key}{separator}{idx}" if parent_key else str(idx)
                if isinstance(value, (dict, list)):
                    items.extend(self._flatten(value, new_key, separator).items())
                else:
                    items.append((new_key, value))
        else:
            items.append((parent_key, data))

        return dict(items)

    def _extract_paths(self, data: Any, prefix: str = "") -> List[str]:
        """Extract all JSON paths."""
        paths = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{prefix}.{key}" if prefix else key
                paths.append(current_path)
                if isinstance(value, (dict, list)):
                    paths.extend(self._extract_paths(value, current_path))
        elif isinstance(data, list):
            for idx, value in enumerate(data):
                current_path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
                paths.append(current_path)
                if isinstance(value, (dict, list)):
                    paths.extend(self._extract_paths(value, current_path))

        return paths

    def _extract_by_path(self, data: Any, key_path: str) -> List[Any]:
        """Extract values by key path."""
        keys = key_path.split(".")
        results = []

        def extract_recursive(
            obj: Any, remaining_keys: List[str], current_path: List[str]
        ):
            if not remaining_keys:
                results.append(obj)
                return

            key = remaining_keys[0]

            if isinstance(obj, dict):
                if key in obj:
                    extract_recursive(
                        obj[key], remaining_keys[1:], current_path + [key]
                    )
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    extract_recursive(item, remaining_keys, current_path + [str(idx)])

        extract_recursive(data, keys, [])
        return results
