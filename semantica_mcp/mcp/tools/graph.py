"""
Graph tools — add entities/relationships, search, analytics, summary.
"""

from __future__ import annotations

import logging
import os

from ..schemas import ADD_ENTITY, ADD_RELATIONSHIP, EMPTY, GET_ANALYTICS, SEARCH_GRAPH
from ..session import get_graph, is_persistence_safe

log = logging.getLogger("semantica.mcp.tools.graph")


def handle_add_entity(args: dict) -> dict:
    """Add a node/entity to the Semantica knowledge graph."""
    node_id = args.get("id", "").strip()
    if not node_id:
        return {"error": "id is required"}
    try:
        graph = get_graph()
        graph.add_node(
            node_id=node_id,
            label=args.get("label", node_id),
            node_type=args.get("type", "Entity"),
            metadata=args.get("metadata", {}),
        )
        # Persist back to disk so the entity survives server restarts.
        # Skip when the initial load failed to avoid overwriting original data.
        kg_path = os.environ.get("SEMANTICA_KG_PATH", "").strip()
        if kg_path:
            if not is_persistence_safe():
                # Roll back: remove the node we just added.
                try:
                    with graph._lock:
                        graph._drop_node_from_indexes(node_id)
                except Exception:
                    pass
                return {
                    "error": (
                        "Persistence blocked: the configured SEMANTICA_KG_PATH "
                        "could not be loaded at startup. Restart the server with "
                        "a readable graph file to re-enable persistence."
                    )
                }
            try:
                graph.save_to_file(kg_path)
            except Exception as save_exc:
                # Roll back: remove the node so in-memory and persisted state agree.
                try:
                    with graph._lock:
                        graph._drop_node_from_indexes(node_id)
                except Exception:
                    pass
                log.exception("save_to_file failed after add_entity; mutation rolled back")
                return {"error": f"Mutation rolled back: could not persist graph: {save_exc}"}
        return {"status": "added", "id": node_id, "type": args.get("type", "Entity")}
    except Exception as exc:
        log.exception("add_entity failed")
        return {"error": str(exc)}


def handle_add_relationship(args: dict) -> dict:
    """Add a directed relationship (edge) between two entities."""
    source = args.get("source", "").strip()
    target = args.get("target", "").strip()
    if not source or not target:
        return {"error": "source and target are required"}
    rel_type = args.get("type", "RELATED_TO")
    try:
        graph = get_graph()
        graph.add_edge(
            source_id=source,
            target_id=target,
            edge_type=rel_type,
            metadata=args.get("metadata", {}),
        )
        # Persist back to disk so the relationship survives server restarts.
        # Skip when the initial load failed to avoid overwriting original data.
        kg_path = os.environ.get("SEMANTICA_KG_PATH", "").strip()
        if kg_path:
            if not is_persistence_safe():
                # Roll back: remove the edge we just added (last matching edge).
                try:
                    with graph._lock:
                        for edge in reversed(list(graph.edges)):
                            if (edge.source_id == source
                                    and edge.target_id == target
                                    and edge.edge_type == rel_type):
                                graph._drop_edge_from_indexes(edge)
                                break
                except Exception:
                    pass
                return {
                    "error": (
                        "Persistence blocked: the configured SEMANTICA_KG_PATH "
                        "could not be loaded at startup. Restart the server with "
                        "a readable graph file to re-enable persistence."
                    )
                }
            try:
                graph.save_to_file(kg_path)
            except Exception as save_exc:
                # Roll back: remove the edge so in-memory and persisted state agree.
                try:
                    with graph._lock:
                        for edge in reversed(list(graph.edges)):
                            if (edge.source_id == source
                                    and edge.target_id == target
                                    and edge.edge_type == rel_type):
                                graph._drop_edge_from_indexes(edge)
                                break
                except Exception:
                    pass
                log.exception("save_to_file failed after add_relationship; mutation rolled back")
                return {"error": f"Mutation rolled back: could not persist graph: {save_exc}"}
        return {"status": "added", "source": source, "target": target, "type": rel_type}
    except Exception as exc:
        log.exception("add_relationship failed")
        return {"error": str(exc)}


def handle_search_graph(args: dict) -> dict:
    """Search nodes in the knowledge graph by label or metadata."""
    query = args.get("query", "").strip()
    if not query:
        return {"error": "query is required", "results": []}
    node_type = args.get("node_type", "").strip() or None
    limit = int(args.get("limit", 20))
    try:
        graph = get_graph()
        if node_type:
            nodes = list(graph.find_nodes(node_type=node_type))
        else:
            nodes = list(graph.find_nodes())
        q = query.lower()
        matched = [
            n for n in nodes
            if q in str(n.get("label", "")).lower()
            or q in str(n.get("id", "")).lower()
        ][:limit]
        return {"results": matched, "count": len(matched), "query": query}
    except Exception as exc:
        log.exception("search_graph failed")
        return {"error": str(exc), "results": []}


