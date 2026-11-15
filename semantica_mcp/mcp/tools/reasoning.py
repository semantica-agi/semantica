"""
Reasoning tools — forward chaining, abductive reasoning.
"""

from __future__ import annotations

import dataclasses
import json
import logging

from ..schemas import ABDUCTIVE_REASONING, RUN_REASONING

log = logging.getLogger("semantica.mcp.tools.reasoning")


def handle_run_reasoning(args: dict) -> dict:
    """Run forward-chaining IF/THEN rules over facts to derive new knowledge."""
    facts = args.get("facts", [])
    rules = args.get("rules", [])
    if not facts:
        return {"error": "facts list is required", "derived_facts": []}
    if not rules:
        return {"error": "rules list is required", "derived_facts": []}
    try:
        from semantica.reasoning import Reasoner
        reasoner = Reasoner()
        for rule in rules:
            reasoner.add_rule(str(rule))
        derived = reasoner.infer_facts(facts)
        result = derived if isinstance(derived, list) else list(derived)
        return {
            "derived_facts": result,
            "count": len(result),
            "input_facts": len(facts),
            "rules_applied": len(rules),
        }
    except Exception as exc:
        log.exception("run_reasoning failed")
        return {"error": str(exc), "derived_facts": []}


def _hypothesis_to_dict(hypothesis) -> dict:
    """Project a Hypothesis dataclass into a JSON-serialisable dict."""
    return json.loads(json.dumps(dataclasses.asdict(hypothesis), default=str))


def handle_abductive_reasoning(args: dict) -> dict:
    """Generate plausible hypotheses that explain a set of observations."""
    observations = args.get("observations", [])
    if not observations:
        return {"error": "observations list is required", "hypotheses": []}
    try:
        max_hypotheses = int(args.get("max_hypotheses", 5))
        # Imported from the defining module so the handler does not depend on
        # what the package namespace happens to re-export.
        from semantica.reasoning.abductive_reasoner import (
            AbductiveReasoner,
            Observation,
        )

        reasoner = AbductiveReasoner(config={"max_hypotheses": max_hypotheses})
        hypotheses = reasoner.generate_hypotheses(
            [
                Observation(observation_id=f"obs_{i}", description=str(text))
                for i, text in enumerate(observations)
            ]
        )
        result = [_hypothesis_to_dict(h) for h in hypotheses]
        return {"hypotheses": result, "count": len(result)}
    except Exception as exc:
        log.exception("abductive_reasoning failed")
        return {"error": str(exc), "hypotheses": []}


REASONING_TOOLS = [
    {
        "name": "run_reasoning",
        "description": "Run forward-chaining IF/THEN rules over a set of facts to derive new facts. E.g. facts=['Person(John)'], rules=['IF Person(?x) THEN Mortal(?x)'] → derives 'Mortal(John)'.",
        "inputSchema": RUN_REASONING,
        "_handler": handle_run_reasoning,
    },
    {
        "name": "abductive_reasoning",
        "description": "Generate plausible hypotheses that best explain a set of observed facts.",
        "inputSchema": ABDUCTIVE_REASONING,
        "_handler": handle_abductive_reasoning,
    },
]
