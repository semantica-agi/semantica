"""
Unit tests for Apache Arrow exporter module.

Tests schema validation, data export, Pandas conversion, empty inputs,
and minimal graph structures.
"""

import os
import unittest
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Try to import pyarrow
try:
    import pyarrow as pa
    import pyarrow.ipc as ipc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

from semantica.export import ArrowExporter
from semantica.utils.exceptions import ValidationError, ProcessingError


@unittest.skipIf(not ARROW_AVAILABLE, "pyarrow not installed")
class TestArrowExporter(unittest.TestCase):
    """Test cases for ArrowExporter class."""

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
                "metadata": {"age": 30, "city": "NYC"}
            },
            {
                "id": "e2",
                "type": "Organization",
                "text": "Acme Corp",
                "entity_type": "ORG",
                "confidence": 0.88,
                "start_offset": 10,
                "end_offset": 19,
                "metadata": {"location": "NY", "employees": 100}
            }
        ]
        
        # Sample relationships
        self.relationships = [
            {
                "id": "r1",
                "source": "e1",
                "target": "e2",
                "type": "WORKS_FOR",
                "confidence": 0.92,
                "metadata": {"role": "Engineer", "since": 2020}
            },
            {
                "source_id": "e2",
                "target_id": "e1",
                "relationship_type": "EMPLOYS",
                "confidence": 0.90
            }
        ]
        
        # Knowledge graph
        self.kg = {
            "entities": self.entities,
            "relationships": self.relationships,
            "metadata": {"version": "1.0", "created": "2024-01-01"}
        }

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test ArrowExporter initialization."""
        exporter = ArrowExporter()
        self.assertIsNotNone(exporter)
        self.assertEqual(exporter.compression, None)
        
        # Test with compression
        exporter_compressed = ArrowExporter(compression="lz4")
        self.assertEqual(exporter_compressed.compression, "lz4")

    def test_initialization_without_pyarrow(self):
        """Test initialization fails gracefully without pyarrow."""
        with patch.dict('sys.modules', {'pyarrow': None}):
            # This test would need to reload the module
            # For now, we just verify the constant
            if not ARROW_AVAILABLE:
                with self.assertRaises(ImportError):
                    from semantica.export.arrow_exporter import ArrowExporter as TestExporter

    def test_export_entities_basic(self):
        """Test basic entity export to Arrow."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities.arrow"
        
        exporter.export_entities(self.entities, str(output_path))
        self.assertTrue(output_path.exists())
        
        # Read and verify Arrow file
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                
                # Verify schema
                from semantica.export.arrow_exporter import ENTITY_SCHEMA
                self.assertEqual(table.schema, ENTITY_SCHEMA)
                
                # Verify data
                self.assertEqual(table.num_rows, 2)
                self.assertEqual(table.column('id')[0].as_py(), 'e1')
                self.assertEqual(table.column('type')[0].as_py(), 'Person')
                self.assertEqual(table.column('confidence')[0].as_py(), 0.95)

    def test_export_entities_field_normalization(self):
        """Test entity field name normalization."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities_normalized.arrow"
        
        # Entities with various field name variations
        varied_entities = [
            {"id": "e1", "text": "Entity 1", "type": "TYPE1"},
            {"entity_id": "e2", "label": "Entity 2", "entity_type": "TYPE2"},
            {"id": "e3", "name": "Entity 3", "type": "TYPE3"}
        ]
        
        exporter.export_entities(varied_entities, str(output_path))
        self.assertTrue(output_path.exists())
        
        # Read and verify normalization
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                
                self.assertEqual(table.num_rows, 3)
                # All entities should have normalized fields
                ids = table.column('id').to_pylist()
                self.assertEqual(ids, ['e1', 'e2', 'e3'])
                
                texts = table.column('text').to_pylist()
                self.assertEqual(texts, ['Entity 1', 'Entity 2', 'Entity 3'])

    def test_export_relationships_basic(self):
        """Test basic relationship export to Arrow."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "relationships.arrow"
        
        exporter.export_relationships(self.relationships, str(output_path))
        self.assertTrue(output_path.exists())
        
        # Read and verify Arrow file
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                
                # Verify data
                self.assertEqual(table.num_rows, 2)
                self.assertEqual(table.column('id')[0].as_py(), 'r1')
                self.assertEqual(table.column('source_id')[0].as_py(), 'e1')
                self.assertEqual(table.column('target_id')[0].as_py(), 'e2')
                self.assertEqual(table.column('type')[0].as_py(), 'WORKS_FOR')

    def test_export_knowledge_graph(self):
        """Test knowledge graph export to multiple Arrow files."""
        exporter = ArrowExporter()
        base_path = Path(self.test_dir) / "kg_output"
        
        exporter.export_knowledge_graph(self.kg, str(base_path))
        
        # Verify files created
        entities_path = Path(self.test_dir) / "kg_output_entities.arrow"
        relationships_path = Path(self.test_dir) / "kg_output_relationships.arrow"
        
        self.assertTrue(entities_path.exists())
        self.assertTrue(relationships_path.exists())
        
        # Verify entities file
        with pa.OSFile(str(entities_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                self.assertEqual(table.num_rows, 2)
        
        # Verify relationships file
        with pa.OSFile(str(relationships_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                self.assertEqual(table.num_rows, 2)

    def test_export_empty_entities(self):
        """Test export with empty entity list."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "empty_entities.arrow"
        
        with self.assertRaises(ValidationError) as context:
            exporter.export_entities([], str(output_path))
        
        self.assertIn("No entities to export", str(context.exception))

    def test_export_empty_relationships(self):
        """Test export with empty relationship list."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "empty_rels.arrow"
        
        with self.assertRaises(ValidationError) as context:
            exporter.export_relationships([], str(output_path))
        
        self.assertIn("No relationships to export", str(context.exception))

    def test_export_minimal_graph(self):
        """Test export with minimal knowledge graph."""
        exporter = ArrowExporter()
        base_path = Path(self.test_dir) / "minimal_kg"
        
        # Minimal graph with only entities
        minimal_kg = {
            "entities": [{"id": "e1", "text": "Entity 1", "type": "TYPE1"}],
            "relationships": []
        }
        
        exporter.export_knowledge_graph(minimal_kg, str(base_path))
        
        # Only entities file should be created
        entities_path = Path(self.test_dir) / "minimal_kg_entities.arrow"
        self.assertTrue(entities_path.exists())

    def test_metadata_serialization(self):
        """Test metadata dictionary to Arrow struct conversion."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities_metadata.arrow"
        
        entities_with_metadata = [
            {
                "id": "e1",
                "text": "Entity 1",
                "type": "TYPE1",
                "metadata": {
                    "key1": "value1",
                    "key2": 123,
                    "key3": {"nested": "dict"}
                }
            }
        ]
        
        exporter.export_entities(entities_with_metadata, str(output_path))
        self.assertTrue(output_path.exists())
        
        # Read and verify metadata structure
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                
                # Verify metadata exists and is a struct
                metadata_col = table.column('metadata')[0]
                if metadata_col.is_valid:
                    metadata = metadata_col.as_py()
                    self.assertIn('keys', metadata)
                    self.assertIn('values', metadata)
                    self.assertIsInstance(metadata['keys'], list)
                    self.assertIsInstance(metadata['values'], list)

    def test_schema_validation(self):
        """Test explicit schema validation."""
        from semantica.export.arrow_exporter import ENTITY_SCHEMA, RELATIONSHIP_SCHEMA
        
        # Verify entity schema structure
        self.assertIsNotNone(ENTITY_SCHEMA)
        self.assertIsInstance(ENTITY_SCHEMA, pa.Schema)
        
        entity_fields = {field.name for field in ENTITY_SCHEMA}
        expected_entity_fields = {'id', 'text', 'type', 'confidence', 'start', 'end', 'metadata'}
        self.assertEqual(entity_fields, expected_entity_fields)
        
        # Verify relationship schema structure
        self.assertIsNotNone(RELATIONSHIP_SCHEMA)
        self.assertIsInstance(RELATIONSHIP_SCHEMA, pa.Schema)
        
        rel_fields = {field.name for field in RELATIONSHIP_SCHEMA}
        expected_rel_fields = {'id', 'source_id', 'target_id', 'type', 'confidence', 'metadata'}
        self.assertEqual(rel_fields, expected_rel_fields)

    def test_pandas_conversion(self):
        """Test conversion to Pandas DataFrame."""
        try:
            import pandas as pd
            
            exporter = ArrowExporter()
            output_path = Path(self.test_dir) / "entities_pandas.arrow"
            
            exporter.export_entities(self.entities, str(output_path))
            
            # Read Arrow file and convert to Pandas
            with pa.OSFile(str(output_path), 'rb') as source:
                with ipc.open_file(source) as reader:
                    table = reader.read_all()
                    df = table.to_pandas()
                    
                    # Verify DataFrame
                    self.assertIsInstance(df, pd.DataFrame)
                    self.assertEqual(len(df), 2)
                    self.assertEqual(df['id'].tolist(), ['e1', 'e2'])
                    
        except ImportError:
            self.skipTest("Pandas not installed")

    def test_invalid_data_type(self):
        """Test export with invalid data type."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "invalid.arrow"
        
        # Test with string instead of list/dict
        with self.assertRaises(ValidationError):
            exporter.export("invalid_data", str(output_path))

    def test_confidence_conversion(self):
        """Test confidence value conversion to float."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities_confidence.arrow"
        
        entities_varied_confidence = [
            {"id": "e1", "text": "Entity 1", "confidence": "0.95"},  # String
            {"id": "e2", "text": "Entity 2", "confidence": 0.88},    # Float
            {"id": "e3", "text": "Entity 3", "confidence": None},    # None
        ]
        
        exporter.export_entities(entities_varied_confidence, str(output_path))
        
        # Read and verify confidence values
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                
                confidences = table.column('confidence').to_pylist()
                # First should be converted to float, third should be None
                self.assertIsInstance(confidences[0], float)
                self.assertEqual(confidences[1], 0.88)
                self.assertIsNone(confidences[2])

    def test_offset_conversion(self):
        """Test start/end offset conversion to int."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities_offsets.arrow"
        
        entities_varied_offsets = [
            {"id": "e1", "text": "Entity 1", "start": "10", "end": "20"},  # Strings
            {"id": "e2", "text": "Entity 2", "start": 30, "end": 40},      # Ints
            {"id": "e3", "text": "Entity 3", "start": None, "end": None},   # None
        ]
        
        exporter.export_entities(entities_varied_offsets, str(output_path))
        
        # Read and verify offset values
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                
                starts = table.column('start').to_pylist()
                ends = table.column('end').to_pylist()
                
                # First should be converted to int
                self.assertEqual(starts[0], 10)
                self.assertEqual(ends[0], 20)
                self.assertEqual(starts[1], 30)
                self.assertEqual(ends[1], 40)
                self.assertIsNone(starts[2])
                self.assertIsNone(ends[2])

    def test_dict_export(self):
        """Test export with dictionary containing multiple lists."""
        exporter = ArrowExporter()
        base_path = Path(self.test_dir) / "dict_export"
        
        data_dict = {
            "entities": self.entities,
            "relationships": self.relationships
        }
        
        exporter.export(data_dict, str(base_path))
        
        # Verify both files created
        entities_path = Path(self.test_dir) / "dict_export_entities.arrow"
        relationships_path = Path(self.test_dir) / "dict_export_relationships.arrow"
        
        self.assertTrue(entities_path.exists())
        self.assertTrue(relationships_path.exists())

    def test_export_preserves_endpoint_aliases(self):
        exporter = ArrowExporter()
        for source, target in (
            ("source_id", "target_id"),
            ("source", "target"),
            ("start_node_id", "end_node_id"),
            ("start_id", "end_id"),
        ):
            for collection in (None, "edges", "relationships"):
                with self.subTest(source=source, collection=collection):
                    record = {"id": "r1", source: "alice", target: "acme"}
                    record["type"] = "WORKS_AT"
                    original = dict(record)
                    data = [record] if collection is None else {collection: [record]}
                    paths = exporter.export(data, Path(self.test_dir) / "graph.arrow")
                    with ipc.open_file(str(paths[0])) as reader:
                        row = reader.read_all().to_pylist()[0]
                    self.assertEqual(row.get("source_id"), "alice")
                    self.assertEqual(row.get("target_id"), "acme")
                    self.assertEqual(row["type"], "WORKS_AT")
                    self.assertEqual(record, original)

    def test_export_preserves_numeric_endpoint_aliases(self):
        exporter = ArrowExporter()
        for source, target in (
            ("source_id", "target_id"),
            ("source", "target"),
            ("start_node_id", "end_node_id"),
            ("start_id", "end_id"),
        ):
            with self.subTest(source=source):
                record = {"id": 7, source: 0, target: 2, "type": "KNOWS"}
                original = dict(record)
                paths = exporter.export(
                    {"edges": [record]}, Path(self.test_dir) / "numeric.arrow"
                )
                with ipc.open_file(str(paths[0])) as reader:
                    row = reader.read_all().to_pylist()[0]
                self.assertEqual(row["id"], "7")
                self.assertEqual(row["source_id"], "0")
                self.assertEqual(row["target_id"], "2")
                self.assertEqual(row["type"], "KNOWS")
                self.assertEqual(record, original)

    def test_export_endpoint_detection_preserves_entity_offsets(self):
        record = {"id": "e1", "text": "Alice", "type": "PERSON", "start": 0, "end": 5}
        paths = ArrowExporter().export([record], Path(self.test_dir) / "entity.arrow")
        with ipc.open_file(str(paths[0])) as reader:
            table = reader.read_all()
        self.assertNotIn("source_id", table.column_names)
        self.assertEqual(table.to_pylist()[0]["start"], 0)
        self.assertEqual(table.to_pylist()[0]["end"], 5)

    def test_export_endpoint_detection_respects_custom_schema(self):
        schema = pa.schema(
            [("start_node_id", pa.string()), ("end_node_id", pa.string())]
        )
        records = [{"start_node_id": "alice", "end_node_id": "acme"}]
        paths = ArrowExporter().export(
            records, Path(self.test_dir) / "custom.arrow", schema=schema
        )
        with ipc.open_file(str(paths[0])) as reader:
            table = reader.read_all()
        self.assertEqual(table.schema, schema)
        self.assertEqual(table.to_pylist(), records)

    def test_progress_tracking(self):
        """Test progress tracker integration."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities_progress.arrow"
        
        # Progress tracker should be enabled
        self.assertTrue(exporter.progress_tracker.enabled)
        
        # Export should complete successfully
        exporter.export_entities(self.entities, str(output_path))
        self.assertTrue(output_path.exists())

    def test_non_dict_entity_skipping(self):
        """Test skipping non-dictionary entities."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "entities_mixed.arrow"
        
        mixed_entities = [
            {"id": "e1", "text": "Entity 1", "type": "TYPE1"},
            "invalid_entity",  # Should be skipped
            {"id": "e2", "text": "Entity 2", "type": "TYPE2"},
        ]
        
        exporter.export_entities(mixed_entities, str(output_path))
        
        # Read and verify only valid entities exported
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                self.assertEqual(table.num_rows, 2)

    def test_non_dict_relationship_skipping(self):
        """Test skipping non-dictionary relationships."""
        exporter = ArrowExporter()
        output_path = Path(self.test_dir) / "rels_mixed.arrow"
        
        mixed_rels = [
            {"id": "r1", "source_id": "e1", "target_id": "e2", "type": "TYPE1"},
            None,  # Should be skipped
            {"id": "r2", "source_id": "e2", "target_id": "e3", "type": "TYPE2"},
        ]
        
        exporter.export_relationships(mixed_rels, str(output_path))
        
        # Read and verify only valid relationships exported
        with pa.OSFile(str(output_path), 'rb') as source:
            with ipc.open_file(source) as reader:
                table = reader.read_all()
                self.assertEqual(table.num_rows, 2)


class TestArrowExporterIntegration(unittest.TestCase):
    """Integration tests for Arrow exporter with export methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.entities = [
            {"id": "e1", "text": "Entity 1", "type": "PERSON"},
            {"id": "e2", "text": "Entity 2", "type": "ORG"}
        ]

    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    @unittest.skipIf(not ARROW_AVAILABLE, "pyarrow not installed")
    def test_export_arrow_method(self):
        """Test export_arrow convenience function."""
        from semantica.export.methods import export_arrow
        
        output_path = Path(self.test_dir) / "entities_method.arrow"
        export_arrow(self.entities, str(output_path))
        
        self.assertTrue(output_path.exists())


if __name__ == '__main__':
    unittest.main()
