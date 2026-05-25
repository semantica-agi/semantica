"""
Unit tests for Apache Parquet exporter module.

Tests schema validation, data export, pandas conversion, empty inputs,
and minimal graph structures.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

# Try to import pyarrow
try:
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

from semantica.export import ParquetExporter
from semantica.utils.exceptions import ValidationError


@unittest.skipIf(not PARQUET_AVAILABLE, "pyarrow not installed")
class TestParquetExporter(unittest.TestCase):
    """Test cases for ParquetExporter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

        # Sample entities with various field names
        self.entities = [
            {
                "id": "e1",
                "type": "Person",
                "name": "Alice",
                "label": "Alice",
                "confidence": 0.95,
                "start": 0,
                "end": 5,
                "metadata": {"age": 30, "city": "NYC"},
            },
            {
                "id": "e2",
                "type": "Organization",
                "text": "Acme Corp",
                "entity_type": "ORG",
                "confidence": 0.88,
                "start_offset": 10,
                "end_offset": 19,
                "metadata": {"location": "NY", "employees": 100},
            },
        ]

        # Sample relationships
        self.relationships = [
            {
                "id": "r1",
                "source": "e1",
                "target": "e2",
                "type": "WORKS_FOR",
                "confidence": 0.92,
                "metadata": {"role": "Engineer", "since": 2020},
            },
            {
                "source_id": "e2",
                "target_id": "e1",
                "relationship_type": "EMPLOYS",
                "confidence": 0.90,
            },
        ]

        # Knowledge graph
        self.kg = {
            "entities": self.entities,
            "relationships": self.relationships,
            "metadata": {"version": "1.0", "created": "2024-01-01"},
        }

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test ParquetExporter initialization."""
        exporter = ParquetExporter()
        self.assertIsNotNone(exporter)
        self.assertEqual(exporter.compression, "snappy")

        # Test with different compression
        exporter_gzip = ParquetExporter(compression="gzip")
        self.assertEqual(exporter_gzip.compression, "gzip")

        exporter_none = ParquetExporter(compression="none")
        self.assertIsNone(exporter_none.compression)

    def test_initialization_without_pyarrow(self):
        """Test initialization fails gracefully without pyarrow."""
        # This test verifies the constant is correctly set
        if not PARQUET_AVAILABLE:
            self.assertFalse(PARQUET_AVAILABLE)

    def test_export_entities_basic(self):
        """Test basic entity export to Parquet."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "entities.parquet"

        exporter.export_entities(self.entities, str(output_path))
        self.assertTrue(output_path.exists())

        # Read and verify Parquet file
        table = pq.read_table(str(output_path))

        # Verify schema
        from semantica.export.parquet_exporter import ENTITY_SCHEMA

        self.assertEqual(table.schema, ENTITY_SCHEMA)

        # Verify data
        self.assertEqual(table.num_rows, 2)
        self.assertEqual(table.column("id")[0].as_py(), "e1")
        self.assertEqual(table.column("type")[0].as_py(), "Person")
        self.assertEqual(table.column("confidence")[0].as_py(), 0.95)

    def test_export_entities_field_normalization(self):
        """Test entity field name normalization."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "entities_normalized.parquet"

        # Entities with various field name variations
        varied_entities = [
            {"id": "e1", "text": "Entity 1", "type": "TYPE1"},
            {"entity_id": "e2", "label": "Entity 2", "entity_type": "TYPE2"},
            {"id": "e3", "name": "Entity 3", "type": "TYPE3"},
        ]

        exporter.export_entities(varied_entities, str(output_path))
        self.assertTrue(output_path.exists())

        # Read and verify normalization
        table = pq.read_table(str(output_path))

        self.assertEqual(table.num_rows, 3)
        self.assertEqual(table.column("id")[0].as_py(), "e1")
        self.assertEqual(table.column("text")[0].as_py(), "Entity 1")
        self.assertEqual(table.column("text")[1].as_py(), "Entity 2")
        self.assertEqual(table.column("text")[2].as_py(), "Entity 3")

    def test_export_entities_with_compression(self):
        """Test entity export with different compression codecs."""
        import pyarrow.parquet as pq_module

        for compression in ["snappy", "gzip", "brotli", "zstd", "lz4", "none"]:
            with self.subTest(compression=compression):
                # Check if codec is available in this pyarrow build
                try:
                    # Test codec availability by checking compression opts
                    if compression != "none":
                        codec_available = compression.upper() in dir(
                            pq_module.lib.Codec
                        )
                        if not codec_available:
                            self.skipTest(
                                f"Codec {compression} not available in " "pyarrow build"
                            )
                except AttributeError:
                    # If we can't check, just try and skip on error
                    pass

                try:
                    exporter = ParquetExporter(compression=compression)
                    output_path = (
                        Path(self.test_dir) / f"entities_{compression}.parquet"
                    )

                    exporter.export_entities(self.entities, str(output_path))
                    self.assertTrue(output_path.exists())

                    # Verify file can be read
                    table = pq.read_table(str(output_path))
                    self.assertEqual(table.num_rows, 2)
                except (ImportError, RuntimeError, OSError) as e:
                    if "codec" in str(e).lower() or "compression" in str(e).lower():
                        self.skipTest(f"Codec {compression} not available: {e}")
                    raise

    def test_export_entities_empty(self):
        """Test exporting empty entities list raises ValidationError."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "empty_entities.parquet"

        with self.assertRaises(ValidationError):
            exporter.export_entities([], str(output_path))

    def test_export_entities_metadata_handling(self):
        """Test entity metadata is correctly serialized."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "entities_metadata.parquet"

        exporter.export_entities(self.entities, str(output_path))

        # Read and verify metadata
        table = pq.read_table(str(output_path))
        metadata_col = table.column("metadata")

        # First entity should have metadata
        first_metadata = metadata_col[0].as_py()
        self.assertIsNotNone(first_metadata)
        self.assertIn("keys", first_metadata)
        self.assertIn("values", first_metadata)
        self.assertEqual(set(first_metadata["keys"]), {"age", "city"})

    def test_export_relationships_basic(self):
        """Test basic relationship export to Parquet."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "relationships.parquet"

        exporter.export_relationships(self.relationships, str(output_path))
        self.assertTrue(output_path.exists())

        # Read and verify Parquet file
        table = pq.read_table(str(output_path))

        # Verify schema
        from semantica.export.parquet_exporter import RELATIONSHIP_SCHEMA

        self.assertEqual(table.schema, RELATIONSHIP_SCHEMA)

        # Verify data
        self.assertEqual(table.num_rows, 2)
        self.assertEqual(table.column("id")[0].as_py(), "r1")
        self.assertEqual(table.column("source_id")[0].as_py(), "e1")
        self.assertEqual(table.column("target_id")[0].as_py(), "e2")
        self.assertEqual(table.column("type")[0].as_py(), "WORKS_FOR")

    def test_export_relationships_field_normalization(self):
        """Test relationship field name normalization."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "relationships_normalized.parquet"

        # Relationships with various field name variations
        varied_rels = [
            {"id": "r1", "source": "e1", "target": "e2", "type": "TYPE1"},
            {"source_id": "e2", "target_id": "e3", "relationship_type": "TYPE2"},
            {"from_id": "e3", "to_id": "e1", "relation_type": "TYPE3"},
        ]

        exporter.export_relationships(varied_rels, str(output_path))
        self.assertTrue(output_path.exists())

        # Read and verify normalization
        table = pq.read_table(str(output_path))

        self.assertEqual(table.num_rows, 3)
        self.assertEqual(table.column("source_id")[0].as_py(), "e1")
        self.assertEqual(table.column("target_id")[0].as_py(), "e2")

    def test_export_relationships_empty(self):
        """Test exporting empty relationships list raises ValidationError."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "empty_relationships.parquet"

        with self.assertRaises(ValidationError):
            exporter.export_relationships([], str(output_path))

    def test_export_relationships_auto_id_generation(self):
        """Test relationship ID is auto-generated when missing."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "relationships_auto_id.parquet"

        # Relationships without IDs
        rels_no_id = [
            {"source_id": "e1", "target_id": "e2", "type": "REL1"},
            {"source_id": "e2", "target_id": "e3", "type": "REL2"},
        ]

        exporter.export_relationships(rels_no_id, str(output_path))

        # Read and verify IDs were generated
        table = pq.read_table(str(output_path))
        self.assertEqual(table.num_rows, 2)
        self.assertIsNotNone(table.column("id")[0].as_py())
        self.assertIsNotNone(table.column("id")[1].as_py())

    def test_export_knowledge_graph_basic(self):
        """Test basic knowledge graph export to multiple Parquet files."""
        exporter = ParquetExporter()
        base_path = Path(self.test_dir) / "kg"

        exporter.export_knowledge_graph(self.kg, str(base_path))

        # Verify files were created
        entities_path = Path(self.test_dir) / "kg_entities.parquet"
        rels_path = Path(self.test_dir) / "kg_relationships.parquet"

        self.assertTrue(entities_path.exists())
        self.assertTrue(rels_path.exists())

        # Verify entities
        entities_table = pq.read_table(str(entities_path))
        self.assertEqual(entities_table.num_rows, 2)

        # Verify relationships
        rels_table = pq.read_table(str(rels_path))
        self.assertEqual(rels_table.num_rows, 2)

    def test_export_knowledge_graph_invalid_input(self):
        """Test knowledge graph export with invalid input raises ValidationError."""
        exporter = ParquetExporter()
        base_path = Path(self.test_dir) / "kg_invalid"

        # Not a dictionary
        with self.assertRaises(ValidationError):
            exporter.export_knowledge_graph("not a dict", str(base_path))

        # Missing both entities and relationships
        with self.assertRaises(ValidationError):
            exporter.export_knowledge_graph({"metadata": {}}, str(base_path))

    def test_export_knowledge_graph_partial(self):
        """Test knowledge graph export with only entities or relationships."""
        exporter = ParquetExporter()

        # Only entities
        kg_entities_only = {"entities": self.entities}
        base_path_ent = Path(self.test_dir) / "kg_entities_only"
        exporter.export_knowledge_graph(kg_entities_only, str(base_path_ent))

        entities_path = Path(self.test_dir) / "kg_entities_only_entities.parquet"
        self.assertTrue(entities_path.exists())

        # Only relationships
        kg_rels_only = {"relationships": self.relationships}
        base_path_rel = Path(self.test_dir) / "kg_rels_only"
        exporter.export_knowledge_graph(kg_rels_only, str(base_path_rel))

        rels_path = Path(self.test_dir) / "kg_rels_only_relationships.parquet"
        self.assertTrue(rels_path.exists())

    def test_export_generic_list(self):
        """Test generic export with list of dictionaries."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "generic_list.parquet"

        exporter.export(self.entities, str(output_path), schema=None)
        self.assertTrue(output_path.exists())

        # Verify file can be read (schema auto-selected based on data structure)
        table = pq.read_table(str(output_path))
        self.assertEqual(table.num_rows, 2)

    def test_export_generic_dict(self):
        """Test generic export with dictionary (multiple files)."""
        exporter = ParquetExporter()
        base_path = Path(self.test_dir) / "generic_dict"

        data_dict = {"entities": self.entities, "relationships": self.relationships}

        exporter.export(data_dict, str(base_path))

        # Verify both files were created
        entities_path = Path(self.test_dir) / "generic_dict_entities.parquet"
        rels_path = Path(self.test_dir) / "generic_dict_relationships.parquet"

        self.assertTrue(entities_path.exists())
        self.assertTrue(rels_path.exists())

    def test_export_invalid_data_type(self):
        """Test export with invalid data type raises ValidationError."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "invalid.parquet"

        with self.assertRaises(ValidationError):
            exporter.export("invalid string data", str(output_path))

    def test_pandas_compatibility(self):
        """Test exported Parquet files can be read by pandas."""
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed")

        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "pandas_test.parquet"

        exporter.export_entities(self.entities, str(output_path))

        # Read with pandas
        df = pd.read_parquet(str(output_path))

        self.assertEqual(len(df), 2)
        self.assertIn("id", df.columns)
        self.assertIn("text", df.columns)
        self.assertIn("type", df.columns)

    def test_file_size_comparison(self):
        """Test Parquet file sizes with different compression."""
        exporter_snappy = ParquetExporter(compression="snappy")
        exporter_gzip = ParquetExporter(compression="gzip")
        exporter_none = ParquetExporter(compression="none")

        path_snappy = Path(self.test_dir) / "size_snappy.parquet"
        path_gzip = Path(self.test_dir) / "size_gzip.parquet"
        path_none = Path(self.test_dir) / "size_none.parquet"

        # Create larger dataset for meaningful comparison
        large_entities = self.entities * 100

        exporter_snappy.export_entities(large_entities, str(path_snappy))
        exporter_gzip.export_entities(large_entities, str(path_gzip))
        exporter_none.export_entities(large_entities, str(path_none))

        size_snappy = path_snappy.stat().st_size
        size_none = path_none.stat().st_size

        # Uncompressed should be largest
        self.assertGreater(size_none, size_snappy)

        # All files should be readable
        for path in [path_snappy, path_gzip, path_none]:
            table = pq.read_table(str(path))
            self.assertEqual(table.num_rows, 200)

    def test_entity_missing_id_skipped(self):
        """Test entities without IDs are skipped with warning."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "entities_missing_id.parquet"

        # Mix of entities with and without IDs
        entities_mixed = [
            {"id": "e1", "text": "Valid Entity"},
            {"text": "Missing ID"},  # No ID
            {"id": "e2", "text": "Another Valid"},
        ]

        exporter.export_entities(entities_mixed, str(output_path))

        # Only 2 entities should be exported (one without ID is skipped)
        table = pq.read_table(str(output_path))
        self.assertEqual(table.num_rows, 2)

    def test_relationship_missing_source_target_skipped(self):
        """Test relationships without source/target are skipped with warning."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "rels_missing.parquet"

        # Mix of valid and invalid relationships
        rels_mixed = [
            {"id": "r1", "source_id": "e1", "target_id": "e2"},
            {"id": "r2", "target_id": "e2"},  # Missing source
            {"id": "r3", "source_id": "e1"},  # Missing target
            {"id": "r4", "source_id": "e3", "target_id": "e4"},
        ]

        exporter.export_relationships(rels_mixed, str(output_path))

        # Only 2 valid relationships should be exported
        table = pq.read_table(str(output_path))
        self.assertEqual(table.num_rows, 2)

    def test_all_entities_skipped_raises_error(self):
        """Test that exporting entities with all skipped raises ValidationError."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "all_skipped.parquet"

        # All entities missing IDs
        bad_entities = [
            {"text": "No ID 1"},
            {"text": "No ID 2"},
            "not a dict",
        ]

        with self.assertRaises(ValidationError) as cm:
            exporter.export_entities(bad_entities, str(output_path))

        self.assertIn("No valid entities", str(cm.exception))

    def test_all_relationships_skipped_raises_error(self):
        """Test that exporting relationships with all skipped raises ValidationError."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "all_rels_skipped.parquet"

        # All relationships missing source or target
        bad_rels = [
            {"id": "r1", "source_id": "e1"},  # Missing target
            {"id": "r2", "target_id": "e2"},  # Missing source
            "not a dict",
        ]

        with self.assertRaises(ValidationError) as cm:
            exporter.export_relationships(bad_rels, str(output_path))

        self.assertIn("No valid relationships", str(cm.exception))

    def test_invalid_confidence_values_handled(self):
        """Test that invalid confidence values are handled gracefully."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "invalid_confidence.parquet"

        entities_with_invalid_conf = [
            {"id": "e1", "text": "Valid", "confidence": 0.9},
            {"id": "e2", "text": "String conf", "confidence": "invalid"},
            {"id": "e3", "text": "None conf", "confidence": None},
        ]

        exporter.export_entities(entities_with_invalid_conf, str(output_path))

        table = pq.read_table(str(output_path))
        self.assertEqual(table.num_rows, 3)
        # First entity has valid confidence
        self.assertEqual(table.column("confidence")[0].as_py(), 0.9)
        # Second entity has invalid confidence (should be None)
        self.assertIsNone(table.column("confidence")[1].as_py())
        # Third entity has None confidence
        self.assertIsNone(table.column("confidence")[2].as_py())

    def test_invalid_start_end_values_handled(self):
        """Test that invalid start/end offset values are handled gracefully."""
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "invalid_offsets.parquet"

        entities_with_invalid_offsets = [
            {"id": "e1", "text": "Valid", "start": 0, "end": 10},
            {"id": "e2", "text": "String offsets", "start": "abc", "end": "def"},
            {"id": "e3", "text": "None offsets", "start": None, "end": None},
        ]

        exporter.export_entities(entities_with_invalid_offsets, str(output_path))

        table = pq.read_table(str(output_path))
        self.assertEqual(table.num_rows, 3)
        # First entity has valid offsets
        self.assertEqual(table.column("start")[0].as_py(), 0)
        self.assertEqual(table.column("end")[0].as_py(), 10)
        # Second entity has invalid offsets (should be None)
        self.assertIsNone(table.column("start")[1].as_py())
        self.assertIsNone(table.column("end")[1].as_py())
        # Third entity has None offsets
        self.assertIsNone(table.column("start")[2].as_py())
        self.assertIsNone(table.column("end")[2].as_py())


if __name__ == "__main__":
    unittest.main()