def handle_get_graph_summary(args: dict) -> dict:  # noqa: ARG001
    """Return a high-level summary of the current knowledge graph."""
    try:
        graph = get_graph()
        all_nodes = list(graph.find_nodes())
        decisions = [n for n in all_nodes if n.get("type") in ("decision", "Decision")]
        node_types: dict[str, int] = {}
        for n in all_nodes:
            t = str(n.get("type", "Unknown"))
            node_types[t] = node_types.get(t, 0) + 1
        edge_count = 0
        if hasattr(graph, "edge_count"):
            try:
                edge_count = graph.edge_count()
            except Exception:
                log.exception("graph.edge_count failed; defaulting edge_count to 0")
        elif hasattr(graph, "stats"):
            edge_count = graph.stats().get("edge_count", 0)
        return {
            "node_count": len(all_nodes),
            "edge_count": edge_count,
            "decision_count": len(decisions),
            "node_types": node_types,
            "graph_ready": True,
        }
    except Exception as exc:
        log.exception("get_graph_summary failed")
        return {"error": str(exc), "graph_ready": False}


def _top_rankings(payload, top_n: int) -> list:
    """Return the first ``top_n`` entries of a centrality result.

    ``CentralityCalculator`` returns ``{"centrality": {node: score},
    "rankings": [...]}`` and the rankings list is already sorted, so the
    handler only has to trim it.  PageRank emits ``(node, score)`` pairs
    while the other measures emit ``{"node": ..., "score": ...}`` dicts;
    both are normalised here so the tool returns one shape.
    """
    if not isinstance(payload, dict):
        return []
    rankings = payload.get("rankings")
    if not isinstance(rankings, list):
        centrality = payload.get("centrality")
        if not isinstance(centrality, dict):
            return []
        rankings = sorted(centrality.items(), key=lambda item: item[1], reverse=True)
    trimmed = []
    for entry in rankings[:top_n]:
        if isinstance(entry, dict):
            trimmed.append(entry)
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            trimmed.append({"node": entry[0], "score": entry[1]})
    return trimmed


def _community_groups(payload) -> list:
    """Return the community groups of a ``detect_communities`` result.

    The detector returns ``{"communities": [set, ...], ...}``; the groups
    are sets, which the JSON transport cannot serialise, so each one is
    returned as a sorted list.
    """
    if isinstance(payload, dict):
        groups = payload.get("communities")
    elif isinstance(payload, list):
        groups = payload
    else:
        groups = None
    if not isinstance(groups, list):
        return []
    return [sorted(group) if isinstance(group, (set, frozenset)) else group for group in groups]


def handle_get_graph_analytics(args: dict) -> dict:
    """Compute centrality, community detection, and other graph metrics."""
    requested = args.get("metrics", ["all"])
    top_n = int(args.get("top_n", 10))
    compute_all = "all" in requested
    result: dict = {}
    try:
        graph = get_graph()
        from semantica.kg import CentralityCalculator, CommunityDetector

        if compute_all or "pagerank" in requested:
            try:
                pr = CentralityCalculator().calculate_pagerank(graph)
                result["pagerank"] = _top_rankings(pr, top_n)
            except Exception as exc:
                result["pagerank_error"] = str(exc)

        if compute_all or "betweenness" in requested:
            try:
                bc = CentralityCalculator().calculate_betweenness_centrality(graph)
                result["betweenness"] = _top_rankings(bc, top_n)
            except Exception as exc:
                result["betweenness_error"] = str(exc)

        if compute_all or "communities" in requested:
            try:
                comms = CommunityDetector().detect_communities(graph)
                groups = _community_groups(comms)
                result["community_count"] = len(groups)
                result["communities"] = groups
            except Exception as exc:
                result["communities_error"] = str(exc)

        if compute_all or "degree" in requested:
            try:
                deg = CentralityCalculator().calculate_degree_centrality(graph)
                result["degree"] = _top_rankings(deg, top_n)
            except Exception as exc:
                result["degree_error"] = str(exc)

        return result
    except Exception as exc:
        log.exception("get_graph_analytics failed")
        return {"error": str(exc)}


GRAPH_TOOLS = [
    {
        "name": "add_entity",
        "description": "Add a node or entity (person, place, concept, organisation) to the knowledge graph.",
        "inputSchema": ADD_ENTITY,
        "_handler": handle_add_entity,
    },
    {
        "name": "add_relationship",
        "description": "Add a directed relationship (edge) between two entities in the knowledge graph.",
        "inputSchema": ADD_RELATIONSHIP,
        "_handler": handle_add_relationship,
    },
    {
        "name": "search_graph",
        "description": "Search nodes in the knowledge graph by label or ID substring.",
        "inputSchema": SEARCH_GRAPH,
        "_handler": handle_search_graph,
    },
    {
        "name": "get_graph_summary",
        "description": "Return a high-level summary of the knowledge graph: node count, edge count, decision count, node type breakdown.",
        "inputSchema": EMPTY,
        "_handler": handle_get_graph_summary,
    },
    {
        "name": "get_graph_analytics",
        "description": "Compute PageRank centrality, betweenness centrality, degree centrality, and community detection over the knowledge graph.",
        "inputSchema": GET_ANALYTICS,
        "_handler": handle_get_graph_analytics,
    },
]
