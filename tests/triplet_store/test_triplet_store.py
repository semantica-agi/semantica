import unittest
from unittest.mock import MagicMock, patch
from semantica.triplet_store.triplet_store import TripletStore
from semantica.triplet_store.query_engine import QueryEngine
from semantica.semantic_extract.triplet_extractor import Triplet

class TestTripletStore(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_tracker = MagicMock()
        
        self.logger_patcher = patch('semantica.triplet_store.triplet_store.get_logger', return_value=self.mock_logger)
        self.tracker_patcher = patch('semantica.triplet_store.triplet_store.get_progress_tracker', return_value=self.mock_tracker)
        
        self.logger_patcher.start()
        self.tracker_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()
        self.tracker_patcher.stop()

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_triplet_store_init(self, mock_blazegraph_store):
        store = TripletStore(backend="blazegraph", endpoint="http://localhost:9999")
        self.assertEqual(store.backend_type, "blazegraph")
        self.assertEqual(store.endpoint, "http://localhost:9999")
        mock_blazegraph_store.assert_called_once()

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_add_triplet(self, mock_blazegraph_store):
        # Setup mock backend
        mock_backend_instance = MagicMock()
        mock_blazegraph_store.return_value = mock_backend_instance
        mock_backend_instance.add_triplet.return_value = {"status": "success"}
        
        store = TripletStore(backend="blazegraph")
        triplet = Triplet(subject="s", predicate="p", object="o")
        
        result = store.add_triplet(triplet)
        
        self.assertEqual(result, {"status": "success"})
        mock_backend_instance.add_triplet.assert_called_once_with(triplet)

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_add_triplets(self, mock_blazegraph_store):
        # Setup mock backend and bulk loader
        mock_backend_instance = MagicMock()
        mock_blazegraph_store.return_value = mock_backend_instance
        
        store = TripletStore(backend="blazegraph")
        
        # Mock bulk loader
        mock_loader = MagicMock()
        store.bulk_loader = mock_loader
        mock_progress = MagicMock()
        mock_progress.metadata = {"success": True}
        mock_progress.total_triplets = 2
        mock_progress.loaded_triplets = 2
        mock_progress.failed_triplets = 0
        mock_progress.total_batches = 1
        mock_loader.load_triplets.return_value = mock_progress
        
        triplets = [
            Triplet(subject="s1", predicate="p1", object="o1"),
            Triplet(subject="s2", predicate="p2", object="o2")
        ]
        
        result = store.add_triplets(triplets, batch_size=2)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 2)
        mock_loader.load_triplets.assert_called_once()

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_get_triplets(self, mock_blazegraph_store):
        mock_backend_instance = MagicMock()
        mock_blazegraph_store.return_value = mock_backend_instance
        expected_triplets = [Triplet(subject="s", predicate="p", object="o")]
        mock_backend_instance.get_triplets.return_value = expected_triplets
        
        store = TripletStore(backend="blazegraph")
        result = store.get_triplets(subject="s")
        
        self.assertEqual(result, expected_triplets)
        mock_backend_instance.get_triplets.assert_called_once_with(subject="s", predicate=None, object=None)

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_delete_triplet(self, mock_blazegraph_store):
        mock_backend_instance = MagicMock()
        mock_blazegraph_store.return_value = mock_backend_instance
        mock_backend_instance.delete_triplet.return_value = {"success": True}
        
        store = TripletStore(backend="blazegraph")
        triplet = Triplet(subject="s", predicate="p", object="o")
        
        result = store.delete_triplet(triplet)
        
        self.assertTrue(result["success"])
        mock_backend_instance.delete_triplet.assert_called_once_with(triplet)
    
    def test_query_engine_build_values_clause(self):
        engine = QueryEngine()
        uris = ["http://ex.org/1", "http://ex.org/2"]
        
        clause = engine.build_values_clause("subject", uris)
        self.assertEqual(clause, "VALUES ?subject { <http://ex.org/1> <http://ex.org/2> }")
        
        empty_clause = engine.build_values_clause("subject", [])
        self.assertEqual(empty_clause, "")

    def test_query_engine_expand_entity_uri_disabled(self):
        engine = QueryEngine()
        mock_backend = MagicMock()
        
        result = engine.expand_entity_uri("http://ex.org/1", mock_backend, use_alignments=False)
        
        # Should return only the original URI and NOT query the store
        self.assertEqual(result, ["http://ex.org/1"])
        mock_backend.execute_sparql.assert_not_called()

    def test_query_engine_expand_entity_uri_enabled(self):
        engine = QueryEngine()
        mock_backend = MagicMock()
        
        # Mock the backend returning an aligned URI
        mock_backend.execute_sparql.return_value = {
            "bindings": [{"aligned": {"value": "http://ex.org/aligned_entity"}}]
        }
        
        result = engine.expand_entity_uri("http://ex.org/original", mock_backend, use_alignments=True)
        
        self.assertIn("http://ex.org/original", result)
        self.assertIn("http://ex.org/aligned_entity", result)
        self.assertEqual(len(result), 2)
        mock_backend.execute_sparql.assert_called_once()
        
    def test_end_to_end_cross_ontology_uri_flow(self):
        """
        Full end-to-end: real expand_entity_uri queries a mock backend,
        then build_values_clause injects the results into a SPARQL template.
        """
        engine = QueryEngine()
        mock_backend = MagicMock()
        mock_backend.execute_sparql.return_value = {
            "bindings": [{"aligned": {"value": "http://aligned.org/2"}}]
        }

        original_uri = "http://ex.org/1"
        expanded = engine.expand_entity_uri(original_uri, store_backend=mock_backend, use_alignments=True)
        values_clause = engine.build_values_clause("subject", expanded)

        sparql_query = f"""
            SELECT ?instance ?name WHERE {{
                {values_clause}
                ?instance a ?subject .
                ?instance <http://schema.org/name> ?name .
            }}
        """

        self.assertIn("http://ex.org/1", sparql_query)
        self.assertIn("http://aligned.org/2", sparql_query)
        self.assertIn("VALUES ?subject", sparql_query)
        mock_backend.execute_sparql.assert_called_once()


