from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from semantica.ingest import (  # noqa: E402
    ParquetData,
    ParquetIngestor,
    ingest,
    ingest_file,
    ingest_parquet,
    list_available_methods,
)
from semantica.ingest.file_ingestor import FileTypeDetector  # noqa: E402
from semantica.utils.exceptions import ValidationError  # noqa: E402


@pytest.fixture
def sample_parquet(tmp_path: Path) -> Path:
    path = tmp_path / "events.parquet"
    table = pa.table(
        {
            "id": [1, 2, 3],
            "name": ["alpha", "beta", "gamma"],
            "score": [0.7, 0.8, 0.9],
            "city": ["Pune", "Delhi", "Mumbai"],
        }
    )
    pq.write_table(table, path, compression="snappy")
    return path


@pytest.fixture
def partitioned_parquet(tmp_path: Path) -> Path:
    root = tmp_path / "events_partitioned"

    us_2025 = root / "country=US" / "year=2025"
    us_2025.mkdir(parents=True)
    pq.write_table(
        pa.table({"id": [1, 2], "value": ["a", "b"]}),
        us_2025 / "part-0.parquet",
        compression="gzip",
    )

    ca_2026 = root / "country=CA" / "year=2026"
    ca_2026.mkdir(parents=True)
    pq.write_table(
        pa.table({"id": [3], "value": ["c"]}),
        ca_2026 / "part-1.parquet",
        compression="gzip",
    )

    return root


def test_parquet_file_ingestion_reads_data_schema_and_metadata(
    sample_parquet: Path,
) -> None:
    ingestor = ParquetIngestor()

    result = ingestor.ingest_file(sample_parquet)

    assert isinstance(result, ParquetData)
    assert result.row_count == 3
    assert result.columns == ["id", "name", "score", "city"]
    assert result.data[0]["name"] == "alpha"
    assert result.schema["columns"] == ["id", "name", "score", "city"]
    assert result.schema["fields"][0]["type"] == "int64"
    assert result.metadata["total_rows"] == 3
    assert result.metadata["row_groups"] == 1
    assert result.metadata["compression_codecs"] == ["SNAPPY"]


def test_parquet_selective_column_reading_with_limit(sample_parquet: Path) -> None:
    ingestor = ParquetIngestor()

    result = ingestor.ingest_file(sample_parquet, columns=["id", "name"], limit=2)

    assert result.row_count == 2
    assert result.columns == ["id", "name"]
    assert result.data == [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]
    assert result.metadata["selected_columns"] == ["id", "name"]
    assert result.metadata["limit"] == 2


def test_parquet_schema_and_metadata_can_be_extracted_without_rows(
    sample_parquet: Path,
) -> None:
    ingestor = ParquetIngestor()

    schema = ingestor.extract_schema(sample_parquet)
    metadata = ingestor.extract_metadata(sample_parquet)
    result = ingestor.ingest_file(sample_parquet, include_data=False)

    assert schema["columns"] == ["id", "name", "score", "city"]
    assert metadata["total_rows"] == 3
    assert metadata["format"] == "parquet"
    assert result.row_count == 0
    assert result.data == []
    assert result.metadata["include_data"] is False


def test_partitioned_parquet_directory_ingestion(partitioned_parquet: Path) -> None:
    ingestor = ParquetIngestor()

    result = ingestor.ingest_directory(partitioned_parquet)

    assert result.row_count == 3
    assert set(result.columns) == {"id", "value", "country", "year"}
    assert {row["country"] for row in result.data} == {"US", "CA"}
    assert result.metadata["file_count"] == 2
    assert result.metadata["total_rows"] == 3
    assert result.metadata["partition_columns"] == ["country", "year"]
    assert result.metadata["partition_values"] == {
        "country": ["CA", "US"],
        "year": ["2025", "2026"],
    }
    assert result.metadata["compression_codecs"] == ["GZIP"]


def test_parquet_convenience_methods_and_unified_dispatch(sample_parquet: Path) -> None:
    direct = ingest_parquet(sample_parquet, columns=["name"])
    via_file_method = ingest_file(sample_parquet, method="parquet", limit=1)
    unified = ingest(sample_parquet)
    unified_batch = ingest([sample_parquet])
    methods = list_available_methods("parquet")

    assert isinstance(direct, ParquetData)
    assert direct.columns == ["name"]
    assert isinstance(via_file_method, ParquetData)
    assert via_file_method.row_count == 1
    assert isinstance(unified["data"], ParquetData)
    assert isinstance(unified_batch["data"][0], ParquetData)
    assert "metadata" in methods["parquet"]


def test_file_type_detector_recognizes_parquet_magic_number() -> None:
    detector = FileTypeDetector()

    assert detector.detect_type("dataset", content=b"PAR1payload") == "parquet"
    assert detector.is_supported("parquet")


def test_parquet_ingestion_rejects_negative_limit(sample_parquet: Path) -> None:
    ingestor = ParquetIngestor()

    with pytest.raises(ValidationError):
        ingestor.ingest_file(sample_parquet, limit=-1)
