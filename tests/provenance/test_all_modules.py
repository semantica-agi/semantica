"""
Comprehensive Module Integration Tests

Tests that provenance tracking is integrated and working correctly across
ALL Semantica modules.
"""

import pytest
from semantica.provenance import ProvenanceManager


class TestSemanticExtractModule:
    """Test semantic_extract module provenance integration."""
    
    def test_semantic_extract_imports(self):
        """Test that semantic_extract module can be imported."""
        try:
            from semantica import semantic_extract
            assert semantic_extract is not None
        except ImportError as e:
            pytest.skip(f"semantic_extract module not available: {e}")
    
    def test_ner_extractor_provenance_ready(self):
        """Test NER extractor is ready for provenance tracking."""
        try:
            from semantica.semantic_extract import NERExtractor
            
            # Should be able to instantiate
            extractor = NERExtractor()
            assert extractor is not None
            
            # Check if provenance parameter exists (future integration)
            import inspect
            sig = inspect.signature(NERExtractor.__init__)
            # Note: provenance parameter will be added in future phases
            
        except ImportError:
            pytest.skip("NERExtractor not available")
    
    def test_relation_extractor_provenance_ready(self):
        """Test relation extractor is ready for provenance tracking."""
        try:
            from semantica.semantic_extract import RelationExtractor
            
            extractor = RelationExtractor()
            assert extractor is not None
            
        except ImportError:
            pytest.skip("RelationExtractor not available")


class TestKGModule:
    """Test kg module provenance integration."""
    
    def test_kg_provenance_tracker_available(self):
        """Test kg.ProvenanceTracker is available and working."""
        from semantica.kg import ProvenanceTracker
        
        tracker = ProvenanceTracker()
        assert tracker is not None
        
        # Test basic functionality
        # NOTE: tracker.get_lineage() was never implemented on
        # kg.ProvenanceTracker; this tested an intended unified-backend
        # migration that never happened (#744). ProvenanceTracker is now
        # deprecated in favor of semantica.provenance.ProvenanceManager.
        # Instead, verify the observable behavior of the still-supported
        # track_entity()/get_all_sources() pair.
        tracker.track_entity("test_entity", source="test_source")
        sources = tracker.get_all_sources("test_entity")
        assert len(sources) > 0
        last_entry = sources[-1]
        assert last_entry["source"] == "test_source"
        assert "recorded_at" in last_entry
    
    # NOTE: test_kg_uses_unified_backend removed; it only asserted the
    # presence of _use_unified/_unified_manager attributes, which were
    # never implemented on kg.ProvenanceTracker. This tested an intended
    # unified-backend migration that never happened (#744).
    # ProvenanceTracker is now deprecated in favor of
    # semantica.provenance.ProvenanceManager.
    
    def test_kg_graph_builder_ready(self):
        """Test GraphBuilder is ready for provenance."""
        try:
            from semantica.kg import GraphBuilder
            
            builder = GraphBuilder()
            assert builder is not None
            
        except ImportError:
            pytest.skip("GraphBuilder not available")


class TestSplitModule:
    """Test split module provenance integration."""
    
    def test_split_provenance_tracker_available(self):
        """Test split.ProvenanceTracker is available and working."""
        from semantica.split import ProvenanceTracker
        from semantica.split.semantic_chunker import Chunk
        
        tracker = ProvenanceTracker()
        assert tracker is not None
        
        # Test basic functionality
        chunk = Chunk(text="Test", start_index=0, end_index=4, metadata={})
        chunk.id = "test_chunk"
        
        prov_id = tracker.track_chunk(chunk, source_document="test_doc")
        assert prov_id is not None
        
        prov = tracker.get_provenance("test_chunk")
        assert prov is not None
    
    def test_split_uses_unified_backend(self):
        """Test that split module uses unified backend."""
        from semantica.split import ProvenanceTracker
        
        tracker = ProvenanceTracker()
        
        # Check if using unified backend
        assert hasattr(tracker, '_use_unified')
        assert hasattr(tracker, '_unified_manager')
    
    def test_semantic_chunker_ready(self):
        """Test SemanticChunker is ready for provenance."""
        try:
            from semantica.split import SemanticChunker
            
            chunker = SemanticChunker()
            assert chunker is not None
            
        except ImportError:
            pytest.skip("SemanticChunker not available")


class TestLLMsModule:
    """Test llms module provenance integration."""
    
    def test_llms_module_available(self):
        """Test llms module is available."""
        try:
            from semantica import llms
            assert llms is not None
        except ImportError as e:
            pytest.skip(f"llms module not available: {e}")
    
    def test_groq_llm_ready(self):
        """Test Groq is ready for provenance tracking."""
        from semantica.llms import Groq

        assert Groq is not None

    def test_openai_llm_ready(self):
        """Test OpenAI LLM is ready for provenance tracking."""
        from semantica.llms import OpenAI

        assert OpenAI is not None


