"""Pure rule-matching helpers shared by the Reasoner and newer engines.

This module extracts the variable substitution and pattern matching logic
that used to live inside ``Reasoner`` so that other components (for example
the truth maintenance session) can reuse the exact same matching semantics
without instantiating a ``Reasoner`` (and therefore without inheriting its
actions, activation deduplication, or iteration limits).

The functions here are intentionally free of framework state: logging is
performed through an explicit ``logger`` argument, and rule evaluation takes
the facts and the substitution callables as arguments. Behavior is identical
to the previous in-class implementation.
"""

import re
from collections.abc import Iterable
from typing import Callable, Dict, List, Optional, Tuple

PatternMatcher = Callable[[str, str, Dict[str, str]], Optional[Dict[str, str]]]
Substituter = Callable[[str, Dict[str, str]], str]


def substitute_variables(template: str, bindings: Dict[str, str]) -> str:
    """Substitute ``?var`` placeholders with their bound values, token-aware.

    A naive ``str.replace(f"?{var}", value)`` corrupts placeholders that share
    a prefix -- e.g. binding ``?x`` would also rewrite the ``?x`` inside ``?xy``.
    We replace every ``?word`` token in a single regex pass so that only whole
    variable names are matched (``\\w+`` never partially matches a longer name),
    leaving unbound placeholders untouched.
    """
    if not bindings:
        return template

    def _replace(match: "re.Match") -> str:
        var_name = match.group(1)
        # Preserve unbound placeholders verbatim.
        return str(bindings[var_name]) if var_name in bindings else match.group(0)

    return re.sub(r"\?(\w+)", _replace, template)


def match_pattern(
    pattern: str,
    fact: str,
    initial_bindings: Dict[str, str],
    *,
    logger=None,
) -> Optional[Dict[str, str]]:
    """Match a pattern against a fact with initial bindings.

    Variables already present in ``initial_bindings`` must match their bound
    value exactly; a variable that occurs multiple times in the pattern must
    bind the same value each time (enforced through a regex backreference).
    Returns the extended bindings on success or ``None`` when the fact does
    not match. Unexpected failures are logged through ``logger`` (if given)
    and also result in ``None``.
    """
    # Split on ?var placeholders first, then escape only the literal segments.
    # This avoids re.escape() mangling the surrounding parentheses and ?
    # before the variable substitution step.
    segments = re.split(r"(\?\w+)", pattern)
    seen_vars: set = set()
    p_regex = ""
    for seg in segments:
        if seg.startswith("?"):
            var_name = seg[1:]
            if var_name in initial_bindings:
                # Already bound — require the exact literal value
                p_regex += re.escape(initial_bindings[var_name])
            elif var_name in seen_vars:
                # Same variable used twice — use a backreference
                p_regex += f"(?P={var_name})"
            else:
                p_regex += f"(?P<{var_name}>.+?)"
                seen_vars.add(var_name)
        else:
            p_regex += re.escape(seg)
    p_regex = f"^{p_regex}$"

    # Simple regex-based matcher for patterns like "Person(?x)" and facts like "Person(John)"

    try:
        match = re.match(p_regex, fact)
        if match:
            new_bindings = initial_bindings.copy()
            for var, value in match.groupdict().items():
                if var in new_bindings and new_bindings[var] != value:
                    return None  # Binding conflict
                new_bindings[var] = value
            return new_bindings
    except Exception as e:  # pragma: no cover - defensive, mirrors legacy behavior
        if logger is not None:
            logger.warning(
                f"Error matching pattern '{pattern}' (regex: '{p_regex}') "
                f"against fact '{fact}': {e}"
            )

    return None


def match_rule(
    conditions: List[str],
    conclusion: str,
    facts: Iterable[str],
    *,
    pattern_matcher: PatternMatcher,
    substituter: Substituter,
) -> List[Tuple[str, List[str], Dict[str, str]]]:
    """Match rule conditions against facts and return instantiated conclusions.

    Returns a list of ``(conclusion, matched_facts, bindings)`` tuples where
    ``matched_facts`` is the ordered list of facts bound to the conditions and
    ``bindings`` maps variable name -> matched value. Rules without conditions
    never match.
    """
    if not conditions:
        return []

    # ``facts`` is not mutated anywhere within this function, so sort it once
    # here rather than re-sorting on every (bindings, condition) pair below --
    # sorted() was previously called once per inner-loop entry, which
    # re-allocates and re-sorts the full fact set repeatedly and is a hot spot
    # for larger fact sets.
    sorted_facts = sorted(facts)

    # Each entry pairs a set of variable bindings with the facts that were
    # matched to produce those bindings, so the facts survive alongside the
    # bindings as conditions accumulate.
    bindings_list: List[Tuple[Dict[str, str], List[str]]] = [({}, [])]

    for condition in conditions:
        new_bindings_list = []
        for bindings, matched_facts in bindings_list:
            for fact in sorted_facts:
                match_bindings = pattern_matcher(condition, fact, bindings)
                if match_bindings is not None:
                    new_bindings_list.append((match_bindings, matched_facts + [fact]))
        bindings_list = new_bindings_list
        if not bindings_list:
            break

    results = []
    for bindings, matched_facts in bindings_list:
        instantiated_conclusion = substituter(conclusion, bindings)
        results.append((instantiated_conclusion, matched_facts, bindings))

    return results