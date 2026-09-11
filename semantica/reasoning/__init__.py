"""
Reasoning Module

This module provides reasoning and inference capabilities for knowledge graph
analysis and query answering, supporting multiple reasoning strategies including
rule-based inference via Rete, SPARQL reasoning, abductive and deductive reasoning,
and native Datalog evaluation.
"""

from .datalog_reasoner import DatalogFact, DatalogReasoner, DatalogRule
from .explanation_generator import (
    Explanation,
    ExplanationGenerator,
    Justification,
    ReasoningPath,
    ReasoningStep,
)
from .graph_reasoner import GraphReasoner
from .reasoner import (
    Action,
    AssertAction,
    CallAction,
    EmitEventAction,
    Fact,
    InferenceResult,
    Reasoner,
    RetractAction,
    Rule,
    RuleType,
)
from .rete_engine import (
    AlphaNode,
    BetaNode,
    Match,
    ReteEngine,
    ReteNode,
    TerminalNode,
)
from .sparql_reasoner import SPARQLQueryResult, SPARQLReasoner
from .temporal_reasoning import (
    IntervalRelation,
    TemporalInterval,
    TemporalReasoningEngine,
)
from .truth_maintenance import TruthMaintenanceSession
from .truth_maintenance_types import (
    Derivation,
    FactExplanation,
    FactSupport,
    MaintenanceDelta,
    TruthMaintenanceSnapshot,
)

__all__ = [
    # Reasoner facade
    "Reasoner",
    "GraphReasoner",
    "InferenceResult",
    "Rule",
    "Fact",
    "RuleType",
    # Rule-driven actions
    "Action",
    "AssertAction",
    "RetractAction",
    "CallAction",
    "EmitEventAction",
    # Rete engine
    "ReteEngine",
    "ReteNode",
    "AlphaNode",
    "BetaNode",
    "TerminalNode",
    "Match",
    # SPARQL reasoning
    "SPARQLReasoner",
    "SPARQLQueryResult",
    # Datalog reasoning
    "DatalogReasoner",
    "DatalogFact",
    "DatalogRule",
    "TemporalInterval",
    "IntervalRelation",
    "TemporalReasoningEngine",
    # Truth maintenance
    "TruthMaintenanceSession",
    "FactSupport",
    "Derivation",
    "FactExplanation",
    "MaintenanceDelta",
    "TruthMaintenanceSnapshot",
    # Explanation
    "ExplanationGenerator",
    "Explanation",
    "ReasoningStep",
    "ReasoningPath",
    "Justification",
]
