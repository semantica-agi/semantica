"""
Apache Arrow Exporter Module

This module provides comprehensive Apache Arrow export capabilities for the
Semantica framework, enabling high-performance columnar data export for entities,
relationships, and knowledge graphs.

Key Features:
    - Arrow IPC file export (.arrow)
    - Explicit schema definition (no inference)
    - Entity and relationship export with metadata
    - Knowledge graph export to multiple Arrow files
    - Pandas and DuckDB compatible
    - Batch export processing
    - Structured metadata handling

Example Usage:
    >>> from semantica.export import ArrowExporter
    >>> exporter = ArrowExporter()
    >>> exporter.export_entities(entities, "entities.arrow")
    >>> exporter.export_knowledge_graph(kg, "kg_base")

Author: Semantica Contributors
License: MIT
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import pyarrow as pa
    import pyarrow.ipc as ipc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.helpers import ensure_directory
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


# Explicit Arrow Schemas (no inference)
if ARROW_AVAILABLE:
    ENTITY_SCHEMA = pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("text", pa.string(), nullable=True),
        pa.field("type", pa.string(), nullable=True),
        pa.field("confidence", pa.float64(), nullable=True),
        pa.field("start", pa.int64(), nullable=True),
        pa.field("end", pa.int64(), nullable=True),
        pa.field("metadata", pa.struct([
            pa.field("keys", pa.list_(pa.string())),
            pa.field("values", pa.list_(pa.string()))
        ]), nullable=True),
    ])

    RELATIONSHIP_SCHEMA = pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("target_id", pa.string(), nullable=False),
        pa.field("type", pa.string(), nullable=True),
        pa.field("confidence", pa.float64(), nullable=True),
        pa.field("metadata", pa.struct([
            pa.field("keys", pa.list_(pa.string())),
            pa.field("values", pa.list_(pa.string()))
        ]), nullable=True),
    ])
else:
    ENTITY_SCHEMA = None
    RELATIONSHIP_SCHEMA = None


class ArrowExporter:
    """
    Apache Arrow exporter for knowledge graphs and structured data.

    This class provides comprehensive Arrow IPC export functionality for entities,
    relationships, and knowledge graphs. Uses explicit schemas for type safety
    and compatibility with Pandas and DuckDB.

    Features:
        - Entity and relationship export
        - Knowledge graph export to multiple Arrow files
        - Explicit schema definition (no inference)
        - Metadata serialization as Arrow struct fields
        - Pandas and DuckDB compatible
        - Progress tracking and error handling

    Example Usage:
        >>> exporter = ArrowExporter()
        >>> exporter.export_entities(entities, "entities.arrow")
        >>> exporter.export_knowledge_graph(kg, "output_base")
    """

    def __init__(
        self,
        compression: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize Arrow exporter.

        Sets up the exporter with specified Arrow formatting options.

        Args:
            compression: Compression codec (default: None)
                - None: No compression
                - "lz4": LZ4 compression
                - "zstd": Zstandard compression
            config: Optional configuration dictionary (merged with kwargs)
            **kwargs: Additional configuration options

        Raises:
            ImportError: If pyarrow is not installed
        """
        if not ARROW_AVAILABLE:
            raise ImportError(
                "pyarrow is not installed. Please install it with: "
                "pip install pyarrow"
            )

        self.logger = get_logger("arrow_exporter")
        self.config = config or {}
        self.config.update(kwargs)

        # Arrow configuration
        self.compression = compression

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug(
            f"Arrow exporter initialized: compression={compression}"
        )

    def export(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        file_path: Union[str, Path],
        schema: Optional[pa.Schema] = None,
        **options,
    ) -> None:
        """
        Export data to Arrow IPC file(s).

        This method handles both single Arrow file export (from list) and multiple
        Arrow file export (from dictionary with multiple keys).

        Args:
            data: Data to export:
                - List of dicts: Exports to single Arrow file
                - Dict with list values: Exports each key as separate Arrow file
            file_path: Output file path (base path for dict exports)
            schema: Arrow schema to use (default: auto-select based on data)
            **options: Additional options

        Raises:
            ValidationError: If data type is unsupported

        Example:
            >>> # Single Arrow file
            >>> exporter.export([{"id": "1", "name": "A"}], "data.arrow")
            >>> # Multiple Arrow files
            >>> exporter.export(
            ...     {"entities": [...], "relationships": [...]},
            ...     "output_base"
            ... )
        """
        # Track Arrow export
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="export",
            submodule="ArrowExporter",
            message=f"Exporting data to Arrow: {file_path}",
        )

        try:
            file_path = Path(file_path)
            ensure_directory(file_path.parent)

            self.logger.debug(f"Exporting data to Arrow: {file_path}")

            # Handle different data structures
            if isinstance(data, dict):
                # Export each key as separate Arrow file
                exported_files = []
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Exporting {len(data)} data groups..."
                )
                for key, value in data.items():
                    if isinstance(value, list):
                        output_path = file_path.parent / f"{file_path.stem}_{key}.arrow"
                        
                        # Select schema based on key
                        key_schema = schema
                        if key == "entities" and schema is None:
                            key_schema = ENTITY_SCHEMA
                        elif key == "relationships" and schema is None:
                            key_schema = RELATIONSHIP_SCHEMA
                        
                        self._write_arrow(value, output_path, schema=key_schema, **options)
                        exported_files.append(output_path)
                    else:
                        self.logger.warning(
                            f"Skipping key '{key}': value is not a list (type: {type(value)})"
                        )

                self.logger.info(
                    f"Exported {len(exported_files)} Arrow file(s) from dictionary: "
                    f"{', '.join(str(f) for f in exported_files)}"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Exported {len(exported_files)} Arrow files",
                )
            elif isinstance(data, list):
                # Single Arrow file
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Exporting {len(data)} records..."
                )
                self._write_arrow(data, file_path, schema=schema, **options)
                self.logger.info(f"Exported Arrow to: {file_path}")
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Exported Arrow to: {file_path}",
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
        Export entities to Arrow IPC file.

        This method normalizes entity data to a consistent format and exports
        to Arrow using the explicit ENTITY_SCHEMA. Handles various entity field
        name variations and serializes metadata as Arrow struct fields.

        Normalized Fields:
            - id: Entity identifier (string)
            - text: Entity text/label/name (string)
            - type: Entity type (string)
            - confidence: Confidence score (float64)
            - start: Start offset/position (int64)
            - end: End offset/position (int64)
            - metadata: Metadata as Arrow struct (keys and values lists)

        Args:
            entities: List of entity dictionaries with various field names
            file_path: Output Arrow file path
            **options: Additional options

        Raises:
            ValidationError: If entities list is empty

        Example:
            >>> entities = [
            ...     {"id": "e1", "text": "Entity 1", "type": "PERSON"},
            ...     {"id": "e2", "label": "Entity 2", "entity_type": "ORG"}
            ... ]
            >>> exporter.export_entities(entities, "entities.arrow")
        """
        if not entities:
            raise ValidationError("No entities to export. Entities list is empty.")

        self.logger.debug(f"Exporting {len(entities)} entity(ies) to Arrow")

        # Normalize entity data to consistent format
        normalized_entities = []
        for i, entity in enumerate(entities):
            if not isinstance(entity, dict):
                self.logger.warning(f"Entity {i} is not a dictionary, skipping")
                continue

            # Extract and normalize fields
            entity_id = entity.get("id") or entity.get("entity_id", "")
            text = entity.get("text") or entity.get("label") or entity.get("name") or ""
            entity_type = entity.get("type") or entity.get("entity_type", "")
            confidence = entity.get("confidence")
            start = entity.get("start") or entity.get("start_offset")
            end = entity.get("end") or entity.get("end_offset")

            # Convert confidence to float
            if confidence is not None:
                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Invalid confidence value for entity {i}: {confidence}. Setting to None."
                    )
                    confidence = None

            # Convert start/end to int
            if start is not None:
                try:
                    start = int(start)
                except (TypeError, ValueError):
                    start = None
            if end is not None:
                try:
                    end = int(end)
                except (TypeError, ValueError):
                    end = None

            # Convert metadata dict to Arrow struct
            metadata = None
            if "metadata" in entity and entity["metadata"]:
                metadata = self._dict_to_struct(entity["metadata"])

            normalized = {
                "id": str(entity_id),
                "text": str(text) if text else None,
                "type": str(entity_type) if entity_type else None,
                "confidence": confidence,
                "start": start,
                "end": end,
                "metadata": metadata,
            }

            normalized_entities.append(normalized)

        self.logger.debug(
            f"Normalized {len(normalized_entities)} entity(ies) for Arrow export"
        )

        self._write_arrow(normalized_entities, file_path, schema=ENTITY_SCHEMA, **options)

    def export_relationships(
        self,
        relationships: List[Dict[str, Any]],
        file_path: Union[str, Path],
        **options,
    ) -> None:
        """
        Export relationships to Arrow IPC file.

        This method normalizes relationship data to a consistent format and exports
        to Arrow using the explicit RELATIONSHIP_SCHEMA. Handles various relationship
        field name variations and serializes metadata as Arrow struct fields.

        Normalized Fields:
            - id: Relationship identifier (string)
            - source_id: Source entity identifier (string)
            - target_id: Target entity identifier (string)
            - type: Relationship type (string)
            - confidence: Confidence score (float64)
            - metadata: Metadata as Arrow struct (keys and values lists)

        Args:
            relationships: List of relationship dictionaries with various field names
            file_path: Output Arrow file path
            **options: Additional options

        Raises:
            ValidationError: If relationships list is empty

        Example:
            >>> relationships = [
            ...     {"id": "r1", "source_id": "e1", "target_id": "e2", "type": "RELATED_TO"},
            ...     {"source": "e2", "target": "e3", "relationship_type": "CONTAINS"}
            ... ]
            >>> exporter.export_relationships(relationships, "relationships.arrow")
        """
        if not relationships:
            raise ValidationError(
                "No relationships to export. Relationships list is empty."
            )

        self.logger.debug(f"Exporting {len(relationships)} relationship(s) to Arrow")

        # Normalize relationship data to consistent format
        normalized_rels = []
        for i, rel in enumerate(relationships):
            if not isinstance(rel, dict):
                self.logger.warning(f"Relationship {i} is not a dictionary, skipping")
                continue

            # Extract and normalize fields
            rel_id = rel.get("id", f"rel_{i}")
            source_id = rel.get("source_id") or rel.get("source", "")
            target_id = rel.get("target_id") or rel.get("target", "")
            rel_type = rel.get("type") or rel.get("relationship_type", "")
            confidence = rel.get("confidence")

            # Convert confidence to float
            if confidence is not None:
                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Invalid confidence value for relationship {i}: {confidence}. Setting to None."
                    )
                    confidence = None

            # Convert metadata dict to Arrow struct
            metadata = None
            if "metadata" in rel and rel["metadata"]:
                metadata = self._dict_to_struct(rel["metadata"])

            normalized = {
                "id": str(rel_id),
                "source_id": str(source_id),
                "target_id": str(target_id),
                "type": str(rel_type) if rel_type else None,
                "confidence": confidence,
                "metadata": metadata,
            }

            normalized_rels.append(normalized)

        self.logger.debug(
            f"Normalized {len(normalized_rels)} relationship(s) for Arrow export"
        )

        self._write_arrow(normalized_rels, file_path, schema=RELATIONSHIP_SCHEMA, **options)

    def export_knowledge_graph(
        self, knowledge_graph: Dict[str, Any], base_path: Union[str, Path], **options
    ) -> None:
        """
        Export knowledge graph to multiple Arrow IPC files.

        This method exports a knowledge graph to separate Arrow files for entities
        and relationships. Each component is exported to its own file with a naming
        pattern: `{base_path}_entities.arrow`, etc.

        Exported Files:
            - {base_path}_entities.arrow: Entity data
            - {base_path}_relationships.arrow: Relationship data

        Args:
            knowledge_graph: Knowledge graph dictionary containing:
                - entities: List of entity dictionaries
                - relationships: List of relationship dictionaries
            base_path: Base path for output files (without extension)
            **options: Additional options passed to export methods

        Example:
            >>> kg = {
            ...     "entities": [...],
            ...     "relationships": [...]
            ... }
            >>> exporter.export_knowledge_graph(kg, "output_base")
            >>> # Creates: output_base_entities.arrow, output_base_relationships.arrow
        """
        base_path = Path(base_path)

        self.logger.debug(
            f"Exporting knowledge graph to Arrow files: base_path={base_path}"
        )

        exported_files = []

        # Export entities
        entities = knowledge_graph.get("entities", [])
        if entities:
            entities_path = base_path.parent / f"{base_path.stem}_entities.arrow"
            self.export_entities(entities, entities_path, **options)
            exported_files.append(entities_path)
            self.logger.debug(
                f"Exported {len(entities)} entity(ies) to {entities_path}"
            )
        else:
            self.logger.debug("No entities found in knowledge graph")

        # Export relationships
        relationships = knowledge_graph.get("relationships", [])
        if relationships:
            rels_path = base_path.parent / f"{base_path.stem}_relationships.arrow"
            self.export_relationships(relationships, rels_path, **options)
            exported_files.append(rels_path)
            self.logger.debug(
                f"Exported {len(relationships)} relationship(s) to {rels_path}"
            )
        else:
            self.logger.debug("No relationships found in knowledge graph")

        if exported_files:
            self.logger.info(
                f"Exported knowledge graph to {len(exported_files)} Arrow file(s): "
                f"{', '.join(str(f) for f in exported_files)}"
            )
        else:
            self.logger.warning("No data found in knowledge graph to export")

    def _dict_to_struct(self, metadata: Dict[str, Any]) -> Dict[str, List]:
        """
        Convert metadata dictionary to Arrow struct format.

        Converts a dictionary into a struct with keys and values lists,
        suitable for Arrow struct fields.

        Args:
            metadata: Metadata dictionary to convert

        Returns:
            Dict with 'keys' and 'values' lists (both strings)
        """
        if not isinstance(metadata, dict):
            return None

        keys = []
        values = []

        for k, v in metadata.items():
            keys.append(str(k))
            # Convert value to JSON string if it's not a simple type
            if isinstance(v, (dict, list)):
                try:
                    values.append(json.dumps(v))
                except (TypeError, ValueError):
                    values.append(str(v))
            else:
                values.append(str(v) if v is not None else "")

        return {"keys": keys, "values": values}

    def _write_arrow(
        self,
        data: List[Dict[str, Any]],
        file_path: Path,
        schema: Optional[pa.Schema] = None,
        **options,
    ) -> None:
        """
        Write data to Arrow IPC file.

        This internal method handles the actual Arrow file writing, including
        schema validation and batch writing.

        Args:
            data: List of dictionaries to write as Arrow records
            file_path: Output Arrow file path
            schema: Arrow schema to use (if None, will try to infer from data structure)
            **options: Unused (for compatibility)

        Raises:
            ValidationError: If data list is empty or schema cannot be determined
            ProcessingError: If file writing fails
        """
        if not data:
            raise ValidationError("No data to write. Data list is empty.")

        # If schema is not provided, try to infer from data structure
        if schema is None:
            # Try to detect if data looks like entities or relationships
            sample = data[0] if data else {}
            
            # Check for relationship-specific fields
            has_source = any(k in sample for k in ['source_id', 'source'])
            has_target = any(k in sample for k in ['target_id', 'target'])
            
            # Check for entity-specific fields
            has_text = any(k in sample for k in ['text', 'label', 'name'])
            
            if has_source and has_target:
                schema = RELATIONSHIP_SCHEMA
                self.logger.debug("Auto-detected relationship schema")
            elif has_text or 'type' in sample:
                schema = ENTITY_SCHEMA
                self.logger.debug("Auto-detected entity schema")
            else:
                raise ValidationError(
                    "Schema is required for Arrow export. "
                    "Cannot auto-detect schema from data structure. "
                    "Provide explicit schema or use export_entities/export_relationships methods."
                )

        self.logger.debug(
            f"Writing Arrow IPC file: {len(data)} row(s), "
            f"schema={schema}, file={file_path}"
        )

        try:
            # Create Arrow table from data using explicit schema
            table = pa.Table.from_pylist(data, schema=schema)

            # Write to Arrow IPC file
            with pa.OSFile(str(file_path), 'wb') as sink:
                with ipc.new_file(sink, schema) as writer:
                    writer.write_table(table)

            self.logger.debug(f"Successfully wrote Arrow IPC file: {file_path}")

        except pa.ArrowInvalid as e:
            error_msg = f"Arrow schema validation failed for {file_path}: {e}"
            self.logger.error(error_msg)
            raise ValidationError(error_msg) from e
        except IOError as e:
            error_msg = f"Failed to write Arrow file {file_path}: {e}"
            self.logger.error(error_msg)
            raise ProcessingError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error writing Arrow file: {e}"
            self.logger.error(error_msg)
            raise ProcessingError(error_msg) from e
