"""
Explanation Generator Module

This module provides explanation generation for reasoning results and inference
chains, creating human-readable justifications and reasoning paths.

Key Features:
    - Explanation generation for reasoning results
    - Reasoning path visualization
    - Justification creation
    - Step-by-step reasoning breakdown
    - Human-readable explanations
    - Evidence tracking

Main Classes:
    - ExplanationGenerator: Explanation generation engine
    - Explanation: Dataclass for explanations
    - ReasoningStep: Dataclass for single reasoning steps
    - ReasoningPath: Dataclass for reasoning path visualization
    - Justification: Dataclass for justifications

Example Usage:
    >>> from semantica.reasoning import (
    ...     ExplanationGenerator, InferenceResult, Rule
    ... )
    >>> generator = ExplanationGenerator()
    >>> rule = Rule("r1", "mortality", ["Human(?x)"], "Mortal(?x)")
    >>> inference = InferenceResult(
    ...     "Mortal(Socrates)", rule, ["Human(Socrates)"]
    ... )
    >>> explanation = generator.generate_explanation(inference)
    >>> path = generator.show_reasoning_path(inference)
    >>> justification = generator.justify_conclusion(
    ...     inference.conclusion, path
    ... )

Author: Semantica Contributors
License: MIT
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .reasoner import InferenceResult, Rule
from .deductive_reasoner import Proof
from .abductive_reasoner import Explanation as AbductiveExplanation


@dataclass
class ReasoningStep:
    """Single reasoning step."""

    step_id: str
    description: str
    rule_applied: Optional[Rule] = None
    input_facts: List[Any] = field(default_factory=list)
    output_fact: Any = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningPath:
    """Reasoning path visualization."""

    path_id: str
    steps: List[ReasoningStep] = field(default_factory=list)
    start_facts: List[Any] = field(default_factory=list)
    end_conclusion: Any = None
    total_confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Justification:
    """Justification for conclusion."""

    justification_id: str
    conclusion: Any
    reasoning_path: ReasoningPath
    supporting_evidence: List[Any] = field(default_factory=list)
    confidence: float = 1.0
    explanation_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Explanation:
    """Reasoning explanation."""

    explanation_id: str
    explanation_type: str
    conclusion: Any
    reasoning_path: Optional[ReasoningPath] = None
    justification: Optional[Justification] = None
    natural_language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExplanationGenerator:
    """
    Explanation generation system.

    • Explanation generation for reasoning results
    • Inference chain visualization
    • Natural language explanation
    • Performance optimization
    • Error handling and recovery
    • Advanced explanation techniques
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize explanation generator.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options:
                - generate_nl: Generate natural language explanations
                - detail_level: Detail level (simple, detailed, verbose)
        """
        self.logger = get_logger("explanation_generator")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.generate_nl = self.config.get("generate_nl", True)
        self.detail_level = self.config.get("detail_level", "detailed")

    def generate_explanation(self, reasoning: Any, **options) -> Explanation:
        """
        Generate reasoning explanation.

        Args:
            reasoning: Reasoning result (InferenceResult, Proof, etc.)
            **options: Additional options

        Returns:
            Generated explanation
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="reasoning",
            submodule="ExplanationGenerator",
            message="Generating explanation for reasoning result",
        )

        try:
            self.progress_tracker.update_tracking(
                tracking_id, message="Identifying reasoning type..."
            )
            if isinstance(reasoning, InferenceResult):
                self.progress_tracker.update_tracking(
                    tracking_id,
                    message="Generating explanation for inference result...",
                )
                result = self._explain_inference_result(reasoning, **options)
            elif isinstance(reasoning, Proof):
                self.progress_tracker.update_tracking(
                    tracking_id, message="Generating explanation for proof..."
                )
                result = self._explain_proof(reasoning, **options)
            elif isinstance(reasoning, AbductiveExplanation):
                self.progress_tracker.update_tracking(
                    tracking_id,
                    message="Generating explanation for abductive explanation...",
                )
                result = self._explain_abductive(reasoning, **options)
            else:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Generating generic explanation..."
                )
                result = self._explain_generic(reasoning, **options)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Generated explanation: {result.explanation_type}",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _explain_inference_result(
        self, result: InferenceResult, **options
    ) -> Explanation:
        """Generate explanation for inference result."""
        # Build reasoning path
        reasoning_path = ReasoningPath(
            path_id=f"path_{result.conclusion}",
            steps=[
                ReasoningStep(
                    step_id=f"step_{i}",
                    description=f"Premise: {premise}",
                    input_facts=[premise],
                    metadata={},
                )
                for i, premise in enumerate(result.premises)
            ],
            start_facts=result.premises,
            end_conclusion=result.conclusion,
            total_confidence=result.confidence,
        )

        # Add rule step if available
        if result.rule_used:
            reasoning_path.steps.append(
                ReasoningStep(
                    step_id="rule_step",
                    description=f"Applied rule: {result.rule_used.name}",
                    rule_applied=result.rule_used,
                    input_facts=result.premises,
                    output_fact=result.conclusion,
                    confidence=result.confidence,
                    metadata={"rule_id": result.rule_used.rule_id},
                )
            )

        # Generate natural language
        nl_text = (
            self._generate_natural_language(result, reasoning_path)
            if self.generate_nl
            else ""
        )

        return Explanation(
            explanation_id=f"exp_{result.conclusion}",
            explanation_type="inference",
            conclusion=result.conclusion,
            reasoning_path=reasoning_path,
            natural_language=nl_text,
            metadata={},
        )

    def _explain_proof(self, proof: Proof, **options) -> Explanation:
        """Generate explanation for proof."""
        # Build reasoning path from proof steps
        reasoning_path = ReasoningPath(
            path_id=f"path_{proof.proof_id}",
            steps=[
                ReasoningStep(
                    step_id=f"step_{i}",
                    description=f"Proof step: {step.statement}",
                    rule_applied=step.rule_applied,
                    input_facts=[p.statement for p in step.premises],
                    output_fact=step.statement,
                    confidence=step.confidence,
                    metadata={"proof_step": i},
                )
                for i, step in enumerate(proof.steps)
            ],
            start_facts=[p.statement for p in proof.premises],
            end_conclusion=proof.theorem,
            total_confidence=1.0 if proof.valid else 0.0,
        )

        # Generate natural language
        nl_text = (
            self._generate_natural_language_from_proof(proof)
            if self.generate_nl
            else ""
        )

        return Explanation(
            explanation_id=f"exp_{proof.proof_id}",
            explanation_type="proof",
            conclusion=proof.theorem,
            reasoning_path=reasoning_path,
            natural_language=nl_text,
            metadata={"valid": proof.valid},
        )

    def _explain_abductive(
        self, explanation: AbductiveExplanation, **options
    ) -> Explanation:
        """Generate explanation for abductive explanation."""
        # Build reasoning path from hypotheses
        reasoning_path = ReasoningPath(
            path_id=f"path_{explanation.explanation_id}",
            steps=[
                ReasoningStep(
                    step_id=f"step_{i}",
                    description=f"Hypothesis: {hyp.explanation}",
                    input_facts=hyp.premises,
                    output_fact=hyp.explanation,
                    confidence=hyp.confidence,
                    metadata={"hypothesis_id": hyp.hypothesis_id},
                )
                for i, hyp in enumerate(explanation.hypotheses)
            ],
            start_facts=explanation.observation.facts,
            end_conclusion=explanation.best_hypothesis.explanation
            if explanation.best_hypothesis
            else None,
            total_confidence=explanation.confidence,
        )

        # Generate natural language
        nl_text = (
            self._generate_natural_language_from_abductive(explanation)
            if self.generate_nl
            else ""
        )

        return Explanation(
            explanation_id=f"exp_{explanation.explanation_id}",
            explanation_type="abductive",
            conclusion=explanation.best_hypothesis.explanation
            if explanation.best_hypothesis
            else None,
            reasoning_path=reasoning_path,
            natural_language=nl_text,
            metadata={},
        )

    def _explain_generic(self, reasoning: Any, **options) -> Explanation:
        """Generate generic explanation."""
        return Explanation(
            explanation_id="exp_generic",
            explanation_type="generic",
            conclusion=reasoning,
            natural_language=str(reasoning),
            metadata={},
        )

    def show_reasoning_path(self, reasoning: Any, **options) -> ReasoningPath:
        """
        Show reasoning path.

        Args:
            reasoning: Reasoning result
            **options: Additional options

        Returns:
            Reasoning path
        """
        explanation = self.generate_explanation(reasoning, **options)
        return explanation.reasoning_path or ReasoningPath(path_id="empty", steps=[])

    def justify_conclusion(
        self, conclusion: Any, reasoning_path: ReasoningPath, **options
    ) -> Justification:
        """
        Justify reasoning conclusion.

        Args:
            conclusion: Conclusion to justify
            reasoning_path: Reasoning path
            **options: Additional options

        Returns:
            Justification
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="reasoning",
            submodule="ExplanationGenerator",
            message=f"Justifying conclusion: {conclusion}",
        )

        try:
            # Collect supporting evidence
            self.progress_tracker.update_tracking(
                tracking_id, message="Collecting supporting evidence..."
            )
            supporting_evidence = []
            for step in reasoning_path.steps:
                supporting_evidence.extend(step.input_facts)

            # Calculate confidence
            self.progress_tracker.update_tracking(
                tracking_id, message="Calculating confidence..."
            )
            confidence = reasoning_path.total_confidence

            # Generate explanation text
            self.progress_tracker.update_tracking(
                tracking_id, message="Generating explanation text..."
            )
            explanation_text = (
                self._generate_justification_text(conclusion, reasoning_path)
                if self.generate_nl
                else ""
            )

            result = Justification(
                justification_id=f"just_{conclusion}",
                conclusion=conclusion,
                reasoning_path=reasoning_path,
                supporting_evidence=supporting_evidence,
                confidence=confidence,
                explanation_text=explanation_text,
                metadata={},
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Justified conclusion with {len(supporting_evidence)} pieces of evidence",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _generate_natural_language(
        self, result: InferenceResult, path: ReasoningPath
    ) -> str:
        """Generate natural language explanation."""
        if self.detail_level == "simple":
            return f"Based on {len(result.premises)} premises, we conclude: {result.conclusion}"
        elif self.detail_level == "detailed":
            premises_str = ", ".join(str(p) for p in result.premises)
            rule_str = (
                f" using rule '{result.rule_used.name}'" if result.rule_used else ""
            )
            return f"Given the premises: {premises_str}, we conclude: {result.conclusion}{rule_str}."
        else:  # verbose
            premises_str = " and ".join(str(p) for p in result.premises)
            rule_str = (
                f" Applying the rule '{result.rule_used.name}'"
                if result.rule_used
                else ""
            )
            return f"From the premises that {premises_str},{rule_str} we can infer: {result.conclusion}. This inference has a confidence of {result.confidence:.2f}."

    def _generate_natural_language_from_proof(self, proof: Proof) -> str:
        """Generate natural language from proof."""
        if proof.valid:
            return f"Proof of '{proof.theorem}' is valid with {len(proof.steps)} steps."
        else:
            return f"Could not prove '{proof.theorem}'."

    def _generate_natural_language_from_abductive(
        self, explanation: AbductiveExplanation
    ) -> str:
        """Generate natural language from abductive explanation."""
        if explanation.best_hypothesis:
            return f"The best explanation for the observation is: {explanation.best_hypothesis.explanation} (confidence: {explanation.confidence:.2f})"
        else:
            return "No explanation found for the observation."

    def _generate_justification_text(self, conclusion: Any, path: ReasoningPath) -> str:
        """Generate justification text."""
        if self.detail_level == "simple":
            return f"Conclusion '{conclusion}' is justified by {len(path.steps)} reasoning steps."
        else:
            steps_desc = " -> ".join(step.description for step in path.steps)
            return f"Conclusion '{conclusion}' is justified by the following reasoning path: {steps_desc}."
