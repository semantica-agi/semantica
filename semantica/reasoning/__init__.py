"""
Reasoning Module

This module provides reasoning and inference capabilities for knowledge graph
analysis and query answering, supporting multiple reasoning strategies including
rule-based inference via Rete, SPARQL reasoning, abductive and deductive reasoning,
and native Datalog evaluation.
"""

from .abductive_reasoner import (
    AbductiveReasoner,
    Hypothesis,
    HypothesisRanking,
    Observation,
)
from .abductive_reasoner import Explanation as AbductiveExplanation
from .datalog_reasoner import DatalogFact, DatalogReasoner, DatalogRule
from .deductive_reasoner import (
    Argument,
    Conclusion,
    DeductiveReasoner,
    Premise,
    Proof,
)
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
from .temporal_truth_maintenance import (
    TemporalFactSnapshot,
    TemporalTruthMaintenanceAdapter,
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
    # Temporal truth maintenance
    "TemporalTruthMaintenanceAdapter",
    "TemporalFactSnapshot",
    # Explanation
    "ExplanationGenerator",
    "Explanation",
    "ReasoningStep",
    "ReasoningPath",
    "Justification",
    # Deductive reasoning
    "DeductiveReasoner",
    "Premise",
    "Conclusion",
    "Proof",
    "Argument",
    # Abductive reasoning. Its Explanation is exported under an alias because
    # explanation_generator already owns the plain name; the same alias is
    # used inside explanation_generator.py.
    "AbductiveReasoner",
    "Observation",
    "Hypothesis",
    "HypothesisRanking",
    "AbductiveExplanation",
]