class TestSKOSTripletStore(unittest.TestCase):
    """Tests for SKOS helper methods on TripletStore."""

    _SKOS = "http://www.w3.org/2004/02/skos/core#"
    _RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_tracker = MagicMock()

        self.logger_patcher = patch(
            'semantica.triplet_store.triplet_store.get_logger', return_value=self.mock_logger
        )
        self.tracker_patcher = patch(
            'semantica.triplet_store.triplet_store.get_progress_tracker', return_value=self.mock_tracker
        )
        self.logger_patcher.start()
        self.tracker_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()
        self.tracker_patcher.stop()

    def _make_store(self, mock_blazegraph):
        """Return a TripletStore backed by a MagicMock BlazegraphStore."""
        mock_backend = MagicMock()
        mock_blazegraph.return_value = mock_backend
        store = TripletStore(backend="blazegraph")
        # Provide a fast no-op bulk loader
        mock_loader = MagicMock()
        mock_progress = MagicMock()
        mock_progress.metadata = {"success": True}
        mock_progress.total_triplets = 0
        mock_progress.loaded_triplets = 0
        mock_progress.failed_triplets = 0
        mock_progress.total_batches = 0
        mock_loader.load_triplets.return_value = mock_progress
        store.bulk_loader = mock_loader
        return store, mock_backend, mock_loader

    # --- add_skos_concept ---

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_add_skos_concept_core_triples(self, mock_bg):
        """add_skos_concept must produce ConceptScheme + Concept + inScheme + prefLabel triples."""
        store, _, mock_loader = self._make_store(mock_bg)

        store.add_skos_concept(
            concept_uri="http://example.org/concept/red",
            scheme_uri="http://example.org/vocab/colours",
            pref_label="Red",
        )

        mock_loader.load_triplets.assert_called_once()
        triplets = mock_loader.load_triplets.call_args[0][0]
        subjects_predicates = {(t.subject, t.predicate) for t in triplets}

        SKOS = self._SKOS
        RDF_TYPE = self._RDF_TYPE

        self.assertIn(("http://example.org/vocab/colours", RDF_TYPE), subjects_predicates)
        self.assertIn(("http://example.org/concept/red", RDF_TYPE), subjects_predicates)
        self.assertIn(("http://example.org/concept/red", f"{SKOS}inScheme"), subjects_predicates)
        self.assertIn(("http://example.org/concept/red", f"{SKOS}prefLabel"), subjects_predicates)

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_add_skos_concept_optional_fields(self, mock_bg):
        """Optional fields produce extra triples."""
        store, _, mock_loader = self._make_store(mock_bg)

        store.add_skos_concept(
            concept_uri="http://example.org/concept/red",
            scheme_uri="http://example.org/vocab/colours",
            pref_label="Red",
            alt_labels=["Crimson", "Rouge"],
            broader=["http://example.org/concept/colour"],
            definition="The colour red.",
            notation="RED",
        )

        triplets = mock_loader.load_triplets.call_args[0][0]
        predicates = [t.predicate for t in triplets]
        SKOS = self._SKOS

        self.assertIn(f"{SKOS}altLabel", predicates)
        self.assertEqual(predicates.count(f"{SKOS}altLabel"), 2)
        self.assertIn(f"{SKOS}broader", predicates)
        self.assertIn(f"{SKOS}definition", predicates)
        self.assertIn(f"{SKOS}notation", predicates)

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_add_skos_concept_scheme_triple_always_included(self, mock_bg):
        """ConceptScheme rdf:type triple is always included even without optional args."""
        store, _, mock_loader = self._make_store(mock_bg)

        store.add_skos_concept(
            concept_uri="http://example.org/concept/blue",
            scheme_uri="http://example.org/vocab/colours",
            pref_label="Blue",
        )

        triplets = mock_loader.load_triplets.call_args[0][0]
        scheme_types = [
            t for t in triplets
            if t.subject == "http://example.org/vocab/colours"
            and t.predicate == self._RDF_TYPE
            and t.object == f"{self._SKOS}ConceptScheme"
        ]
        self.assertEqual(len(scheme_types), 1)

    # --- get_skos_concepts ---

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_get_skos_concepts_all(self, mock_bg):
        """get_skos_concepts returns all concepts when no scheme_uri given."""
        store, mock_backend, _ = self._make_store(mock_bg)

        from semantica.triplet_store.query_engine import QueryResult
        mock_result = QueryResult(
            bindings=[
                {"concept": {"value": "http://example.org/concept/red"},
                 "prefLabel": {"value": "Red"},
                 "altLabel": {"value": "Crimson"},
                 "broader": None, "narrower": None, "related": None},
                {"concept": {"value": "http://example.org/concept/red"},
                 "prefLabel": {"value": "Red"},
                 "altLabel": {"value": "Rouge"},
                 "broader": None, "narrower": None, "related": None},
                {"concept": {"value": "http://example.org/concept/blue"},
                 "prefLabel": {"value": "Blue"},
                 "altLabel": None,
                 "broader": None, "narrower": None, "related": None},
            ],
            variables=["concept", "prefLabel", "altLabel"],
        )
        mock_backend.execute_sparql.return_value = {
            "bindings": mock_result.bindings,
            "variables": mock_result.variables,
            "metadata": {},
        }

        # Patch query_engine.execute_query to return mock_result directly
        store.query_engine.execute_query = MagicMock(return_value=mock_result)

        concepts = store.get_skos_concepts()
        self.assertEqual(len(concepts), 2)

        red = next(c for c in concepts if "red" in c["uri"])
        self.assertEqual(red["pref_label"], "Red")
        self.assertIn("Crimson", red["alt_labels"])
        self.assertIn("Rouge", red["alt_labels"])

        blue = next(c for c in concepts if "blue" in c["uri"])
        self.assertEqual(blue["alt_labels"], [])

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_get_skos_concepts_scheme_filter_in_query(self, mock_bg):
        """When scheme_uri is given the scheme URI appears in the issued SPARQL."""
        store, _, _ = self._make_store(mock_bg)

        from semantica.triplet_store.query_engine import QueryResult
        empty_result = QueryResult(bindings=[], variables=[])
        store.query_engine.execute_query = MagicMock(return_value=empty_result)

        store.get_skos_concepts(scheme_uri="http://example.org/vocab/colours")

        issued_sparql = store.query_engine.execute_query.call_args[0][0]
        self.assertIn("http://example.org/vocab/colours", issued_sparql)

    @patch('semantica.triplet_store.blazegraph_store.BlazegraphStore')
    def test_get_skos_concepts_empty_store(self, mock_bg):
        """Returns empty list when no concepts exist."""
        store, _, _ = self._make_store(mock_bg)
        from semantica.triplet_store.query_engine import QueryResult
        store.query_engine.execute_query = MagicMock(
            return_value=QueryResult(bindings=[], variables=[])
        )
        self.assertEqual(store.get_skos_concepts(), [])
