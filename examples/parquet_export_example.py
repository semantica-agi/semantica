"""
Apache Parquet Exporter - Example Usage

This script demonstrates how to use the ParquetExporter to export
knowledge graphs, entities, and relationships to Apache Parquet format.
"""

import tempfile
from pathlib import Path

from semantica.export import ParquetExporter, export_parquet


def main():
    print("=" * 70)
    print("Apache Parquet Exporter - Example Usage")
    print("=" * 70)

    # Create a temporary directory for outputs
    temp_dir = Path(tempfile.mkdtemp())
    print(f"\n📁 Output directory: {temp_dir}\n")

    # Sample data
    entities = [
        {
            "id": "e1",
            "text": "Alice",
            "type": "Person",
            "confidence": 0.95,
            "start": 0,
            "end": 5,
            "metadata": {"age": 30, "city": "New York"},
        },
        {
            "id": "e2",
            "text": "Acme Corp",
            "type": "Organization",
            "confidence": 0.88,
            "start": 10,
            "end": 19,
            "metadata": {"location": "NY", "employees": 100},
        },
        {
            "id": "e3",
            "text": "Bob",
            "type": "Person",
            "confidence": 0.92,
            "metadata": {"age": 35, "department": "Engineering"},
        },
    ]

    relationships = [
        {
            "id": "r1",
            "source_id": "e1",
            "target_id": "e2",
            "type": "WORKS_FOR",
            "confidence": 0.90,
            "metadata": {"role": "Engineer", "since": 2020},
        },
        {
            "id": "r2",
            "source_id": "e3",
            "target_id": "e2",
            "type": "WORKS_FOR",
            "confidence": 0.85,
            "metadata": {"role": "Manager", "since": 2018},
        },
    ]

    knowledge_graph = {
        "entities": entities,
        "relationships": relationships,
        "metadata": {"version": "1.0", "created": "2024-01-01"},
    }

    # Example 1: Export entities using ParquetExporter class
    print("Example 1: Export entities to Parquet")
    print("-" * 70)
    exporter = ParquetExporter(compression="snappy")
    entities_path = temp_dir / "entities.parquet"
    exporter.export_entities(entities, entities_path)
    print(f"✓ Entities exported to: {entities_path}")
    print(f"  File size: {entities_path.stat().st_size} bytes\n")

    # Example 2: Export relationships
    print("Example 2: Export relationships to Parquet")
    print("-" * 70)
    rels_path = temp_dir / "relationships.parquet"
    exporter.export_relationships(relationships, rels_path)
    print(f"✓ Relationships exported to: {rels_path}")
    print(f"  File size: {rels_path.stat().st_size} bytes\n")

    # Example 3: Export complete knowledge graph
    print("Example 3: Export knowledge graph to multiple Parquet files")
    print("-" * 70)
    kg_base_path = temp_dir / "knowledge_graph"
    exporter.export_knowledge_graph(knowledge_graph, kg_base_path)
    kg_entities = temp_dir / "knowledge_graph_entities.parquet"
    kg_rels = temp_dir / "knowledge_graph_relationships.parquet"
    print("✓ Knowledge graph exported to:")
    print(f"  - {kg_entities} ({kg_entities.stat().st_size} bytes)")
    print(f"  - {kg_rels} ({kg_rels.stat().st_size} bytes)\n")

    # Example 4: Using convenience function
    print("Example 4: Using export_parquet convenience function")
    print("-" * 70)
    conv_path = temp_dir / "convenience_export.parquet"
    export_parquet(entities, conv_path, compression="gzip")
    print(f"✓ Exported using convenience function: {conv_path}")
    print(f"  File size: {conv_path.stat().st_size} bytes\n")

    # Example 5: Different compression codecs
    print("Example 5: Compare compression codecs")
    print("-" * 70)

    # Create larger dataset for meaningful comparison
    large_entities = entities * 50

    compression_codecs = ["snappy", "gzip", "brotli", "zstd", "lz4", "none"]
    sizes = {}

    for codec in compression_codecs:
        codec_exporter = ParquetExporter(compression=codec)
        codec_path = temp_dir / f"entities_{codec}.parquet"
        codec_exporter.export_entities(large_entities, codec_path)
        sizes[codec] = codec_path.stat().st_size
        print(f"  {codec:8} - {sizes[codec]:,} bytes")

    print()

    # Example 6: Load Parquet with pandas (if available)
    print("Example 6: Loading Parquet files with pandas")
    print("-" * 70)
    try:
        import pandas as pd

        df = pd.read_parquet(entities_path)
        print("✓ Loaded entities as pandas DataFrame")
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
        print()

    except ImportError:
        print("⚠ pandas not installed - skipping pandas example\n")

    # Example 7: Load Parquet with pyarrow
    print("Example 7: Loading Parquet files with pyarrow")
    print("-" * 70)
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(entities_path)
        print("✓ Loaded entities as Arrow Table")
        print(f"  Rows: {table.num_rows}")
        print(f"  Columns: {table.num_columns}")
        print("  Schema:")
        for i, field in enumerate(table.schema):
            print(f"    - {field.name}: {field.type}")
        print()

    except ImportError:
        print("⚠ pyarrow not installed - skipping pyarrow example\n")

    # Example 8: Schema validation
    print("Example 8: Explicit schema validation")
    print("-" * 70)
    try:
        import pyarrow.parquet as pq

        # Read parquet file and verify schema
        table = pq.read_table(entities_path)

        print("✓ Schema validation:")
        print(f"  - ID column type: {table.schema.field('id').type}")
        print(f"  - Text column type: {table.schema.field('text').type}")
        print(f"  - Confidence column type: {table.schema.field('confidence').type}")
        print(f"  - Metadata column type: {table.schema.field('metadata').type}")
        print()

        # Verify metadata structure
        metadata_field = table.schema.field("metadata")
        print("  Metadata structure:")
        if hasattr(metadata_field.type, "num_fields"):
            for i in range(metadata_field.type.num_fields):
                subfield = metadata_field.type.field(i)
                print(f"    - {subfield.name}: {subfield.type}")
        print()

    except Exception as e:
        print(f"⚠ Schema validation error: {e}\n")

    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print("✓ All examples completed successfully")
    print(f"✓ Output directory: {temp_dir}")
    print(f"✓ Files created: {len(list(temp_dir.glob('*.parquet')))}")
    print("\nKey Features:")
    print("  - Columnar storage optimized for analytics")
    print("  - Multiple compression options (snappy, gzip, brotli, zstd, lz4)")
    print("  - Compatible with pandas, Spark, Snowflake, BigQuery, Databricks")
    print("  - Explicit schemas for type safety")
    print("  - Structured metadata handling")
    print("\nFor more information, see the Semantica documentation.")
    print("=" * 70)


if __name__ == "__main__":
    main()
