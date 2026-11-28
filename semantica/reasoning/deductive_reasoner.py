"""
Deductive Reasoner Module

This module provides deductive reasoning capabilities for logical inference
and proof generation, supporting formal logic and theorem proving.

Key Features:
    - Deductive reasoning for logical inference
    - Proof generation and validation
    - Premise and conclusion management
    - Logical argument construction
    - Theorem proving
    - Confidence calculation

Main Classes:
    - DeductiveReasoner: Deductive reasoning engine
    - Premise: Dataclass for logical premises
    - Conclusion: Dataclass for logical conclusions
    - Proof: Dataclass for logical proofs
    - Argument: Dataclass for logical arguments

Example Usage:
    Inference rules live on the wrapped ``Reasoner``, which is what
    ``apply_logic`` reads; premises are matched against rule conditions, so
    they use the same pattern form rather than prose:

    >>> from semantica.reasoning import DeductiveReasoner, Premise, Rule
    >>> reasoner = DeductiveReasoner()
    >>> rule = reasoner.reasoner.add_rule(
    ...     Rule("r1", "mortality", ["Human(?x)"], "Mortal(?x)")
    ... )
    >>> premises = [Premise("p1", "Human(Socrates)")]
    >>> conclusions = reasoner.apply_logic(premises)
    >>> proof = reasoner.prove_theorem("Mortal(Socrates)")

Author: Semantica Contributors
License: MIT
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import re

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .reasoner import Rule, Reasoner


@dataclass
class Premise:
    """Logical premise."""

    premise_id: str
    statement: Any
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conclusion:
    """Logical conclusion."""

    conclusion_id: str
    statement: Any
    premises: List[Premise] = field(default_factory=list)
    rule_applied: Optional[Rule] = None
    confidence: float = 1.0
    proof_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Proof:
    """Logical proof."""

    proof_id: str
    theorem: Any
    premises: List[Premise] = field(default_factory=list)
    steps: List[Conclusion] = field(default_factory=list)
    valid: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Argument:
    """Logical argument."""

    argument_id: str
    premises: List[Premise] = field(default_factory=list)
    conclusion: Conclusion = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeductiveReasoner:
    """
    Deductive reasoning engine.

    • Deductive reasoning algorithms
    • Logical inference and proof generation
    • Rule application and validation
    • Performance optimization
    • Error handling and recovery
    • Advanced deductive techniques
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize deductive reasoner.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options
        """
        self.logger = get_logger("deductive_reasoner")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.reasoner = Reasoner(**self.config)
        self.known_facts: Set[Any] = set()

    def apply_logic(self, premises: List[Premise], **options) -> List[Conclusion]:
        """
        Apply logical inference rules to premises.

        Args:
            premises: List of premises
            **options: Additional options

        Returns:
            List of conclusions
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="reasoning",
            submodule="DeductiveReasoner",
            message=f"Applying logic to {len(premises)} premises",
        )

        try:
            conclusions = []

            # Add premises to known facts
            self.progress_tracker.update_tracking(
                tracking_id, message="Adding premises to knowledge base..."
            )
            for premise in premises:
                self.known_facts.add(premise.statement)

            # Apply inference rules
            self.progress_tracker.update_tracking(
                tracking_id, message="Applying inference rules..."
            )
            rules = self.reasoner.rules

            for rule in rules:
                # Find all matches (bindings) for the rule
                matches = self._find_matches(rule.conditions, {})
                
                for bindings in matches:
                    conclusion = self._apply_rule_to_premises(rule, premises, bindings)
                    if conclusion:
                        # Check if conclusion is new (not in known facts)
                        if conclusion.statement not in self.known_facts:
                            conclusions.append(conclusion)
                            self.known_facts.add(conclusion.statement)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Applied logic: {len(conclusions)} conclusions from {len(premises)} premises",
            )
            return conclusions

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _parse_predicate(self, text: str) -> tuple[str, List[str]]:
        """Parse 'Predicate(arg1, arg2)' into ('Predicate', ['arg1', 'arg2'])."""
        if not isinstance(text, str):
            return text, []
        match = re.match(r"(\w+)\((.+)\)", text)
        if not match:
            return text, []
        predicate = match.group(1)
        args = [arg.strip() for arg in match.group(2).split(",")]
        return predicate, args

    def _unify(self, condition: str, fact: str, bindings: Dict[str, str]) -> Optional[Dict[str, str]]:
        """
        Try to unify a condition (with vars) against a fact.
        Returns new bindings if successful, None otherwise.
        """
        if condition == fact:
            return bindings
            
        cond_pred, cond_args = self._parse_predicate(condition)
        fact_pred, fact_args = self._parse_predicate(fact)
        
        if cond_pred != fact_pred:
            return None
        if len(cond_args) != len(fact_args):
            return None
            
        new_bindings = bindings.copy()
        for c_arg, f_arg in zip(cond_args, fact_args):
            if c_arg.startswith("?"):
                if c_arg in new_bindings:
                    if new_bindings[c_arg] != f_arg:
                        return None # Conflict
                else:
                    new_bindings[c_arg] = f_arg
            else:
                if c_arg != f_arg:
                    return None # Constant mismatch
        return new_bindings

    def _substitute_bindings(self, text: str, bindings: Dict[str, str]) -> str:
        """Substitute variables in text with bindings."""
        if not isinstance(text, str):
            return text
        pred, args = self._parse_predicate(text)
        if not args:
            return text
            
        new_args = []
        for arg in args:
            if arg in bindings:
                new_args.append(bindings[arg])
            else:
                new_args.append(arg)
        
        return f"{pred}({', '.join(new_args)})"

    def _find_matches(self, conditions: List[str], bindings: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Recursively find all bindings that satisfy the conditions.
        """
        if not conditions:
            return [bindings]
            
        first = conditions[0]
        # Substitute current bindings into first condition before matching
        first_substituted = self._substitute_bindings(first, bindings)
        rest = conditions[1:]
        
        valid_bindings = []
        
        # Try to match 'first' against all known facts
        for fact in self.known_facts:
            # Skip if fact is not a string (unhashable/objects) for now
            if not isinstance(fact, str):
                continue
                
            unified = self._unify(first_substituted, fact, bindings)
            if unified is not None:
                # Recursive step
                results = self._find_matches(rest, unified)
                valid_bindings.extend(results)
                
        return valid_bindings

    def _apply_rule_to_premises(
        self, rule: Rule, premises: List[Premise], bindings: Dict[str, str]
    ) -> Optional[Conclusion]:
        """Apply rule to premises and generate conclusion."""
        # Find matching premises (those that support the bindings)
        # This is a bit approximate, ideally we track which premise supported which condition
        matching_premises = []
        
        # Instantiate conclusion
        conclusion_stmt = rule.conclusion
        if bindings:
            conclusion_stmt = self._substitute_bindings(conclusion_stmt, bindings)
        
        # Find premises that match the conditions (instantiated)
        for cond in rule.conditions:
            instantiated = self._substitute_bindings(cond, bindings)
            for p in premises:
                if p.statement == instantiated:
                    matching_premises.append(p)
                    break
            # Note: some conditions might be matched by self.known_facts which are not in 'premises' arg
            # but are in self.known_facts. 
            # If a premise is not in the passed list but in known_facts, we can't add it to matching_premises list 
            # unless we find the Premise object. 
            # But known_facts stores strings. 
            # So matching_premises might be incomplete if we rely on known_facts.
            # However, for this method signature, we return a Conclusion with premises.
        
        conclusion = Conclusion(
            conclusion_id=f"conc_{rule.name}_{len(matching_premises)}",
            statement=conclusion_stmt,
            premises=matching_premises,
            rule_applied=rule,
            confidence=rule.confidence,
            proof_steps=[f"Applied rule: {rule.name} with bindings {bindings}"],
            metadata={"rule_id": rule.rule_id, "bindings": bindings},
        )

        return conclusion

    def prove_theorem(self, theorem: Any, **options) -> Optional[Proof]:
        """
        Prove logical theorem.

        Args:
            theorem: Theorem to prove
            **options: Additional options

        Returns:
            Proof or None
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="reasoning",
            submodule="DeductiveReasoner",
            message=f"Proving theorem: {theorem}",
        )

        try:
            # Start with empty proof
            self.progress_tracker.update_tracking(
                tracking_id, message="Initializing proof..."
            )
            proof = Proof(
                proof_id=f"proof_{theorem}",
                theorem=theorem,
                premises=[],
                steps=[],
                valid=False,
            )

            # Try to prove using backward chaining
            self.progress_tracker.update_tracking(
                tracking_id, message="Attempting backward chaining proof..."
            )
            conclusion = self._prove_backward(theorem, proof, **options)

            if conclusion:
                proof.steps.append(conclusion)
                proof.valid = True
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Successfully proved theorem: {theorem}",
                )
            else:
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Could not prove theorem: {theorem}",
                )

            return proof

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def _prove_backward(
        self, goal: Any, proof: Proof, depth: int = 0, max_depth: int = 10, **options
    ) -> Optional[Conclusion]:
        """Prove goal using backward chaining."""
        if depth > max_depth:
            return None

        # Check if goal is already known
        # Try direct match
        if goal in self.known_facts:
            return Conclusion(
                conclusion_id=f"known_{goal}",
                statement=goal,
                confidence=1.0,
                proof_steps=["Known fact"],
            )
        
        # Try unification with known facts
        if isinstance(goal, str) and "?" in goal:
            for fact in self.known_facts:
                if isinstance(fact, str):
                    if self._unify(goal, fact, {}) is not None:
                         return Conclusion(
                            conclusion_id=f"known_{fact}",
                            statement=fact,
                            confidence=1.0,
                            proof_steps=[f"Known fact (matched pattern {goal})"],
                        )

        # Find rules that can prove goal
        rules = self.reasoner.rules
        
        # Use unified matching for finding applicable rules
        applicable_rules_and_bindings = []
        for r in rules:
            bindings = self._unify(r.conclusion, goal, {})
            if bindings is not None:
                applicable_rules_and_bindings.append((r, bindings))

        for rule, initial_bindings in applicable_rules_and_bindings:
            # Try to prove all premises
            premise_conclusions = []
            all_proven = True
            current_bindings = initial_bindings.copy()

            for condition in rule.conditions:
                # Instantiate condition with current bindings
                instantiated_cond = self._substitute_bindings(condition, current_bindings)
                
                premise_conclusion = self._prove_backward(
                    instantiated_cond, proof, depth + 1, max_depth, **options
                )
                if premise_conclusion:
                    premise_conclusions.append(premise_conclusion)
                    # Update bindings if we proved something more specific
                    new_bindings = self._unify(instantiated_cond, premise_conclusion.statement, current_bindings)
                    if new_bindings:
                        current_bindings = new_bindings
                else:
                    all_proven = False
                    break

            if all_proven:
                # All premises proven, rule can fire
                # Instantiate conclusion with final bindings
                final_conclusion = self._substitute_bindings(rule.conclusion, current_bindings)
                
                conclusion = Conclusion(
                    conclusion_id=f"conc_{goal}",
                    statement=final_conclusion,
                    premises=[p for p in premise_conclusions], # Use actual premises found
                    rule_applied=rule,
                    confidence=rule.confidence,
                    proof_steps=[f"Proved using rule: {rule.name} with bindings {current_bindings}"],
                    metadata={"rule_id": rule.rule_id, "bindings": current_bindings}
                )
                return conclusion

        return None

    def validate_argument(self, argument: Argument, **options) -> Dict[str, Any]:
        """
        Validate logical argument.

        Args:
            argument: Argument to validate
            **options: Additional options

        Returns:
            Validation result
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="reasoning",
            submodule="DeductiveReasoner",
            message=f"Validating argument: {argument.argument_id}",
        )

        try:
            errors = []
            warnings = []

            # Check if premises are valid
            self.progress_tracker.update_tracking(
                tracking_id, message="Validating premises..."
            )
            for premise in argument.premises:
                if premise.statement not in self.known_facts:
                    warnings.append(
                        f"Premise '{premise.statement}' not in knowledge base"
                    )

            # Try to prove conclusion from premises
            self.progress_tracker.update_tracking(
                tracking_id, message="Applying logic to premises..."
            )
            conclusions = self.apply_logic(argument.premises, **options)

            valid = False
            if argument.conclusion:
                # Check if conclusion follows from premises
                self.progress_tracker.update_tracking(
                    tracking_id,
                    message="Checking if conclusion follows from premises...",
                )
                for conclusion in conclusions:
                    if conclusion.statement == argument.conclusion.statement:
                        valid = True
                        break

            result = {
                "valid": valid,
                "errors": errors,
                "warnings": warnings,
                "conclusions": conclusions,
                "argument_id": argument.argument_id,
            }

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Argument validation complete: {'Valid' if valid else 'Invalid'} ({len(warnings)} warnings)",
            )
            return result

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def add_fact(self, fact: Any) -> None:
        """Add fact to knowledge base."""
        self.known_facts.add(fact)

    def add_facts(self, facts: List[Any]) -> None:
        """Add multiple facts."""
        for fact in facts:
            self.add_fact(fact)

    def clear_facts(self) -> None:
        """Clear knowledge base."""
        self.known_facts.clear()
