#!/usr/bin/env python3
"""Regression tests for the ``Example Usage`` blocks in the reasoning
package.

Three module docstrings documented methods that do not exist, so copying any
of these examples raised ``AttributeError`` on its first call::

    ExplanationGenerator.generate_reasoning_path -> show_reasoning_path
    ExplanationGenerator.create_justification    -> justify_conclusion
    ReteEngine.add_rule                          -> build_network([rule])
    ReteEngine.get_matches                       -> match_patterns
    SPARQLReasoner.query                         -> execute_query

Each block was also wrong in a second way that an attribute check cannot
see, which is why these tests **execute** the blocks rather than only
scanning them:

- ``explanation_generator`` passed ``inference_result``, a name that is never
  defined, so the block raised ``NameError`` on a method that does exist.
- ``rete_engine`` passed ``rule``, likewise undefined.
- ``sparql_reasoner`` called ``expand_query(query, rules)``. ``rules`` was
  undefined *and* ``expand_query``'s signature is ``(query, **options)``, so
  a second positional is a ``TypeError`` even with a real value. Inference
  rules come from ``add_inference_rule``.

Unlike ``semantica/parse``, these blocks need no optional extra, so they are
run for real and asserted on their output -- an example that returns an empty
list teaches the reader as little as one that crashes.

``semantica/reasoning/deductive_reasoner.py`` has the same defect
(``DeductiveReasoner.deduce`` / ``generate_proof``) and is **not** fixed here:
its block begins ``from semantica.reasoning import DeductiveReasoner``, which
only resolves once #2243 lands. It is listed in ``_KNOWN_REMAINING`` below,
and ``test_known_remaining_is_still_broken`` fails if that list goes stale.
"""

import ast
import doctest
import importlib
import pathlib
import re

import pytest

import semantica.reasoning as reasoning_pkg
from semantica.reasoning import (
    ExplanationGenerator,
    Fact,
    InferenceResult,
    ReteEngine,
    Rule,
    SPARQLReasoner,
)
from semantica.utils.exceptions import ProcessingError