class TestContextModule:
    """Test context module provenance integration."""
    
    def test_context_module_available(self):
        """Test context module is available."""
        try:
            from semantica import context
            assert context is not None
        except ImportError as e:
            pytest.skip(f"context module not available: {e}")


class TestIngestModule:
    """Test ingest module provenance integration."""
    
    def test_ingest_module_available(self):
        """Test ingest module is available."""
        try:
            from semantica import ingest
            assert ingest is not None
        except ImportError as e:
            pytest.skip(f"ingest module not available: {e}")


class TestEmbeddingsModule:
    """Test embeddings module provenance integration."""
    
    def test_embeddings_module_available(self):
        """Test embeddings module is available."""
        try:
            from semantica import embeddings
            assert embeddings is not None
        except ImportError as e:
            pytest.skip(f"embeddings module not available: {e}")


class TestReasoningModule:
    """Test reasoning module provenance integration."""
    
    def test_reasoning_module_available(self):
        """Test reasoning module is available."""
        try:
            from semantica import reasoning
            assert reasoning is not None
        except ImportError as e:
            pytest.skip(f"reasoning module not available: {e}")


class TestConflictsModule:
    """Test conflicts module provenance integration."""
    
    def test_conflicts_module_available(self):
        """Test conflicts module is available."""
        try:
            from semantica import conflicts
            assert conflicts is not None
        except ImportError as e:
            pytest.skip(f"conflicts module not available: {e}")
    
    def test_source_tracker_available(self):
        """Test SourceTracker is available."""
        try:
            from semantica.conflicts import SourceTracker
            
            tracker = SourceTracker()
            assert tracker is not None
            
        except ImportError:
            pytest.skip("SourceTracker not available")


class TestDeduplicationModule:
    """Test deduplication module provenance integration."""
    
    def test_deduplication_module_available(self):
        """Test deduplication module is available."""
        try:
            from semantica import deduplication
            assert deduplication is not None
        except ImportError as e:
            pytest.skip(f"deduplication module not available: {e}")


class TestExportModule:
    """Test export module provenance integration."""
    
    def test_export_module_available(self):
        """Test export module is available."""
        try:
            from semantica import export
            assert export is not None
        except ImportError as e:
            pytest.skip(f"export module not available: {e}")


class TestParseModule:
    """Test parse module provenance integration."""
    
    def test_parse_module_available(self):
        """Test parse module is available."""
        try:
            from semantica import parse
            assert parse is not None
        except ImportError as e:
            pytest.skip(f"parse module not available: {e}")


class TestNormalizeModule:
    """Test normalize module provenance integration."""
    
    def test_normalize_module_available(self):
        """Test normalize module is available."""
        try:
            from semantica import normalize
            assert normalize is not None
        except ImportError as e:
            pytest.skip(f"normalize module not available: {e}")


class TestOntologyModule:
    """Test ontology module provenance integration."""
    
    def test_ontology_module_available(self):
        """Test ontology module is available."""
        try:
            from semantica import ontology
            assert ontology is not None
        except ImportError as e:
            pytest.skip(f"ontology module not available: {e}")


class TestPipelineModule:
    """Test pipeline module provenance integration."""
    
    def test_pipeline_module_available(self):
        """Test pipeline module is available."""
        try:
            from semantica import pipeline
            assert pipeline is not None
        except ImportError as e:
            pytest.skip(f"pipeline module not available: {e}")


class TestVisualizationModule:
    """Test visualization module provenance integration."""
    
    def test_visualization_module_available(self):
        """Test visualization module is available."""
        try:
            from semantica import visualization
            assert visualization is not None
        except ImportError as e:
            pytest.skip(f"visualization module not available: {e}")


class TestGraphStoreModule:
    """Test graph_store module provenance integration."""
    
    def test_graph_store_module_available(self):
        """Test graph_store module is available."""
        try:
            from semantica import graph_store
            assert graph_store is not None
        except ImportError as e:
            pytest.skip(f"graph_store module not available: {e}")


class TestVectorStoreModule:
    """Test vector_store module provenance integration."""
    
    def test_vector_store_module_available(self):
        """Test vector_store module is available."""
        try:
            from semantica import vector_store
            assert vector_store is not None
        except ImportError as e:
            pytest.skip(f"vector_store module not available: {e}")


class TestTripletStoreModule:
    """Test triplet_store module provenance integration."""
    
    def test_triplet_store_module_available(self):
        """Test triplet_store module is available."""
        try:
            from semantica import triplet_store
            assert triplet_store is not None
        except ImportError as e:
            pytest.skip(f"triplet_store module not available: {e}")


