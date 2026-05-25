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

    def test_owl_generator_user_facing_schema_compatibility(self):
        try:
            from semantica.ontology.owl_generator import OWLGenerator
        except ImportError:
            self.skipTest("OWLGenerator not importable")

        generator = OWLGenerator()
        ontology = {
            "name": "UserFacingOntology",
            "uri": "http://example.org/ontology/",
            "classes": [
                # label should be preferred over name for generated class IRI
                {"name": "Human", "label": "Person", "subclassOf": "Agent"},
            ],
            "properties": [
                {
                    # label should be preferred over name for generated property IRI
                    "name": "birthDateInternal",
                    "label": "birthDate",
                    "type": "datatype",
                    "domain": "Person",
                    # datatype range may be list in user-facing schema
                    "range": ["xsd:date", "http://example.org/ontology/CustomDateType"],
                }
            ],
        }

        owl_output = generator.generate_owl(ontology, format="turtle")

        self.assertIn("owl:DatatypeProperty", owl_output)
        self.assertIn("@prefix : <http://example.org/ontology/> .", owl_output)
        self.assertIn("rdfs:subClassOf", owl_output)
        self.assertIn("birthDate", owl_output)
        self.assertIn("xsd:date", owl_output)
        self.assertIn("CustomDateType", owl_output)
        self.assertIn(":Person", owl_output)
        self.assertIn(":Agent", owl_output)
        self.assertNotIn("https://semantica.dev/ontology/", owl_output)

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


