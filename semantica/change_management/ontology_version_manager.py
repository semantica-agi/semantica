"""
Ontology Version Manager Module

This module provides ontology versioning following best practices:
- Single ontology IRI that resolves to specific version (includes version in IRI)
- Version-less element IRIs (stable across versions)
- owl:versionInfo for tool compatibility
- Version-less logical IRIs for latest stable release
- Multiple versions can coexist in same graph database

Key Features:
    - Version-aware IRI generation (version in ontology IRI, not element IRIs)
    - Version-less element IRIs for stability
    - owl:versionInfo metadata support
    - Logical version-less IRIs for latest releases
    - Multi-version coexistence in graph database
    - Import closure resolution under versioning
    - Version comparison and diff generation
    - Migration and upgrade utilities

Main Classes:
    - VersionManager: Manager for ontology versioning
    - OntologyVersion: Dataclass representing an ontology version

Example Usage:
    >>> from semantica.ontology import VersionManager
    >>> manager = VersionManager(base_uri="https://example.org/ontology/")
    >>> version = manager.create_version("1.0", ontology, changes=["Added Person class"])
    >>> element_iri = manager.generate_element_iri("Person", "class")
    >>> comparison = manager.compare_versions("1.0", "2.0")
    >>> migrated = manager.migrate_ontology("1.0", "2.0", ontology)

Author: Semantica Contributors
License: MIT
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from ..ontology.namespace_manager import NamespaceManager


@dataclass
class OntologyVersion:
    """Ontology version information."""

    version: str
    ontology_iri: str
    version_info: str
    created_at: str
    changes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VersionManager:
    """
    Ontology version management system.

    • Version-aware IRI generation (version in ontology IRI, not element IRIs)
    • Version-less element IRIs for stability
    • owl:versionInfo metadata support
    • Logical version-less IRIs for latest releases
    • Multi-version coexistence in graph database
    • Import closure resolution under versioning
    • Version comparison and diff generation
    • Migration and upgrade utilities
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize version manager.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options:
                - base_uri: Base URI for ontology
                - namespace_manager: Namespace manager instance
        """
        self.logger = get_logger("version_manager")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.namespace_manager = self.config.get(
            "namespace_manager"
        ) or NamespaceManager(**self.config)
        self.versions: Dict[str, OntologyVersion] = {}
        self.latest_version: Optional[str] = None

    def create_version(
        self, version: str, ontology: Dict[str, Any], **options
    ) -> OntologyVersion:
        """
        Create a new ontology version.

        Args:
            version: Version string (e.g., "1.0", "2.1")
            ontology: Ontology dictionary
            **options: Additional options:
                - changes: List of changes
                - metadata: Additional metadata

        Returns:
            Created version record
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="ontology",
            submodule="VersionManager",
            message=f"Creating ontology version {version}",
        )

        try:
            # Generate versioned ontology IRI
            self.progress_tracker.update_tracking(
                tracking_id, message="Generating versioned IRI..."
            )
            base_uri = ontology.get("uri") or self.namespace_manager.get_base_uri()
            versioned_iri = self._generate_versioned_iri(base_uri, version)

            # Create version record
            self.progress_tracker.update_tracking(
                tracking_id, message="Creating version record..."
            )
            version_record = OntologyVersion(
                version=version,
                ontology_iri=versioned_iri,
                version_info=f"{version}",
                created_at=datetime.now().isoformat(),
                changes=options.get("changes", []),
                metadata=options.get("metadata", {}),
            )

            self.versions[version] = version_record
            self.latest_version = version

            # Update ontology with version info
            ontology["version"] = version
            ontology["uri"] = versioned_iri
            ontology["versionInfo"] = version_record.version_info

            self.logger.info(f"Created ontology version: {version}")
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Created ontology version {version}",
            )
            return version_record

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _generate_versioned_iri(self, base_uri: str, version: str) -> str:
        """Generate versioned ontology IRI."""
        # Remove trailing slash
        base_uri = base_uri.rstrip("/")

        # Add version to IRI
        suffix = f"/v{version}"
        if base_uri.endswith(suffix):
            return base_uri
        return f"{base_uri}{suffix}"

    def generate_element_iri(
        self, element_name: str, element_type: str = "class"
    ) -> str:
        """
        Generate version-less element IRI.

        Args:
            element_name: Element name
            element_type: Element type ('class', 'property', 'individual')

        Returns:
            Element IRI (version-less)
        """
        # Use base URI without version for elements
        base_uri = self.namespace_manager.get_base_uri()

        if element_type == "class":
            return self.namespace_manager.generate_class_iri(element_name)
        elif element_type == "property":
            return self.namespace_manager.generate_property_iri(element_name)
        else:
            return self.namespace_manager.generate_individual_iri(element_name)

    def compare_versions(self, version1: str, version2: str) -> Dict[str, Any]:
        """
        Compare two ontology versions with detailed structural analysis.

        Args:
            version1: First version
            version2: Second version

        Returns:
            Detailed comparison results including structural differences
        """
        if version1 not in self.versions:
            raise ValidationError(f"Version not found: {version1}")
        if version2 not in self.versions:
            raise ValidationError(f"Version not found: {version2}")

        v1 = self.versions[version1]
        v2 = self.versions[version2]

        # Basic metadata comparison
        metadata_changes = {}
        if v1.ontology_iri != v2.ontology_iri:
            metadata_changes["ontology_iri"] = {"from": v1.ontology_iri, "to": v2.ontology_iri}
        if v1.version_info != v2.version_info:
            metadata_changes["version_info"] = {"from": v1.version_info, "to": v2.version_info}

        # Structural comparison (if ontology data is available in metadata)
        structural_diff = self._compare_ontology_structures(v1, v2)

        return {
            "version1": version1,
            "version2": version2,
            "metadata_changes": metadata_changes,
            **structural_diff
        }

    def _compare_ontology_structures(self, v1: OntologyVersion, v2: OntologyVersion) -> Dict[str, Any]:
        """
        Compare structural elements between two ontology versions.
        
        Args:
            v1: First ontology version
            v2: Second ontology version
            
        Returns:
            Dictionary with structural differences
        """
        # Extract structural information from metadata if available
        v1_structure = v1.metadata.get("structure", {})
        v2_structure = v2.metadata.get("structure", {})
        
        # Compare classes
        v1_classes = set(v1_structure.get("classes", []))
        v2_classes = set(v2_structure.get("classes", []))
        
        classes_added = list(v2_classes - v1_classes)
        classes_removed = list(v1_classes - v2_classes)
        
        # Compare properties
        v1_properties = set(v1_structure.get("properties", []))
        v2_properties = set(v2_structure.get("properties", []))
        
        properties_added = list(v2_properties - v1_properties)
        properties_removed = list(v1_properties - v2_properties)
        
        # Compare individuals
        v1_individuals = set(v1_structure.get("individuals", []))
        v2_individuals = set(v2_structure.get("individuals", []))
        
        individuals_added = list(v2_individuals - v1_individuals)
        individuals_removed = list(v1_individuals - v2_individuals)
        
        # Compare axioms/rules if available
        v1_axioms = set(v1_structure.get("axioms", []))
        v2_axioms = set(v2_structure.get("axioms", []))
        
        axioms_added = list(v2_axioms - v1_axioms)
        axioms_removed = list(v1_axioms - v2_axioms)
        
        return {
            "classes_added": classes_added,
            "classes_removed": classes_removed,
            "properties_added": properties_added,
            "properties_removed": properties_removed,
            "individuals_added": individuals_added,
            "individuals_removed": individuals_removed,
            "axioms_added": axioms_added,
            "axioms_removed": axioms_removed,
            "summary": {
                "classes_added": len(classes_added),
                "classes_removed": len(classes_removed),
                "properties_added": len(properties_added),
                "properties_removed": len(properties_removed),
                "individuals_added": len(individuals_added),
                "individuals_removed": len(individuals_removed),
                "axioms_added": len(axioms_added),
                "axioms_removed": len(axioms_removed)
            }
        }
    
    def diff_ontologies(self, base: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes a structured diff between two ontology versions.
        """
        def _compute_section_diff(base_list, target_list):
    
            base_map = {}
            for item in base_list:
                if isinstance(item, dict):
                    key = item.get("uri") or item.get("name")
                    if key:
                        base_map[key] = item
                elif isinstance(item, str):
                    base_map[item] = {"uri": item}

            target_map = {}
            for item in target_list:
                if isinstance(item, dict):
                    key = item.get("uri") or item.get("name")
                    if key:
                        target_map[key] = item
                elif isinstance(item, str):
                    target_map[item] = {"uri": item}
            
            added, removed, changed = [], [], []
            
            # Find Added and Changed 
            for key, t_item in target_map.items():
                if key not in base_map:
                    added.append(t_item)
                else:
                    b_item = base_map[key]
                    changes = {}
                    
                    all_fields = set(b_item.keys()).union(t_item.keys())
                    for field in all_fields:
                        if field in ["uri", "name"]: 
                            continue
                        
                        b_val = b_item.get(field)
                        t_val = t_item.get(field)
                        
                        # Deep equality check for lists
                        if isinstance(b_val, list) and isinstance(t_val, list):
                            if set(str(x) for x in b_val) != set(str(x) for x in t_val):
                                changes[field] = {"old": b_val, "new": t_val}
                        elif b_val != t_val:
                            changes[field] = {"old": b_val, "new": t_val}
                    
                    if changes:
                        changed.append({
                            "uri": t_item.get("uri") or key,
                            "name": t_item.get("name") or key,
                            "changes": changes
                        })
                        
            # Find deleted
            for key, b_item in base_map.items():
                if key not in target_map:
                    removed.append(b_item)
                    
            return added, removed, changed


        classes_added, classes_removed, classes_changed = _compute_section_diff(
            base.get("classes", []), target.get("classes", [])
        )
        props_added, props_removed, props_changed = _compute_section_diff(
            base.get("properties", []), target.get("properties", [])
        )
        inds_added, inds_removed, inds_changed = _compute_section_diff(
            base.get("individuals", []), target.get("individuals", [])
        )
        axioms_added, axioms_removed, axioms_changed = _compute_section_diff(
            base.get("axioms", []), target.get("axioms", [])
        )

        return {
            "added_classes": classes_added,
            "removed_classes": classes_removed,
            "changed_classes": classes_changed,
            "added_properties": props_added,
            "removed_properties": props_removed,
            "changed_properties": props_changed,
            "added_individuals": inds_added,
            "removed_individuals": inds_removed,
            "changed_individuals": inds_changed,
            "added_axioms": axioms_added,
            "removed_axioms": axioms_removed,
            "changed_axioms": axioms_changed,
        }

    def get_version(self, version: str) -> Optional[OntologyVersion]:
        """Get version by version string."""
        return self.versions.get(version)

    def get_latest_version(self) -> Optional[OntologyVersion]:
        """Get latest version."""
        if self.latest_version:
            return self.versions.get(self.latest_version)
        return None

    def list_versions(self) -> List[str]:
        """List all version strings."""
        return list(self.versions.keys())

    def migrate_ontology(
        self, from_version: str, to_version: str, ontology: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Migrate ontology between versions.

        Args:
            from_version: Source version
            to_version: Target version
            ontology: Ontology dictionary

        Returns:
            Migrated ontology
        """
        if from_version not in self.versions:
            raise ValidationError(f"Source version not found: {from_version}")
        if to_version not in self.versions:
            raise ValidationError(f"Target version not found: {to_version}")

        # Update version info
        ontology["version"] = to_version
        ontology["uri"] = self.versions[to_version].ontology_iri
        ontology["versionInfo"] = self.versions[to_version].version_info

        self.logger.info(f"Migrated ontology from {from_version} to {to_version}")

        return ontology

    def resolve_versioned_imports(self, ontology: Dict[str, Any]) -> List[str]:
        """
        Resolve import closure under versioning.

        Args:
            ontology: Ontology dictionary

        Returns:
            List of resolved import URIs
        """
        imports = ontology.get("imports", [])
        resolved = set(imports)

        # Resolve transitive imports (basic implementation)
        for import_uri in imports:
            # Check if it's a versioned import
            if "/v" in import_uri:
                # Extract version
                version_match = re.search(r"/v(\d+\.\d+)", import_uri)
                if version_match:
                    version = version_match.group(1)
                    # Check if we have this version
                    if version in self.versions:
                        version_imports = self.versions[version].metadata.get(
                            "imports", []
                        )
                        resolved.update(version_imports)

        return list(resolved)
