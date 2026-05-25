"""
Apache Parquet Exporter Module

This module provides comprehensive Apache Parquet export capabilities for the
Semantica framework, enabling efficient columnar data export for entities,
relationships, and knowledge graphs optimized for analytics and data warehousing.

Key Features:
    - Parquet file export (.parquet)
    - Explicit schema definition (no inference)
    - Entity and relationship export with metadata
    - Knowledge graph export to multiple Parquet files
    - Compatible with pandas, Spark, Snowflake, BigQuery, and Databricks
    - Configurable compression (snappy, gzip, brotli, zstd, lz4)
    - Batch export processing
    - Structured metadata handling

Example Usage:
    >>> from semantica.export import ParquetExporter
    >>> exporter = ParquetExporter(compression="snappy")
    >>> exporter.export_entities(entities, "entities.parquet")
    >>> exporter.export_knowledge_graph(kg, "kg_base")

Author: Semantica Contributors
License: MIT
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    import pyarrow as pa  # noqa: F401

try:
    import pyarrow as pa  # noqa: F811
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True

    # Explicit Parquet Schemas (no inference)
    ENTITY_SCHEMA = pa.schema(
        [
            pa.field("id", pa.string(), nullable=False),
            pa.field("text", pa.string(), nullable=True),
            pa.field("type", pa.string(), nullable=True),
            pa.field("confidence", pa.float64(), nullable=True),
            pa.field("start", pa.int64(), nullable=True),
            pa.field("end", pa.int64(), nullable=True),
            pa.field(
                "metadata",
                pa.struct(
                    [
                        pa.field("keys", pa.list_(pa.string())),
                        pa.field("values", pa.list_(pa.string())),
                    ]
                ),
                nullable=True,
            ),
        ]
    )

    RELATIONSHIP_SCHEMA = pa.schema(
        [
            pa.field("id", pa.string(), nullable=False),
            pa.field("source_id", pa.string(), nullable=False),
            pa.field("target_id", pa.string(), nullable=False),
            pa.field("type", pa.string(), nullable=True),
            pa.field("confidence", pa.float64(), nullable=True),
            pa.field(
                "metadata",
                pa.struct(
                    [
                        pa.field("keys", pa.list_(pa.string())),
                        pa.field("values", pa.list_(pa.string())),
                    ]
                ),
                nullable=True,
            ),
        ]
    )
except ImportError:
    PARQUET_AVAILABLE = False
    ENTITY_SCHEMA = None
    RELATIONSHIP_SCHEMA = None

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.helpers import ensure_directory
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class ParquetExporter:
    """
    Apache Parquet exporter for knowledge graphs and structured data.

    This class provides comprehensive Parquet export functionality for entities,
    relationships, and knowledge graphs. Uses explicit schemas for type safety
    and compatibility with analytics platforms like pandas, Spark, Snowflake,
    BigQuery, and Databricks.

    Features:
        - Entity and relationship export
        - Knowledge graph export to multiple Parquet files
        - Explicit schema definition (no inference)
        - Metadata serialization as Parquet struct fields
        - Configurable compression (snappy, gzip, brotli, zstd, lz4)
        - Compatible with major analytics platforms
        - Progress tracking and error handling

    Example Usage:
        >>> exporter = ParquetExporter(compression="snappy")
        >>> exporter.export_entities(entities, "entities.parquet")
        >>> exporter.export_knowledge_graph(kg, "output_base")
    """

    def __init__(
        self,
        compression: str = "snappy",
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize Parquet exporter.

        Sets up the exporter with specified Parquet formatting options.

        Args:
            compression: Compression codec (default: "snappy")
                - "snappy": Snappy compression (fast, good compression)
                - "gzip": GZIP compression (slower, better compression)
                - "brotli": Brotli compression (slow, best compression)
                - "zstd": Zstandard compression (balanced)
                - "lz4": LZ4 compression (very fast, moderate compression)
                - "none" or None: No compression
            config: Optional configuration dictionary (merged with kwargs)
            **kwargs: Additional configuration options

        Raises:
            ImportError: If pyarrow is not installed
        """
        if not PARQUET_AVAILABLE:
            raise ImportError(
                "pyarrow is not installed. Please install it with: "
                "pip install pyarrow"
            )

        self.logger = get_logger("parquet_exporter")
        self.config = config or {}
        self.config.update(kwargs)

        # Parquet configuration
        self.compression = compression if compression != "none" else None

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug(f"Parquet exporter initialized: compression={compression}")

    def export(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        file_path: Union[str, Path],
        schema: Optional["pa.Schema"] = None,
        **options,
    ) -> None:
        """
        Export data to Parquet file(s).

        This method handles both single Parquet file export (from list) and multiple
        Parquet file export (from dictionary with multiple keys).

        Args:
            data: Data to export:
                - List of dicts: Exports to single Parquet file
                - Dict with list values: Exports each key as separate Parquet file
            file_path: Output file path (base path for dict exports)
            schema: Parquet schema to use (default: auto-select based on data)
            **options: Additional options

        Raises:
            ValidationError: If data type is unsupported

        Example:
            >>> # Single Parquet file
            >>> exporter.export([{"id": "1", "name": "A"}], "data.parquet")
            >>> # Multiple Parquet files
            >>> exporter.export(
            ...     {"entities": [...], "relationships": [...]},
            ...     "output_base"
            ... )
        """
        # Track Parquet export
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="export",
            submodule="ParquetExporter",
            message=f"Exporting data to Parquet: {file_path}",
        )

        try:
            file_path = Path(file_path)
            ensure_directory(file_path.parent)

            self.logger.debug(f"Exporting data to Parquet: {file_path}")

            # Handle different data structures
            if isinstance(data, dict):
                # Export each key as separate Parquet file
                exported_files = []
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Exporting {len(data)} data groups..."
                )
                for key, value in data.items():
                    if isinstance(value, list):
                        output_path = (
                            file_path.parent / f"{file_path.stem}_{key}.parquet"
                        )

                        # Use dedicated export methods for entities and relationships
                        # to ensure proper normalization
                        if key == "entities" and schema is None:
                            self.export_entities(value, output_path, **options)
                        elif key == "relationships" and schema is None:
                            self.export_relationships(value, output_path, **options)
                        else:
                            # For other keys, write directly with provided schema
                            self._write_parquet(
                                value, output_path, schema=schema, **options
                            )

                        exported_files.append(output_path)
                    else:
                        self.logger.warning(
                            f"Skipping key '{key}': value is not a list "
                            f"(type: {type(value)})"
                        )

                self.logger.info(
                    f"Exported {len(exported_files)} Parquet file(s) from dictionary: "
                    f"{', '.join(str(f) for f in exported_files)}"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Exported {len(exported_files)} Parquet files",
                )
            elif isinstance(data, list):
                # Single Parquet file - auto-detect if entities or relationships
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Exporting {len(data)} records..."
                )

                # If no schema provided, try to auto-detect from data structure
                if schema is None:
                    if not data:
                        raise ValidationError(
                            "Cannot export empty list without explicit schema. "
                            "Provide a schema or use "
                            "export_entities/export_relationships."
                        )
                    sample = data[0]
                    has_source = any(
                        k in sample for k in ["source_id", "source", "from_id", "from"]
                    )
                    has_target = any(
                        k in sample for k in ["target_id", "target", "to_id", "to"]
                    )

                    if has_source and has_target:
                        # Use dedicated method for relationship normalization
                        self.export_relationships(data, file_path, **options)
                    else:
                        # Use dedicated method for entity normalization
                        self.export_entities(data, file_path, **options)
                else:
                    # Schema provided - write directly
                    self._write_parquet(data, file_path, schema=schema, **options)

                self.logger.info(f"Exported Parquet to: {file_path}")
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Exported Parquet to: {file_path}",
                )
            else:
                raise ValidationError(
                    f"Unsupported data type: {type(data)}. "
                    "Expected list of dicts or dict with list values."
                )

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def export_entities(
        self, entities: List[Dict[str, Any]], file_path: Union[str, Path], **options
    ) -> None:
        """
        Export entities to Parquet file.

        This method normalizes entity data to a consistent format and exports
        to Parquet using the explicit ENTITY_SCHEMA. Handles various entity field
        name variations and serializes metadata as Parquet structs.

        Normalized Fields:
            - id: Entity identifier (required)
            - text: Entity text/label/name
            - type: Entity type
            - confidence: Confidence score
            - start: Start offset/position
            - end: End offset/position
            - metadata: Metadata as struct (keys and values lists)

        Args:
            entities: List of entity dictionaries with various field names
            file_path: Output Parquet file path
            **options: Additional options passed to _write_parquet()

        Raises:
            ValidationError: If entities list is empty

        Example:
            >>> entities = [
            ...     {"id": "e1", "text": "Entity 1", "type": "PERSON"},
            ...     {"id": "e2", "label": "Entity 2", "entity_type": "ORG"}
            ... ]
            >>> exporter.export_entities(entities, "entities.parquet")
        """
        if not entities:
            raise ValidationError("No entities to export. Entities list is empty.")

        self.logger.debug(f"Exporting {len(entities)} entity(ies) to Parquet")

        # Normalize entity data to consistent format
        normalized_entities = []
        for i, entity in enumerate(entities):
            if not isinstance(entity, dict):
                self.logger.warning(f"Entity {i} is not a dictionary, skipping")
                continue

            # Extract and normalize fields
            entity_id = entity.get("id") or entity.get("entity_id")
            if not entity_id:
                self.logger.warning(f"Entity {i} missing ID, skipping")
                continue

            # Normalize confidence to float, with validation
            raw_confidence = entity.get("confidence")
            confidence_value = None
            if raw_confidence is not None:
                try:
                    confidence_value = float(raw_confidence)
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Entity {i} has non-numeric confidence {raw_confidence!r}; "
                        "setting to None"
                    )
                    confidence_value = None

            # Normalize start/end to int, with validation
            start_value = entity.get("start")
            if start_value is None:
                start_value = entity.get("start_offset")
            if start_value is not None:
                try:
                    start_value = int(start_value)
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Entity {i} has non-integer start {start_value!r}; "
                        "setting to None"
                    )
                    start_value = None

            end_value = entity.get("end")
            if end_value is None:
                end_value = entity.get("end_offset")
            if end_value is not None:
                try:
                    end_value = int(end_value)
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Entity {i} has non-integer end {end_value!r}; "
                        "setting to None"
                    )
                    end_value = None

            normalized = {
                "id": str(entity_id),
                "text": (
                    entity.get("text") or entity.get("label") or entity.get("name")
                ),
                "type": entity.get("type") or entity.get("entity_type"),
                "confidence": confidence_value,
                "start": start_value,
                "end": end_value,
            }

            # Convert metadata to struct format (keys and values lists)
            if "metadata" in entity and isinstance(entity["metadata"], dict):
                metadata_dict = entity["metadata"]
                normalized["metadata"] = {
                    "keys": list(metadata_dict.keys()),
                    "values": [
                        json.dumps(v) if not isinstance(v, str) else v
                        for v in metadata_dict.values()
                    ],
                }
            else:
                normalized["metadata"] = None

            normalized_entities.append(normalized)

        self.logger.debug(
            f"Normalized {len(normalized_entities)} entity(ies) for Parquet export"
        )

        if not normalized_entities:
            raise ValidationError(
                "No valid entities to export after normalization. "
                "All entities were skipped due to missing IDs or invalid format."
            )

        self._write_parquet(
            normalized_entities, file_path, schema=ENTITY_SCHEMA, **options
        )

    def export_relationships(
        self,
        relationships: List[Dict[str, Any]],
        file_path: Union[str, Path],
        **options,
    ) -> None:
        """
        Export relationships to Parquet file.

        This method normalizes relationship data to a consistent format and exports
        to Parquet using the explicit RELATIONSHIP_SCHEMA. Handles various relationship
        field name variations and serializes metadata as Parquet structs.

        Normalized Fields:
            - id: Relationship identifier (generated if missing)
            - source_id: Source entity ID (required)
            - target_id: Target entity ID (required)
            - type: Relationship type
            - confidence: Confidence score
            - metadata: Metadata as struct (keys and values lists)

        Args:
            relationships: List of relationship dictionaries with various field names
            file_path: Output Parquet file path
            **options: Additional options passed to _write_parquet()

        Raises:
            ValidationError: If relationships list is empty

        Example:
            >>> relationships = [
            ...     {"id": "r1", "source": "e1", "target": "e2", "type": "KNOWS"},
            ...     {"source_id": "e2", "target_id": "e3", "relationship_type": "LIKES"}
            ... ]
            >>> exporter.export_relationships(relationships, "relationships.parquet")
        """
        if not relationships:
            raise ValidationError(
                "No relationships to export. Relationships list is empty."
            )

        self.logger.debug(f"Exporting {len(relationships)} relationship(s) to Parquet")

        # Normalize relationship data to consistent format
        normalized_rels = []
        for i, rel in enumerate(relationships):
            if not isinstance(rel, dict):
                self.logger.warning(f"Relationship {i} is not a dictionary, skipping")
                continue

            # Extract source and target IDs
            source_id = (
                rel.get("source_id")
                or rel.get("source")
                or rel.get("from_id")
                or rel.get("from")
            )
            target_id = (
                rel.get("target_id")
                or rel.get("target")
                or rel.get("to_id")
                or rel.get("to")
            )

            if not source_id or not target_id:
                self.logger.warning(
                    f"Relationship {i} missing source or target ID, skipping"
                )
                continue

            # Generate ID if missing
            rel_id = rel.get("id") or rel.get("relationship_id") or f"rel_{i}"

            # Normalize confidence to float, with validation
            raw_confidence = rel.get("confidence")
            confidence_value = None
            if raw_confidence is not None:
                try:
                    confidence_value = float(raw_confidence)
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Relationship {i} has non-numeric confidence "
                        f"{raw_confidence!r}; setting to None"
                    )
                    confidence_value = None

            normalized = {
                "id": str(rel_id),
                "source_id": str(source_id),
                "target_id": str(target_id),
                "type": (
                    rel.get("type")
                    or rel.get("relationship_type")
                    or rel.get("relation_type")
                ),
                "confidence": confidence_value,
            }

            # Convert metadata to struct format (keys and values lists)
            if "metadata" in rel and isinstance(rel["metadata"], dict):
                metadata_dict = rel["metadata"]
                normalized["metadata"] = {
                    "keys": list(metadata_dict.keys()),
                    "values": [
                        json.dumps(v) if not isinstance(v, str) else v
                        for v in metadata_dict.values()
                    ],
                }
            else:
                normalized["metadata"] = None

            normalized_rels.append(normalized)

        self.logger.debug(
            f"Normalized {len(normalized_rels)} relationship(s) for Parquet export"
        )

        if not normalized_rels:
            raise ValidationError(
                "No valid relationships to export after normalization. "
                "Ensure each relationship is a dictionary and includes valid "
                "'source'/'source_id' and 'target'/'target_id' fields."
            )

        self._write_parquet(
            normalized_rels, file_path, schema=RELATIONSHIP_SCHEMA, **options
        )

    def export_knowledge_graph(
        self, kg: Dict[str, Any], base_path: Union[str, Path], **options
    ) -> None:
        """
        Export knowledge graph to multiple Parquet files.

        This method exports a knowledge graph to separate Parquet files for
        entities and relationships. Files are named using the base_path with
        suffixes: _entities.parquet and _relationships.parquet.

        Args:
            kg: Knowledge graph dictionary with 'entities' and 'relationships' keys
            base_path: Base path for output files (without extension)
            **options: Additional options passed to export methods

        Raises:
            ValidationError: If knowledge graph is missing required keys

        Example:
            >>> kg = {
            ...     "entities": [...],
            ...     "relationships": [...]
            ... }
            >>> exporter.export_knowledge_graph(kg, "output/kg_base")
            # Creates: output/kg_base_entities.parquet and
            # output/kg_base_relationships.parquet
        """
        if not isinstance(kg, dict):
            raise ValidationError(
                f"Knowledge graph must be a dictionary, got {type(kg)}"
            )

        if "entities" not in kg and "relationships" not in kg:
            raise ValidationError(
                "Knowledge graph must contain 'entities' or 'relationships' key"
            )

        base_path = Path(base_path)
        ensure_directory(base_path.parent)

        self.logger.debug(f"Exporting knowledge graph to Parquet: {base_path}")

        # Track KG export
        tracking_id = self.progress_tracker.start_tracking(
            file=str(base_path),
            module="export",
            submodule="ParquetExporter",
            message=f"Exporting knowledge graph to Parquet: {base_path}",
        )

        try:
            exported_files = []

            # Export entities
            if "entities" in kg and kg["entities"]:
                entities_path = base_path.parent / f"{base_path.stem}_entities.parquet"
                self.export_entities(kg["entities"], entities_path, **options)
                exported_files.append(entities_path)
                self.logger.info(f"Exported entities to: {entities_path}")

            # Export relationships
            if "relationships" in kg and kg["relationships"]:
                rels_path = base_path.parent / f"{base_path.stem}_relationships.parquet"
                self.export_relationships(kg["relationships"], rels_path, **options)
                exported_files.append(rels_path)
                self.logger.info(f"Exported relationships to: {rels_path}")

            self.logger.info(
                f"Exported knowledge graph to {len(exported_files)} Parquet file(s)"
            )
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Exported {len(exported_files)} Parquet files",
            )

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _write_parquet(
        self,
        data: List[Dict[str, Any]],
        file_path: Union[str, Path],
        schema: Optional["pa.Schema"] = None,
        **options,
    ) -> None:
        """
        Write data to Parquet file.

        Internal method that handles the actual Parquet file writing using pyarrow.

        Args:
            data: List of dictionaries to write
            file_path: Output Parquet file path
            schema: Parquet schema to use (required for type safety)
            **options: Additional parquet write options

        Raises:
            ProcessingError: If Parquet writing fails
            ValidationError: If schema is not provided
        """
        if not schema:
            raise ValidationError("Schema is required for Parquet export")

        # Ensure file_path is a Path object
        file_path = Path(file_path)

        if not data:
            self.logger.warning(f"No data to write to {file_path}")
            # Write empty Parquet file with schema
            empty_table = pa.table({field.name: [] for field in schema}, schema=schema)
            pq.write_table(
                empty_table, str(file_path), compression=self.compression, **options
            )
            return

        try:
            # Create PyArrow table from data using explicit schema
            table = pa.Table.from_pylist(data, schema=schema)

            # Write to Parquet file
            pq.write_table(
                table, str(file_path), compression=self.compression, **options
            )

            file_size = file_path.stat().st_size
            self.logger.debug(
                f"Wrote {len(data)} row(s) to {file_path} ({file_size} bytes)"
            )

        except pa.ArrowInvalid as e:
            raise ProcessingError(
                f"Failed to create Parquet table: {e}. "
                "Check that data matches schema."
            )
        except Exception as e:
            raise ProcessingError(f"Failed to write Parquet file: {e}")
