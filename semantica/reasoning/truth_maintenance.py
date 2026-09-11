"""Source-support based truth maintenance session.

Implements the maintenance contract::

    session.facts == closure(fixed_rules, facts_with_remaining_external_support)

Public API is :class:`TruthMaintenanceSession`, created with a fixed rule set
and updated through :meth:`TruthMaintenanceSession.apply` batches of
assertions/retractions of :class:`FactSupport` entries.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Dict, FrozenSet, List, Set, Tuple

from ..utils.exceptions import ProcessingError, ValidationError
from ._truth_maintenance_validation import (
    _RuleSnapshot,
    build_rule_snapshots,
    canonical_atom,
    parse_atom,
    validate_fact_text,
)
from .reasoner import Rule
from .truth_maintenance_types import (
    Derivation,
    FactExplanation,
    FactSupport,
    MaintenanceDelta,
    TruthMaintenanceSnapshot,
)

__all__ = ["TruthMaintenanceSession"]


DerivationKey = Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...]]


def _variable(term: str) -> bool:
    return term.startswith("?")


class _SessionState:
    """Mutable working state; cloned per apply() batch for atomic commits."""

    __slots__ = (
        "active_facts",
        "active_supports",
        "arities",
        "derivations",
        "derivations_by_conclusion",
        "derivations_by_rule",
        "facts_by_pred",
        "support_catalog",
        "supports_by_fact",
    )

    def __init__(self) -> None:
        self.support_catalog: Dict[str, str] = {}
        self.active_supports: Dict[str, FactSupport] = {}
        self.supports_by_fact: Dict[str, Set[str]] = {}
        self.active_facts: Set[str] = set()
        self.facts_by_pred: Dict[str, Set[str]] = {}
        self.derivations: Dict[DerivationKey, Derivation] = {}
        self.derivations_by_rule: Dict[str, Set[DerivationKey]] = {}
        self.derivations_by_conclusion: Dict[str, Set[DerivationKey]] = {}
        self.arities: Dict[str, int] = {}

    def clone(self) -> _SessionState:
        clone = _SessionState()
        clone.support_catalog = dict(self.support_catalog)
        clone.active_supports = dict(self.active_supports)
        clone.supports_by_fact = {
            fact: set(ids) for fact, ids in self.supports_by_fact.items()
        }
        clone.active_facts = set(self.active_facts)
        clone.facts_by_pred = {
            pred: set(facts) for pred, facts in self.facts_by_pred.items()
        }
        clone.derivations = dict(self.derivations)
        clone.derivations_by_rule = {
            rid: set(keys) for rid, keys in self.derivations_by_rule.items()
        }
        clone.derivations_by_conclusion = {
            fact: set(keys) for fact, keys in self.derivations_by_conclusion.items()
        }
        clone.arities = dict(self.arities)
        return clone

    # -- fact helpers -------------------------------------------------

    def add_fact(self, fact: str, affected: Set[str]) -> None:
        self.active_facts.add(fact)
        predicate, _terms = parse_atom(fact)
        self.facts_by_pred.setdefault(predicate, set()).add(fact)
        affected.add(predicate)

    def remove_fact(self, fact: str, affected: Set[str]) -> None:
        self.active_facts.discard(fact)
        predicate, _terms = parse_atom(fact)
        bucket = self.facts_by_pred.get(predicate)
        if bucket is not None:
            bucket.discard(fact)
            if not bucket:
                del self.facts_by_pred[predicate]
        affected.add(predicate)

    def has_active_fact(self, fact: str) -> bool:
        return fact in self.active_facts

    def has_support(self, fact: str) -> bool:
        return bool(self.supports_by_fact.get(fact))

    def has_derivation(self, fact: str) -> bool:
        return bool(self.derivations_by_conclusion.get(fact))

    # -- derivation helpers --------------------------------------------

    def add_derivation(self, derivation: Derivation) -> None:
        key: DerivationKey = (
            derivation.rule_id,
            derivation.premises,
            derivation.bindings,
        )
        self.derivations[key] = derivation
        self.derivations_by_rule.setdefault(derivation.rule_id, set()).add(key)
        self.derivations_by_conclusion.setdefault(
            derivation.conclusion, set()
        ).add(key)

    def remove_rule_derivations(self, rule_id: str) -> Set[str]:
        """Drop every derivation of ``rule_id``; return affected conclusions."""
        conclusions: Set[str] = set()
        for key in list(self.derivations_by_rule.get(rule_id, ())):
            derivation = self.derivations.pop(key)
            self.derivations_by_rule[rule_id].discard(key)
            bucket = self.derivations_by_conclusion.get(derivation.conclusion)
            if bucket is not None:
                bucket.discard(key)
                if not bucket:
                    del self.derivations_by_conclusion[derivation.conclusion]
            conclusions.add(derivation.conclusion)
        if not self.derivations_by_rule.get(rule_id):
            self.derivations_by_rule.pop(rule_id, None)
        return conclusions


class TruthMaintenanceSession:
    """Maintains facts as the closure of fixed rules over externally supported facts.

    Rules are snapshotted at construction time; later mutation of the original
    :class:`~semantica.reasoning.reasoner.Rule` objects does not affect the
    session. Updates are applied atomically: a failed batch leaves the
    session (including support-id assignments) untouched.
    """

    def __init__(self, *, rules: Iterable[Rule]) -> None:
        snapshots, arities = build_rule_snapshots(rules)
        self._rules: List[_RuleSnapshot] = snapshots
        self._state = _SessionState()
        self._state.arities = dict(arities)
        self._version = 0

    # -- read-only views -------------------------------------------------

    @property
    def facts(self) -> FrozenSet[str]:
        """Frozenset of all currently believed facts (explicit + derived)."""
        return frozenset(self._state.active_facts)

    @property
    def version(self) -> int:
        """Monotonic commit counter; unchanged for net-zero updates."""
        return self._version

    def snapshot(self) -> TruthMaintenanceSnapshot:
        """Return an immutable, detached view of the current committed state.

        The snapshot is a full copy: later ``apply`` batches never change an
        existing snapshot.  Reading it obeys the same caller-serialized
        access contract as the rest of the session API.
        """
        state = self._state
        return TruthMaintenanceSnapshot(
            version=self._version,
            facts=frozenset(state.active_facts),
            active_supports=tuple(
                sorted(
                    state.active_supports.values(),
                    key=lambda support: support.support_id,
                )
            ),
        )

    def explain(self, fact: str) -> FactExplanation:
        """Explain one fact: explicit supports plus retained derivations."""
        canonical = validate_fact_text(fact)
        state = self._state
        if canonical not in state.active_facts:
            return FactExplanation(canonical, False, (), ())
        support_ids = tuple(sorted(state.supports_by_fact.get(canonical, ())))
        derivations = sorted(
            (
                state.derivations[key]
                for key in state.derivations_by_conclusion.get(canonical, ())
            ),
            key=lambda item: (item.rule_id, item.premises, item.bindings),
        )
        return FactExplanation(canonical, True, support_ids, tuple(derivations))

    # -- batched updates --------------------------------------------------

    def apply(
        self,
        *,
        assertions: Iterable[FactSupport] = (),
        retractions: Iterable[str] = (),
    ) -> MaintenanceDelta:
        """Atomically apply one batch of assertions and retractions.

        Raises :class:`~semantica.utils.exceptions.ValidationError` for any
        malformed input without changing session state; wraps unexpected
        internal errors in :class:`~semantica.utils.exceptions.ProcessingError`.
        """
        try:
            assertion_items = _coerce_support_iterable(assertions)
            retraction_items = _coerce_id_iterable(retractions)
            effective_assertions, new_arities = self._validate_assertions(
                assertion_items, retraction_items
            )
        except ValidationError:
            raise
        except Exception as exc:  # unexpected input shaping failure
            raise ProcessingError(
                "truth maintenance batch validation failed",
                validation_context={},
            ) from exc

        # Deduplicate while preserving order: a support id listed twice in one
        # batch is one net retraction, not an error.
        effective_retractions = [
            rid
            for rid in dict.fromkeys(retraction_items)
            if rid in self._state.active_supports
        ]
        if not effective_assertions and not effective_retractions:
            return MaintenanceDelta(
                self._version, frozenset(), frozenset(), (), ()
            )

        try:
            candidate = self._state.clone()
            affected: Set[str] = set()
            self._remove_retracted(candidate, effective_retractions, affected)
            self._assert_supports(candidate, effective_assertions, affected)
            candidate.arities.update(new_arities)
            self._rematch_dirty_rules(candidate, affected)
        except Exception as exc:
            raise ProcessingError(
                "truth maintenance update failed",
                validation_context={"version": self._version},
            ) from exc

        return self._commit(candidate)

    # -- validation -------------------------------------------------------

    def _validate_assertions(
        self, assertion_items: List[FactSupport], retraction_items: List[str]
    ) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
        state = self._state
        batch_arities = dict(state.arities)
        seen: Dict[str, str] = {}
        effective: List[Tuple[str, str]] = []
        for support in assertion_items:
            if not isinstance(support, FactSupport):
                raise ValidationError(
                    "assertions must contain FactSupport instances",
                    validation_context={"item_type": type(support).__name__},
                )
            support_id = support.support_id
            if not isinstance(support_id, str) or not support_id:
                raise ValidationError(
                    "support_id must be a non-empty string",
                    validation_context={"support_id": repr(support_id)},
                )
            canonical = validate_fact_text(support.fact)
            predicate, terms = parse_atom(canonical)
            _check_arity(batch_arities, predicate, len(terms))
            previous = seen.get(support_id)
            if previous is not None:
                if previous != canonical:
                    raise ValidationError(
                        "support_id asserted twice with different facts in one batch",
                        validation_context={
                            "support_id": support_id,
                            "first_fact": previous,
                            "second_fact": canonical,
                        },
                    )
                continue
            seen[support_id] = canonical
            registered = state.support_catalog.get(support_id)
            if registered is not None and registered != canonical:
                raise ValidationError(
                    "support_id is permanently bound to a different fact",
                    validation_context={
                        "support_id": support_id,
                        "registered_fact": registered,
                        "requested_fact": canonical,
                    },
                )
            if support_id not in state.active_supports:
                effective.append((support_id, canonical))
        overlap = set(seen) & set(retraction_items)
        if overlap:
            raise ValidationError(
                "support_id appears in both assertions and retractions",
                validation_context={
                    "conflicting_ids": tuple(sorted(overlap)),
                },
            )
        # Predicates first observed in this batch: their arities must be
        # persisted with the commit, otherwise a later batch could re-assert
        # the same predicate with a different arity.
        new_arities = {
            predicate: arity
            for predicate, arity in batch_arities.items()
            if predicate not in state.arities
        }
        return effective, new_arities

    # -- staged mutation on the candidate state ----------------------------

    def _remove_retracted(
        self,
        candidate: _SessionState,
        retraction_ids: List[str],
        affected: Set[str],
    ) -> None:
        for support_id in retraction_ids:
            support = candidate.active_supports.pop(support_id)
            bucket = candidate.supports_by_fact.get(support.fact)
            if bucket is not None:
                bucket.discard(support_id)
                if not bucket:
                    del candidate.supports_by_fact[support.fact]
            if not candidate.has_support(support.fact) and not candidate.has_derivation(
                support.fact
            ):
                if candidate.has_active_fact(support.fact):
                    candidate.remove_fact(support.fact, affected)

    def _assert_supports(
        self,
        candidate: _SessionState,
        assertions: List[Tuple[str, str]],
        affected: Set[str],
    ) -> None:
        for support_id, canonical in assertions:
            candidate.support_catalog[support_id] = canonical
            candidate.active_supports[support_id] = FactSupport(support_id, canonical)
            candidate.supports_by_fact.setdefault(canonical, set()).add(support_id)
            if not candidate.has_active_fact(canonical):
                candidate.add_fact(canonical, affected)

    def _rematch_dirty_rules(
        self, candidate: _SessionState, affected: Set[str]
    ) -> None:
        # Single pass in topological rule order: rules are visited after all
        # rules that can produce their premises, so affected-set growth is
        # observed in time.
        for snapshot in self._rules:
            body_predicates = {predicate for predicate, _ in snapshot.parsed_conditions}
            if not body_predicates & affected:
                continue
            conclusions = candidate.remove_rule_derivations(snapshot.rule_id)
            for premises, bindings, conclusion in self._match_rule(
                snapshot, candidate
            ):
                candidate.add_derivation(
                    Derivation(snapshot.rule_id, conclusion, premises, bindings)
                )
                if not candidate.has_active_fact(conclusion):
                    candidate.add_fact(conclusion, affected)
            for conclusion in sorted(conclusions):
                if not candidate.has_active_fact(conclusion):
                    continue
                if candidate.has_support(conclusion) or candidate.has_derivation(
                    conclusion
                ):
                    continue
                candidate.remove_fact(conclusion, affected)

    def _match_rule(
        self, snapshot: _RuleSnapshot, facts: _SessionState
    ) -> List[Tuple[Tuple[str, ...], Tuple[Tuple[str, str], ...], str]]:
        """Matcher seam: single delegation point for rule snapshot matching.

        Delegates to the module-level ``_match_snapshot`` helper, which
        enumerates matches against the candidate state's predicate-indexed
        facts and filters facts whose term count differs from the pattern's
        (term-level arity check). It intentionally does not call
        ``_rule_matching.match_rule``: that helper matches against a flat
        fact iterable, and its regex-based matcher would accept cross-arity
        matches such as ``Q(?x)`` against ``Q(a, b)``. The two matchers are
        kept semantically aligned by the parity and differential tests.

        Exists to isolate matching responsibility and to give tests a
        fault-injection and call-counting site; not part of the public API.
        """
        return _match_snapshot(snapshot, facts)

    # -- commit -------------------------------------------------------------

    def _commit(self, candidate: _SessionState) -> MaintenanceDelta:
        state = self._state
        old_facts = frozenset(state.active_facts)
        new_facts = frozenset(candidate.active_facts)
        added_facts = frozenset(new_facts - old_facts)
        removed_facts = frozenset(old_facts - new_facts)
        added_supports = tuple(
            sorted(
                (
                    support
                    for support_id, support in candidate.active_supports.items()
                    if support_id not in state.active_supports
                ),
                key=lambda item: item.support_id,
            )
        )
        removed_supports = tuple(
            sorted(
                (
                    support
                    for support_id, support in state.active_supports.items()
                    if support_id not in candidate.active_supports
                ),
                key=lambda item: item.support_id,
            )
        )
        if not (
            added_facts
            or removed_facts
            or added_supports
            or removed_supports
        ):
            return MaintenanceDelta(
                self._version, frozenset(), frozenset(), (), ()
            )
        self._state = candidate
        self._version += 1
        return MaintenanceDelta(
            self._version,
            added_facts,
            removed_facts,
            added_supports,
            removed_supports,
        )


def _check_arity(arities: Dict[str, int], predicate: str, arity: int) -> None:
    registered = arities.get(predicate)
    if registered is None:
        arities[predicate] = arity
    elif registered != arity:
        raise ValidationError(
            "predicate arity conflict",
            validation_context={
                "predicate": predicate,
                "registered_arity": registered,
                "observed_arity": arity,
            },
        )


def _match_snapshot(
    snapshot: _RuleSnapshot, state: _SessionState
) -> List[Tuple[Tuple[str, ...], Tuple[Tuple[str, str], ...], str]]:
    """Enumerate all matches of a rule snapshot against active facts.

    Returns ``(premises, bindings, conclusion)`` tuples with premises in
    condition order and bindings sorted by variable name.
    """
    conditions = snapshot.parsed_conditions
    conclusion_predicate, conclusion_terms = snapshot.parsed_conclusion
    results: List[Tuple[Tuple[str, ...], Tuple[Tuple[str, str], ...], str]] = []

    def recurse(index: int, bindings: Dict[str, str], premises: List[str]) -> None:
        if index == len(conditions):
            substituted = tuple(
                bindings.get(term, term) for term in conclusion_terms
            )
            results.append(
                (
                    tuple(premises),
                    tuple(sorted(bindings.items())),
                    canonical_atom(conclusion_predicate, list(substituted)),
                )
            )
            return
        predicate, pattern_terms = conditions[index]
        for fact in sorted(state.facts_by_pred.get(predicate, ())):
            _pred, fact_terms = parse_atom(fact)
            if len(fact_terms) != len(pattern_terms):
                continue
            local = dict(bindings)
            consistent = True
            for pattern_term, fact_term in zip(pattern_terms, fact_terms):
                if _variable(pattern_term):
                    bound = local.get(pattern_term)
                    if bound is None:
                        local[pattern_term] = fact_term
                    elif bound != fact_term:
                        consistent = False
                        break
                elif pattern_term != fact_term:
                    consistent = False
                    break
            if consistent:
                recurse(index + 1, local, premises + [fact])

    recurse(0, {}, [])
    return results


def _coerce_support_iterable(value: object) -> List[FactSupport]:
    if isinstance(value, (str, bytes)):
        raise ValidationError(
            "assertions must be an iterable of FactSupport, not a string",
            validation_context={"received": repr(value)[:64]},
        )
    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValidationError(
            "assertions must be an iterable of FactSupport",
            validation_context={"received_type": type(value).__name__},
        ) from exc


def _coerce_id_iterable(value: object) -> List[str]:
    if isinstance(value, (str, bytes)):
        raise ValidationError(
            "retractions must be an iterable of support-id strings, not a string",
            validation_context={"received": repr(value)[:64]},
        )
    try:
        items = list(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValidationError(
            "retractions must be an iterable of support-id strings",
            validation_context={"received_type": type(value).__name__},
        ) from exc
    for item in items:
        if not isinstance(item, str) or not item:
            raise ValidationError(
                "retraction entries must be non-empty support-id strings",
                validation_context={"entry": repr(item)[:64]},
            )
    return items