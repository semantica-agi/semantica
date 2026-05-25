"""
Provenance routes for lineage visualization and exportable reports.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import networkx as nx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response

from ..dependencies import get_session
from ..schemas import ProvenanceEdge, ProvenanceNode, ProvenanceResponse
from ..session import GraphSession

router = APIRouter(prefix="/api/provenance", tags=["Power User Tools"])

_AGENT_TYPES = {"person", "organization", "system", "agent"}
_ACTIVITY_TYPES = {"action", "event", "process", "activity", "decision", "publication"}


def _classify_prov(node_type: str) -> tuple[str, str]:
    lowered = node_type.lower()
    if lowered in _AGENT_TYPES:
        return "Agent", "group_agent"
    if lowered in _ACTIVITY_TYPES:
        return "Activity", "group_activity"
    return "Entity", "group_entity"


def _build_provenance(session: GraphSession, node_id: Optional[str] = None) -> dict:
    if not node_id or node_id not in session.graph.nodes:
        return {"nodes": [], "edges": []}

    graph = nx.DiGraph()
    graph.add_node(node_id)

    hop_nodes = {node_id}
    for edge in session.graph.edges:
        if edge.source_id == node_id or edge.target_id == node_id:
            graph.add_edge(edge.source_id, edge.target_id, label=edge.edge_type)
            hop_nodes.add(edge.source_id)
            hop_nodes.add(edge.target_id)

    for edge in session.graph.edges:
        if edge.source_id in hop_nodes or edge.target_id in hop_nodes:
            graph.add_edge(edge.source_id, edge.target_id, label=edge.edge_type)

    subgraph = nx.ego_graph(graph, node_id, radius=2, undirected=True)
    provenance_nodes: List[Dict[str, Any]] = []
    for graph_node_id in subgraph.nodes():
        node = session.graph.nodes.get(graph_node_id)
        if node is None:
            continue
        prov_type, parent_id = _classify_prov(node.node_type)
        provenance_nodes.append(
            {
                "id": graph_node_id,
                "label": node.content or graph_node_id,
                "prov_type": prov_type,
                "parent_id": parent_id,
            }
        )

    provenance_edges: List[Dict[str, Any]] = []
    for source, target, data in subgraph.edges(data=True):
        if target == node_id:
            direction = "upstream"
        elif source == node_id:
            direction = "downstream"
        else:
            direction = "lateral"
        provenance_edges.append(
            {
                "id": f"{source}-{target}",
                "source": source,
                "target": target,
                "label": data.get("label", "related_to"),
                "direction": direction,
            }
        )

    return {"nodes": provenance_nodes, "edges": provenance_edges}


def _build_report(session: GraphSession, node_id: str) -> Dict[str, Any]:
    node = session.get_node(node_id)
    provenance = _build_provenance(session, node_id)
    return {
        "node_id": node_id,
        "label": node.get("content", node_id) if node else node_id,
        "type": node.get("type", "entity") if node else "entity",
        "properties": node.get("metadata", node.get("properties", {})) if node else {},
        "lineage": provenance,
    }


def _render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# Provenance Report: {report['label']}",
        "",
        f"- Node ID: `{report['node_id']}`",
        f"- Type: `{report['type']}`",
        "",
        "## Properties",
    ]
    properties = report.get("properties", {})
    if properties:
        for key, value in properties.items():
            lines.append(f"- **{key}**: {value}")
    else:
        lines.append("- No properties recorded")

    lines.extend(["", "## Lineage Nodes"])
    for node in report.get("lineage", {}).get("nodes", []):
        lines.append(f"- `{node['id']}` ({node['prov_type']}): {node['label']}")

    edges = report.get("lineage", {}).get("edges", [])
    grouped_edges: Dict[str, List] = {"upstream": [], "downstream": [], "lateral": []}
    for edge in edges:
        direction = edge.get("direction", "lateral")
        if direction not in grouped_edges:
            direction = "lateral"
        grouped_edges[direction].append(edge)

    if grouped_edges["upstream"]:
        lines.extend(["", "## Upstream"])
        for edge in grouped_edges["upstream"]:
            lines.append(f"- `{edge['source']}` -[{edge['label']}]-> `{edge['target']}`")

    if grouped_edges["downstream"]:
        lines.extend(["", "## Downstream"])
        for edge in grouped_edges["downstream"]:
            lines.append(f"- `{edge['source']}` -[{edge['label']}]-> `{edge['target']}`")

    if grouped_edges["lateral"]:
        lines.extend(["", "## Lateral"])
        for edge in grouped_edges["lateral"]:
            lines.append(f"- `{edge['source']}` -[{edge['label']}]-> `{edge['target']}`")

    return "\n".join(lines)


@router.get("", response_model=ProvenanceResponse)
@router.get("/", response_model=ProvenanceResponse, include_in_schema=False)
async def get_provenance_lineage(
    node_id: Optional[str] = None,
    session: GraphSession = Depends(get_session),
):
    data = await asyncio.to_thread(_build_provenance, session, node_id)
    return ProvenanceResponse(
        nodes=[ProvenanceNode(**node) for node in data["nodes"]],
        edges=[ProvenanceEdge(**edge) for edge in data["edges"]],
    )


@router.get("/report")
async def export_provenance_report(
    node_id: str = Query(..., description="Node ID to export"),
    format: str = Query("json", description="json or markdown"),
    session: GraphSession = Depends(get_session),
):
    report = await asyncio.to_thread(_build_report, session, node_id)
    if format.lower() in {"md", "markdown"}:
        content = _render_markdown(report)
        return PlainTextResponse(
            content,
            headers={"Content-Disposition": f'attachment; filename="{node_id}_provenance.md"'},
        )

    content = json.dumps(report, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{node_id}_provenance.json"'},
    )
