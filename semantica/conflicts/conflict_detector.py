"""
Conflict Detector

This module provides comprehensive conflict detection capabilities for the
Semantica framework, detecting conflicts from multiple sources and tracking
source disagreements for compliance and investigation.
Includes integrated progress tracking for large-scale conflict detection.

Algorithms Used:

Conflict Detection:
    - Value Comparison: Property value comparison across sources with equality checking
    - Type Mismatch Detection: Entity type comparison and mismatch identification
    - Relationship Consistency: Relationship property comparison and inconsistency
      detection
    - Temporal Analysis: Time-based conflict detection using timestamp comparison
    - Logical Consistency: Logical rule validation and inconsistency detection

Severity Calculation:
    - Multi-factor Severity Scoring: Combines property importance, value difference
      magnitude, and source count to calculate conflict severity (low, medium,
      high, critical)
    - Critical Field Detection: Identifies critical fields (id, name, type, etc.)
      for higher severity
    - Numeric Difference Analysis: Calculates severity based on numeric value
      differences

Confidence Scoring:
    - Source Credibility Weighting: Uses average confidence of sources
    - Value Diversity Factor: Higher confidence for more diverse conflicting values
    - Combined Confidence: Combines source confidence and value diversity

Key Features:
    - Detects property value conflicts
    - Identifies relationship conflicts
    - Tracks source disagreements
    - Generates conflict reports
    - Provides investigation guides
    - Multiple conflict types (value, type, relationship, temporal, logical)
    - Severity calculation
    - Confidence scoring
    - Source provenance tracking

Main Classes:
    - ConflictType: Conflict type enumeration
    - Conflict: Conflict information data structure
    - ConflictDetector: Conflict detector for multi-source conflict identification

Example Usage:
    >>> from semantica.conflicts import ConflictDetector
    >>> detector = ConflictDetector()
    >>> conflicts = detector.detect_value_conflicts(entities, "name")
    >>> report = detector.get_conflict_report()

Author: Semantica Contributors
License: MIT
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .source_tracker import SourceReference, SourceTracker


class ConflictType(str, Enum):
    """Conflict type enumeration."""

    VALUE_CONFLICT = "value_conflict"
    TYPE_CONFLICT = "type_conflict"
    RELATIONSHIP_CONFLICT = "relationship_conflict"
    TEMPORAL_CONFLICT = "temporal_conflict"
    LOGICAL_CONFLICT = "logical_conflict"


@dataclass
class Conflict:
    """Conflict information."""

    conflict_id: str
    conflict_type: ConflictType
    entity_id: Optional[str] = None
    property_name: Optional[str] = None
    relationship_id: Optional[str] = None
    conflicting_values: List[Any] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    severity: str = "medium"  # low, medium, high, critical
    recommended_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConflictDetector:
    """
    Conflict detector for multi-source conflict identification.

    • Detects property value conflicts
    • Identifies relationship conflicts
    • Tracks source disagreements
    • Generates conflict reports
    • Provides investigation guides
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize conflict detector.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options:
                - track_provenance: Track source provenance (default: True)
                - conflict_fields: Fields to monitor for conflicts
                - confidence_threshold: Minimum confidence for conflicts (default: 0.7)
                - auto_resolve: Auto-resolve simple conflicts (default: False)
        """
        self.logger = get_logger("conflict_detector")
        self.config = config or {}
        self.config.update(kwargs)

        self.source_tracker = self.config.get("source_tracker") or SourceTracker()
        self.track_provenance = self.config.get("track_provenance", True)
        self.conflict_fields = self.config.get("conflict_fields", {})
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.auto_resolve = self.config.get("auto_resolve", False)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.detected_conflicts: Dict[str, Conflict] = {}

    def detect_value_conflicts(
        self,
        entities: Union[List[Dict[str, Any]], Dict[str, Any]],
        property_name: str,
        entity_type: Optional[str] = None,
    ) -> List[Conflict]:
        """
        Detect property value conflicts.

        Args:
            entities: List of entity dictionaries or Graph dictionary
            property_name: Property name to check
            entity_type: Optional entity type filter

        Returns:
            List of detected conflicts
        """
        # Handle graph dictionary input
        if isinstance(entities, dict):
            if "entities" in entities:
                entities = entities["entities"]
            else:
                entities = [entities]

        # Track conflict detection
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting value conflicts for property: {property_name}",
        )

        try:
            conflicts = []

            # Group entities by ID (same entity from different sources)
            entity_groups: Dict[str, List[Dict[str, Any]]] = {}

            self.progress_tracker.update_tracking(
                tracking_id, message=f"Analyzing {len(entities)} entities..."
            )

            total_entities = len(entities)
            if total_entities <= 10:
                update_interval = 1  # Update every item for small datasets
            else:
                update_interval = max(1, min(10, total_entities // 100))
            
            # Initial progress update - ALWAYS show this
            remaining = total_entities
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_entities,
                message=f"Analyzing entities... 0/{total_entities} (remaining: {remaining})"
            )
            
            for i, entity in enumerate(entities):
                entity_id = entity.get("id") or entity.get("entity_id")
                if not entity_id:
                    continue

                if entity_type and entity.get("type") != entity_type:
                    continue

                if entity_id not in entity_groups:
                    entity_groups[entity_id] = []
                entity_groups[entity_id].append(entity)
                
                remaining = total_entities - (i + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (i + 1) % update_interval == 0 or 
                    (i + 1) == total_entities or 
                    i == 0 or
                    total_entities <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=i + 1,
                        total=total_entities,
                        message=f"Analyzing entities... {i + 1}/{total_entities} (remaining: {remaining})"
                    )

            # Check each entity group for conflicts
            total_groups = len(entity_groups)
            if total_groups <= 10:
                group_update_interval = 1  # Update every item for small datasets
            else:
                group_update_interval = max(1, min(10, total_groups // 100))
            
            # Initial progress update for group checking
            remaining_groups = total_groups
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_groups,
                message=f"Checking entity groups for conflicts... 0/{total_groups} (remaining: {remaining_groups})"
            )
            
            for j, (entity_id, entity_list) in enumerate(entity_groups.items()):
                if len(entity_list) < 2:
                    continue  # Need at least 2 sources to have conflict

                values = []
                sources = []

                for entity in entity_list:
                    if property_name in entity:
                        value = entity[property_name]
                        values.append(value)

                        # Track source if available
                        if self.track_provenance:
                            source_ref = SourceReference(
                                document=entity.get("source", "unknown"),
                                page=entity.get("page"),
                                section=entity.get("section"),
                                confidence=entity.get("confidence", 1.0),
                                metadata=entity.get("metadata", {}),
                            )
                            self.source_tracker.track_property_source(
                                entity_id, property_name, value, source_ref
                            )
                            sources.append(
                                {
                                    "document": source_ref.document,
                                    "page": source_ref.page,
                                    "confidence": source_ref.confidence,
                                    "metadata": source_ref.metadata,
                                }
                            )

                # Check for value conflicts
                unique_values = list(set(str(v) for v in values if v is not None))

                if len(unique_values) > 1:
                    conflict = Conflict(
                        conflict_id=f"{entity_id}_{property_name}_conflict",
                        conflict_type=ConflictType.VALUE_CONFLICT,
                        entity_id=entity_id,
                        property_name=property_name,
                        conflicting_values=values,
                        sources=sources,
                        confidence=self._calculate_conflict_confidence(values, sources),
                        severity=self._calculate_severity(property_name, values),
                        recommended_action=self._recommend_action(
                            property_name, values
                        ),
                    )
                    conflicts.append(conflict)
                    self.detected_conflicts[conflict.conflict_id] = conflict

                    self.logger.warning(
                        f"Value conflict detected: {entity_id}.{property_name} "
                        f"has conflicting values: {unique_values}"
                    )
                
                remaining_groups = total_groups - (j + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (j + 1) % group_update_interval == 0 or 
                    (j + 1) == total_groups or 
                    j == 0 or
                    total_groups <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=j + 1,
                        total=total_groups,
                        message=f"Checking entity groups for conflicts... {j + 1}/{total_groups} (remaining: {remaining_groups})"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(conflicts)} conflicts",
            )
            return conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def detect_property_conflicts(
        self, entities: List[Dict[str, Any]], property_name: str
    ) -> List[Conflict]:
        """
        Detect conflicts in a specific property across entities.

        Args:
            entities: List of entity dictionaries
            property_name: Property name to check

        Returns:
            List of detected conflicts
        """
        return self.detect_value_conflicts(entities, property_name)

    def detect_relationship_conflicts(
        self, relationships: List[Dict[str, Any]]
    ) -> List[Conflict]:
        """
        Detect conflicts in relationships.

        Args:
            relationships: List of relationship dictionaries

        Returns:
            List of detected conflicts
        """
        # Track relationship conflict detection
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting relationship conflicts in {len(relationships)} relationships",
        )

        try:
            conflicts = []

            # Group relationships by ID
            rel_groups: Dict[str, List[Dict[str, Any]]] = {}
            total_rels = len(relationships)
            if total_rels <= 10:
                update_interval = 1  # Update every item for small datasets
            else:
                update_interval = max(1, min(10, total_rels // 100))
            
            # Initial progress update
            remaining = total_rels
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_rels,
                message=f"Grouping relationships... 0/{total_rels} (remaining: {remaining})"
            )

            for i, rel in enumerate(relationships):
                rel_id = (
                    rel.get("id")
                    or f"{rel.get('source_id')}_{rel.get('target_id')}_{rel.get('type')}"
                )

                if rel_id not in rel_groups:
                    rel_groups[rel_id] = []
                rel_groups[rel_id].append(rel)
                
                remaining = total_rels - (i + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (i + 1) % update_interval == 0 or 
                    (i + 1) == total_rels or 
                    i == 0 or
                    total_rels <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=i + 1,
                        total=total_rels,
                        message=f"Grouping relationships... {i + 1}/{total_rels} (remaining: {remaining})"
                    )

            # Check for conflicts
            total_groups = len(rel_groups)
            if total_groups <= 10:
                group_update_interval = 1  # Update every item for small datasets
            else:
                group_update_interval = max(1, min(10, total_groups // 100))
            
            # Initial progress update for group checking
            remaining_groups = total_groups
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_groups,
                message=f"Checking relationship groups... 0/{total_groups} (remaining: {remaining_groups})"
            )
            
            for j, (rel_id, rel_list) in enumerate(rel_groups.items()):
                if len(rel_list) < 2:
                    continue

                # Check for conflicting properties
                for prop_name in ["type", "properties", "confidence"]:
                    values = [r.get(prop_name) for r in rel_list if prop_name in r]
                    unique_values = list(set(str(v) for v in values if v is not None))

                    if len(unique_values) > 1:
                        conflict = Conflict(
                            conflict_id=f"{rel_id}_{prop_name}_conflict",
                            conflict_type=ConflictType.RELATIONSHIP_CONFLICT,
                            relationship_id=rel_id,
                            property_name=prop_name,
                            conflicting_values=values,
                            confidence=0.8,
                            severity="medium",
                            recommended_action="Review relationship definition",
                        )
                        conflicts.append(conflict)
                        self.detected_conflicts[conflict.conflict_id] = conflict
                
                remaining_groups = total_groups - (j + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (j + 1) % group_update_interval == 0 or 
                    (j + 1) == total_groups or 
                    j == 0 or
                    total_groups <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=j + 1,
                        total=total_groups,
                        message=f"Checking relationship groups... {j + 1}/{total_groups} (remaining: {remaining_groups})"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(conflicts)} relationship conflicts",
            )
            return conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def detect_entity_conflicts(
        self, entities: List[Dict[str, Any]], entity_type: Optional[str] = None
    ) -> List[Conflict]:
        """
        Detect conflicts across all monitored properties for entities.

        Args:
            entities: List of entity dictionaries
            entity_type: Optional entity type filter

        Returns:
            List of detected conflicts
        """
        # Track entity conflict detection
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting entity conflicts in {len(entities)} entities",
        )

        try:
            all_conflicts = []

            # Get fields to monitor
            if entity_type and entity_type in self.conflict_fields:
                fields_to_check = self.conflict_fields[entity_type]
            else:
                # Check all common properties
                fields_to_check = set()
                for entity in entities:
                    fields_to_check.update(entity.keys())
                fields_to_check = list(
                    fields_to_check - {"id", "entity_id", "type", "source", "metadata"}
                )

            total_fields = len(fields_to_check)
            if total_fields <= 10:
                update_interval = 1  # Update every item for small datasets
            else:
                update_interval = max(1, min(10, total_fields // 100))
            
            # Initial progress update
            remaining = total_fields
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_fields,
                message=f"Checking fields for conflicts... 0/{total_fields} (remaining: {remaining})"
            )

            # Check each field
            for i, field_name in enumerate(fields_to_check):
                conflicts = self.detect_value_conflicts(entities, field_name, entity_type)
                all_conflicts.extend(conflicts)
                
                remaining = total_fields - (i + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (i + 1) % update_interval == 0 or 
                    (i + 1) == total_fields or 
                    i == 0 or
                    total_fields <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=i + 1,
                        total=total_fields,
                        message=f"Checking fields for conflicts... {i + 1}/{total_fields} (remaining: {remaining})"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(all_conflicts)} entity conflicts",
            )
            return all_conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _calculate_conflict_confidence(
        self, values: List[Any], sources: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for conflict."""
        if not sources:
            return 0.5

        # Average confidence of sources
        avg_confidence = sum(s.get("confidence", 0.5) for s in sources) / len(sources)

        # Higher confidence if values are very different
        value_diversity = (
            len(set(str(v) for v in values)) / len(values) if values else 0
        )

        return min(1.0, avg_confidence * (1 + value_diversity))

    def _calculate_severity(self, property_name: str, values: List[Any]) -> str:
        """Calculate conflict severity."""
        # Critical fields
        critical_fields = ["id", "name", "type", "founded_year", "revenue"]
        if property_name.lower() in critical_fields:
            return "critical"

        # High severity for numeric conflicts with large differences
        try:
            numeric_values = [float(v) for v in values if v is not None]
            if numeric_values:
                value_range = max(numeric_values) - min(numeric_values)
                if value_range > 1000:  # Large difference
                    return "high"
        except (ValueError, TypeError):
            pass

        return "medium"

    def _recommend_action(self, property_name: str, values: List[Any]) -> str:
        """Recommend action for conflict."""
        try:
            if len(set(values)) == 2:
                return (
                    "Compare source documents and use most recent or authoritative "
                    "source"
                )
        except TypeError:
            # Handle unhashable types (like dicts or lists)
            # Convert to string representation for set comparison
            str_values = [str(v) for v in values]
            if len(set(str_values)) == 2:
                return (
                    "Compare source documents and use most recent or authoritative "
                    "source"
                )

        return "Multiple conflicting values detected. Manual review recommended."

    def get_conflict_report(self) -> Dict[str, Any]:
        """
        Generate conflict report.

        Returns:
            Conflict report dictionary
        """
        report = {
            "total_conflicts": len(self.detected_conflicts),
            "by_type": {},
            "by_severity": {},
            "conflicts": [],
        }

        for conflict in self.detected_conflicts.values():
            # Count by type
            conflict_type = conflict.conflict_type.value
            report["by_type"][conflict_type] = (
                report["by_type"].get(conflict_type, 0) + 1
            )

            # Count by severity
            report["by_severity"][conflict.severity] = (
                report["by_severity"].get(conflict.severity, 0) + 1
            )

            # Add conflict details
            conflict_data = {
                "conflict_id": conflict.conflict_id,
                "type": conflict_type,
                "entity_id": conflict.entity_id,
                "property_name": conflict.property_name,
                "severity": conflict.severity,
                "conflicting_values": conflict.conflicting_values,
                "sources": conflict.sources,
                "recommended_action": conflict.recommended_action,
            }
            report["conflicts"].append(conflict_data)

        return report

    def detect_type_conflicts(self, entities: List[Dict[str, Any]]) -> List[Conflict]:
        """
        Detect entity type conflicts.

        Args:
            entities: List of entity dictionaries

        Returns:
            List of detected conflicts
        """
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting type conflicts in {len(entities)} entities",
        )

        try:
            conflicts = []

            # Group entities by ID
            entity_groups: Dict[str, List[Dict[str, Any]]] = {}
            total_entities = len(entities)
            if total_entities <= 10:
                update_interval = 1  # Update every item for small datasets
            else:
                update_interval = max(1, min(10, total_entities // 100))
            
            # Initial progress update
            remaining = total_entities
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_entities,
                message=f"Grouping entities... 0/{total_entities} (remaining: {remaining})"
            )

            for i, entity in enumerate(entities):
                entity_id = entity.get("id") or entity.get("entity_id")
                if not entity_id:
                    continue

                if entity_id not in entity_groups:
                    entity_groups[entity_id] = []
                entity_groups[entity_id].append(entity)
                
                remaining = total_entities - (i + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (i + 1) % update_interval == 0 or 
                    (i + 1) == total_entities or 
                    i == 0 or
                    total_entities <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=i + 1,
                        total=total_entities,
                        message=f"Grouping entities... {i + 1}/{total_entities} (remaining: {remaining})"
                    )

            # Check each entity group for type conflicts
            total_groups = len(entity_groups)
            if total_groups <= 10:
                group_update_interval = 1  # Update every item for small datasets
            else:
                group_update_interval = max(1, min(10, total_groups // 100))
            
            # Initial progress update for group checking
            remaining_groups = total_groups
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_groups,
                message=f"Checking entity groups for type conflicts... 0/{total_groups} (remaining: {remaining_groups})"
            )
            
            for j, (entity_id, entity_list) in enumerate(entity_groups.items()):
                if len(entity_list) < 2:
                    continue  # Need at least 2 sources to have conflict

                types = []
                sources = []

                for entity in entity_list:
                    entity_type = entity.get("type") or entity.get("entity_type")
                    if entity_type:
                        types.append(entity_type)

                        if self.track_provenance:
                            source_ref = SourceReference(
                                document=entity.get("source", "unknown"),
                                page=entity.get("page"),
                                section=entity.get("section"),
                                confidence=entity.get("confidence", 1.0),
                                metadata=entity.get("metadata", {}),
                            )
                            self.source_tracker.track_entity_source(
                                entity_id, source_ref
                            )
                            sources.append(
                                {
                                    "document": source_ref.document,
                                    "page": source_ref.page,
                                    "confidence": source_ref.confidence,
                                }
                            )

                # Check for type conflicts
                unique_types = list(set(str(t) for t in types if t is not None))

                if len(unique_types) > 1:
                    conflict = Conflict(
                        conflict_id=f"{entity_id}_type_conflict",
                        conflict_type=ConflictType.TYPE_CONFLICT,
                        entity_id=entity_id,
                        property_name="type",
                        conflicting_values=types,
                        sources=sources,
                        confidence=self._calculate_conflict_confidence(types, sources),
                        severity=self._calculate_severity("type", types),
                        recommended_action=(
                            "Review entity type definitions and classification"
                        ),
                    )
                    conflicts.append(conflict)
                    self.detected_conflicts[conflict.conflict_id] = conflict

                    self.logger.warning(
                        f"Type conflict detected: {entity_id} conflicting types: "
                        f"{unique_types}"
                    )
                
                remaining_groups = total_groups - (j + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (j + 1) % group_update_interval == 0 or 
                    (j + 1) == total_groups or 
                    j == 0 or
                    total_groups <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=j + 1,
                        total=total_groups,
                        message=f"Checking entity groups for type conflicts... {j + 1}/{total_groups} (remaining: {remaining_groups})"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(conflicts)} type conflicts",
            )
            return conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def detect_temporal_conflicts(
        self, entities: List[Dict[str, Any]]
    ) -> List[Conflict]:
        """
        Detect temporal conflicts (e.g., founded year conflicts).

        Args:
            entities: List of entity dictionaries

        Returns:
            List of detected conflicts
        """
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting temporal conflicts in {len(entities)} entities",
        )

        try:
            conflicts = []

            # Temporal property patterns
            temporal_properties = [
                "founded",
                "founded_year",
                "established",
                "created",
                "timestamp",
                "date",
                "start_date",
                "end_date",
            ]

            # Group entities by ID
            entity_groups: Dict[str, List[Dict[str, Any]]] = {}
            total_entities = len(entities)
            if total_entities <= 10:
                update_interval = 1  # Update every item for small datasets
            else:
                update_interval = max(1, min(10, total_entities // 100))
            
            # Initial progress update
            remaining = total_entities
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_entities,
                message=f"Grouping entities... 0/{total_entities} (remaining: {remaining})"
            )

            for i, entity in enumerate(entities):
                entity_id = entity.get("id") or entity.get("entity_id")
                if not entity_id:
                    continue

                if entity_id not in entity_groups:
                    entity_groups[entity_id] = []
                entity_groups[entity_id].append(entity)
                
                remaining = total_entities - (i + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (i + 1) % update_interval == 0 or 
                    (i + 1) == total_entities or 
                    i == 0 or
                    total_entities <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=i + 1,
                        total=total_entities,
                        message=f"Grouping entities... {i + 1}/{total_entities} (remaining: {remaining})"
                    )

            # Check each entity group for temporal conflicts
            total_groups = len(entity_groups)
            if total_groups <= 10:
                group_update_interval = 1  # Update every item for small datasets
            else:
                group_update_interval = max(1, min(10, total_groups // 100))
            
            # Initial progress update for group checking
            remaining_groups = total_groups
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_groups,
                message=f"Checking entity groups for temporal conflicts... 0/{total_groups} (remaining: {remaining_groups})"
            )
            
            for j, (entity_id, entity_list) in enumerate(entity_groups.items()):
                if len(entity_list) < 2:
                    continue

                # Check each temporal property
                for prop_name in temporal_properties:
                    values = []
                    sources = []

                    for entity in entity_list:
                        if prop_name in entity:
                            value = entity[prop_name]
                            values.append(value)

                            if self.track_provenance:
                                source_ref = SourceReference(
                                    document=entity.get("source", "unknown"),
                                    page=entity.get("page"),
                                    section=entity.get("section"),
                                    confidence=entity.get("confidence", 1.0),
                                    metadata=entity.get("metadata", {}),
                                )
                                self.source_tracker.track_property_source(
                                    entity_id, prop_name, value, source_ref
                                )
                                sources.append(
                                    {
                                        "document": source_ref.document,
                                        "page": source_ref.page,
                                        "confidence": source_ref.confidence,
                                    }
                                )

                    # Check for temporal conflicts
                    if len(values) > 1:
                        # Normalize values for comparison
                        normalized_values = []
                        for v in values:
                            try:
                                # Try to convert to comparable format
                                if isinstance(v, str):
                                    # Try to extract year from string
                                    import re

                                    year_match = re.search(r"\b(19|20)\d{2}\b", v)
                                    if year_match:
                                        normalized_values.append(
                                            int(year_match.group())
                                        )
                                    else:
                                        normalized_values.append(v)
                                else:
                                    normalized_values.append(v)
                            except (ValueError, TypeError):
                                normalized_values.append(v)

                        unique_values = list(
                            set(str(v) for v in normalized_values if v is not None)
                        )

                        if len(unique_values) > 1:
                            conflict_id = f"{entity_id}_{prop_name}_temporal_conflict"
                            conflict = Conflict(
                                conflict_id=conflict_id,
                                conflict_type=ConflictType.TEMPORAL_CONFLICT,
                                entity_id=entity_id,
                                property_name=prop_name,
                                conflicting_values=values,
                                sources=sources,
                                confidence=self._calculate_conflict_confidence(
                                    values, sources
                                ),
                                severity=self._calculate_severity(prop_name, values),
                                recommended_action=(
                                    "Check temporal context and determine correct time "
                                    "period"
                                ),
                            )
                            conflicts.append(conflict)
                            self.detected_conflicts[conflict.conflict_id] = conflict

                            self.logger.warning(
                                f"Temporal conflict detected: {entity_id}.{prop_name} "
                                f"has conflicting values: {unique_values}"
                            )
                
                remaining_groups = total_groups - (j + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (j + 1) % group_update_interval == 0 or 
                    (j + 1) == total_groups or 
                    j == 0 or
                    total_groups <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=j + 1,
                        total=total_groups,
                        message=f"Checking entity groups for temporal conflicts... {j + 1}/{total_groups} (remaining: {remaining_groups})"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(conflicts)} temporal conflicts",
            )
            return conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def detect_logical_conflicts(
        self, entities: List[Dict[str, Any]]
    ) -> List[Conflict]:
        """
        Detect logical conflicts (e.g., Person cannot be Organization).

        Args:
            entities: List of entity dictionaries

        Returns:
            List of detected conflicts
        """
        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting logical conflicts in {len(entities)} entities",
        )

        try:
            conflicts = []

            # Logical rules: incompatible type combinations
            incompatible_types = {
                "Person": ["Organization", "Company", "Institution"],
                "Organization": ["Person"],
                "Company": ["Person"],
                "Location": ["Person", "Organization"],
            }

            # Group entities by ID
            entity_groups: Dict[str, List[Dict[str, Any]]] = {}
            total_entities = len(entities)
            if total_entities <= 10:
                update_interval = 1  # Update every item for small datasets
            else:
                update_interval = max(1, min(10, total_entities // 100))
            
            # Initial progress update
            remaining = total_entities
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_entities,
                message=f"Grouping entities... 0/{total_entities} (remaining: {remaining})"
            )

            for i, entity in enumerate(entities):
                entity_id = entity.get("id") or entity.get("entity_id")
                if not entity_id:
                    continue

                if entity_id not in entity_groups:
                    entity_groups[entity_id] = []
                entity_groups[entity_id].append(entity)
                
                remaining = total_entities - (i + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (i + 1) % update_interval == 0 or 
                    (i + 1) == total_entities or 
                    i == 0 or
                    total_entities <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=i + 1,
                        total=total_entities,
                        message=f"Grouping entities... {i + 1}/{total_entities} (remaining: {remaining})"
                    )

            # Check each entity group for logical conflicts
            total_groups = len(entity_groups)
            if total_groups <= 10:
                group_update_interval = 1  # Update every item for small datasets
            else:
                group_update_interval = max(1, min(10, total_groups // 100))
            
            # Initial progress update for group checking
            remaining_groups = total_groups
            self.progress_tracker.update_progress(
                tracking_id,
                processed=0,
                total=total_groups,
                message=f"Checking entity groups for logical conflicts... 0/{total_groups} (remaining: {remaining_groups})"
            )
            
            for j, (entity_id, entity_list) in enumerate(entity_groups.items()):
                if len(entity_list) < 2:
                    continue

                types = []
                sources = []

                for entity in entity_list:
                    entity_type = entity.get("type") or entity.get("entity_type")
                    if entity_type:
                        types.append(entity_type)

                        if self.track_provenance:
                            source_ref = SourceReference(
                                document=entity.get("source", "unknown"),
                                page=entity.get("page"),
                                section=entity.get("section"),
                                confidence=entity.get("confidence", 1.0),
                                metadata=entity.get("metadata", {}),
                            )
                            sources.append(
                                {
                                    "document": source_ref.document,
                                    "page": source_ref.page,
                                    "confidence": source_ref.confidence,
                                }
                            )

                # Check for logical conflicts
                if len(types) > 1:
                    for i, type1 in enumerate(types):
                        for type2 in types[i + 1 :]:
                            type1_str = str(type1)
                            type2_str = str(type2)

                            # Check if types are incompatible
                            if type1_str in incompatible_types:
                                if type2_str in incompatible_types[type1_str]:
                                    conflict = Conflict(
                                        conflict_id=f"{entity_id}_logical_conflict",
                                        conflict_type=ConflictType.LOGICAL_CONFLICT,
                                        entity_id=entity_id,
                                        property_name="type",
                                        conflicting_values=[type1, type2],
                                        sources=sources,
                                        confidence=1.0,
                                        severity="critical",
                                        recommended_action=(
                                            f"Entity cannot be both {type1_str} and "
                                            f"{type2_str}. Review classification."
                                        ),
                                    )
                                    conflicts.append(conflict)
                                    self.detected_conflicts[
                                        conflict.conflict_id
                                    ] = conflict

                                    self.logger.warning(
                                        f"Logical conflict: {entity_id} cannot be both "
                                        f"{type1_str} and {type2_str}"
                                    )
                                    break
                
                remaining_groups = total_groups - (j + 1)
                # Update progress: always update for small datasets, or at intervals for large ones
                should_update = (
                    (j + 1) % group_update_interval == 0 or 
                    (j + 1) == total_groups or 
                    j == 0 or
                    total_groups <= 10  # Always update for small datasets
                )
                if should_update:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=j + 1,
                        total=total_groups,
                        message=f"Checking entity groups for logical conflicts... {j + 1}/{total_groups} (remaining: {remaining_groups})"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(conflicts)} logical conflicts",
            )
            return conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def detect_conflicts(
        self,
        entities: Union[List[Dict[str, Any]], Dict[str, Any]],
        method: str = "all",
        property_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        **kwargs,
    ) -> List[Conflict]:
        """
        Detect conflicts using the specified method.

        Args:
            entities: List of entity dictionaries or Graph dictionary
            method: Detection method — "all" (default), "value", "property", "type",
                    "relationship", "temporal", "logical", or "entity"
            property_name: Property name required for ``method="value"`` and ``method="property"``
            entity_type: Optional entity type filter
            **kwargs: Extra arguments forwarded to the underlying method
                      (e.g. ``relationships=`` for ``method="relationship"``)

        Returns:
            List of detected conflicts
        """
        # Handle graph dictionary input
        if isinstance(entities, dict):
            if "entities" in entities:
                entities = entities["entities"]
            else:
                # If it's a single entity dict, wrap in list
                entities = [entities]

        # Dispatch to a specific sub-method when one is requested
        if method == "value":
            if not property_name:
                raise ValueError("property_name is required for method='value'")
            return self.detect_value_conflicts(entities, property_name, entity_type)
        elif method == "property":
            if not property_name:
                raise ValueError("property_name is required for method='property'")
            return self.detect_property_conflicts(entities, property_name)
        elif method == "type":
            return self.detect_type_conflicts(entities)
        elif method == "relationship":
            relationships = kwargs.get("relationships", [])
            if isinstance(relationships, dict):
                inner = relationships.get("relationships", relationships)
                relationships = inner if isinstance(inner, list) else [inner]
            if not isinstance(relationships, list):
                relationships = [relationships]
            return self.detect_relationship_conflicts(relationships)
        elif method == "temporal":
            return self.detect_temporal_conflicts(entities)
        elif method == "logical":
            return self.detect_logical_conflicts(entities)
        elif method == "entity":
            return self.detect_entity_conflicts(entities, entity_type)
        elif method != "all":
            raise ValueError(f"Unknown conflict detection method: {method!r}")

        tracking_id = self.progress_tracker.start_tracking(
            file=None,
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Detecting all conflicts in {len(entities)} entities",
        )

        try:
            all_conflicts = []

            # Filter by entity type if specified
            filtered_entities = entities
            if entity_type:
                filtered_entities = [
                    e
                    for e in entities
                    if (e.get("type") or e.get("entity_type")) == entity_type
                ]

            # Track overall progress across multiple detection methods
            detection_steps = []
            
            # Detect value conflicts (for common properties)
            if self.conflict_fields:
                for entity_type_key, fields in self.conflict_fields.items():
                    if not entity_type or entity_type_key == entity_type:
                        for field_name in fields:
                            detection_steps.append(("value", field_name))
            else:
                detection_steps.append(("entity_wide", None))

            # Add other detection steps
            detection_steps.extend([
                ("type", None),
                ("temporal", None),
                ("logical", None)
            ])

            total_steps = len(detection_steps)
            update_interval = max(1, total_steps // 10)  # Update every 10%

            for step_idx, (step_type, step_param) in enumerate(detection_steps):
                if step_type == "value":
                    conflicts = self.detect_value_conflicts(
                        filtered_entities, step_param, entity_type
                    )
                    all_conflicts.extend(conflicts)
                elif step_type == "entity_wide":
                    conflicts = self.detect_entity_conflicts(filtered_entities, entity_type)
                    all_conflicts.extend(conflicts)
                elif step_type == "type":
                    conflicts = self.detect_type_conflicts(filtered_entities)
                    all_conflicts.extend(conflicts)
                elif step_type == "temporal":
                    conflicts = self.detect_temporal_conflicts(filtered_entities)
                    all_conflicts.extend(conflicts)
                elif step_type == "logical":
                    conflicts = self.detect_logical_conflicts(filtered_entities)
                    all_conflicts.extend(conflicts)
                
                # Update progress periodically
                if (step_idx + 1) % update_interval == 0 or (step_idx + 1) == total_steps:
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=step_idx + 1,
                        total=total_steps,
                        message=f"Detecting conflicts... {step_idx + 1}/{total_steps} steps completed"
                    )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Detected {len(all_conflicts)} total conflicts",
            )
            return all_conflicts

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def resolve_conflicts(self, conflicts: List[Conflict]) -> Dict[str, int]:
        """
        Attempt to resolve conflicts based on configuration.

        Args:
            conflicts: List of conflicts to resolve

        Returns:
            Dictionary with resolution statistics
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="conflicts",
            submodule="ConflictDetector",
            message=f"Resolving {len(conflicts)} conflicts",
        )

        resolved_count = 0
        unresolved_count = 0
        
        total_conflicts = len(conflicts)
        if total_conflicts <= 10:
            update_interval = 1  # Update every item for small datasets
        else:
            update_interval = max(1, min(10, total_conflicts // 100))
        
        # Initial progress update
        remaining = total_conflicts
        self.progress_tracker.update_progress(
            tracking_id,
            processed=0,
            total=total_conflicts,
            message=f"Resolving conflicts... 0/{total_conflicts} (remaining: {remaining})"
        )

        for i, conflict in enumerate(conflicts):
            if self.auto_resolve:
                # Simple resolution logic: pick value with highest confidence
                # This is a placeholder for more complex logic
                if conflict.conflicting_values:
                    # Mark as resolved (in a real system we would update the entity)
                    resolved_count += 1
                else:
                    unresolved_count += 1
            else:
                unresolved_count += 1
            
            remaining = total_conflicts - (i + 1)
            # Update progress: always update for small datasets, or at intervals for large ones
            should_update = (
                (i + 1) % update_interval == 0 or 
                (i + 1) == total_conflicts or 
                i == 0 or
                total_conflicts <= 10  # Always update for small datasets
            )
            if should_update:
                self.progress_tracker.update_progress(
                    tracking_id,
                    processed=i + 1,
                    total=total_conflicts,
                    message=f"Resolving conflicts... {i + 1}/{total_conflicts} (remaining: {remaining})"
                )

        self.progress_tracker.stop_tracking(
            tracking_id,
            status="completed",
            message=f"Resolved {resolved_count} conflicts",
        )

        return {
            "resolved_count": resolved_count,
            "unresolved_count": unresolved_count,
            "total_conflicts": len(conflicts),
        }

    def clear_conflicts(self) -> None:
        """Clear all detected conflicts."""
        self.detected_conflicts.clear()
        self.logger.info("Cleared all detected conflicts")
