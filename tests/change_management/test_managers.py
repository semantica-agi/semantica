"""
Tests for Enhanced Version Managers

This module tests the enhanced version management capabilities for both
knowledge graphs and ontologies with comprehensive change tracking.
"""

import os
import tempfile
import pytest
from semantica.change_management import (
    TemporalVersionManager,
    OntologyVersionManager,
    ChangeLogEntry
)
from semantica.change_management.change_log import generate_change_report, ChangeLogAnalyzer
from semantica.change_management.ontology_version_manager import VersionManager
from semantica.ontology.engine import OntologyEngine
from semantica.utils.exceptions import ValidationError, ProcessingError


class TestTemporalVersionManager:
    """Test cases for TemporalVersionManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_graph = {
            "entities": [
                {"id": "entity1", "name": "Entity 1", "type": "Person"},
                {"id": "entity2", "name": "Entity 2", "type": "Organization"}
            ],
            "relationships": [
                {"source": "entity1", "target": "entity2", "type": "works_for"}
            ]
        }
    
    def test_in_memory_initialization(self):
        """Test initialization with in-memory storage."""
        manager = TemporalVersionManager()
        assert manager.storage is not None
        assert manager.logger is not None
    
    def test_sqlite_initialization(self):
        """Test initialization with SQLite storage."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            manager = TemporalVersionManager(storage_path=db_path)
            assert manager.storage is not None
            assert os.path.exists(db_path)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
    
    def test_create_snapshot_basic(self):
        """Test basic snapshot creation."""
        manager = TemporalVersionManager()
        
        snapshot = manager.create_snapshot(
            self.sample_graph,
            "test_v1.0",
            "test@example.com",
            "Test snapshot creation"
        )
        
        assert snapshot["label"] == "test_v1.0"
        assert snapshot["author"] == "test@example.com"
        assert snapshot["description"] == "Test snapshot creation"
        assert "checksum" in snapshot
        assert "timestamp" in snapshot
        assert len(snapshot["entities"]) == 2
        assert len(snapshot["relationships"]) == 1
    
    def test_create_snapshot_with_invalid_author(self):
        """Test snapshot creation with invalid author email."""
        manager = TemporalVersionManager()
        
        with pytest.raises(ValidationError, match="Invalid email format"):
            manager.create_snapshot(
                self.sample_graph,
                "test_v1.0",
                "invalid-email",
                "Test snapshot"
            )
    
    def test_create_snapshot_with_long_description(self):
        """Test snapshot creation with description too long."""
        manager = TemporalVersionManager()
        long_description = "x" * 501  # Exceeds 500 character limit
        
        with pytest.raises(ValidationError, match="Description too long"):
            manager.create_snapshot(
                self.sample_graph,
                "test_v1.0",
                "test@example.com",
                long_description
            )
    
    def test_list_versions(self):
        """Test listing versions."""
        manager = TemporalVersionManager()
        
        # Initially empty
        versions = manager.list_versions()
        assert len(versions) == 0
        
        # Create snapshot
        manager.create_snapshot(
            self.sample_graph,
            "test_v1.0",
            "test@example.com",
            "Test snapshot"
        )
        
        # Should have one version
        versions = manager.list_versions()
        assert len(versions) == 1
        assert versions[0]["label"] == "test_v1.0"
    
    def test_get_version(self):
        """Test retrieving specific version."""
        manager = TemporalVersionManager()
        
        # Create snapshot
        original_snapshot = manager.create_snapshot(
            self.sample_graph,
            "test_v1.0",
            "test@example.com",
            "Test snapshot"
        )
        
        # Retrieve version
        retrieved = manager.get_version("test_v1.0")
        assert retrieved is not None
        assert retrieved["label"] == "test_v1.0"
        assert retrieved["checksum"] == original_snapshot["checksum"]
        
        # Non-existent version
        assert manager.get_version("nonexistent") is None
    
    def test_verify_checksum(self):
        """Test checksum verification."""
        manager = TemporalVersionManager()
        
        snapshot = manager.create_snapshot(
            self.sample_graph,
            "test_v1.0",
            "test@example.com",
            "Test snapshot"
        )
        
        # Valid checksum
        assert manager.verify_checksum(snapshot) is True
        
        # Invalid checksum
        snapshot["checksum"] = "invalid_checksum"
        assert manager.verify_checksum(snapshot) is False
    
    def test_compare_versions_detailed(self):
        """Test detailed version comparison."""
        manager = TemporalVersionManager()
        
        # Create first version
        graph_v1 = {
            "entities": [
                {"id": "entity1", "name": "Entity 1", "type": "Person"},
                {"id": "entity2", "name": "Entity 2", "type": "Organization"}
            ],
            "relationships": [
                {"source": "entity1", "target": "entity2", "type": "works_for"}
            ]
        }
        
        manager.create_snapshot(graph_v1, "v1.0", "test@example.com", "Version 1")
        
        # Create second version with changes
        graph_v2 = {
            "entities": [
                {"id": "entity1", "name": "Entity 1 Updated", "type": "Person"},  # Modified
                {"id": "entity3", "name": "Entity 3", "type": "Project"}  # Added
            ],
            "relationships": [
                {"source": "entity1", "target": "entity3", "type": "manages"}  # Added
            ]
        }
        
        manager.create_snapshot(graph_v2, "v2.0", "test@example.com", "Version 2")
        
        # Compare versions
        diff = manager.compare_versions("v1.0", "v2.0")
        
        assert diff["version1"] == "v1.0"
        assert diff["version2"] == "v2.0"
        assert diff["summary"]["entities_added"] == 1
        assert diff["summary"]["entities_removed"] == 1
        assert diff["summary"]["entities_modified"] == 1
        assert diff["summary"]["relationships_added"] == 1
        assert diff["summary"]["relationships_removed"] == 1
        
        # Check detailed changes
        assert len(diff["entities_added"]) == 1
        assert diff["entities_added"][0]["id"] == "entity3"
        
        assert len(diff["entities_modified"]) == 1
        assert diff["entities_modified"][0]["id"] == "entity1"
        assert diff["entities_modified"][0]["changes"]["name"]["from"] == "Entity 1"
        assert diff["entities_modified"][0]["changes"]["name"]["to"] == "Entity 1 Updated"


