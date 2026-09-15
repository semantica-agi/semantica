"""Internal validation and parsing helpers for truth maintenance.

Grammar::

    identifier := [A-Za-z_][A-Za-z0-9_]*
    variable   := '?' identifier
    constant   := [A-Za-z0-9_][A-Za-z0-9_./:#-]*
    atom       := identifier '(' [term (',' term)*] ')'

Whitespace between tokens is normalized to the canonical form ``P(a, b)``.
Everything in this module is pure: it neither touches session state nor
invokes the rule matcher.
"""

import re
from collections.abc import Iterable
from typing import Dict, List, Optional, Set, Tuple

from semantica.utils.exceptions import ValidationError

from .reasoner import Rule, RuleType
from .truth_maintenance_types import _RuleSnapshot

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_VARIABLE = r"\?" + _IDENTIFIER
_CONSTANT = r"[A-Za-z0-9_][A-Za-z0-9_./:#-]*"

_ATOM_RE = re.compile(
    r"^(?P<predicate>" + _IDENTIFIER + r")\s*\((?P<args>.*)\)$",
    re.DOTALL,
)
_TERM_RE = re.compile(r"^(" + _VARIABLE + r"|" + _CONSTANT + r")$")
_VARIABLE_RE = re.compile(r"^" + _VARIABLE + r"$")


def _fail(message: str, **details: object) -> ValidationError:
    return ValidationError(message, validation_context=dict(details))


def parse_atom(text: object) -> Tuple[str, Tuple[str, ...]]:
    """Parse and normalize an atom string.

    Returns ``(predicate, terms)`` where each term is a variable (leading
    ``?``) or a constant.  Raises ``ValidationError`` on any syntax error.
    """
    if not isinstance(text, str):
        raise _fail("atom must be a string", atom=repr(text))
    stripped = text.strip()
    match = _ATOM_RE.match(stripped)
    if match is None:
        raise _fail("atom must look like P(a, b)", atom=text)
    predicate = match.group("predicate")
    raw_args = match.group("args").strip()
    terms: List[str] = []
    if raw_args:
        for raw_term in raw_args.split(","):
            term = raw_term.strip()
            if not _TERM_RE.match(term):
                raise _fail(
                    "atom argument must be a variable or constant",
                    atom=text,
                    argument=raw_term.strip(),
                )
            terms.append(term)
    return predicate, tuple(terms)


def normalize_atom(text: object) -> str:
    """Return the canonical whitespace-normalized form of an atom."""
    predicate, terms = parse_atom(text)
    return canonical_atom(predicate, terms)


def canonical_atom(predicate: str, terms: Iterable[str]) -> str:
    return predicate + "(" + ", ".join(terms) + ")"


def _is_variable(term: str) -> bool:
    return _VARIABLE_RE.match(term) is not None


def validate_fact_text(text: object) -> str:
    """Validate a fact atom: constant arguments only. Returns canonical form."""
    predicate, terms = parse_atom(text)
    for term in terms:
        if _is_variable(term):
            raise _fail(
                "fact arguments must be constants, not variables",
                fact=text,
            )
    return canonical_atom(predicate, terms)


def _validate_rule_shape(rule: object, index: int) -> Tuple[str, List[str], str]:
    if not isinstance(rule, Rule):
        raise _fail("rules must be Rule instances", index=index, rule=repr(rule))
    rule_id = rule.rule_id
    if not isinstance(rule_id, str) or not rule_id:
        raise _fail("rule_id must be a non-empty string", rule=repr(rule_id))
    if rule.rule_type != RuleType.IMPLICATION:
        raise _fail(
            "truth maintenance supports IMPLICATION rules only",
            rule_id=rule_id,
            rule_type=str(rule.rule_type),
        )
    confidence = rule.confidence
    if isinstance(confidence, bool) or confidence != 1.0:
        raise _fail(
            "truth maintenance requires deterministic rules with confidence 1.0",
            rule_id=rule_id,
            confidence=repr(confidence),
        )
    if rule.handler is not None:
        raise _fail("rules with handlers are not supported", rule_id=rule_id)
    if rule.actions:
        raise _fail("rules with actions are not supported", rule_id=rule_id)
    conditions = rule.conditions
    if not isinstance(conditions, (list, tuple)) or not conditions:
        raise _fail(
            "rule must have a non-empty list of conditions",
            rule_id=rule_id,
        )
    condition_texts: List[str] = []
    for condition in conditions:
        if not isinstance(condition, str):
            raise _fail(
                "rule conditions must be atom strings",
                rule_id=rule_id,
                condition=repr(condition),
            )
        parse_atom(condition)  # syntax check
        condition_texts.append(normalize_atom(condition))
    conclusion = rule.conclusion
    if not isinstance(conclusion, str):
        raise _fail(
            "rule conclusion must be an atom string",
            rule_id=rule_id,
            conclusion=repr(conclusion),
        )
    return rule_id, condition_texts, conclusion


