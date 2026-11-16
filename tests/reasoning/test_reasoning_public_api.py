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
from semantica.reasoning import abductive_reasoner, explanation_generator


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

    This asserts only that the import resolves. The tool has further defects
    that are out of scope here (it supplies no rules, so there is nothing to
    reason from; it passes raw strings where ``Observation`` objects are
    required; and ``Hypothesis`` is not JSON-serializable), which is why this
    checks for the absence of the import error rather than for hypotheses.
    """

    def test_handler_does_not_report_a_missing_reasoner(self):
        from semantica_mcp.mcp.tools.reasoning import (
            handle_abductive_reasoning,
        )

        result = handle_abductive_reasoning(
            {"observations": ["the lawn is wet"]}
        )

        assert "cannot import name" not in result.get("error", "")
        assert "AbductiveReasoner" not in result.get("error", "")
