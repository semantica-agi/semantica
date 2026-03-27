import unittest
from unittest.mock import MagicMock, patch
from collections import defaultdict

import pytest

from semantica.ontology.class_inferrer import ClassInferrer
from semantica.ontology.property_generator import PropertyGenerator
from semantica.ontology.naming_conventions import NamingConventions
from semantica.ontology.ontology_generator import OntologyGenerator
from semantica.ontology.namespace_manager import NamespaceManager
from semantica.ontology.module_manager import ModuleManager

pytestmark = pytest.mark.integration

class TestOntologyComprehensive(unittest.TestCase):
    
    def setUp(self):
        # Mock dependencies
        self.mock_logger = MagicMock()
        self.mock_tracker = MagicMock()
        self.mock_tracker.start_tracking.return_value = "track_id"
        
        # Patch loggers and trackers
        self.patchers = [
            patch('semantica.ontology.class_inferrer.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.class_inferrer.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.property_generator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.property_generator.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.naming_conventions.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.naming_conventions.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.ontology_generator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.ontology_generator.get_progress_tracker', return_value=self.mock_tracker),
        ]
        
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # --- NamingConventions Tests ---
    def test_naming_conventions(self):
        nc = NamingConventions()
        
        # Test class naming (PascalCase)
        self.assertEqual(nc.normalize_class_name("person"), "Person")
        self.assertEqual(nc.normalize_class_name("my class"), "MyClass")
        self.assertEqual(nc.normalize_class_name("MY_CLASS"), "MyClass")
        
        # Test property naming (camelCase)
        self.assertEqual(nc.normalize_property_name("has name", "data"), "hasName")
        self.assertEqual(nc.normalize_property_name("is related to", "object"), "isRelatedTo")
        
        # Test validation
        is_valid, _ = nc.validate_class_name("Person")
        self.assertTrue(is_valid)
        
        is_valid, _ = nc.validate_property_name("hasName", "data")
        self.assertTrue(is_valid)

    # --- ClassInferrer Tests ---
    def test_class_inferrer(self):
        inferrer = ClassInferrer(min_occurrences=1)
        
        entities = [
            {"type": "Person", "name": "Alice", "age": 30},
            {"type": "Person", "name": "Bob", "age": 25},
            {"type": "Organization", "name": "Acme Corp", "location": "US"}
        ]
        
        classes = inferrer.infer_classes(entities)
        
        self.assertEqual(len(classes), 2)
        
        person_class = next(c for c in classes if c["name"] == "Person")
        org_class = next(c for c in classes if c["name"] == "Organization")
        
        self.assertEqual(person_class["entity_count"], 2)
        self.assertEqual(org_class["entity_count"], 1)
        
        # Check inferred properties in class definition metadata
        # (Implementation detail: infer_classes calls _create_class_from_entities)
        # We might need to check if properties are in metadata or top level
        # Based on docstring: properties: List of common property names
        self.assertIn("name", person_class["properties"])
        self.assertIn("age", person_class["properties"])

    def test_class_inferrer_min_occurrences(self):
        inferrer = ClassInferrer(min_occurrences=2)
        
        entities = [
            {"type": "Person", "name": "Alice"},
            {"type": "Person", "name": "Bob"},
            {"type": "RareEntity", "name": "Rare"}
        ]
        
        classes = inferrer.infer_classes(entities)
        
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]["name"], "Person")

    # --- PropertyGenerator Tests ---
    def test_property_generator(self):
        # Test property inference logic
        generator = PropertyGenerator(min_occurrences=1)
        
        entities = [{"id": "p1", "type": "Person"}, {"id": "o1", "type": "Organization"}]
        relationships = [
            {"source_id": "p1", "target_id": "o1", "type": "worksFor", "source_type": "Person", "target_type": "Organization"}
        ]
        classes = [{"name": "Person"}, {"name": "Organization"}]
        
        properties = generator.infer_properties(entities, relationships, classes)
        
        # Debug print
        # print(f"Properties: {properties}")

        # Check object property
        works_for = next((p for p in properties if p["name"] == "worksFor"), None)
        self.assertIsNotNone(works_for)

    # --- OntologyGenerator Tests ---
    def test_ontology_generator_pipeline(self):
        # Test full pipeline with mocks
        generator = OntologyGenerator()
        
        # Mock dependencies
        generator.class_inferrer.infer_classes = MagicMock(return_value=[
            {"name": "Person", "uri": "http://example.org/Person"}
        ])
        generator.property_generator.infer_properties = MagicMock(return_value=[
            {"name": "worksFor", "type": "object", "domain": ["Person"], "range": ["Organization"]}
        ])
        
        data = {
            "entities": [{"type": "Person", "id": "p1"}],
            "relationships": [{"type": "worksFor", "source": "p1"}]
        }
        
        ontology = generator.generate_ontology(data, name="TestOntology")
        
        self.assertEqual(ontology["name"], "TestOntology")
        self.assertIn("classes", ontology)
        self.assertIn("properties", ontology)
        
    # --- OWLGenerator Tests ---
    def test_owl_generator(self):
        try:
            from semantica.ontology.owl_generator import OWLGenerator
        except ImportError:
            self.skipTest("OWLGenerator not importable")
            
        generator = OWLGenerator()
        ontology = {
            "name": "TestOntology",
            "uri": "http://example.org/ontology",
            "classes": [{"name": "Person", "uri": "http://example.org/ontology/Person"}],
            "properties": [{"name": "hasName", "type": "data", "uri": "http://example.org/ontology/hasName"}]
        }
        
        owl_output = generator.generate_owl(ontology, format="turtle")
        self.assertIsInstance(owl_output, str)
        self.assertIn("Person", owl_output)
        self.assertIn("hasName", owl_output)

    # --- OntologyValidator Tests ---
    # Removed as per request
        
    # --- LLMOntologyGenerator Tests ---
    def test_llm_ontology_generator(self):
        try:
            from semantica.ontology.llm_generator import LLMOntologyGenerator
        except ImportError:
            self.skipTest("LLMOntologyGenerator not importable")
            
        # Mock provider
        with patch('semantica.ontology.llm_generator.create_provider') as mock_create:
            mock_provider = MagicMock()
            mock_create.return_value = mock_provider
            
            # Setup mock return
            mock_provider.generate_structured.return_value = {
                "name": "AI Generated",
                "classes": [{"name": "Robot", "label": "A Robot"}],
                "properties": [{"name": "hasModel", "type": "data"}]
            }
            
            generator = LLMOntologyGenerator(provider="openai")
            ontology = generator.generate_ontology_from_text("Create ontology about robots")
            
            self.assertEqual(ontology["name"], "AI Generated")
            self.assertEqual(len(ontology["classes"]), 1)
            self.assertEqual(ontology["classes"][0]["name"], "Robot")
            
    # --- OntologyEngine Tests ---
    def test_ontology_engine(self):
        try:
            from semantica.ontology.engine import OntologyEngine
        except ImportError:
            self.skipTest("OntologyEngine not importable")
            
        engine = OntologyEngine()
        
        # Mock internal components
        engine.generator.generate_ontology = MagicMock(return_value={"name": "EngineOntology"})
        
        ontology = engine.from_data({"entities": []})
        self.assertEqual(ontology["name"], "EngineOntology")

    # --- NamespaceManager Tests ---
    def test_namespace_manager(self):
        nm = NamespaceManager(base_uri="http://example.org/")
        
        iri = nm.generate_class_iri("Person")
        self.assertEqual(iri, "http://example.org/Person")
        
        prop_iri = nm.generate_property_iri("hasName")
        # With fix, it should preserve hasName
        self.assertEqual(prop_iri, "http://example.org/hasName")
        
        # bind_prefix is not in NamespaceManager, checking code...
        # It's register_namespace
        nm.register_namespace("ex", "http://example.org/")
        self.assertEqual(nm.get_namespace("ex"), "http://example.org/")

    # --- ModuleManager Tests ---
    def test_module_manager(self):
        mm = ModuleManager()
        
        module_def = {
            "name": "PersonModule",
            "classes": ["Person"],
            "properties": ["hasName"]
        }
        
        # ModuleManager uses create_module
        mm.create_module("PersonModule", "http://example.org/person", classes=["Person"], properties=["hasName"])
        self.assertIn("PersonModule", mm.modules)
        
        mod = mm.get_module("PersonModule")
        self.assertEqual(mod.name, "PersonModule")
        self.assertIn("Person", mod.classes)