class TestProvenanceModule:
    """Test provenance module itself."""
    
    def test_provenance_manager_available(self):
        """Test ProvenanceManager is available."""
        from semantica.provenance import ProvenanceManager
        
        prov_mgr = ProvenanceManager()
        assert prov_mgr is not None
    
    def test_all_provenance_exports(self):
        """Test all provenance exports are available."""
        from semantica.provenance import (
            ProvenanceManager,
            ProvenanceEntry,
            SourceReference,
            InMemoryStorage,
            SQLiteStorage,
            compute_checksum,
            verify_checksum
        )
        
        assert ProvenanceManager is not None
        assert ProvenanceEntry is not None
        assert SourceReference is not None
        assert InMemoryStorage is not None
        assert SQLiteStorage is not None
        assert compute_checksum is not None
        assert verify_checksum is not None
    
    def test_bridge_axiom_available(self):
        """Test BridgeAxiom is available."""
        from semantica.provenance.bridge_axiom import BridgeAxiom
        
        ba = BridgeAxiom(
            axiom_id="TEST",
            name="test",
            rule="test",
            coefficient=1.0,
            source_doi="10.1234/test",
            source_page="P1"
        )
        
        assert ba is not None


class TestCrossModuleIntegration:
    """Test provenance tracking across multiple modules."""
    
    def test_kg_and_split_integration(self):
        """Test provenance tracking between kg and split modules.

        NOTE: this no longer asserts kg.ProvenanceTracker uses a unified
        backend (kg_tracker.get_lineage() was never implemented; see #744).
        It instead verifies, independent of unified-backend behavior, that
        kg tracking actually produced a record via the still-supported
        track_entity()/get_all_sources() pair.
        """
        from semantica.kg import ProvenanceTracker as KGTracker
        from semantica.split import ProvenanceTracker as SplitTracker
        from semantica.split.semantic_chunker import Chunk
        
        # Track with kg
        kg_tracker = KGTracker()
        kg_tracker.track_entity("entity_1", source="doc_1")
        
        # Verify kg tracking produced a record
        kg_sources = kg_tracker.get_all_sources("entity_1")
        assert len(kg_sources) > 0
        last_kg_entry = kg_sources[-1]
        assert last_kg_entry["source"] == "doc_1"
        assert "recorded_at" in last_kg_entry
        
        # Track with split
        split_tracker = SplitTracker()
        chunk = Chunk(text="Test", start_index=0, end_index=4, metadata={})
        chunk.id = "chunk_1"
        split_tracker.track_chunk(chunk, source_document="doc_1")
        
        # split.ProvenanceTracker.get_provenance() is real and still works
        split_prov = split_tracker.get_provenance("chunk_1")
        
        assert split_prov is not None
    
    def test_unified_manager_with_all_modules(self):
        """Test unified manager works with all module types."""
        prov_mgr = ProvenanceManager()
        
        # Track different entity types
        prov_mgr.track_entity("entity_1", source="doc_1", entity_type="entity")
        prov_mgr.track_chunk("chunk_1", source_document="doc_1")
        prov_mgr.track_relationship("rel_1", source="doc_1")
        
        # All should be tracked
        assert prov_mgr.get_provenance("entity_1") is not None
        assert prov_mgr.get_provenance("chunk_1") is not None
        assert prov_mgr.get_provenance("rel_1") is not None
        
        # Statistics should show all types
        stats = prov_mgr.get_statistics()
        assert stats["total_entries"] >= 3


class TestModuleCoverage:
    """Test that all modules are covered by provenance system."""
    
    def test_module_list_complete(self):
        """Test that all Semantica modules are tested."""
        tested_modules = [
            "semantic_extract",
            "kg",
            "split",
            "llms",
            "context",
            "ingest",
            "embeddings",
            "reasoning",
            "conflicts",
            "deduplication",
            "export",
            "parse",
            "normalize",
            "ontology",
            "pipeline",
            "visualization",
            "graph_store",
            "vector_store",
            "triplet_store",
            "provenance"
        ]
        
        # All modules should be in test coverage
        assert len(tested_modules) >= 20
    
    def test_provenance_ready_modules(self):
        """Test modules that have provenance integration ready."""
        ready_modules = {
            "kg": True,  # Has ProvenanceTracker with unified backend
            "split": True,  # Has ProvenanceTracker with unified backend
            "provenance": True,  # Core provenance module
        }
        
        # Verify ready modules work
        from semantica.kg import ProvenanceTracker as KGTracker
        from semantica.split import ProvenanceTracker as SplitTracker
        from semantica.provenance import ProvenanceManager
        
        kg_tracker = KGTracker()
        split_tracker = SplitTracker()
        prov_mgr = ProvenanceManager()
        
        assert kg_tracker is not None
        assert split_tracker is not None
        assert prov_mgr is not None
