"""
Change Log Module

This module provides standardized metadata structures for version changes
across both ontology and knowledge graph versioning systems.

Key Features:
    - Standardized ChangeLogEntry dataclass
    - Email validation for authors
    - Timestamp handling in ISO 8601 format
    - Optional change linking and tracking

Main Classes:
    - ChangeLogEntry: Standard metadata for version changes

Example Usage:
    >>> from semantica.common.change_log import ChangeLogEntry
    >>> entry = ChangeLogEntry(
    ...     timestamp="2024-01-15T10:30:00Z",
    ...     author="alice@company.com",
    ...     description="Added Customer entity"
    ... )

Author: Semantica Contributors
License: MIT
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any, Dict, Tuple, Union, Set
from enum import Enum

from ..utils.exceptions import ValidationError


@dataclass
class ChangeLogEntry:
    """
    Standard metadata for version changes.
    
    This dataclass provides a consistent structure for tracking changes
    across both ontology and knowledge graph versioning systems.
    
    Attributes:
        timestamp: ISO 8601 timestamp of the change
        author: Email address of the change author
        description: Description of the change (max 500 characters)
        change_id: Optional unique identifier for the change
        related_changes: Optional list of related change IDs
    """
    
    timestamp: str
    author: str
    description: str
    change_id: Optional[str] = None
    related_changes: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate fields after initialization."""
        self._validate_timestamp()
        self._validate_author()
        self._validate_description()
    
    def _validate_timestamp(self):
        """Validate timestamp is in ISO 8601 format."""
        try:
            # More strict validation for ISO 8601 format
            if 'T' not in self.timestamp:
                raise ValueError("Missing 'T' separator")
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError(f"Invalid timestamp format: {self.timestamp}. Expected ISO 8601 format.")
    
    def _validate_author(self):
        """Validate author is a valid email address."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.author):
            raise ValidationError(f"Invalid email format: {self.author}")
    
    def _validate_description(self):
        """Validate description length."""
        if len(self.description) > 500:
            raise ValidationError(f"Description too long: {len(self.description)} characters (max 500)")
        if not self.description.strip():
            raise ValidationError("Description cannot be empty")
    
    @classmethod
    def create_now(cls, author: str, description: str, change_id: Optional[str] = None, 
                   related_changes: Optional[List[str]] = None) -> 'ChangeLogEntry':
        """
        Create a ChangeLogEntry with current timestamp.
        
        Args:
            author: Email address of the change author
            description: Description of the change
            change_id: Optional unique identifier for the change
            related_changes: Optional list of related change IDs
            
        Returns:
            ChangeLogEntry with current timestamp
        """
        return cls(
            timestamp=datetime.now().isoformat(),
            author=author,
            description=description,
            change_id=change_id,
            related_changes=related_changes or []
        )
        
class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    
class ChangeCategory(Enum):
    BREAKING = "breaking"
    POTENTIALLY_BREAKING = "potentially_breaking"
    NON_BREAKING = "non_breaking"
    UNKNOWN = "unknown"
    
@dataclass
class ImpactReport:
    """ Structured impact analysis report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    summary: Dict[str, Any] = field(default_factory=dict)
    breaking_changes: List[Dict[str, Any]] = field(default_factory=list)
    potentially_breaking: List[Dict[str, Any]] = field(default_factory=list)
    safe_changes: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "summary": self.summary,
            "impact_classification": {
                "breaking": self.breaking_changes,
                "potentially_breaking": self.potentially_breaking,
                "safe": self.safe_changes
            },
            "recommendations": self.recommendations
        }

