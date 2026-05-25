"""
Tests for ArangoDB AQL Exporter Module

This module contains comprehensive tests for the ArangoDB AQL exporter,
validating AQL syntax generation, node and edge handling, and edge cases.
"""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from semantica.export import ArangoAQLExporter


class TestArangoAQLExporter(unittest.TestCase):
    """Test cases for ArangoDB AQL Exporter."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

        # Sample entities for testing
        self.entities = [
            {
                "id": "e1",
                "type": "Person",
                "name": "Alice",
                "label": "Alice",
                "properties": {"age": 30, "email": "alice@example.com"},
            },
            {
                "id": "e2",
                "type": "Organization",
                "name": "Acme Corp",
                "label": "Acme Corp",
                "properties": {"location": "New York", "founded": 2010},
            },
            {
                "id": "e3",
                "type": "Person",
                "name": "Bob",
                "label": "Bob",
                "properties": {"age": 25},
            },
        ]

        # Sample relationships for testing
        self.relationships = [
            {
                "id": "r1",
                "source": "e1",
                "target": "e2",
                "type": "WORKS_FOR",
                "properties": {"role": "Engineer", "since": 2020},
            },
            {
                "id": "r2",
                "source": "e3",
                "target": "e2",
                "type": "WORKS_FOR",
                "properties": {"role": "Manager"},
            },
            {
                "id": "r3",
                "source": "e1",
                "target": "e3",
                "type": "KNOWS",
            },
        ]

        # Complete knowledge graph
        self.kg = {
            "entities": self.entities,
            "relationships": self.relationships,
            "metadata": {"version": "1.0", "created": "2024-01-01"},
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_exporter_initialization(self):
        """Test exporter initialization with default and custom parameters."""
        # Default initialization
        exporter = ArangoAQLExporter()
        self.assertEqual(exporter.vertex_collection, "vertices")
        self.assertEqual(exporter.edge_collection, "edges")
        self.assertEqual(exporter.batch_size, 1000)
        self.assertTrue(exporter.include_collection_creation)

        # Custom initialization
        exporter = ArangoAQLExporter(
            vertex_collection="nodes",
            edge_collection="links",
            batch_size=500,
            include_collection_creation=False,
        )
        self.assertEqual(exporter.vertex_collection, "nodes")
        self.assertEqual(exporter.edge_collection, "links")
        self.assertEqual(exporter.batch_size, 500)
        self.assertFalse(exporter.include_collection_creation)

    def test_export_knowledge_graph(self):
        """Test exporting a complete knowledge graph."""
        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "graph.aql"

        exporter.export_knowledge_graph(self.kg, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for collection creation comments
        self.assertIn("Create vertex collection", content)
        self.assertIn("Create edge collection", content)

        # Check for INSERT statements
        self.assertIn("INSERT doc INTO vertices", content)
        self.assertIn("INSERT doc INTO edges", content)

        # Check for entity data
        self.assertIn("Alice", content)
        self.assertIn("Acme Corp", content)
        self.assertIn("Bob", content)
        self.assertIn("Person", content)
        self.assertIn("Organization", content)

        # Check for relationship data
        self.assertIn("WORKS_FOR", content)
        self.assertIn("KNOWS", content)
        self.assertIn("vertices/e1", content)
        self.assertIn("vertices/e2", content)

    def test_export_entities_only(self):
        """Test exporting only entities (vertices)."""
        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "entities.aql"

        exporter.export_entities(self.entities, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for vertices INSERT
        self.assertIn("INSERT doc INTO vertices", content)
        self.assertIn("Alice", content)
        self.assertIn("Acme Corp", content)

        # Check that edges are NOT present (empty relationships)
        self.assertIn("Attempting to insert 0 edges", content)

    def test_export_relationships_only(self):
        """Test exporting only relationships (edges)."""
        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "relationships.aql"

        exporter.export_relationships(self.relationships, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for edges INSERT
        self.assertIn("INSERT doc INTO edges", content)
        self.assertIn("WORKS_FOR", content)
        self.assertIn("KNOWS", content)

        # Check that vertices section indicates 0 vertices
        self.assertIn("Inserting 0 vertices", content)

    def test_custom_collection_names(self):
        """Test exporting with custom collection names."""
        exporter = ArangoAQLExporter(
            vertex_collection="custom_nodes", edge_collection="custom_edges"
        )
        output_path = Path(self.test_dir) / "custom.aql"

        exporter.export(self.kg, str(output_path))

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for custom collection names
        self.assertIn("INSERT doc INTO custom_nodes", content)
        self.assertIn("INSERT doc INTO custom_edges", content)
        self.assertIn("custom_nodes/e1", content)

    def test_special_characters_in_properties(self):
        """Test handling of special characters in node and edge properties."""
        special_entities = [
            {
                "id": "special_1",
                "type": "Person",
                "name": "O'Brien",
                "properties": {"quote": 'She said "hello"', "path": "C:\\Users\\test"},
            }
        ]

        special_relationships = [
            {
                "id": "special_r1",
                "source": "special_1",
                "target": "e1",
                "type": "KNOWS",
                "properties": {"note": "Uses 'quotes' and \"escapes\""},
            }
        ]

        kg = {"entities": special_entities, "relationships": special_relationships}

        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "special_chars.aql"

        exporter.export(kg, str(output_path))

        # Verify file was created and is valid JSON structure
        self.assertTrue(output_path.exists())

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # The content should contain the special characters properly escaped in JSON
        self.assertIn("O'Brien", content)
        self.assertIn("She said", content)

    def test_empty_collections(self):
        """Test handling of empty entity and relationship collections."""
        empty_kg = {"entities": [], "relationships": []}

        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "empty.aql"

        exporter.export(empty_kg, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Should have collection creation comments but no INSERT statements
        self.assertIn("Inserting 0 vertices", content)
        self.assertIn("Attempting to insert 0 edges", content)

    def test_missing_source_or_target(self):
        """Test handling of edges with missing source or target."""
        invalid_relationships = [
            {"id": "r_invalid_1", "source": "e1", "type": "KNOWS"},  # Missing target
            {"id": "r_invalid_2", "target": "e2", "type": "RELATED"},  # Missing source
            {
                "id": "r_valid",
                "source": "e1",
                "target": "e2",
                "type": "VALID",
            },  # Valid
        ]

        kg = {"entities": self.entities, "relationships": invalid_relationships}

        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "invalid_edges.aql"

        # Should not raise an exception, but should skip invalid edges
        exporter.export(kg, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # The data section should only contain the valid relationship
        self.assertIn("VALID", content)
        # The header comment should count all input edges, including invalid ones
        self.assertIn("Attempting to insert 3 edges", content)

    def test_key_sanitization(self):
        """Test sanitization of keys with invalid characters."""
        entities_with_invalid_keys = [
            {
                "id": "e1@domain.com",
                "type": "Email",
                "name": "Test Email",
            },
            {
                "id": "user/123/profile",
                "type": "Profile",
                "name": "User Profile",
            },
            {
                "id": "_system",
                "type": "System",
                "name": "System Node",
            },
        ]

        kg = {"entities": entities_with_invalid_keys, "relationships": []}

        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "sanitized.aql"

        exporter.export(kg, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Keys should be sanitized (@ and / replaced with _)
        self.assertIn("e1_domain_com", content)
        self.assertIn("user_123_profile", content)
        # _system should become k_system (no leading underscore)
        self.assertIn("k_system", content)

    def test_batch_processing(self):
        """Test batch processing with small batch size."""
        # Create many entities to test batching
        many_entities = [
            {"id": f"e{i}", "type": "Node", "name": f"Node {i}"} for i in range(250)
        ]

        kg = {"entities": many_entities, "relationships": []}

        # Use small batch size
        exporter = ArangoAQLExporter(batch_size=100)
        output_path = Path(self.test_dir) / "batched.aql"

        exporter.export(kg, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Count number of INSERT statements (should be 3 batches: 100, 100, 50)
        insert_count = content.count("INSERT doc INTO vertices")
        self.assertEqual(insert_count, 3, "Should have 3 batches for 250 entities")

    def test_nested_properties(self):
        """Test handling of nested dictionaries and lists in properties."""
        entities_with_nested = [
            {
                "id": "complex_1",
                "type": "ComplexNode",
                "name": "Complex",
                "properties": {
                    "nested_dict": {"key1": "value1", "key2": "value2"},
                    "nested_list": [1, 2, 3, 4, 5],
                    "mixed": {"list": [1, 2], "value": "test"},
                },
            }
        ]

        kg = {"entities": entities_with_nested, "relationships": []}

        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "nested.aql"

        exporter.export(kg, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Nested structures should be properly serialized as JSON
        self.assertIn("nested_dict", content)
        self.assertIn("nested_list", content)
        # Check for the list values (may be formatted on separate lines)
        self.assertIn("1", content)
        self.assertIn("2", content)
        self.assertIn("3", content)
        self.assertIn("4", content)
        self.assertIn("5", content)

    def test_aql_syntax_validity(self):
        """Test that generated AQL has valid syntax structure."""
        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "syntax_test.aql"

        exporter.export(self.kg, str(output_path))

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for valid AQL structure
        # Should have FOR doc IN [array] INSERT doc INTO collection pattern
        # Using re.search with DOTALL flag
        pattern = r"FOR doc IN \[.*?\]\s+INSERT doc INTO \w+"
        self.assertTrue(
            re.search(pattern, content, re.DOTALL),
            f"Pattern '{pattern}' not found in generated AQL",
        )

        # Check that JSON arrays in the INSERT statements are valid
        # Find all JSON arrays in the content
        json_arrays = re.findall(r"FOR doc IN (\[.*?\])\s+INSERT", content, re.DOTALL)
        for json_array_match in json_arrays:
            # Extract just the array part
            json_str = json_array_match.replace("\n  INSERT", "").strip()
            try:
                # This should parse without errors
                parsed = json.loads(json_str)
                self.assertIsInstance(parsed, list)
            except json.JSONDecodeError as e:
                self.fail(f"Invalid JSON in AQL: {e}")

    def test_without_collection_creation(self):
        """Test export without collection creation statements."""
        exporter = ArangoAQLExporter(include_collection_creation=False)
        output_path = Path(self.test_dir) / "no_creation.aql"

        exporter.export(self.kg, str(output_path))

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Should still have INSERT statements
        self.assertIn("INSERT doc INTO vertices", content)
        self.assertIn("INSERT doc INTO edges", content)

    def test_export_with_nodes_edges_keys(self):
        """Test export using 'nodes' and 'edges' keys.

        Instead of 'entities' and 'relationships'.
        """
        kg_alt = {
            "nodes": self.entities,
            "edges": self.relationships,
        }

        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "nodes_edges.aql"

        exporter.export(kg_alt, str(output_path))

        # Verify file was created
        self.assertTrue(output_path.exists())

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Should have all the data
        self.assertIn("Alice", content)
        self.assertIn("WORKS_FOR", content)

    def test_override_collection_names_in_export(self):
        """Test overriding collection names via export options."""
        exporter = ArangoAQLExporter(
            vertex_collection="default_v", edge_collection="default_e"
        )
        output_path = Path(self.test_dir) / "override.aql"

        # Override via options
        exporter.export(
            self.kg,
            str(output_path),
            vertex_collection="override_v",
            edge_collection="override_e",
        )

        # Read and verify content
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Should use overridden names
        self.assertIn("INSERT doc INTO override_v", content)
        self.assertIn("INSERT doc INTO override_e", content)
        self.assertIn("override_v/e1", content)

    def test_invalid_collection_name_on_init(self):
        """Test that invalid collection names raise ValueError on initialization."""
        # Test collection name starting with number
        with self.assertRaises(ValueError) as context:
            ArangoAQLExporter(vertex_collection="123invalid")
        self.assertIn("must start with a letter or underscore", str(context.exception))

        # Test collection name with invalid characters
        with self.assertRaises(ValueError) as context:
            ArangoAQLExporter(edge_collection="invalid@name")
        self.assertIn("contains invalid character", str(context.exception))

        # Test empty collection name
        with self.assertRaises(ValueError) as context:
            ArangoAQLExporter(vertex_collection="")
        self.assertIn("cannot be empty", str(context.exception))

        # Test too long collection name
        with self.assertRaises(ValueError) as context:
            ArangoAQLExporter(vertex_collection="a" * 257)
        self.assertIn("exceeds maximum length", str(context.exception))

    def test_invalid_collection_name_on_export(self):
        """Test invalid collection names raise ValueError when overriding."""
        exporter = ArangoAQLExporter()
        output_path = Path(self.test_dir) / "test.aql"

        kg = {"entities": self.entities, "relationships": self.relationships}

        # Test invalid vertex collection override
        with self.assertRaises(ValueError) as context:
            exporter.export(kg, str(output_path), vertex_collection="123invalid")
        self.assertIn("must start with a letter or underscore", str(context.exception))

        # Test invalid edge collection override
        with self.assertRaises(ValueError) as context:
            exporter.export(kg, str(output_path), edge_collection="invalid@name")
        self.assertIn("contains invalid character", str(context.exception))


if __name__ == "__main__":
    unittest.main()