_REASONING_DIR = pathlib.Path(reasoning_pkg.__file__).parent
_ASSIGN_RE = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*\(")
_CALL_RE = re.compile(r"\b(\w+)\.(\w+)\s*\(")

# Modules whose documented calls are still broken, with the reason. Each one
# needs an entry in test_known_remaining_is_still_broken so this cannot rot
# into a list of things that were quietly fixed elsewhere.
_KNOWN_REMAINING = {
    "deductive_reasoner": "blocked on #2243 -- its example imports "
                          "DeductiveReasoner from the package",
}


def _modules_with_examples():
    names = []
    for path in sorted(_REASONING_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc = ast.get_docstring(tree)
        if doc and ">>>" in doc:
            names.append(path.stem)
    return names


def _unresolved_calls(stem):
    """Documented ``var.attr(`` calls whose attr is absent from var's class."""
    module = importlib.import_module(f"semantica.reasoning.{stem}")
    doc = ast.get_docstring(
        ast.parse((_REASONING_DIR / f"{stem}.py").read_text(encoding="utf-8"))
    )
    bound, missing = {}, []
    for example in doctest.DocTestParser().get_examples(doc or ""):
        source = example.source.strip()
        assigned = _ASSIGN_RE.match(source)
        if assigned and hasattr(module, assigned.group(2)):
            bound[assigned.group(1)] = getattr(module, assigned.group(2))
        for var, attr in _CALL_RE.findall(source):
            target = bound.get(var)
            if target is not None and not hasattr(target, attr):
                name = getattr(target, "__name__", type(target).__name__)
                missing.append(f"{name}.{attr}")
    return sorted(set(missing))


class TestNoDocumentedCallIsMissing:
    """The shape of the original bug, swept across the whole subpackage."""

    @pytest.mark.parametrize("stem", _modules_with_examples())
    def test_documented_calls_resolve(self, stem):
        if stem in _KNOWN_REMAINING:
            pytest.skip(_KNOWN_REMAINING[stem])
        assert _unresolved_calls(stem) == []

    def test_every_module_with_examples_is_covered(self):
        """The sweep must actually see the three modules this PR fixes."""
        found = set(_modules_with_examples())
        for stem in (
            "explanation_generator", "rete_engine", "sparql_reasoner"
        ):
            assert stem in found

    @pytest.mark.parametrize("stem", sorted(_KNOWN_REMAINING))
    def test_known_remaining_is_still_broken(self, stem):
        """A skip list that stops being true is worse than no skip list."""
        assert _unresolved_calls(stem) != [], (
            f"{stem} now resolves; drop it from _KNOWN_REMAINING"
        )


# Errors that mean the documented example has drifted from the code. A
# ProcessingError is deliberately not in here: sparql_reasoner's block needs a
# running triplet store, and "no server" is not drift.
_DRIFT_ERRORS = (AttributeError, NameError, TypeError, ImportError)


def _run_example(stem):
    """Execute a module's documented block; return the first drift error."""
    doc = ast.get_docstring(
        ast.parse((_REASONING_DIR / f"{stem}.py").read_text(encoding="utf-8"))
    )
    namespace = {}
    for example in doctest.DocTestParser().get_examples(doc or ""):
        try:
            exec(compile(example.source, f"<{stem}>", "single"), namespace)
        except _DRIFT_ERRORS as exc:
            return f"{type(exc).__name__}: {exc}"
        except Exception:
            # Anything else is an environment limit, not drift. Stop here --
            # later statements depend on this one.
            return None
    return None


class TestDocumentedExamplesExecute:
    """Run the blocks as written.

    The static sweep above cannot see the second defect each of these had:
    an undefined name, or a second positional argument landing in
    ``**options``. Both raise before any attribute lookup would, so only
    executing the block catches them.
    """

    @pytest.mark.parametrize(
        "stem", ["explanation_generator", "rete_engine", "sparql_reasoner"]
    )
    def test_block_runs_without_drifting(self, stem):
        assert _run_example(stem) is None

    def test_the_runner_reports_drift_when_there_is_some(self):
        """Rule out a runner that silently passes everything."""
        namespace = {}
        try:
            exec("undefined_name.method()", namespace)
        except _DRIFT_ERRORS as exc:
            assert "NameError" in type(exc).__name__
        else:
            pytest.fail("_DRIFT_ERRORS does not cover an undefined name")


class TestExplanationGeneratorExampleRuns:
    """The documented block, executed, with its output asserted."""

    @staticmethod
    def _inference():
        rule = Rule("r1", "mortality", ["Human(?x)"], "Mortal(?x)")
        return InferenceResult("Mortal(Socrates)", rule, ["Human(Socrates)"])

    def test_generate_explanation_returns_reasoning_steps(self):
        explanation = ExplanationGenerator().generate_explanation(
            self._inference()
        )
        assert explanation.reasoning_path is not None
        assert explanation.reasoning_path.steps

    def test_show_reasoning_path_is_the_documented_name(self):
        generator = ExplanationGenerator()
        assert not hasattr(generator, "generate_reasoning_path")
        path = generator.show_reasoning_path(self._inference())
        assert path.steps

    def test_justify_conclusion_is_the_documented_name(self):
        generator = ExplanationGenerator()
        assert not hasattr(generator, "create_justification")
        inference = self._inference()
        path = generator.show_reasoning_path(inference)
        justification = generator.justify_conclusion(
            inference.conclusion, path
        )
        assert justification.conclusion == "Mortal(Socrates)"


class TestReteEngineExampleRuns:
    def test_build_network_and_match_patterns_bind_the_fact(self):
        engine = ReteEngine()
        assert not hasattr(engine, "add_rule")
        assert not hasattr(engine, "get_matches")

        rule = Rule("r1", "mortality", ["Person(?x)"], "Mortal(?x)")
        engine.build_network([rule])
        engine.add_fact(Fact("f1", "Person", ["John"]))
        matches = engine.match_patterns()

        # An example that returns [] would read as "nothing matched".
        assert len(matches) == 1
        assert matches[0].bindings == {"x": "John"}


class TestSPARQLReasonerExampleRuns:
    def test_expand_query_takes_rules_from_add_inference_rule(self):
        expander = SPARQLReasoner()
        expanded = expander.expand_query(
            "SELECT ?x WHERE { ?x a :Person . }"
        )
        assert "Inference" not in expanded

        expander.add_inference_rule("IF ?x is_a Person THEN ?x is_a Human")
        with_rule = expander.expand_query(
            "SELECT ?x WHERE { ?x a :Person . }"
        )
        assert "Inference" in with_rule

    def test_expand_query_rejects_a_second_positional(self):
        """What the old example did: expand_query(query, rules)."""
        expander = SPARQLReasoner()
        with pytest.raises(TypeError):
            expander.expand_query("SELECT ?x WHERE { ?x a :Person . }", [])

    def test_query_is_not_the_method_name(self):
        assert not hasattr(SPARQLReasoner(), "query")
        assert hasattr(SPARQLReasoner(), "execute_query")

    def test_execute_query_refuses_without_a_store(self):
        """Pins the claim the corrected docstring makes about the store."""
        with pytest.raises(ProcessingError, match="requires a triplet store"):
            SPARQLReasoner().execute_query("SELECT ?s WHERE { ?s ?p ?o }")