class TestOntologyVersionManager:
    """Test cases for OntologyVersionManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_ontology = {
            "uri": "https://example.com/ontology",
            "version_info": {"version": "1.0", "date": "2024-01-15"},
            "structure": {
                "classes": ["Person", "Organization"],
                "properties": ["name", "email"],
                "individuals": ["john_doe", "acme_corp"],
                "axioms": ["Person hasName exactly 1 string"]
            }
        }
    
    def test_initialization(self):
        """Test initialization."""
        manager = OntologyVersionManager()
        assert manager.storage is not None
        assert manager.logger is not None
        assert manager.versions == {}
    
    def test_create_snapshot(self):
        """Test ontology snapshot creation."""
        manager = OntologyVersionManager()
        
        snapshot = manager.create_snapshot(
            self.sample_ontology,
            "ont_v1.0",
            "test@example.com",
            "Initial ontology version"
        )
        
        assert snapshot["label"] == "ont_v1.0"
        assert snapshot["author"] == "test@example.com"
        assert snapshot["ontology_iri"] == "https://example.com/ontology"
        assert "checksum" in snapshot
        assert "timestamp" in snapshot
        assert snapshot["structure"]["classes"] == ["Person", "Organization"]
    
    def test_compare_versions_structural(self):
        """Test structural comparison between ontology versions."""
        manager = OntologyVersionManager()
        
        # Create first version
        ontology_v1 = {
            "uri": "https://example.com/ontology",
            "structure": {
                "classes": ["Person", "Organization"],
                "properties": ["name", "email"],
                "individuals": ["john_doe"],
                "axioms": ["Person hasName exactly 1 string"]
            }
        }
        
        manager.create_snapshot(ontology_v1, "v1.0", "test@example.com", "Version 1")
        
        # Create second version with structural changes
        ontology_v2 = {
            "uri": "https://example.com/ontology",
            "structure": {
                "classes": ["Person", "Organization", "Project"],  # Added Project
                "properties": ["name", "email", "description"],  # Added description
                "individuals": ["john_doe", "acme_corp"],  # Added acme_corp
                "axioms": [
                    "Person hasName exactly 1 string",
                    "Project hasDescription some string"  # Added axiom
                ]
            }
        }
        
        manager.create_snapshot(ontology_v2, "v2.0", "test@example.com", "Version 2")
        
        # Compare versions
        diff = manager.compare_versions("v1.0", "v2.0")
        
        assert diff["version1"] == "v1.0"
        assert diff["version2"] == "v2.0"
        
        # Check structural changes
        assert "Project" in diff["classes_added"]
        assert "description" in diff["properties_added"]
        assert "acme_corp" in diff["individuals_added"]
        assert "Project hasDescription some string" in diff["axioms_added"]
        
        # Check summary counts
        assert diff["summary"]["classes_added"] == 1
        assert diff["summary"]["properties_added"] == 1
        assert diff["summary"]["individuals_added"] == 1
        assert diff["summary"]["axioms_added"] == 1
    
    def test_compare_versions_nonexistent(self):
        """Test comparison with nonexistent version."""
        manager = OntologyVersionManager()
        
        with pytest.raises(ValidationError, match="Version not found"):
            manager.compare_versions("nonexistent1", "nonexistent2")
    
    def test_persistence_across_instances(self):
        """Test that data persists across manager instances."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Create snapshot with first instance
            manager1 = OntologyVersionManager(storage_path=db_path)
            manager1.create_snapshot(
                self.sample_ontology,
                "persistent_v1.0",
                "test@example.com",
                "Persistent test"
            )
            
            # Retrieve with second instance
            manager2 = OntologyVersionManager(storage_path=db_path)
            retrieved = manager2.get_version("persistent_v1.0")
            
            assert retrieved is not None
            assert retrieved["label"] == "persistent_v1.0"
            assert retrieved["ontology_iri"] == "https://example.com/ontology"
            
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
                

    def test_diff_empty_ontologies(self):
        """Test diffing entirely empty dictionaries."""
        manager = VersionManager()
        diff = manager.diff_ontologies({}, {})
        
        assert len(diff["added_classes"]) == 0
        assert len(diff["removed_classes"]) == 0
        assert len(diff["changed_classes"]) == 0

    def test_diff_unordered_list_equality(self):
        """Test that list order doesn't trigger a false positive change."""
        manager = VersionManager()
        base = {"classes": [{"uri": "http://ex.org/C1", "domain": ["A", "B"]}]}
        target = {"classes": [{"uri": "http://ex.org/C1", "domain": ["B", "A"]}]}  
        
        diff = manager.diff_ontologies(base, target)
        assert len(diff["changed_classes"]) == 0  

    def test_diff_missing_uris(self):
        """Tests whether missing URIs fallback to 'name' deterministically."""
        manager = VersionManager()
        base = {"classes": [{"name": "Person", "label": "Human"}]}
        target = {"classes": [{"name": "Person", "label": "Homo Sapiens"}]}
        
        diff = manager.diff_ontologies(base, target)
        assert len(diff["changed_classes"]) == 1
        
        change = diff["changed_classes"][0]
        assert change["name"] == "Person"
        assert change["changes"]["label"]["old"] == "Human"
        assert change["changes"]["label"]["new"] == "Homo Sapiens"


