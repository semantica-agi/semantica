import unittest
from unittest.mock import MagicMock, patch

import pytest

from semantica.ontology import (
    OntologyEngine, 
    ClassInferrer, 
    PropertyGenerator, 
    OntologyOptimizer,
    CompetencyQuestionsManager,
    LLMOntologyGenerator
)
from semantica.visualization import OntologyVisualizer

pytestmark = pytest.mark.integration

class TestNotebook14(unittest.TestCase):
    """
    Tests mirroring the steps in cookbook/introduction/14_Ontology.ipynb
    to ensure the documented examples work correctly.
    """

    def _run_full_pipeline(self):
        """Helper to run the full pipeline and return the ontology."""
        engine = OntologyEngine(base_uri="https://docs.semantica.dev/ontology/")
        
        # Sample Data
        entities = [
            {"id": "e1", "type": "Company", "name": "TechCorp", "founded": "2010"},
            {"id": "e2", "type": "Person", "name": "Alice", "role": "CEO"},
            {"id": "e3", "type": "Person", "name": "Bob", "role": "CTO"},
            {"id": "e4", "type": "Department", "name": "Engineering"},
            {"id": "e5", "type": "Project", "name": "Project Phoenix"}
        ]

        relationships = [
            {"source": "e2", "target": "e1", "type": "leads"},
            {"source": "e3", "target": "e4", "type": "manages"},
            {"source": "e4", "target": "e1", "type": "part_of"},
            {"source": "e3", "target": "e5", "type": "works_on"}
        ]

        data = {
            "entities": entities,
            "relationships": relationships
        }

        # Run the full pipeline
        ontology = engine.from_data(data, name="CorporateOntology", min_occurrences=1)
        return ontology

    def test_full_pipeline(self):
        """Test the 6-stage generation pipeline with sample data."""
        ontology = self._run_full_pipeline()
        
        # Verification
        self.assertEqual(ontology['name'], "CorporateOntology")
        self.assertGreater(len(ontology['classes']), 0)
        self.assertGreater(len(ontology['properties']), 0)
        
        # Inspect Classes (just to ensure no errors in access)
        for cls in ontology['classes']:
            self.assertIn('name', cls)
            self.assertIn('uri', cls)

        # Inspect Properties
        for prop in ontology['properties']:
            self.assertIn('name', prop)
            self.assertIn('type', prop)

    def _run_class_inferrer(self):
        """Helper to run class inference and return classes."""
        inferrer = ClassInferrer(min_occurrences=1)

        raw_entities = [
            {"type": "Manager", "name": "Dave", "level": 5},
            {"type": "Manager", "name": "Eve", "level": 4},
            {"type": "Employee", "name": "Frank"}, 
            {"type": "TemporaryWorker", "name": "Grace"} 
        ]

        classes = inferrer.infer_classes(raw_entities, build_hierarchy=True)
        return classes

    def test_class_inferrer(self):
        """Test ClassInferrer usage."""
        classes = self._run_class_inferrer()
        
        self.assertGreater(len(classes), 0)
        class_names = [c['name'] for c in classes]
        self.assertIn("Manager", class_names)
        self.assertIn("Employee", class_names)

    def test_property_generator(self):
        """Test PropertyGenerator usage."""
        # Setup context classes (reusing logic from previous test)
        classes = self._run_class_inferrer()
        
        prop_gen = PropertyGenerator()
        
        complex_entities = [
            {"id": "m1", "type": "Manager", "name": "Dave", "level": 5},
            {"id": "e1", "type": "Employee", "name": "Frank"}
        ]
        complex_relationships = [
            {"source": "m1", "target": "e1", "type": "supervises"}
        ]

        properties = prop_gen.infer_properties(
            entities=complex_entities,
            relationships=complex_relationships,
            classes=classes,
            min_occurrences=1
        )
        
        self.assertGreater(len(properties), 0)
        prop_names = [p['name'] for p in properties]
        # "level" should be a data property, "supervises" an object property
        self.assertTrue(any("level" in p['name'].lower() for p in properties))
        self.assertTrue(any("supervises" in p['name'].lower() for p in properties))

    def test_ontology_optimizer(self):
        """Test OntologyOptimizer usage."""
        optimizer = OntologyOptimizer()

        messy_ontology = {
            "classes": [
                {"name": "Person", "uri": "http://example.org/Person"},
                {"name": "Person", "uri": "http://example.org/Person"} # Duplicate!
            ],
            "properties": []
        }

        clean_ontology = optimizer.optimize_ontology(messy_ontology, remove_redundancy=True)

        self.assertEqual(len(messy_ontology['classes']), 2)
        self.assertEqual(len(clean_ontology['classes']), 1)

    # visualize_structure delegates to KGVisualizer, which holds its own
    # module-level plotly reference, so it has to be mocked as well for the
    # test to run without the optional viz extra.
    @patch("semantica.visualization.kg_visualizer.go")
    @patch("semantica.visualization.ontology_visualizer.make_subplots")
    @patch("semantica.visualization.ontology_visualizer.go")
    def test_visualization(self, mock_go, mock_make_subplots, mock_kg_go):
        """Test OntologyVisualizer usage (mocking plotly)."""
        viz = OntologyVisualizer()
        ontology = self._run_full_pipeline()

        # Mock figures
        mock_fig = MagicMock()
        mock_go.Figure.return_value = mock_fig
        mock_make_subplots.return_value = mock_fig
        mock_go.Scatter.return_value = MagicMock()
        mock_go.Indicator.return_value = MagicMock()

        # 1. Interactive Class Hierarchy
        fig_hierarchy = viz.visualize_hierarchy(ontology, output="interactive")
        # Just check it didn't crash; real test would check calls

        # 2. Ontology Structure Network
        fig_structure = viz.visualize_structure(ontology, output="interactive")

        # 3. Metrics Dashboard
        fig_metrics = viz.visualize_metrics(ontology, output="interactive")

    @patch("semantica.ontology.llm_generator.LLMOntologyGenerator.generate_ontology_from_text")
    def test_llm_ontology_generator(self, mock_generate):
        """Test LLMOntologyGenerator (mocked)."""
        mock_generate.return_value = {
            "classes": [{"name": "Department"}, {"name": "Course"}],
            "properties": [],
            "name": "UniversityOntology"
        }

        llm_gen = LLMOntologyGenerator(provider="openai", model="gpt-4")

        text_description = "A University has many Departments."

        llm_ontology = llm_gen.generate_ontology_from_text(
            text=text_description,
            name="UniversityOntology"
        )

        self.assertEqual(llm_ontology['name'], "UniversityOntology")
        self.assertEqual(len(llm_ontology['classes']), 2)

    def test_competency_questions(self):
        """Test CompetencyQuestionsManager."""
        cq_manager = CompetencyQuestionsManager()
        
        cq_manager.add_question("Who is the CEO?", category="general")
        questions = cq_manager.questions
        self.assertGreater(len(questions), 0)

    def test_ontology_engine_initialization(self):
        """Test initializing the OntologyEngine."""
        engine = OntologyEngine(base_uri="https://docs.semantica.dev/ontology/")
        self.assertIsNotNone(engine)

if __name__ == '__main__':
    unittest.main()
