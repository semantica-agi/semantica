"""
Apache Parquet Ingestion Module

This module provides dedicated Parquet ingestion for local files and partitioned
directories. It uses PyArrow when available so callers can read selected
columns, inspect schemas and file metadata, and ingest Hive-style partitioned
datasets without database credentials.

Example Usage:
    >>> from semantica.ingest import ParquetIngestor
    >>> ingestor = ParquetIngestor()
    >>> data = ingestor.ingest_file("events.parquet", columns=["id", "event_type"])
    >>> schema = ingestor.extract_schema("events.parquet")
    >>> partitioned = ingestor.ingest_directory("./events_by_date")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

try:
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True
except (ImportError, OSError):
    pa = None
    ds = None
    pq = None
    PARQUET_AVAILABLE = False

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


@dataclass
class ParquetData:
    """Parquet ingestion result."""

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    schema: Dict[str, Any]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


class ParquetIngestor:
    """
    Dedicated Parquet ingestion handler.

    Features:
        - Single Parquet file ingestion
        - Partitioned directory ingestion with Hive partition discovery
        - Selective column reads
        - Schema and file metadata extraction
        - Optional row limits for sampling large files
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize Parquet ingestor.

        Args:
            config: Optional configuration dictionary
            **kwargs: Additional configuration options

        Raises:
            ImportError: If pyarrow is not installed
        """
        if not PARQUET_AVAILABLE:
            raise ImportError(
                "pyarrow is required for ParquetIngestor. "
                "Install it with: pip install pyarrow"
            )

        self.logger = get_logger("parquet_ingestor")
        self.config = config or {}
        self.config.update(kwargs)
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Parquet ingestor initialized")

    def ingest(
        self,
        source: Union[str, Path],
        columns: Optional[Union[str, Sequence[str]]] = None,
        limit: Optional[int] = None,
        filters: Any = None,
        include_data: bool = True,
        **options,
    ) -> ParquetData:
        """
        Ingest a Parquet file or partitioned Parquet directory.

        Args:
            source: Parquet file or directory path
            columns: Optional column name or names to read
            limit: Optional maximum number of rows to return
            filters: Optional PyArrow filter expression or tuple filters
            include_data: If False, return schema and metadata without rows
            **options: Additional options

        Returns:
            ParquetData: Ingested data and metadata
        """
        source_path = Path(source)
        if source_path.is_dir():
            return self.ingest_directory(
                source_path,
                columns=columns,
                limit=limit,
                filters=filters,
                include_data=include_data,
                **options,
            )
        return self.ingest_file(
            source_path,
            columns=columns,
            limit=limit,
            filters=filters,
            include_data=include_data,
            **options,
        )

    def ingest_file(
        self,
        file_path: Union[str, Path],
        columns: Optional[Union[str, Sequence[str]]] = None,
        limit: Optional[int] = None,
        filters: Any = None,
        include_data: bool = True,
        batch_size: Optional[int] = None,
        **options,
    ) -> ParquetData:
        """
        Ingest a single Parquet file.

        Args:
            file_path: Path to Parquet file
            columns: Optional column name or names to read
            limit: Optional maximum number of rows to return
            filters: Optional PyArrow-compatible filters
            include_data: If False, skip reading row data
            batch_size: Batch size used when sampling with limit
            **options: Additional options

        Returns:
            ParquetData: Ingested data, schema, and metadata
        """
        file_path = Path(file_path)
        self._validate_file(file_path)

        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="ingest",
            submodule="ParquetIngestor",
            message=f"Ingesting Parquet: {file_path.name}",
        )

        try:
            parquet_file = pq.ParquetFile(str(file_path))
            selected_columns = self._normalize_columns(
                columns,
                [field.name for field in parquet_file.schema_arrow],
            )
            metadata = self._file_metadata(file_path, parquet_file)

            if include_data:
                table = self._read_file_table(
                    file_path=file_path,
                    parquet_file=parquet_file,
                    columns=selected_columns,
                    limit=limit,
                    filters=filters,
                    batch_size=batch_size,
                )
                data = table.to_pylist()
                schema = self._schema_to_dict(table.schema)
                result_columns = list(table.column_names)
            else:
                selected_schema = self._select_schema(
                    parquet_file.schema_arrow, selected_columns
                )
                data = []
                schema = self._schema_to_dict(selected_schema)
                result_columns = [field.name for field in selected_schema]

            metadata.update(
                {
                    "returned_rows": len(data),
                    "selected_columns": result_columns,
                    "filters_applied": filters is not None,
                    "limit": limit,
                    "include_data": include_data,
                }
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested Parquet: {len(data)} rows",
            )

            self.logger.info(
                f"Parquet ingestion completed: {len(data)} row(s) from {file_path}"
            )

            return ParquetData(
                data=data,
                row_count=len(data),
                columns=result_columns,
                schema=schema,
                source=str(file_path),
                metadata=metadata,
            )

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="Parquet ingestion failed"
            )
            raise
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(f"Failed to ingest Parquet {file_path}: {e}")
            raise ProcessingError(f"Failed to ingest Parquet: {e}") from e

    def ingest_directory(
        self,
        directory_path: Union[str, Path],
        columns: Optional[Union[str, Sequence[str]]] = None,
        limit: Optional[int] = None,
        filters: Any = None,
        include_data: bool = True,
        partitioning: Optional[Union[str, Any]] = "hive",
        **options,
    ) -> ParquetData:
        """
        Ingest a directory containing Parquet files.

        Hive-style partitions such as ``country=US/year=2026`` are discovered
        by default and included as partition columns in the returned schema/data.

        Args:
            directory_path: Directory containing Parquet files
            columns: Optional column name or names to read
            limit: Optional maximum number of rows to return
            filters: Optional PyArrow filter expression or tuple filters
            include_data: If False, return only schema and metadata
            partitioning: PyArrow partitioning mode, defaults to "hive"
            **options: Additional options

        Returns:
            ParquetData: Ingested dataset data and metadata
        """
        directory_path = Path(directory_path)
        parquet_files = self._validate_directory(directory_path)
        if limit is not None and limit < 0:
            raise ValidationError("limit must be greater than or equal to 0")

        tracking_id = self.progress_tracker.start_tracking(
            file=str(directory_path),
            module="ingest",
            submodule="ParquetIngestor",
            message=f"Ingesting Parquet directory: {directory_path.name}",
        )

        try:
            dataset = ds.dataset(
                str(directory_path),
                format="parquet",
                partitioning=partitioning,
            )
            selected_columns = self._normalize_columns(
                columns,
                [field.name for field in dataset.schema],
            )
            filter_expression = self._dataset_filter(filters)
            metadata = self._directory_metadata(
                directory_path,
                parquet_files,
                partitioning=partitioning,
            )

            if include_data:
                if limit is not None:
                    table = dataset.head(
                        limit,
                        columns=selected_columns,
                        filter=filter_expression,
                    )
                else:
                    table = dataset.to_table(
                        columns=selected_columns,
                        filter=filter_expression,
                    )
                data = table.to_pylist()
                schema = self._schema_to_dict(table.schema)
                result_columns = list(table.column_names)
            else:
                selected_schema = self._select_schema(dataset.schema, selected_columns)
                data = []
                schema = self._schema_to_dict(selected_schema)
                result_columns = [field.name for field in selected_schema]

            metadata.update(
                {
                    "returned_rows": len(data),
                    "selected_columns": result_columns,
                    "filters_applied": filters is not None,
                    "limit": limit,
                    "include_data": include_data,
                }
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested Parquet directory: {len(data)} rows",
            )

            self.logger.info(
                "Parquet directory ingestion completed: "
                f"{len(data)} row(s) from {directory_path}"
            )

            return ParquetData(
                data=data,
                row_count=len(data),
                columns=result_columns,
                schema=schema,
                source=str(directory_path),
                metadata=metadata,
            )

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="failed",
                message="Parquet directory ingestion failed",
            )
            raise
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(
                f"Failed to ingest Parquet directory {directory_path}: {e}"
            )
            raise ProcessingError(f"Failed to ingest Parquet directory: {e}") from e

    def read_columns(
        self,
        source: Union[str, Path],
        columns: Union[str, Sequence[str]],
        **options,
    ) -> ParquetData:
        """
        Read selected columns from a Parquet file or directory.

        Args:
            source: Parquet file or directory path
            columns: Column name or names to read
            **options: Additional ingestion options

        Returns:
            ParquetData: Ingested data containing only selected columns
        """
        return self.ingest(source, columns=columns, **options)

    def extract_schema(self, source: Union[str, Path], **options) -> Dict[str, Any]:
        """
        Extract schema from a Parquet file or directory.

        Args:
            source: Parquet file or directory path
            **options: Additional options

        Returns:
            dict: Schema with column names, types, nullability, and metadata
        """
        source_path = Path(source)
        if source_path.is_dir():
            self._validate_directory(source_path)
            dataset = ds.dataset(
                str(source_path),
                format="parquet",
                partitioning=options.get("partitioning", "hive"),
            )
            return self._schema_to_dict(dataset.schema)

        self._validate_file(source_path)
        parquet_file = pq.ParquetFile(str(source_path))
        return self._schema_to_dict(parquet_file.schema_arrow)

    def extract_metadata(self, source: Union[str, Path], **options) -> Dict[str, Any]:
        """
        Extract Parquet file or directory metadata without reading row data.

        Args:
            source: Parquet file or directory path
            **options: Additional options

        Returns:
            dict: Row counts, row groups, compression, partitions, and file info
        """
        source_path = Path(source)
        if source_path.is_dir():
            parquet_files = self._validate_directory(source_path)
            return self._directory_metadata(
                source_path,
                parquet_files,
                partitioning=options.get("partitioning", "hive"),
            )

        self._validate_file(source_path)
        parquet_file = pq.ParquetFile(str(source_path))
        return self._file_metadata(source_path, parquet_file)

    def _read_file_table(
        self,
        file_path: Path,
        parquet_file: Any,
        columns: Optional[List[str]],
        limit: Optional[int],
        filters: Any,
        batch_size: Optional[int],
    ) -> Any:
        """Read a Parquet file, using batches when a simple limit is requested."""
        if limit is not None and limit < 0:
            raise ValidationError("limit must be greater than or equal to 0")

        if limit == 0:
            return pa.Table.from_batches(
                [],
                schema=self._select_schema(parquet_file.schema_arrow, columns),
            )

        if limit is not None and filters is None:
            return self._read_file_limited(parquet_file, columns, limit, batch_size)

        table = pq.read_table(str(file_path), columns=columns, filters=filters)
        if limit is not None:
            table = table.slice(0, limit)
        return table

    def _read_file_limited(
        self,
        parquet_file: Any,
        columns: Optional[List[str]],
        limit: int,
        batch_size: Optional[int],
    ) -> Any:
        """Read at most ``limit`` rows from a file without loading the full file."""
        batches = []
        remaining = limit
        effective_batch_size = batch_size or min(max(limit, 1), 65_536)

        for batch in parquet_file.iter_batches(
            batch_size=effective_batch_size,
            columns=columns,
        ):
            if batch.num_rows > remaining:
                batch = batch.slice(0, remaining)
            batches.append(batch)
            remaining -= batch.num_rows
            if remaining <= 0:
                break

        return pa.Table.from_batches(
            batches,
            schema=self._select_schema(parquet_file.schema_arrow, columns),
        )

    def _validate_file(self, file_path: Path) -> None:
        """Validate a local Parquet file path."""
        if not file_path.exists():
            raise ValidationError(f"Parquet file not found: {file_path}")
        if not file_path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}")
        if file_path.suffix.lower() not in {".parquet", ".pq"}:
            raise ValidationError(f"File is not a Parquet file: {file_path}")

    def _validate_directory(self, directory_path: Path) -> List[Path]:
        """Validate a Parquet directory and return contained Parquet files."""
        if not directory_path.exists():
            raise ValidationError(f"Parquet directory not found: {directory_path}")
        if not directory_path.is_dir():
            raise ValidationError(f"Path is not a directory: {directory_path}")

        parquet_files = self._parquet_files(directory_path)
        if not parquet_files:
            raise ValidationError(
                f"No Parquet files found in directory: {directory_path}"
            )
        return parquet_files

    def _parquet_files(self, directory_path: Path) -> List[Path]:
        """Return Parquet files under a directory."""
        return sorted(
            path
            for path in directory_path.rglob("*")
            if path.is_file() and path.suffix.lower() in {".parquet", ".pq"}
        )

    def _normalize_columns(
        self,
        columns: Optional[Union[str, Sequence[str]]],
        available_columns: Sequence[str],
    ) -> Optional[List[str]]:
        """Normalize and validate optional selected columns."""
        if columns is None:
            configured_columns = self.config.get("columns")
            if configured_columns is None:
                return None
            columns = configured_columns

        if isinstance(columns, str):
            normalized = [columns]
        else:
            normalized = list(columns)

        missing = [column for column in normalized if column not in available_columns]
        if missing:
            raise ValidationError(
                "Column(s) not found in Parquet schema: "
                f"{', '.join(missing)}. Available columns: "
                f"{', '.join(available_columns)}"
            )
        return normalized

    def _select_schema(self, schema: Any, columns: Optional[List[str]]) -> Any:
        """Return schema limited to selected columns when provided."""
        if columns is None:
            return schema
        fields = [schema.field(column) for column in columns]
        return pa.schema(fields, metadata=schema.metadata)

    def _schema_to_dict(self, schema: Any) -> Dict[str, Any]:
        """Convert PyArrow schema to serializable metadata."""
        fields = []
        for schema_field in schema:
            fields.append(
                {
                    "name": schema_field.name,
                    "type": str(schema_field.type),
                    "nullable": schema_field.nullable,
                    "metadata": self._decode_metadata_map(schema_field.metadata),
                }
            )

        return {
            "columns": [field_info["name"] for field_info in fields],
            "fields": fields,
            "metadata": self._decode_metadata_map(schema.metadata),
        }

    def _file_metadata(self, file_path: Path, parquet_file: Any) -> Dict[str, Any]:
        """Extract metadata for a single Parquet file."""
        metadata = parquet_file.metadata
        compression_by_column = self._compression_by_column(metadata)

        return {
            "format": "parquet",
            "source_type": "file",
            "file": str(file_path),
            "file_size": file_path.stat().st_size,
            "total_rows": metadata.num_rows,
            "row_groups": metadata.num_row_groups,
            "created_by": metadata.created_by,
            "format_version": getattr(metadata, "format_version", None),
            "serialized_size": getattr(metadata, "serialized_size", None),
            "schema_metadata": self._decode_metadata_map(metadata.metadata),
            "compression": {
                column: sorted(codecs)
                for column, codecs in compression_by_column.items()
            },
            "compression_codecs": sorted(
                {codec for codecs in compression_by_column.values() for codec in codecs}
            ),
        }

    def _directory_metadata(
        self,
        directory_path: Path,
        parquet_files: Sequence[Path],
        partitioning: Optional[Union[str, Any]],
    ) -> Dict[str, Any]:
        """Extract aggregate metadata for a Parquet directory."""
        file_entries = []
        total_rows = 0
        total_row_groups = 0
        compression_by_column: Dict[str, set] = {}
        partition_columns = set()
        partition_values: Dict[str, set] = {}

        for parquet_path in parquet_files:
            parquet_file = pq.ParquetFile(str(parquet_path))
            file_metadata = self._file_metadata(parquet_path, parquet_file)
            partitions = self._partition_values(directory_path, parquet_path)

            total_rows += file_metadata["total_rows"]
            total_row_groups += file_metadata["row_groups"]
            for column, codecs in file_metadata["compression"].items():
                compression_by_column.setdefault(column, set()).update(codecs)

            for key, value in partitions.items():
                partition_columns.add(key)
                partition_values.setdefault(key, set()).add(value)

            file_entries.append(
                {
                    "path": str(parquet_path),
                    "relative_path": str(parquet_path.relative_to(directory_path)),
                    "rows": file_metadata["total_rows"],
                    "row_groups": file_metadata["row_groups"],
                    "file_size": file_metadata["file_size"],
                    "partitions": partitions,
                }
            )

        return {
            "format": "parquet",
            "source_type": "directory",
            "directory": str(directory_path),
            "file_count": len(parquet_files),
            "files": file_entries,
            "total_rows": total_rows,
            "row_groups": total_row_groups,
            "partitioning": partitioning,
            "partition_columns": sorted(partition_columns),
            "partition_values": {
                key: sorted(values) for key, values in partition_values.items()
            },
            "compression": {
                column: sorted(codecs)
                for column, codecs in compression_by_column.items()
            },
            "compression_codecs": sorted(
                {codec for codecs in compression_by_column.values() for codec in codecs}
            ),
        }

    def _compression_by_column(self, metadata: Any) -> Dict[str, set]:
        """Return compression codecs used for each column across row groups."""
        compression_by_column: Dict[str, set] = {}
        for row_group_index in range(metadata.num_row_groups):
            row_group = metadata.row_group(row_group_index)
            for column_index in range(row_group.num_columns):
                column_chunk = row_group.column(column_index)
                column_name = column_chunk.path_in_schema
                compression = str(column_chunk.compression)
                compression_by_column.setdefault(column_name, set()).add(compression)
        return compression_by_column

    def _partition_values(self, root: Path, parquet_path: Path) -> Dict[str, str]:
        """Extract Hive-style partition key/value pairs from a file path."""
        partitions = {}
        relative_parent = parquet_path.parent.relative_to(root)
        for part in relative_parent.parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            if key:
                partitions[key] = value
        return partitions

    def _decode_metadata_map(
        self, metadata: Optional[Dict[Any, Any]]
    ) -> Dict[str, str]:
        """Decode PyArrow metadata bytes to strings."""
        if not metadata:
            return {}

        decoded = {}
        for key, value in metadata.items():
            decoded[self._decode_metadata_value(key)] = self._decode_metadata_value(
                value
            )
        return decoded

    def _decode_metadata_value(self, value: Any) -> str:
        """Decode a metadata key or value."""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _dataset_filter(self, filters: Any) -> Any:
        """Convert simple tuple filters to a PyArrow dataset expression."""
        if filters is None:
            return None
        if self._is_filter_tuple(filters):
            return self._comparison_expression(*filters)
        if isinstance(filters, list):
            if all(self._is_filter_tuple(item) for item in filters):
                return self._and_expressions(
                    self._comparison_expression(*item) for item in filters
                )
            if all(isinstance(group, list) for group in filters):
                return self._or_expressions(
                    self._and_expressions(
                        self._comparison_expression(*item) for item in group
                    )
                    for group in filters
                )
        return filters

    def _is_filter_tuple(self, value: Any) -> bool:
        """Return whether value is a simple (column, operator, value) filter."""
        return (
            isinstance(value, tuple)
            and len(value) == 3
            and isinstance(value[0], str)
            and isinstance(value[1], str)
        )

    def _comparison_expression(self, column: str, operator: str, value: Any) -> Any:
        """Create a PyArrow dataset comparison expression."""
        field = ds.field(column)
        if operator in {"=", "=="}:
            return field == value
        if operator == "!=":
            return field != value
        if operator == ">":
            return field > value
        if operator == ">=":
            return field >= value
        if operator == "<":
            return field < value
        if operator == "<=":
            return field <= value
        if operator.lower() == "in":
            return field.isin(value)
        if operator.lower() in {"not in", "not_in"}:
            return ~field.isin(value)
        raise ValidationError(f"Unsupported Parquet filter operator: {operator}")

    def _and_expressions(self, expressions: Iterable[Any]) -> Any:
        """Combine expressions with AND."""
        expression_list = list(expressions)
        if not expression_list:
            return None
        combined = expression_list[0]
        for expression in expression_list[1:]:
            combined = combined & expression
        return combined

    def _or_expressions(self, expressions: Iterable[Any]) -> Any:
        """Combine expressions with OR."""
        expression_list = [expr for expr in expressions if expr is not None]
        if not expression_list:
            return None
        combined = expression_list[0]
        for expression in expression_list[1:]:
            combined = combined | expression
        return combined