class ChangeLogAnalyzer:
    """
    Analyzes ontology diffs and classifies impact severity.
    """
    
    VALIDITY_CONSTRAINTS = {'domain', 'range', 'cardinality', 'max_cardinality'}
    STRUCTURAL_FIELDS = {'subclasses', 'superclasses', 'equivalent_to', 'disjoint_with'}
    
    def analyze(self, diff: Dict[str, Any]) -> ImpactReport:
        report = ImpactReport()
        if not diff:
            report.summary = {"error": "Empty diff provided"}
            return report

        all_changes = []

        for key, entity_type, change_type in [
            ("added_classes", "class", "added"), ("added_properties", "property", "added"),
            ("removed_classes", "class", "removed"), ("removed_properties", "property", "removed"),
            ("changed_classes", "class", "modified"), ("changed_properties", "property", "modified")
        ]:
            for item in diff.get(key, []):
                all_changes.append({
                    "uri": item.get("uri", item.get("name", "unknown")),
                    "entity_type": entity_type,
                    "change_type": change_type,
                    "changes": item.get("changes", {})
                })

        report.summary = {"total_changes": len(all_changes)}

        for change in all_changes:
            severity, category, description, mitigation = self._classify_change(change)
            entry = {
                "entity_uri": change['uri'],
                "entity_type": change['entity_type'],
                "change_type": change['change_type'],
                "description": description,
                "severity": severity.value,
                "mitigation": mitigation
            }

            if category == ChangeCategory.BREAKING:
                report.breaking_changes.append(entry)
            elif category == ChangeCategory.POTENTIALLY_BREAKING:
                report.potentially_breaking.append(entry)
            else:
                report.safe_changes.append(entry)

        self._generate_recommendations(report)
        return report
    
    
    def _classify_change(self, change: Dict[str, Any]) -> Tuple[Severity, ChangeCategory, str, str]:
        change_type = change.get('change_type')
        entity_type = change.get('entity_type')
        uri = change.get('uri')
        
        if change_type == 'removed':
            if entity_type == 'class':
                return (Severity.CRITICAL, ChangeCategory.BREAKING, f"Class {uri} removed.", "Migrate orphaned instances.")
            return (Severity.CRITICAL, ChangeCategory.BREAKING, f"Property {uri} removed.", "Migrate property values.")
        
        if change_type == 'added':
            return (Severity.INFO, ChangeCategory.NON_BREAKING, f"New {entity_type} {uri} added.", "No action required.")
        
        if change_type == 'modified':
            return self._analyze_field_changes(uri, change.get('changes', {}))
        
        return (Severity.LOW, ChangeCategory.UNKNOWN, f"Unknown change for {uri}", "Manual review required.")
    
    def _analyze_field_changes(self, uri: str, field_changes: Dict[str, Any]) -> Tuple[Severity, ChangeCategory, str, str]:
        has_restriction = False
        has_structural = False

        for field, vals in field_changes.items():
            if field in self.VALIDITY_CONSTRAINTS:
                old_val, new_val = vals.get("old"), vals.get("new")

                if old_val is None or new_val is None:
                    has_restriction = True
                    continue

                # if new constraint is smaller, it is a restriction
                old_set = set(old_val) if isinstance(old_val, list) else {old_val}
                new_set = set(new_val) if isinstance(new_val, list) else {new_val}

                if new_set < old_set:
                    has_restriction = True

            elif field in self.STRUCTURAL_FIELDS:
                has_structural = True
        
        if has_restriction:
            return (Severity.HIGH, ChangeCategory.BREAKING, f"Domain/range restricted on {uri}", "Validate existing data against new constraints.")
        if has_structural:
            return (Severity.MEDIUM, ChangeCategory.POTENTIALLY_BREAKING, f"Hierarchy modified for {uri}", "Check dependent reasoning chains.")
        
        return (Severity.LOW, ChangeCategory.NON_BREAKING, f"Safe annotations updated for {uri}", "No action required.")
    
    def _generate_recommendations(self, report: ImpactReport) -> None:
        if report.breaking_changes:
            report.recommendations.append("[BREAKING] Schedule downtime or validate existing data.")
        if report.potentially_breaking:
            report.recommendations.append("[WARNING] Run full regression tests on queries.")
        if not report.breaking_changes and not report.potentially_breaking:
            report.recommendations.append("[SAFE] Minor version bump sufficient.")


def generate_change_report(diff: Dict[str, Any]) -> Dict[str, Any]:
    """Public API for generating impact reports from diffs."""
    analyzer = ChangeLogAnalyzer()
    return analyzer.analyze(diff).to_dict()
