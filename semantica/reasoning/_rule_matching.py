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


_VARIABLE = re.compile(r"\?\w+")


def split_atom(text: str) -> Optional[Tuple[str, List[str]]]:
    """Split ``"Pred(a, f(b, c), d)"`` into ``("Pred", ["a", "f(b, c)", "d"])``.

    Arguments are split on top-level commas only (commas inside nested
    parentheses stay in their argument) and stripped, so ``"P(a,b)"`` and
    ``"P(a, b)"`` are the same atom. Returns ``None`` for text that is not a
    single ``name(args)`` atom.
    """
    if not isinstance(text, str):
        return None
    match = re.match(r"^\s*([^\s(),]+)\s*\((.*)\)\s*$", text, re.DOTALL)
    if not match:
        return None
    predicate, body = match.group(1), match.group(2)
    if not body.strip():
        return predicate, []
    args: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return None
        if ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if depth != 0:
        return None
    args.append("".join(current).strip())
    return predicate, args


def render_atom(predicate: str, args: List[str]) -> str:
    """Render an atom in the canonical ``Pred(a, b)`` form."""
    return f"{predicate}({', '.join(args)})"


def canonical_atom(text: str) -> str:
    """``text`` in canonical ``Pred(a, b)`` spacing, or unchanged if not an atom."""
    parts = split_atom(text)
    return render_atom(*parts) if parts else text


def _match_term(
    term: str, value: str, bindings: Dict[str, str]
) -> Optional[Dict[str, str]]:
    """Match one pattern argument against one value, extending ``bindings``."""
    if _VARIABLE.fullmatch(term):
        name = term[1:]
        if name in bindings:
            return bindings if bindings[name] == value else None
        bindings[name] = value
        return bindings
    if "?" in term:
        inner_pattern, inner_value = split_atom(term), split_atom(value)
        if inner_pattern and inner_value:
            return _match_atoms(inner_pattern, inner_value, bindings)
        return match_pattern(term, value, bindings)
    return bindings if term == value else None


def _match_atoms(
    pattern: Tuple[str, List[str]],
    value: Tuple[str, List[str]],
    bindings: Dict[str, str],
) -> Optional[Dict[str, str]]:
    """Match a parsed ``name(args)`` pattern against a parsed atom.

    Arguments are compared one by one, so spacing never ends up in a binding;
    the argument counts must be equal; a variable already in ``bindings`` must
    equal its bound value, and a variable used twice must bind one value.
    """
    (p_pred, p_args), (v_pred, v_args) = pattern, value
    if len(p_args) != len(v_args):
        return None
    result: Optional[Dict[str, str]] = _match_term(p_pred, v_pred, dict(bindings))
    for term, arg in zip(p_args, v_args):
        if result is None:
            return None
        result = _match_term(term, arg, result)
    return result


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