class TestSHACLGeneration(unittest.TestCase):
    """Tests 1-16: SHACL shape generation from flat ontologies."""

    # Shared flat ontology fixture
    _ONTOLOGY = {
        "classes": [
            {"name": "Person", "label": "Person", "description": "A human individual"},
            {"name": "Organization", "label": "Organization"},
        ],
        "properties": [
            {
                "name": "name",
                "type": "datatype",
                "range": "string",
                "domain": "Person",
                "required": True,
            },
            {
                "name": "age",
                "type": "datatype",
                "range": "integer",
                "domain": "Person",
                "cardinality": {"min": 0, "max": 1},
            },
            {
                "name": "worksFor",
                "type": "object",
                "range": "Organization",
                "domain": "Person",
            },
            {
                "name": "legalName",
                "type": "datatype",
                "range": "string",
                "domain": "Organization",
                "required": True,
            },
        ],
    }

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_tracker = MagicMock()
        self.mock_tracker.start_tracking.return_value = "track_shacl"
        self.patchers = [
            patch(
                "semantica.ontology.ontology_generator.get_logger",
                return_value=self.mock_logger,
            ),
            patch(
                "semantica.ontology.ontology_generator.get_progress_tracker",
                return_value=self.mock_tracker,
            ),
        ]
        for p in self.patchers:
            p.start()
        from semantica.ontology.ontology_generator import SHACLGenerator
        self.gen = SHACLGenerator(
            base_uri="https://semantica.dev/shapes/",
            quality_tier="standard",
        )

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    # 1
    def test_generate_returns_shacl_graph(self):
        from semantica.ontology.ontology_generator import SHACLGraph
        graph = self.gen.generate(self._ONTOLOGY)
        self.assertIsInstance(graph, SHACLGraph)

    # 2
    def test_node_shape_count_matches_class_count(self):
        graph = self.gen.generate(self._ONTOLOGY)
        self.assertEqual(len(graph.node_shapes), 2)

    # 3
    def test_node_shape_target_classes(self):
        graph = self.gen.generate(self._ONTOLOGY)
        classes = {ns.target_class for ns in graph.node_shapes}
        self.assertIn("Person", classes)
        self.assertIn("Organization", classes)

    # 4
    def test_required_property_gets_min_count_1(self):
        graph = self.gen.generate(self._ONTOLOGY)
        person = next(ns for ns in graph.node_shapes if ns.target_class == "Person")
        name_ps = next(ps for ps in person.property_shapes if ps.path == "name")
        self.assertEqual(name_ps.min_count, 1)

    # 5
    def test_cardinality_min_max(self):
        graph = self.gen.generate(self._ONTOLOGY)
        person = next(ns for ns in graph.node_shapes if ns.target_class == "Person")
        age_ps = next(ps for ps in person.property_shapes if ps.path == "age")
        self.assertEqual(age_ps.min_count, 0)
        self.assertEqual(age_ps.max_count, 1)

    # 6
    def test_datatype_property_gets_xsd_datatype(self):
        graph = self.gen.generate(self._ONTOLOGY)
        person = next(ns for ns in graph.node_shapes if ns.target_class == "Person")
        name_ps = next(ps for ps in person.property_shapes if ps.path == "name")
        self.assertEqual(name_ps.datatype, "xsd:string")
        self.assertIsNone(name_ps.class_)

    # 7
    def test_object_property_gets_sh_class(self):
        graph = self.gen.generate(self._ONTOLOGY)
        person = next(ns for ns in graph.node_shapes if ns.target_class == "Person")
        wf_ps = next(ps for ps in person.property_shapes if ps.path == "worksFor")
        self.assertEqual(wf_ps.class_, "Organization")
        self.assertIsNone(wf_ps.datatype)

    # 8
    def test_turtle_contains_sh_node_shape(self):
        graph = self.gen.generate(self._ONTOLOGY)
        ttl = self.gen.serialize(graph, format="turtle")
        self.assertIn("sh:NodeShape", ttl)
        self.assertIn("sh:targetClass", ttl)
        self.assertIn("sh:property", ttl)

    # 9
    def test_jsonld_is_valid_json(self):
        import json
        graph = self.gen.generate(self._ONTOLOGY)
        jld = self.gen.serialize(graph, format="json-ld")
        parsed = json.loads(jld)
        self.assertIn("@context", parsed)
        self.assertIn("@graph", parsed)

    # 10
    def test_ntriples_uses_expanded_uris(self):
        graph = self.gen.generate(self._ONTOLOGY)
        nt = self.gen.serialize(graph, format="n-triples")
        self.assertNotIn("@prefix", nt)
        self.assertIn("<http://www.w3.org/ns/shacl#NodeShape>", nt)

    # 11
    def test_unknown_format_raises_value_error(self):
        graph = self.gen.generate(self._ONTOLOGY)
        with self.assertRaises(ValueError):
            self.gen.serialize(graph, format="csv")

    # 12
    def test_non_dict_ontology_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.gen.generate("not a dict")

    # 13
    def test_ontology_missing_both_keys_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.gen.generate({"namespace": {}})

    # 14
    def test_enumeration_produces_sh_in(self):
        onto = {
            "classes": [{"name": "Order"}],
            "properties": [
                {
                    "name": "status",
                    "type": "datatype",
                    "range": "string",
                    "domain": "Order",
                    "one_of": ["pending", "shipped", "delivered", "cancelled"],
                }
            ],
        }
        graph = self.gen.generate(onto)
        ttl = self.gen.serialize(graph, format="turtle")
        self.assertIn("sh:in", ttl)
        self.assertIn('"pending"', ttl)

    # 15
    def test_custom_namespace_in_prefixes(self):
        onto = dict(self._ONTOLOGY)
        onto["namespace"] = {"base_uri": "https://custom.org/onto/"}
        graph = self.gen.generate(onto)
        self.assertIn("https://custom.org/onto/", graph.prefixes.values())

    # 16
    def test_standard_tier_is_default(self):
        from semantica.ontology.ontology_generator import SHACLGenerator
        gen = SHACLGenerator()
        self.assertEqual(gen.quality_tier, "standard")


if __name__ == '__main__':
    unittest.main()
