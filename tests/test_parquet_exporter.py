"""Unit tests for Apache Parquet exporter."""

import shutil
import tempfile
import unittest
from pathlib import Path

try:
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False

from semantica.export import ParquetExporter
from semantica.export.parquet_exporter import ENTITY_SCHEMA, RELATIONSHIP_SCHEMA


@unittest.skipIf(not PARQUET_AVAILABLE, "pyarrow not installed")
class TestParquetExporter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.entities = [
            {
                "id": "e1",
                "type": "Person",
                "name": "Alice",
                "confidence": 0.95,
                "start": 0,
                "end": 5,
                "metadata": {"age": 30},
            },
            {
                "id": "e2",
                "type": "Organization",
                "text": "Acme Corp",
                "confidence": 0.88,
                "metadata": {"location": "NY"},
            },
        ]
        self.relationships = [
            {
                "id": "r1",
                "source": "e1",
                "target": "e2",
                "type": "WORKS_FOR",
                "confidence": 0.91,
                "metadata": {"since": 2020},
            }
        ]
        self.kg = {
            "entities": self.entities,
            "relationships": self.relationships,
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_export_entities_and_read_back(self):
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "entities.parquet"

        exporter.export_entities(self.entities, output_path)

        self.assertTrue(output_path.exists())
        table = pq.read_table(output_path)

        self.assertEqual(table.num_rows, 2)
        self.assertEqual(table.schema, ENTITY_SCHEMA)
        self.assertEqual(table.column("id")[0].as_py(), "e1")
        self.assertEqual(table.column("type")[1].as_py(), "Organization")

    def test_export_relationships_and_read_back(self):
        exporter = ParquetExporter()
        output_path = Path(self.test_dir) / "relationships.parquet"

        exporter.export_relationships(self.relationships, output_path)

        self.assertTrue(output_path.exists())
        table = pq.read_table(output_path)

        self.assertEqual(table.num_rows, 1)
        self.assertEqual(table.schema, RELATIONSHIP_SCHEMA)
        self.assertEqual(table.column("source_id")[0].as_py(), "e1")
        self.assertEqual(table.column("target_id")[0].as_py(), "e2")

    def test_export_knowledge_graph_end_to_end(self):
        exporter = ParquetExporter()
        base_path = Path(self.test_dir) / "kg_output"

        exporter.export_knowledge_graph(self.kg, base_path)

        entities_path = Path(self.test_dir) / "kg_output_entities.parquet"
        relationships_path = Path(self.test_dir) / "kg_output_relationships.parquet"

        self.assertTrue(entities_path.exists())
        self.assertTrue(relationships_path.exists())

        entities_table = pq.read_table(entities_path)
        relationships_table = pq.read_table(relationships_path)

        self.assertEqual(entities_table.num_rows, 2)
        self.assertEqual(relationships_table.num_rows, 1)
        self.assertEqual(entities_table.schema, ENTITY_SCHEMA)
        self.assertEqual(relationships_table.schema, RELATIONSHIP_SCHEMA)


if __name__ == "__main__":
    unittest.main()