def build_rule_snapshots(rules: Iterable[Rule]) -> Tuple[List[_RuleSnapshot], Dict[str, int]]:
    """Validate rules and return ordered snapshots plus the arity registry.

    The returned snapshots are sorted by (topological depth of the head
    predicate, rule_id) so incremental re-evaluation can process them in a
    single pass.
    """
    seen_rule_ids: Set[str] = set()
    arities: Dict[str, int] = {}
    entries: List[dict] = []
    predicate_graph: Dict[str, Set[str]] = {}
    predicate_depth: Dict[str, int] = {}

    def register_arity(predicate: str, arity: int, where: str, rule_id: str) -> None:
        existing = arities.get(predicate)
        if existing is not None and existing != arity:
            raise _fail(
                "predicate arity conflict",
                predicate=predicate,
                existing_arity=existing,
                conflicting_arity=arity,
                location=where,
                rule_id=rule_id,
            )
        arities[predicate] = arity

    for index, rule in enumerate(rules):
        rule_id, condition_texts, conclusion = _validate_rule_shape(rule, index)
        if rule_id in seen_rule_ids:
            raise _fail("duplicate rule_id", rule_id=rule_id)
        seen_rule_ids.add(rule_id)

        parsed_conditions = [parse_atom(text) for text in condition_texts]
        parsed_conclusion = parse_atom(conclusion)
        head_predicate, head_terms = parsed_conclusion

        body_variables: Set[str] = set()
        for predicate, terms in parsed_conditions:
            register_arity(predicate, len(terms), "condition", rule_id)
            body_variables.update(term for term in terms if _is_variable(term))
        register_arity(head_predicate, len(head_terms), "conclusion", rule_id)
        head_variables = {term for term in head_terms if _is_variable(term)}
        unbound = head_variables - body_variables
        if unbound:
            raise _fail(
                "conclusion variables must be bound by the rule body",
                rule_id=rule_id,
                unbound_variables=sorted(unbound),
            )

        body_predicates = {predicate for predicate, _ in parsed_conditions}
        if head_predicate in body_predicates:
            raise _fail(
                "predicate dependency cycles are not supported "
                "(a rule head must not appear in its own body)",
                rule_id=rule_id,
                predicate=head_predicate,
            )
        predicate_graph.setdefault(head_predicate, set()).update(body_predicates)
        for predicate in body_predicates | {head_predicate}:
            predicate_depth.setdefault(predicate, 0)

        entries.append(
            {
                "rule_id": rule_id,
                "conditions": tuple(condition_texts),
                "conclusion": normalize_atom(conclusion),
                "parsed_conditions": tuple(parsed_conditions),
                "parsed_conclusion": parsed_conclusion,
                "head_variables": frozenset(head_variables),
                "body_variables": frozenset(body_variables),
                "body_predicates": body_predicates,
            }
        )

    _assign_depths(predicate_graph, predicate_depth)

    snapshots: List[_RuleSnapshot] = []
    for entry in entries:
        head_predicate = entry["parsed_conclusion"][0]
        snapshots.append(
            _RuleSnapshot(
                rule_id=entry["rule_id"],
                conditions=entry["conditions"],
                conclusion=entry["conclusion"],
                parsed_conditions=entry["parsed_conditions"],
                parsed_conclusion=entry["parsed_conclusion"],
                head_variables=entry["head_variables"],
                body_variables=entry["body_variables"],
                order=(predicate_depth[head_predicate], entry["rule_id"]),
            )
        )
    snapshots.sort(key=lambda snapshot: snapshot.order)
    return snapshots, arities


def _assign_depths(
    predicate_graph: Dict[str, Set[str]], predicate_depth: Dict[str, int]
) -> None:
    """Compute topological depth per predicate, rejecting cycles."""
    resolved: Dict[str, Optional[int]] = {}
    for predicate in predicate_depth:
        resolved[predicate] = None
    for predicate in predicate_depth:
        _visit(predicate, predicate_graph, resolved, [])
    for predicate, depth in resolved.items():
        predicate_depth[predicate] = depth  # type: ignore[assignment]


def _visit(
    predicate: str,
    predicate_graph: Dict[str, Set[str]],
    resolved: Dict[str, Optional[int]],
    stack: List[str],
) -> int:
    if predicate in stack:
        cycle = stack[stack.index(predicate):] + [predicate]
        raise _fail(
            "predicate dependency cycles are not supported",
            cycle=" -> ".join(cycle),
        )
    already = resolved.get(predicate)
    if already is not None:
        return already
    stack.append(predicate)
    depth = 0
    for dependency in sorted(predicate_graph.get(predicate, ())):
        depth = max(depth, _visit(dependency, predicate_graph, resolved, stack) + 1)
    stack.pop()
    resolved[predicate] = depth
    return depth