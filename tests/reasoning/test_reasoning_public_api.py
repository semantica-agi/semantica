"""Tests for the ``semantica.reasoning`` public package API.

``semantica/reasoning/__init__.py`` re-exported six of the package's eight
reasoners. ``DeductiveReasoner`` and ``AbductiveReasoner`` -- both listed
under "Main Classes" in their own module docstrings, and both documented
there as ``from semantica.reasoning import ...`` -- were never imported into
the package namespace, so those documented imports raised ``ImportError``.

The live consequence was in the MCP server: ``handle_abductive_reasoning``
imports ``AbductiveReasoner`` from the package, so the ``abductive_reasoning``
tool answered every single call with ``{"error": "cannot import name
'AbductiveReasoner' ...", "hypotheses": []}``.

Nothing caught it because ``tests/reasoning`` imports both classes by their
full module path (``semantica.reasoning.abductive_reasoner``) and so never
touches the package's public surface, and no test exercised the MCP tool at
all. These tests import through the package on purpose -- that is the thing
under test.
"""

import pytest

import semantica.reasoning as reasoning
from semantica.reasoning import (
    abductive_reasoner,
    deductive_reasoner,
    explanation_generator,
)

# The module each advertised name has to resolve to. Checking only that the
# attribute exists and appears in ``__all__`` lets a name bound to the wrong
# class pass, which is the exact failure this file exists to catch.
EXPECTED_BINDINGS = {
    "DeductiveReasoner": deductive_reasoner.DeductiveReasoner,
    "Premise": deductive_reasoner.Premise,
    "Conclusion": deductive_reasoner.Conclusion,
    "Proof": deductive_reasoner.Proof,
    "Argument": deductive_reasoner.Argument,
    "AbductiveReasoner": abductive_reasoner.AbductiveReasoner,
    "Observation": abductive_reasoner.Observation,
    "Hypothesis": abductive_reasoner.Hypothesis,
    "HypothesisRanking": abductive_reasoner.HypothesisRanking,
    "AbductiveExplanation": abductive_reasoner.Explanation,
}


class TestDocumentedImports:
    """The imports the module docstrings tell users to write."""

    def test_deductive_reasoner_module_docstring_import(self):
        from semantica.reasoning import DeductiveReasoner, Premise

        assert DeductiveReasoner is not None
        assert Premise("p1", "Human(Socrates)").statement == "Human(Socrates)"

    def test_abductive_reasoner_module_docstring_import(self):
        from semantica.reasoning import AbductiveReasoner, Observation

        assert AbductiveReasoner is not None
        observation = Observation("o1", "WetLawn(yard)")
        assert observation.description == "WetLawn(yard)"

    @pytest.mark.parametrize(
        "name",
        [
            "DeductiveReasoner",
            "Premise",
            "Conclusion",
            "Proof",
            "Argument",
            "AbductiveReasoner",
            "Observation",
            "Hypothesis",
            "HypothesisRanking",
            "AbductiveExplanation",
        ],
    )
    def test_name_is_bound_and_advertised(self, name):
        assert hasattr(reasoning, name)
        assert name in reasoning.__all__
        assert getattr(reasoning, name) is EXPECTED_BINDINGS[name]


class TestExplanationNameCollision:
    """``Explanation`` exists in two modules; the package keeps one meaning.

    ``explanation_generator.Explanation`` is what ``semantica.reasoning.
    Explanation`` has always meant. Re-exporting the abductive module's
    same-named class under the plain name would silently change that for
    every existing caller, so it is exported as ``AbductiveExplanation`` --
    the alias ``explanation_generator.py`` itself already uses.
    """

    def test_plain_name_still_means_the_explanation_generator_class(self):
        assert reasoning.Explanation is explanation_generator.Explanation

    def test_abductive_class_is_reachable_under_the_alias(self):
        assert reasoning.AbductiveExplanation is abductive_reasoner.Explanation

    def test_the_two_are_not_the_same_class(self):
        assert reasoning.Explanation is not reasoning.AbductiveExplanation


class TestAllIsConsistent:
    def test_every_advertised_name_resolves(self):
        missing = sorted(
            n for n in reasoning.__all__ if not hasattr(reasoning, n)
        )
        assert missing == []

    def test_no_duplicate_entries(self):
        assert len(reasoning.__all__) == len(set(reasoning.__all__))


class TestMCPAbductiveToolImportsItsReasoner:
    """The live victim: the MCP tool's import must resolve.

    The handler swallows every exception into its own return value, so the
    failure never surfaced as a traceback -- it surfaced as an ``error`` key
    that looked like a runtime problem with the request.

    This pins the success shape, not just the absence of an error: the handler
    returns ``{"count": ..., "hypotheses": ...}`` and puts ``error`` in the
    result only when it fails. The tool has further defects that are out of
    scope here (it supplies no rules, so there is nothing to reason from; it
    passes raw strings where ``Observation`` objects are required; and
    ``Hypothesis`` is not JSON-serializable), which is why the assertions stop
    at the empty-hypotheses shape instead of checking hypothesis contents.
    """

    def test_handler_does_not_report_a_missing_reasoner(self):
        from semantica_mcp.mcp.tools.reasoning import (
            handle_abductive_reasoning,
        )

        result = handle_abductive_reasoning(
            {"observations": ["the lawn is wet"]}
        )

        assert "error" not in result
        assert result["hypotheses"] == []
        assert result["count"] == 0
