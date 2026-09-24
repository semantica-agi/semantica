"""
CSV Exporter Module

This module provides comprehensive CSV export capabilities for the Semantica
framework, enabling tabular data export for entities, relationships, and
knowledge graphs.

Key Features:
    - CSV export for entities and relationships
    - Knowledge graph export to multiple CSV files
    - Configurable delimiters and encoding
    - Metadata serialization
    - Batch export processing
    - Custom field name support

Example Usage:
    >>> from semantica.export import CSVExporter
    >>> exporter = CSVExporter(delimiter=",", encoding="utf-8")
    >>> exporter.export_entities(entities, "entities.csv")
    >>> exporter.export_knowledge_graph(kg, "kg_base")

Author: Semantica Contributors
License: MIT
"""

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.helpers import ensure_directory
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class CSVExporter:
    """
    CSV exporter for knowledge graphs and structured data.

    This class provides comprehensive CSV export functionality for entities,
    relationships, and knowledge graphs. Supports configurable delimiters,
    encoding, and custom field names.

    Features:
        - Entity and relationship export
        - Knowledge graph export to multiple CSV files
        - Configurable delimiters and encoding
        - Metadata serialization as JSON strings
        - Custom field name support
        - Header row inclusion control

    Example Usage:
        >>> exporter = CSVExporter(
        ...     delimiter=",",
        ...     encoding="utf-8",
        ...     include_header=True
        ... )
        >>> exporter.export_entities(entities, "entities.csv")
        >>> exporter.export_knowledge_graph(kg, "output_base")
    """

    def __init__(
        self,
        delimiter: str = ",",
        encoding: str = "utf-8",
        include_header: bool = True,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize CSV exporter.

        Sets up the exporter with specified CSV formatting options.

        Args:
            delimiter: CSV field delimiter (default: ',')
            encoding: File encoding for output (default: 'utf-8')
            include_header: Whether to include header row in CSV (default: True)
            config: Optional configuration dictionary (merged with kwargs)
            **kwargs: Additional configuration options
        """
        self.logger = get_logger("csv_exporter")
        self.config = config or {}
        self.config.update(kwargs)

        # CSV configuration
        self.delimiter = delimiter
        self.encoding = encoding
        self.include_header = include_header

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug(
            f"CSV exporter initialized: delimiter='{delimiter}', "
            f"encoding={encoding}, include_header={include_header}"
        )

    def export(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        file_path: Union[str, Path],
        fieldnames: Optional[List[str]] = None,
        mode: str = "w",
        **options,
    ) -> List[Path]:
        """
        Export data to CSV file(s).

        This method handles both single CSV file export (from list) and multiple
        CSV file export (from dictionary with multiple keys).

        Args:
            data: Data to export:
                - List of dicts: Exports to single CSV file
                - Dict with list values: Exports each key as separate CSV file
            file_path: Output file path (base path for dict exports)
            fieldnames: Custom field names for CSV columns (default: auto-detect)
            mode: Write mode - 'w' (write) or 'a' (append) (default: 'w')
            **options: Additional options passed to _write_csv()

        Raises:
            ValidationError: If data type is unsupported

        Returns:
            The files written. A dictionary is written one file per key, so
            this is how a caller learns which files a multi-file export
            produced; a list is written to ``file_path``.

        Example:
            >>> # Single CSV file
            >>> exporter.export([{"id": 1, "name": "A"}], "data.csv")
            >>> # Multiple CSV files
            >>> exporter.export(
            ...     {"entities": [...], "relationships": [...]},
            ...     "output_base"
            ... )
        """
        # Track CSV export
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="export",
            submodule="CSVExporter",
            message=f"Exporting data to CSV: {file_path}",
        )

        try:
            file_path = Path(file_path)
            ensure_directory(file_path.parent)

            self.logger.debug(f"Exporting data to CSV: {file_path}")

            # Handle different data structures
            if isinstance(data, dict):
                # Export each key as separate CSV file
                exported_files: List[Path] = []
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Exporting {len(data)} data groups..."
                )
                for key, value in data.items():
                    if isinstance(value, list):
                        if not value:
                            # An empty collection has nothing to write, and
                            # writing an empty file would be a guess at a
                            # header. Skipping it also keeps a graph with no
                            # relationships exportable: the entity file is
                            # still produced instead of the call aborting.
                            self.logger.debug(
                                f"Skipping key '{key}': collection is empty"
                            )
                            continue
                        output_path = file_path.parent / f"{file_path.stem}_{key}.csv"
                        self._write_csv(
                            value,
                            output_path,
                            fieldnames=fieldnames,
                            mode=mode,
                            **options,
                        )
                        exported_files.append(output_path)
                    else:
                        self.logger.warning(
                            f"Skipping key '{key}': value is not a list (type: {type(value)})"
                        )

                self.logger.info(
                    f"Exported {len(exported_files)} CSV file(s) from dictionary: "
                    f"{', '.join(str(f) for f in exported_files)}"
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Exported {len(exported_files)} CSV files",
                )
                return exported_files
            elif isinstance(data, list):
                # Single CSV file
                self.progress_tracker.update_tracking(
                    tracking_id, message=f"Exporting {len(data)} records..."
                )
                self._write_csv(
                    data, file_path, fieldnames=fieldnames, mode=mode, **options
                )
                self.logger.info(f"Exported CSV to: {file_path}")
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Exported CSV to: {file_path}",
                )
                return [file_path]
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
        Export entities to CSV file.

        This method normalizes entity data to a consistent format and exports
        to CSV. Handles various entity field name variations and serializes
        metadata as JSON strings.

        Normalized Fields:
            - id: Entity identifier
            - text: Entity text/label/name
            - type: Entity type
            - confidence: Confidence score
            - start: Start offset/position
            - end: End offset/position
            - metadata: Metadata as JSON string (if present)

        Args:
            entities: List of entity dictionaries with various field names
            file_path: Output CSV file path
            **options: Additional options passed to _write_csv()

        Raises:
            ValidationError: If entities list is empty

        Example:
            >>> entities = [
            ...     {"id": "e1", "text": "Entity 1", "type": "PERSON"},
            ...     {"id": "e2", "label": "Entity 2", "entity_type": "ORG"}
            ... ]
            >>> exporter.export_entities(entities, "entities.csv")
        """
        if not entities:
            raise ValidationError("No entities to export. Entities list is empty.")

        self.logger.debug(f"Exporting {len(entities)} entity(ies) to CSV")

        # Normalize entity data to consistent format
        normalized_entities = []
        for i, entity in enumerate(entities):
            if not isinstance(entity, dict):
                self.logger.warning(f"Entity {i} is not a dictionary, skipping")
                continue

            normalized = {
                "id": entity.get("id") or entity.get("entity_id", ""),
                "text": (
                    entity.get("text")
                    or entity.get("label")
                    or entity.get("name")
                    or ""
                ),
                "type": entity.get("type") or entity.get("entity_type", ""),
                "confidence": entity.get("confidence", ""),
                "start": entity.get("start") or entity.get("start_offset", ""),
                "end": entity.get("end") or entity.get("end_offset", ""),
            }

            # Add metadata as JSON string if present
            if "metadata" in entity:
                import json

                try:
                    normalized["metadata"] = json.dumps(entity["metadata"])
                except (TypeError, ValueError) as e:
                    self.logger.warning(
                        f"Failed to serialize metadata for entity {i}: {e}. "
                        "Skipping metadata."
                    )

            normalized_entities.append(normalized)

        self.logger.debug(
            f"Normalized {len(normalized_entities)} entity(ies) for CSV export"
        )

        self._write_csv(normalized_entities, file_path, **options)

    def export_relationships(
        self,
        relationships: List[Dict[str, Any]],
        file_path: Union[str, Path],
        **options,
    ) -> None:
        """
        Export relationships to CSV file.

        This method normalizes relationship data to a consistent format and exports
        to CSV. Handles various relationship field name variations and serializes
        metadata as JSON strings.

        Normalized Fields:
            - id: Relationship identifier
            - source_id: Source entity identifier
            - target_id: Target entity identifier
            - type: Relationship type
            - confidence: Confidence score
            - metadata: Metadata as JSON string (if present)

        Args:
            relationships: List of relationship dictionaries with various field names
            file_path: Output CSV file path
            **options: Additional options passed to _write_csv()

        Raises:
            ValidationError: If relationships list is empty

        Example:
            >>> relationships = [
            ...     {"id": "r1", "source_id": "e1", "target_id": "e2", "type": "RELATED_TO"},
            ...     {"source": "e2", "target": "e3", "relationship_type": "CONTAINS"}
            ... ]
            >>> exporter.export_relationships(relationships, "relationships.csv")
        """
        if not relationships:
            raise ValidationError(
                "No relationships to export. Relationships list is empty."
            )

        self.logger.debug(f"Exporting {len(relationships)} relationship(s) to CSV")

        # Normalize relationship data to consistent format
        normalized_rels = []
        for i, rel in enumerate(relationships):
            if not isinstance(rel, dict):
                self.logger.warning(f"Relationship {i} is not a dictionary, skipping")
                continue

            normalized = {
                "id": rel.get("id", ""),
                "source_id": rel.get("source_id") or rel.get("source", ""),
                "target_id": rel.get("target_id") or rel.get("target", ""),
                "type": rel.get("type") or rel.get("relationship_type", ""),
                "confidence": rel.get("confidence", ""),
            }

            # Add metadata as JSON string if present
            if "metadata" in rel:
                import json

                try:
                    normalized["metadata"] = json.dumps(rel["metadata"])
                except (TypeError, ValueError) as e:
                    self.logger.warning(
                        f"Failed to serialize metadata for relationship {i}: {e}. "
                        "Skipping metadata."
                    )

            normalized_rels.append(normalized)

        self.logger.debug(
            f"Normalized {len(normalized_rels)} relationship(s) for CSV export"
        )

        self._write_csv(normalized_rels, file_path, **options)

    def export_knowledge_graph(
        self, knowledge_graph: Dict[str, Any], base_path: Union[str, Path], **options
    ) -> List[Path]:
        """
        Export knowledge graph to multiple CSV files.

        This method exports a knowledge graph to separate CSV files for entities,
        relationships, nodes, and edges. Each component is exported to its own
        file with a naming pattern: `{base_path}_entities.csv`, etc.

        Exported Files:
            - {base_path}_entities.csv: Entity data
            - {base_path}_relationships.csv: Relationship data
            - {base_path}_nodes.csv: Node data (if present)
            - {base_path}_edges.csv: Edge data (if present)

        Args:
            knowledge_graph: Knowledge graph dictionary containing:
                - entities: List of entity dictionaries
                - relationships: List of relationship dictionaries
                - nodes: List of node dictionaries (optional)
                - edges: List of edge dictionaries (optional)
            base_path: Base path for output files (without extension)
            **options: Additional options passed to export methods

        Returns:
            The files written, in the order they were exported. An empty
            collection is not written, so a graph with no relationships
            produces one file rather than two.

        Example:
            >>> kg = {
            ...     "entities": [...],
            ...     "relationships": [...],
            ...     "nodes": [...],
            ...     "edges": [...]
            ... }
            >>> exporter.export_knowledge_graph(kg, "output_base")
            >>> # Creates: output_base_entities.csv, output_base_relationships.csv, etc.
        """
        base_path = Path(base_path)

        self.logger.debug(
            f"Exporting knowledge graph to CSV files: base_path={base_path}"
        )

        exported_files = []

        # Export entities
        entities = knowledge_graph.get("entities", [])
        if entities:
            entities_path = base_path.parent / f"{base_path.stem}_entities.csv"
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
            rels_path = base_path.parent / f"{base_path.stem}_relationships.csv"
            self.export_relationships(relationships, rels_path, **options)
            exported_files.append(rels_path)
            self.logger.debug(
                f"Exported {len(relationships)} relationship(s) to {rels_path}"
            )
        else:
            self.logger.debug("No relationships found in knowledge graph")

        # Export nodes if available
        nodes = knowledge_graph.get("nodes", [])
        if nodes:
            nodes_path = base_path.parent / f"{base_path.stem}_nodes.csv"
            self._write_csv(nodes, nodes_path, **options)
            exported_files.append(nodes_path)
            self.logger.debug(f"Exported {len(nodes)} node(s) to {nodes_path}")

        # Export edges if available
        edges = knowledge_graph.get("edges", [])
        if edges:
            edges_path = base_path.parent / f"{base_path.stem}_edges.csv"
            self._write_csv(edges, edges_path, **options)
            exported_files.append(edges_path)
            self.logger.debug(f"Exported {len(edges)} edge(s) to {edges_path}")

        if exported_files:
            self.logger.info(
                f"Exported knowledge graph to {len(exported_files)} CSV file(s): "
                f"{', '.join(str(f) for f in exported_files)}"
            )
        else:
            self.logger.warning("No data found in knowledge graph to export")

        return exported_files

    def _write_csv(
        self,
        data: List[Dict[str, Any]],
        file_path: Path,
        fieldnames: Optional[List[str]] = None,
        mode: str = "w",
        **options,
    ) -> None:
        """
        Write data to CSV file.

        This internal method handles the actual CSV file writing, including
        field name detection, header writing, and value conversion.

        Args:
            data: List of dictionaries to write as CSV rows
            file_path: Output CSV file path
            fieldnames: Custom field names (default: auto-detect from data)
            mode: Write mode - 'w' (write) or 'a' (append) (default: 'w')
            **options: Unused (for compatibility)

        Raises:
            ValidationError: If data list is empty
            ProcessingError: If file writing fails
        """
        if not data:
            raise ValidationError("No data to write. Data list is empty.")

        # Determine field names
        if not fieldnames:
            # Auto-detect: get all unique keys from data
            fieldnames_set = set()
            for item in data:
                if isinstance(item, dict):
                    fieldnames_set.update(item.keys())
            fieldnames = sorted(list(fieldnames_set))

        if not fieldnames:
            raise ValidationError("No field names found in data")

        self.logger.debug(
            f"Writing CSV: {len(data)} row(s), {len(fieldnames)} column(s), "
            f"mode={mode}, file={file_path}"
        )

        try:
            with open(file_path, mode, newline="", encoding=self.encoding) as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=fieldnames,
                    delimiter=self.delimiter,
                    extrasaction="ignore",  # Ignore extra fields not in fieldnames
                )

                # Write header if requested and in write mode
                if self.include_header and mode == "w":
                    writer.writeheader()

                # Write data rows
                for i, row in enumerate(data):
                    if not isinstance(row, dict):
                        self.logger.warning(f"Row {i} is not a dictionary, skipping")
                        continue

                    # Convert values to strings (CSV requires string values)
                    row_str = {
                        k: str(v) if v is not None else ""
                        for k, v in row.items()
                        if k in fieldnames
                    }
                    writer.writerow(row_str)

        except IOError as e:
            error_msg = f"Failed to write CSV file {file_path}: {e}"
            self.logger.error(error_msg)
            raise ProcessingError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error writing CSV file: {e}"
            self.logger.error(error_msg)
            raise ProcessingError(error_msg) from e

        self.logger.debug(f"Successfully wrote CSV file: {file_path}")
