"""
Decision intelligence tools — record, query, precedents, causal chain, impact.
"""

from __future__ import annotations

import logging

from mcp.schemas import (
    ANALYZE_DECISION_IMPACT,
    FIND_PRECEDENTS,
    GET_CAUSAL_CHAIN,
    QUERY_DECISIONS,
    RECORD_DECISION,
)
from mcp.session import get_graph

log = logging.getLogger("semantica.mcp.tools.decisions")


def handle_record_decision(args: dict) -> dict:
    """Record a decision with full context into the knowledge graph."""
    required = ["category", "scenario", "reasoning", "outcome", "confidence"]
    missing = [f for f in required if f not in args]
    if missing:
        return {"error": f"Missing required fields: {', '.join(missing)}"}
    try:
        graph = get_graph()
        decision_id = graph.record_decision(
            category=str(args["category"]),
            scenario=str(args["scenario"]),
            reasoning=str(args["reasoning"]),
            outcome=str(args["outcome"]),
            confidence=float(args["confidence"]),
            entities=args.get("entities", []),
            decision_maker=args.get("decision_maker", "mcp_client"),
            valid_from=args.get("valid_from"),
            valid_until=args.get("valid_until"),
        )
        return {
            "decision_id": decision_id,
            "status": "recorded",
            "category": args["category"],
            "outcome": args["outcome"],
        }
    except Exception as exc:
        log.exception("record_decision failed")
        return {"error": str(exc)}


def handle_query_decisions(args: dict) -> dict:
    """Query recorded decisions by natural language or structured filters."""
    query = args.get("query", "").strip()
    category = args.get("category", "").strip()
    outcome_filter = args.get("outcome", "").strip()
    limit = int(args.get("limit", 10))
    try:
        graph = get_graph()
        if query:
            results = graph.find_similar_decisions(query, max_results=limit)
            decisions = results if isinstance(results, list) else list(results)
        else:
            nodes = graph.find_nodes(node_type="decision")
            decisions = list(nodes)[:limit * 5]  # over-fetch for filtering
            if category:
                decisions = [d for d in decisions if d.get("category") == category]
            if outcome_filter:
                decisions = [d for d in decisions if d.get("outcome") == outcome_filter]
            decisions = decisions[:limit]
        return {"decisions": decisions, "count": len(decisions)}
    except Exception as exc:
        log.exception("query_decisions failed")
        return {"error": str(exc), "decisions": []}


def handle_find_precedents(args: dict) -> dict:
    """Find past decisions similar to a given scenario using hybrid similarity search."""
    scenario = args.get("scenario", "").strip()
    if not scenario:
        return {"error": "scenario is required", "precedents": []}
    max_results = int(args.get("max_results", 5))
    try:
        graph = get_graph()
        precedents = graph.find_similar_decisions(scenario, max_results=max_results)
        results = precedents if isinstance(precedents, list) else list(precedents)
        return {"precedents": results, "count": len(results)}
    except Exception as exc:
        log.exception("find_precedents failed")
        return {"error": str(exc), "precedents": []}


def handle_get_causal_chain(args: dict) -> dict:
    """Trace the upstream or downstream causal chain from a decision."""
    decision_id = args.get("decision_id", "").strip()
    if not decision_id:
        return {"error": "decision_id is required", "chain": []}
    direction = args.get("direction", "downstream")
    max_depth = int(args.get("max_depth", 5))
    try:
        graph = get_graph()
        try:
            from semantica.context.causal_analyzer import CausalChainAnalyzer
            analyzer = CausalChainAnalyzer(graph_store=graph)
            chain = analyzer.get_causal_chain(
                decision_id, direction=direction, max_depth=max_depth
            )
        except (ImportError, AttributeError):
            chain = graph.get_causal_chain(decision_id) if hasattr(graph, "get_causal_chain") else []
        result = chain if isinstance(chain, list) else list(chain)
        return {"chain": result, "count": len(result), "direction": direction}
    except Exception as exc:
        log.exception("get_causal_chain failed")
        return {"error": str(exc), "chain": []}


def handle_analyze_decision_impact(args: dict) -> dict:
    """Analyse the downstream impact of a decision on the graph."""
    decision_id = args.get("decision_id", "").strip()
    if not decision_id:
        return {"error": "decision_id is required"}
    try:
        graph = get_graph()
        if hasattr(graph, "analyze_decision_impact"):
            impact = graph.analyze_decision_impact(decision_id)
        elif hasattr(graph, "analyze_decision_influence"):
            impact = graph.analyze_decision_influence(decision_id)
        else:
            impact = {"message": "impact analysis not available on this graph instance"}
        return {"decision_id": decision_id, "impact": impact}
    except Exception as exc:
        log.exception("analyze_decision_impact failed")
        return {"error": str(exc)}


DECISION_TOOLS = [
    {
        "name": "record_decision",
        "description": "Record a decision with full context, causal links, and metadata into the Semantica knowledge graph.",
        "inputSchema": RECORD_DECISION,
        "_handler": handle_record_decision,
    },
    {
        "name": "query_decisions",
        "description": "Query recorded decisions by natural language, category, or outcome filter.",
        "inputSchema": QUERY_DECISIONS,
        "_handler": handle_query_decisions,
    },
    {
        "name": "find_precedents",
        "description": "Find past decisions similar to a given scenario using hybrid similarity search.",
        "inputSchema": FIND_PRECEDENTS,
        "_handler": handle_find_precedents,
    },
    {
        "name": "get_causal_chain",
        "description": "Trace the causal chain upstream or downstream from a recorded decision.",
        "inputSchema": GET_CAUSAL_CHAIN,
        "_handler": handle_get_causal_chain,
    },
    {
        "name": "analyze_decision_impact",
        "description": "Analyse the downstream impact and influence of a decision across the knowledge graph.",
        "inputSchema": ANALYZE_DECISION_IMPACT,
        "_handler": handle_analyze_decision_impact,
    },
]