class TestSKOSOntologyEngine(unittest.TestCase):
    """Tests for SKOS vocabulary management APIs in OntologyEngine."""

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_tracker = MagicMock()
        self.mock_tracker.start_tracking.return_value = "track_id"

        patchers = [
            patch('semantica.ontology.engine.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.engine.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.ontology_generator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.ontology_generator.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.class_inferrer.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.class_inferrer.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.property_generator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.property_generator.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.owl_generator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.owl_generator.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.ontology_evaluator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.ontology_evaluator.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.ontology.ontology_validator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.llm_generator.get_logger', return_value=self.mock_logger),
            patch('semantica.ontology.llm_generator.get_progress_tracker', return_value=self.mock_tracker),
            patch('semantica.change_management.ontology_version_manager.get_logger', return_value=self.mock_logger),
            patch('semantica.change_management.ontology_version_manager.get_progress_tracker', return_value=self.mock_tracker),
        ]
        self.patchers = patchers
        for p in self.patchers:
            p.start()

        # Mock store with a controllable execute_query
        self.mock_store = MagicMock()
        from semantica.ontology.engine import OntologyEngine
        self.engine = OntologyEngine(store=self.mock_store)

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def _make_result(self, bindings):
        """Build a fake QueryResult-like object."""
        result = MagicMock()
        result.bindings = bindings
        return result

    # --- NamespaceManager SKOS helpers ---

    def test_get_skos_uri(self):
        from semantica.ontology.namespace_manager import NamespaceManager
        nm = NamespaceManager()
        self.assertEqual(
            nm.get_skos_uri("Concept"),
            "http://www.w3.org/2004/02/skos/core#Concept",
        )
        self.assertEqual(
            nm.get_skos_uri("prefLabel"),
            "http://www.w3.org/2004/02/skos/core#prefLabel",
        )

    def test_build_concept_scheme_uri(self):
        from semantica.ontology.namespace_manager import NamespaceManager
        nm = NamespaceManager(base_uri="https://example.org/onto/")
        uri = nm.build_concept_scheme_uri("My Vocabulary")
        self.assertIn("my-vocabulary", uri)
        self.assertTrue(uri.startswith("https://example.org/onto/"))

    def test_build_concept_scheme_uri_special_chars(self):
        from semantica.ontology.namespace_manager import NamespaceManager
        nm = NamespaceManager()
        uri = nm.build_concept_scheme_uri("ISO 3166 Countries")
        self.assertIn("iso-3166-countries", uri)

    # --- list_vocabularies ---

    def test_list_vocabularies_returns_schemes(self):
        self.mock_store.execute_query.return_value = self._make_result([
            {"scheme": {"value": "http://example.org/vocab/colours"},
             "label":  {"value": "Colours"}},
            {"scheme": {"value": "http://example.org/vocab/sizes"},
             "label":  None},
        ])
        vocabs = self.engine.list_vocabularies()
        self.assertEqual(len(vocabs), 2)
        uris = [v["uri"] for v in vocabs]
        self.assertIn("http://example.org/vocab/colours", uris)
        self.assertIn("http://example.org/vocab/sizes", uris)
        colours = next(v for v in vocabs if "colours" in v["uri"])
        self.assertEqual(colours["label"], "Colours")

    def test_list_vocabularies_deduplicates(self):
        # Same scheme URI appearing twice (multi-valued label rows)
        self.mock_store.execute_query.return_value = self._make_result([
            {"scheme": {"value": "http://example.org/vocab/colours"},
             "label":  {"value": "Colours"}},
            {"scheme": {"value": "http://example.org/vocab/colours"},
             "label":  {"value": "Colors"}},
        ])
        vocabs = self.engine.list_vocabularies()
        self.assertEqual(len(vocabs), 1)

    def test_list_vocabularies_no_store_raises(self):
        from semantica.utils.exceptions import ProcessingError
        from semantica.ontology.engine import OntologyEngine
        engine_no_store = OntologyEngine()
        with self.assertRaises(ProcessingError):
            engine_no_store.list_vocabularies()

    # --- list_concepts ---

    def test_list_concepts_returns_concepts(self):
        self.mock_store.execute_query.return_value = self._make_result([
            {"concept": {"value": "http://example.org/concept/red"},
             "prefLabel": {"value": "Red"},
             "altLabel":  {"value": "Crimson"}},
            {"concept": {"value": "http://example.org/concept/red"},
             "prefLabel": {"value": "Red"},
             "altLabel":  {"value": "Rouge"}},
            {"concept": {"value": "http://example.org/concept/blue"},
             "prefLabel": {"value": "Blue"},
             "altLabel":  None},
        ])
        concepts = self.engine.list_concepts("http://example.org/vocab/colours")
        self.assertEqual(len(concepts), 2)
        red = next(c for c in concepts if "red" in c["uri"])
        self.assertEqual(red["pref_label"], "Red")
        self.assertIn("Crimson", red["alt_labels"])
        self.assertIn("Rouge", red["alt_labels"])
        blue = next(c for c in concepts if "blue" in c["uri"])
        self.assertEqual(blue["alt_labels"], [])

    def test_list_concepts_no_store_raises(self):
        from semantica.utils.exceptions import ProcessingError
        from semantica.ontology.engine import OntologyEngine
        engine_no_store = OntologyEngine()
        with self.assertRaises(ProcessingError):
            engine_no_store.list_concepts("http://example.org/vocab/colours")

    # --- search_concepts ---

    def test_search_concepts_returns_matches(self):
        self.mock_store.execute_query.return_value = self._make_result([
            {"concept": {"value": "http://example.org/concept/red"},
             "label":   {"value": "Red"}},
            {"concept": {"value": "http://example.org/concept/infrared"},
             "label":   {"value": "Infrared"}},
        ])
        results = self.engine.search_concepts("red")
        self.assertEqual(len(results), 2)
        uris = [r["uri"] for r in results]
        self.assertIn("http://example.org/concept/red", uris)
        self.assertIn("http://example.org/concept/infrared", uris)

    def test_search_concepts_with_scheme_filter(self):
        self.mock_store.execute_query.return_value = self._make_result([
            {"concept": {"value": "http://example.org/concept/red"},
             "label":   {"value": "Red"}},
        ])
        results = self.engine.search_concepts("red", scheme_uri="http://example.org/vocab/colours")
        self.assertEqual(len(results), 1)
        # Scheme URI should appear in the SPARQL issued to the store
        issued_sparql = self.mock_store.execute_query.call_args[0][0]
        self.assertIn("http://example.org/vocab/colours", issued_sparql)

    def test_search_concepts_empty_result(self):
        self.mock_store.execute_query.return_value = self._make_result([])
        results = self.engine.search_concepts("zzznomatch")
        self.assertEqual(results, [])

    def test_search_concepts_no_store_raises(self):
        from semantica.utils.exceptions import ProcessingError
        from semantica.ontology.engine import OntologyEngine
        engine_no_store = OntologyEngine()
        with self.assertRaises(ProcessingError):
            engine_no_store.search_concepts("red")

    def test_search_concepts_sanitizes_query(self):
        """Ensure user input containing SPARQL-special chars doesn't break the query."""
        self.mock_store.execute_query.return_value = self._make_result([])
        # Should not raise
        self.engine.search_concepts('red" } MALICIOUS { ?x ?y ?z')

    def test_search_concepts_deduplicates(self):
        # Same concept URI matched by both prefLabel and altLabel
        self.mock_store.execute_query.return_value = self._make_result([
            {"concept": {"value": "http://example.org/concept/red"},
             "label":   {"value": "Red"}},
            {"concept": {"value": "http://example.org/concept/red"},
             "label":   {"value": "Reddish"}},
        ])
        results = self.engine.search_concepts("red")
        self.assertEqual(len(results), 1)


if __name__ == '__main__':
    unittest.main()
