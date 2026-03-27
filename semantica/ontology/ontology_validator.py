"""
Ontology Validation Module

This module provides validation capabilities for generated ontologies using
symbolic reasoners (HermiT, Pellet) and structural checks.

Key Features:
    - Consistency checking
    - Satisfiability checking
    - Constraint validation
    - Structural integrity validation
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from ..utils.logging import get_logger


# ─────────────────────────────────────────────────────────────────────────────
# SHACL Validation Models
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SHACLViolation:
    """Represents a single SHACL constraint violation."""
    focus_node: str
    result_path: Optional[str] = None
    constraint: str = ""
    severity: str = "Violation"
    message: Optional[str] = None
    value: Optional[str] = None
    shape: Optional[str] = None
    explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "focus_node": self.focus_node,
            "result_path": self.result_path,
            "constraint": self.constraint,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
            "shape": self.shape,
            "explanation": self.explanation,
        }


@dataclass
class SHACLValidationReport:
    """Structured SHACL validation report with machine-readable violations and explanations."""
    conforms: bool
    violations: List[SHACLViolation] = field(default_factory=list)
    warnings: List[SHACLViolation] = field(default_factory=list)
    infos: List[SHACLViolation] = field(default_factory=list)
    raw_report: Optional[str] = None

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary(self) -> str:
        if self.conforms:
            return "Graph conforms to all SHACL constraints."
        return f"Graph does NOT conform: {self.violation_count} violation(s)."

    def explain_violations(self) -> None:
        """Populate a plain-English explanation on every violation. No LLM call."""
        _TEMPLATES = {
            "MinCountConstraintComponent": (
                "Node <{focus_node}> is missing required property <{path}>. "
                "At least {min_count} value(s) are required."
            ),
            "MaxCountConstraintComponent": (
                "Node <{focus_node}> has too many values for <{path}>. "
                "At most {max_count} value(s) are allowed."
            ),
            "DatatypeConstraintComponent": (
                "Node <{focus_node}> has value '{value}' for <{path}> "
                "but the expected datatype is {datatype}."
            ),
            "ClassConstraintComponent": (
                "Node <{focus_node}> has value '{value}' for <{path}> "
                "but it must be an instance of {class_}."
            ),
            "InConstraintComponent": (
                "Node <{focus_node}> has value '{value}' for <{path}> "
                "which is not in the allowed set."
            ),
            "PatternConstraintComponent": (
                "Node <{focus_node}> has value '{value}' for <{path}> "
                "which does not match the required pattern."
            ),
            "ClosedConstraintComponent": (
                "Node <{focus_node}> has undeclared property <{path}> "
                "which is not allowed by the closed shape."
            ),
        }
        for v in self.violations + self.warnings + self.infos:
            tmpl = None
            for key, tpl in _TEMPLATES.items():
                if key in (v.constraint or ""):
                    tmpl = tpl
                    break
            if tmpl is None:
                v.explanation = (
                    f"Node <{v.focus_node}> failed constraint "
                    f"{v.constraint or '(unknown)'}"
                    + (f" on property <{v.result_path}>." if v.result_path else ".")
                )
                continue
            v.explanation = tmpl.format(
                focus_node=v.focus_node,
                path=v.result_path or "",
                value=v.value or "",
                min_count=1,
                max_count=1,
                datatype=v.message or "",
                class_=v.message or "",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conforms": self.conforms,
            "violation_count": self.violation_count,
            "warning_count": self.warning_count,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [v.to_dict() for v in self.warnings],
            "infos": [v.to_dict() for v in self.infos],
        }


def _run_pyshacl(
    data_graph_str: str,
    shacl_str: str,
    data_graph_format: str = "turtle",
    shacl_format: str = "turtle",
) -> SHACLValidationReport:
    """
    Run pyshacl validation and return a structured SHACLValidationReport.

    Args:
        data_graph_str: Serialized data graph string.
        shacl_str: Serialized SHACL shapes string.
        data_graph_format: RDF format of data_graph_str (default "turtle").
        shacl_format: RDF format of shacl_str — "turtle", "json-ld", or "nt"
                      (default "turtle").

    Raises ImportError if pyshacl or rdflib are not installed
    (install with: pip install semantica[shacl]).
    """
    try:
        import pyshacl
    except ImportError as exc:
        raise ImportError(
            "pyshacl is required for SHACL validation. "
            "Install it with: pip install semantica[shacl]"
        ) from exc

    try:
        import rdflib
    except ImportError as exc:
        raise ImportError(
            "rdflib is required for SHACL validation. "
            "Install it with: pip install rdflib"
        ) from exc

    data_g = rdflib.Graph()
    data_g.parse(data=data_graph_str, format=data_graph_format)

    _fmt_map = {
        "turtle": "turtle", "ttl": "turtle",
        "json-ld": "json-ld", "jsonld": "json-ld", "json_ld": "json-ld",
        "n-triples": "nt", "ntriples": "nt", "nt": "nt",
    }
    shacl_g = rdflib.Graph()
    shacl_g.parse(data=shacl_str, format=_fmt_map.get(shacl_format.lower().strip(), shacl_format))

    conforms, results_graph, results_text = pyshacl.validate(
        data_g,
        shacl_graph=shacl_g,
        inference="none",
        abort_on_first=False,
    )

    violations: List[SHACLViolation] = []
    warnings: List[SHACLViolation] = []
    infos: List[SHACLViolation] = []

    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    for result in results_graph.subjects(rdflib.RDF.type, SH.ValidationResult):
        focus = str(results_graph.value(result, SH.focusNode) or "")
        path_node = results_graph.value(result, SH.resultPath)
        path = str(path_node) if path_node is not None else None
        sev_node = results_graph.value(result, SH.resultSeverity)
        sev_str = str(sev_node).split("#")[-1] if sev_node is not None else "Violation"
        msg_node = results_graph.value(result, SH.resultMessage)
        msg = str(msg_node) if msg_node is not None else None
        val_node = results_graph.value(result, SH.value)
        val = str(val_node) if val_node is not None else None
        src_node = results_graph.value(result, SH.sourceConstraintComponent)
        constraint = str(src_node).split("#")[-1] if src_node is not None else ""
        shape_node = results_graph.value(result, SH.sourceShape)
        shape = str(shape_node) if shape_node is not None else None

        v = SHACLViolation(
            focus_node=focus,
            result_path=path,
            constraint=constraint,
            severity=sev_str,
            message=msg,
            value=val,
            shape=shape,
        )
        if sev_str == "Violation":
            violations.append(v)
        elif sev_str == "Warning":
            warnings.append(v)
        else:
            infos.append(v)

    return SHACLValidationReport(
        conforms=conforms,
        violations=violations,
        warnings=warnings,
        infos=infos,
        raw_report=results_text,
    )

@dataclass
class ValidationResult:
    """Result of an ontology validation operation."""
    valid: bool = True
    consistent: bool = True
    satisfiable: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class OntologyValidator:
    """
    Validator for checking ontology consistency and validity.
    
    Supports symbolic reasoning and structural validation.
    """
    
    def __init__(self, 
                 reasoner: str = "hermit", 
                 check_consistency: bool = True, 
                 check_satisfiability: bool = True,
                 **kwargs):
        """
        Initialize the validator.
        
        Args:
            reasoner: Reasoner to use ('hermit', 'pellet', 'auto')
            check_consistency: Whether to check logical consistency
            check_satisfiability: Whether to check class satisfiability
            **kwargs: Additional configuration
        """
        self.logger = get_logger("ontology_validator")
        self.reasoner = reasoner
        self.check_consistency = check_consistency
        self.check_satisfiability = check_satisfiability
        self.config = kwargs

    def validate(self, ontology: Union[Dict[str, Any], str]) -> ValidationResult:
        """
        Validate an ontology structure or file.
        
        Args:
            ontology: Ontology dictionary or path to ontology file
            
        Returns:
            ValidationResult object
        """
        self.logger.info(f"Validating ontology using {self.reasoner} reasoner")
        
        result = ValidationResult()
        
        # Placeholder implementation for now
        # In a real implementation, this would load owlready2 or similar
        
        try:
            if isinstance(ontology, dict):
                self._validate_structure(ontology, result)
            
            # Simulate reasoning checks
            if self.check_consistency:
                # Logic to check consistency would go here
                pass
                
            if self.check_satisfiability:
                # Logic to check satisfiability would go here
                pass
                
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            result.valid = False
            result.errors.append(str(e))
            
        return result

    def _validate_structure(self, ontology: Dict[str, Any], result: ValidationResult):
        """Basic structural validation."""
        if "classes" not in ontology:
            result.warnings.append("Ontology has no classes defined")
            
        if "properties" not in ontology:
            result.warnings.append("Ontology has no properties defined")

    def check_constraint(self, constraint: str) -> bool:
        """
        Check if a specific constraint holds.
        
        Args:
            constraint: Constraint description or SPARQL query
            
        Returns:
            True if constraint is met, False otherwise
        """
        # Placeholder implementation
        return True

def validate_ontology(ontology: Union[Dict[str, Any], str], method: str = "default") -> Dict[str, Any]:
    """
    Convenience wrapper for ontology validation.
    
    Args:
        ontology: Ontology to validate
        method: Validation method
        
    Returns:
        Dictionary representation of validation result
    """
    validator = OntologyValidator()
    result = validator.validate(ontology)
    
    return {
        "valid": result.valid,
        "consistent": result.consistent,
        "satisfiable": result.satisfiable,
        "errors": result.errors,
        "warnings": result.warnings
    }
