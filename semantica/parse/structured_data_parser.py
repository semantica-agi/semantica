"""
Structured Data Parsing Module

This module handles parsing of structured data formats including JSON, CSV, XML,
and YAML, providing validation, type conversion, and data transformation.

Key Features:
    - JSON data parsing and validation
    - CSV data processing
    - XML data extraction
    - YAML configuration parsing
    - Data type conversion and validation
    - Nested structure handling
    - Batch processing support

Main Classes:
    - StructuredDataParser: Main structured data parser

Example Usage:
    >>> from semantica.parse import StructuredDataParser
    >>> parser = StructuredDataParser()
    >>> json_data = parser.parse_data("data.json")
    >>> csv_data = parser.parse_data("data.csv")
    >>> xml_data = parser.parse_data("data.xml", data_format="xml")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .csv_parser import CSVParser
from .json_parser import JSONParser
from .xml_parser import XMLParser


class StructuredDataParser:
    """
    Structured data format parsing handler.

    • Parses JSON, CSV, XML, YAML formats
    • Validates data structure and types
    • Converts data to standard formats
    • Handles nested and complex structures
    • Processes large datasets efficiently
    • Supports various encoding formats
    """

    def __init__(self, config=None, **kwargs):
        """Initialize structured data parser."""
        self.logger = get_logger("structured_data_parser")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()

        # Initialize parsers
        self.json_parser = JSONParser(**self.config.get("json", {}))
        self.csv_parser = CSVParser(**self.config.get("csv", {}))
        self.xml_parser = XMLParser(**self.config.get("xml", {}))

    def parse_data(
        self, data: Union[str, Path], data_format: Optional[str] = None, **options
    ) -> Dict[str, Any]:
        """
        Parse structured data of any supported format.

        Args:
            data: Data content or file path
            data_format: Data format (auto-detected if None)
            **options: Parsing options

        Returns:
            dict: Parsed data
        """
        # Track structured data parsing
        file_path = None
        if isinstance(data, Path) or (isinstance(data, str) and Path(data).exists()):
            file_path = Path(data)

        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path) if file_path else None,
            module="parse",
            submodule="StructuredDataParser",
            message=f"Structured data: {file_path.name if file_path else 'content'}",
        )

        try:
            # Detect format if not specified
            if data_format is None:
                data_format = self._detect_format(data)

            self.progress_tracker.update_tracking(
                tracking_id, message=f"Parsing {data_format}..."
            )

            # Route to appropriate parser
            if data_format == "json":
                result = self.json_parser.parse(data, **options).__dict__
            elif data_format == "csv":
                result = self.csv_parser.parse(data, **options).__dict__
            elif data_format == "xml":
                result = self.xml_parser.parse(data, **options).__dict__
            elif data_format == "yaml":
                result = self._parse_yaml(data, **options)
            else:
                raise ValidationError(f"Unsupported data format: {data_format}")

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Parsed {data_format} successfully",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def validate_data(
        self, data: Any, schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate structured data against schema.

        Args:
            data: Data to validate
            schema: Validation schema

        Returns:
            dict: Validation result
        """
        result = {"valid": True, "errors": []}

        if schema is None:
            result["valid"] = True
            result["message"] = "No schema provided, skipping validation"
            return result

        # Basic schema validation
        if isinstance(data, dict):
            # Check required fields
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in data:
                    result["valid"] = False
                    result["errors"].append(f"Missing required field: {field}")

            # Check field types
            properties = schema.get("properties", {})
            for field, value in data.items():
                if field in properties:
                    expected_type = properties[field].get("type")
                    actual_type = type(value).__name__

                    type_mapping = {
                        "string": "str",
                        "number": ("int", "float"),
                        "integer": "int",
                        "boolean": "bool",
                        "array": "list",
                        "object": "dict",
                    }

                    expected_types = type_mapping.get(expected_type, [expected_type])
                    if isinstance(expected_types, tuple):
                        if actual_type not in expected_types:
                            result["valid"] = False
                            result["errors"].append(
                                f"Field {field}: expected {expected_type}, got {actual_type}"
                            )
                    elif actual_type != expected_types:
                        result["valid"] = False
                        result["errors"].append(
                            f"Field {field}: expected {expected_type}, got {actual_type}"
                        )

        return result

    def convert_data(self, data: Any, from_format: str, to_format: str) -> Any:
        """
        Convert data between different formats.

        Args:
            data: Input data
            from_format: Source format
            to_format: Target format

        Returns:
            Converted data
        """
        # Parse from source format
        if isinstance(data, (str, Path)):
            parsed = self.parse_data(data, data_format=from_format)
            if isinstance(parsed, dict) and "data" in parsed:
                parsed = parsed["data"]
        else:
            parsed = data

        # Convert to target format
        if to_format == "json":
            import json

            return json.dumps(parsed, indent=2)
        elif to_format == "csv":
            return self._convert_to_csv(parsed)
        elif to_format == "xml":
            return self._convert_to_xml(parsed)
        elif to_format == "yaml":
            return yaml.dump(parsed, default_flow_style=False)
        else:
            raise ValidationError(f"Unsupported target format: {to_format}")

    def extract_schema(self, data: Any) -> Dict[str, Any]:
        """
        Extract schema from structured data.

        Args:
            data: Structured data

        Returns:
            dict: Extracted schema
        """
        schema = {
            "type": "object"
            if isinstance(data, dict)
            else "array"
            if isinstance(data, list)
            else type(data).__name__,
            "properties": {},
        }

        if isinstance(data, dict):
            for key, value in data.items():
                schema["properties"][key] = self._infer_type(value)
        elif isinstance(data, list) and len(data) > 0:
            schema["items"] = self._infer_type(data[0])

        return schema

    def _detect_format(self, data: Union[str, Path]) -> str:
        """Detect data format from content or extension."""
        # Check if it's a file path
        if isinstance(data, Path) or (isinstance(data, str) and Path(data).exists()):
            file_path = Path(data)
            suffix = file_path.suffix.lower()
            format_map = {
                ".json": "json",
                ".csv": "csv",
                ".xml": "xml",
                ".yaml": "yaml",
                ".yml": "yaml",
            }
            if suffix in format_map:
                return format_map[suffix]

        # Check content if string
        if isinstance(data, str):
            data_str = data.strip()
            if data_str.startswith("{") or data_str.startswith("["):
                return "json"
            elif data_str.startswith("<"):
                return "xml"
            elif "," in data_str and "\n" in data_str:
                return "csv"

        return "unknown"

    def _parse_yaml(self, data: Union[str, Path], **options) -> Dict[str, Any]:
        """Parse YAML data."""
        if isinstance(data, Path) or (isinstance(data, str) and Path(data).exists()):
            file_path = Path(data)
            with open(file_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
        else:
            yaml_data = yaml.safe_load(data)

        return {
            "data": yaml_data,
            "type": type(yaml_data).__name__,
            "metadata": {"format": "yaml"},
        }

    def _convert_to_csv(self, data: Any) -> str:
        """Convert data to CSV format."""
        import csv
        import io

        if isinstance(data, dict):
            # Convert dict to CSV (single row)
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
            return output.getvalue()
        elif isinstance(data, list):
            if not data:
                return ""

            output = io.StringIO()
            if isinstance(data[0], dict):
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            else:
                writer = csv.writer(output)
                writer.writerows(data)
            return output.getvalue()
        else:
            return str(data)

    def _convert_to_xml(self, data: Any, root_tag: str = "root") -> str:
        """Convert data to XML format."""
        import xml.dom.minidom
        from xml.etree.ElementTree import Element, tostring

        def dict_to_xml(d: Dict[str, Any], parent: Element):
            for key, value in d.items():
                elem = Element(key)
                if isinstance(value, dict):
                    dict_to_xml(value, elem)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            dict_to_xml(item, elem)
                        else:
                            child = Element("item")
                            child.text = str(item)
                            elem.append(child)
                else:
                    elem.text = str(value)
                parent.append(elem)

        root = Element(root_tag)
        if isinstance(data, dict):
            dict_to_xml(data, root)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    dict_to_xml(item, root)
                else:
                    elem = Element("item")
                    elem.text = str(item)
                    root.append(elem)
        else:
            root.text = str(data)

        # Pretty print
        rough_string = tostring(root, encoding="unicode")
        reparsed = xml.dom.minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def _infer_type(self, value: Any) -> Dict[str, Any]:
        """Infer JSON Schema type from Python value."""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        python_type = type(value)
        json_type = type_mapping.get(python_type, "string")

        result = {"type": json_type}

        if json_type == "array" and isinstance(value, list) and len(value) > 0:
            result["items"] = self._infer_type(value[0])
        elif json_type == "object" and isinstance(value, dict):
            result["properties"] = {k: self._infer_type(v) for k, v in value.items()}

        return result
