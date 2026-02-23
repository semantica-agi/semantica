"""
Apache Parquet Exporter Module

This module provides Apache Parquet export capabilities for entities,
relationships, and knowledge graphs.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import pyarrow as pa
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.helpers import ensure_directory
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


if PARQUET_AVAILABLE:
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
else:
    ENTITY_SCHEMA = None
    RELATIONSHIP_SCHEMA = None


class ParquetExporter:
    """Apache Parquet exporter for knowledge graph data."""

    def __init__(self, compression: Optional[str] = "snappy", **kwargs):
        if not PARQUET_AVAILABLE:
            raise ImportError(
                "pyarrow is not installed. Please install it with: pip install pyarrow"
            )

        self.logger = get_logger("parquet_exporter")
        self.compression = compression
        self.config = kwargs
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

    def export_entities(self, entities: List[Dict[str, Any]], file_path: Union[str, Path]) -> None:
        if not entities:
            raise ValidationError("No entities to export. Entities list is empty.")
        normalized_entities = [self._normalize_entity(i, entity) for i, entity in enumerate(entities)]
        self._write_parquet(normalized_entities, Path(file_path), schema=ENTITY_SCHEMA)

    def export_relationships(
        self, relationships: List[Dict[str, Any]], file_path: Union[str, Path]
    ) -> None:
        if not relationships:
            raise ValidationError("No relationships to export. Relationships list is empty.")
        normalized_relationships = [
            self._normalize_relationship(i, relationship)
            for i, relationship in enumerate(relationships)
        ]
        self._write_parquet(normalized_relationships, Path(file_path), schema=RELATIONSHIP_SCHEMA)

    def export_knowledge_graph(
        self, knowledge_graph: Dict[str, Any], base_path: Union[str, Path]
    ) -> None:
        base_path = Path(base_path)
        entities = knowledge_graph.get("entities", [])
        relationships = knowledge_graph.get("relationships", [])

        if entities:
            self.export_entities(entities, base_path.parent / f"{base_path.stem}_entities.parquet")
        if relationships:
            self.export_relationships(
                relationships,
                base_path.parent / f"{base_path.stem}_relationships.parquet",
            )

    def export(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]],
        file_path: Union[str, Path],
    ) -> None:
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="export",
            submodule="ParquetExporter",
            message=f"Exporting data to Parquet: {file_path}",
        )

        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    if not isinstance(value, list):
                        continue
                    output_path = Path(file_path).parent / f"{Path(file_path).stem}_{key}.parquet"
                    if key == "entities":
                        self.export_entities(value, output_path)
                    elif key == "relationships":
                        self.export_relationships(value, output_path)
                    else:
                        self._write_parquet(value, output_path)
            elif isinstance(data, list):
                self._write_parquet(data, Path(file_path))
            else:
                raise ValidationError(
                    f"Unsupported data type: {type(data)}. Expected list or dict with list values."
                )

            self.progress_tracker.stop_tracking(
                tracking_id, status="completed", message=f"Exported Parquet: {file_path}"
            )
        except Exception as e:
            self.progress_tracker.stop_tracking(tracking_id, status="failed", message=str(e))
            raise

    def _normalize_entity(self, index: int, entity: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(entity, dict):
            raise ValidationError(f"Entity {index} is not a dictionary")

        confidence = entity.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        start = entity.get("start") or entity.get("start_offset")
        if start is not None:
            try:
                start = int(start)
            except (TypeError, ValueError):
                start = None

        end = entity.get("end") or entity.get("end_offset")
        if end is not None:
            try:
                end = int(end)
            except (TypeError, ValueError):
                end = None

        return {
            "id": str(entity.get("id") or entity.get("entity_id", "")),
            "text": entity.get("text") or entity.get("label") or entity.get("name"),
            "type": entity.get("type") or entity.get("entity_type"),
            "confidence": confidence,
            "start": start,
            "end": end,
            "metadata": self._dict_to_struct(entity.get("metadata")) if entity.get("metadata") else None,
        }

    def _normalize_relationship(self, index: int, relationship: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(relationship, dict):
            raise ValidationError(f"Relationship {index} is not a dictionary")

        confidence = relationship.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        return {
            "id": str(relationship.get("id", f"rel_{index}")),
            "source_id": str(relationship.get("source_id") or relationship.get("source", "")),
            "target_id": str(relationship.get("target_id") or relationship.get("target", "")),
            "type": relationship.get("type") or relationship.get("relationship_type"),
            "confidence": confidence,
            "metadata": self._dict_to_struct(relationship.get("metadata"))
            if relationship.get("metadata")
            else None,
        }

    def _dict_to_struct(self, metadata: Dict[str, Any]) -> Optional[Dict[str, List[str]]]:
        if not isinstance(metadata, dict):
            return None

        keys: List[str] = []
        values: List[str] = []
        for key, value in metadata.items():
            keys.append(str(key))
            if isinstance(value, (dict, list)):
                try:
                    values.append(json.dumps(value))
                except (TypeError, ValueError):
                    values.append(str(value))
            else:
                values.append(str(value) if value is not None else "")
        return {"keys": keys, "values": values}

    def _write_parquet(
        self,
        data: List[Dict[str, Any]],
        file_path: Path,
        schema: Optional[pa.Schema] = None,
    ) -> None:
        if not data:
            raise ValidationError("No data to write. Data list is empty.")

        ensure_directory(file_path.parent)

        try:
            table = pa.Table.from_pylist(data, schema=schema)
            pq.write_table(table, str(file_path), compression=self.compression)
        except pa.ArrowInvalid as e:
            raise ValidationError(f"Parquet schema validation failed for {file_path}: {e}") from e
        except IOError as e:
            raise ProcessingError(f"Failed to write Parquet file {file_path}: {e}") from e
        except Exception as e:
            raise ProcessingError(f"Unexpected error writing Parquet file: {e}") from e