class TestChangeLogAnalyzer:
    """Test cases for Impact Analysis & Reporting."""

    def test_breaking_change_removed_class(self):
        """Test that removing a class is flagged as CRITICAL/BREAKING."""
        diff = {"removed_classes": [{"uri": "http://ex.org/Person"}]}
        report = generate_change_report(diff)
        
        assert len(report["impact_classification"]["breaking"]) == 1
        assert report["impact_classification"]["breaking"][0]["severity"] == "critical"
        assert "removed" in report["impact_classification"]["breaking"][0]["description"]

    def test_breaking_change_narrowed_domain(self):
        """Test that narrowing a domain is flagged as HIGH/BREAKING."""
        diff = {
            "changed_properties": [{
                "uri": "http://ex.org/worksFor", 
                "changes": {"domain": {"old": ["Person", "Organization"], "new": ["Person"]}}
            }]
        }
        report = generate_change_report(diff)
        
        assert len(report["impact_classification"]["breaking"]) == 1
        assert report["impact_classification"]["breaking"][0]["severity"] == "high"
        assert "restricted" in report["impact_classification"]["breaking"][0]["description"]

    def test_safe_change_added_class_and_label(self):
        """Test that adding classes and changing annotations is SAFE."""
        diff = {
            "added_classes": [{"uri": "http://ex.org/NewClass"}],
            "changed_properties": [{
                "uri": "http://ex.org/name", 
                "changes": {"label": {"old": "Name", "new": "Full Name"}}
            }]
        }
        report = generate_change_report(diff)
        
        assert len(report["impact_classification"]["safe"]) == 2
        assert len(report["impact_classification"]["breaking"]) == 0
        assert len(report["impact_classification"]["potentially_breaking"]) == 0


class TestOntologyEngineMigration:
    """Test cases for Public API Orchestration."""

    def test_compare_versions_with_dicts_override(self):
        """Test for bypassing the DB fetch by passing dicts directly."""
        engine = OntologyEngine()
        
        base_dict = {"classes": [{"uri": "http://ex.org/C1", "label": "Old"}]}
        target_dict = {"classes": [{"uri": "http://ex.org/C1", "label": "New"}]}
        
        # We pass fake version IDs ("v1", "v2"), but the engine should use our dicts
        report = engine.compare_versions("v1", "v2", base_dict=base_dict, target_dict=target_dict)
        
        assert report["summary"]["total_changes"] == 1
        assert len(report["impact_classification"]["safe"]) == 1
        assert report["impact_classification"]["safe"][0]["entity_uri"] == "http://ex.org/C1"

    def test_compare_versions_version_not_found_raises(self):
        """Test that compare_versions raises ProcessingError when version ID is not registered."""
        engine = OntologyEngine()

        with pytest.raises(ProcessingError):
            engine.compare_versions("nonexistent_v1", "nonexistent_v2")

    def test_compare_versions_diff_includes_individuals_and_axioms(self):
        """Test that the diff covers individuals and axioms, not just classes/properties."""
        engine = OntologyEngine()

        base_dict = {
            "classes": [],
            "properties": [],
            "individuals": [{"uri": "http://ex.org/john"}],
            "axioms": [{"uri": "http://ex.org/rule1", "expression": "Person hasName exactly 1 string"}],
        }
        target_dict = {
            "classes": [],
            "properties": [],
            "individuals": [
                {"uri": "http://ex.org/john"},
                {"uri": "http://ex.org/jane"},
            ],
            "axioms": [],
        }

        report = engine.compare_versions("v1", "v2", base_dict=base_dict, target_dict=target_dict)

        diff = report["diff"]
        assert any(i.get("uri") == "http://ex.org/jane" for i in diff["added_individuals"])
        assert any(a.get("uri") == "http://ex.org/rule1" for a in diff["removed_axioms"])

    def test_compare_versions_null_constraint_value_flagged_as_breaking(self):
        """Test that a constraint field going from None to a value is flagged as breaking."""
        diff = {
            "changed_properties": [{
                "uri": "http://ex.org/worksFor",
                "changes": {"domain": {"old": None, "new": ["Person"]}}
            }]
        }
        report = generate_change_report(diff)

        assert len(report["impact_classification"]["breaking"]) == 1
        assert report["impact_classification"]["breaking"][0]["severity"] == "high"
