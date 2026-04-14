"""
Graph routes for explorer node, edge, path, and search APIs.
"""

import asyncio
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_session
from ..schemas import (
    EdgeListResponse,
    EdgeResponse,
    GraphStatsResponse,
    NeighborResponse,
    NodeListResponse,
    NodeResponse,
    PathResponse,
    SearchRequest,
    SearchResultItem,
    SearchResultResponse,
)
from ..session import GraphSession

router = APIRouter(prefix="/api/graph", tags=["Graph"])


def _parse_bbox(raw_bbox: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not raw_bbox:
        return None
    parts = [part.strip() for part in raw_bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be four comma-separated numbers: min_x,min_y,max_x,max_y")
    min_x, min_y, max_x, max_y = [float(part) for part in parts]
    if min_x > max_x or min_y > max_y:
        raise ValueError("bbox minimum values must be less than or equal to maximum values")
    return min_x, min_y, max_x, max_y


def _node_response(node: dict) -> NodeResponse:
    return NodeResponse(**node)


def _edge_response(edge: dict) -> EdgeResponse:
    return EdgeResponse(**edge)


@router.get("/nodes", response_model=NodeListResponse)
async def list_nodes(
    type: Optional[str] = Query(None, description="Filter by node type"),
    search: Optional[str] = Query(None, description="Keyword search over node content"),
    bbox: Optional[str] = Query(None, description="Viewport filter: min_x,min_y,max_x,max_y"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    cursor: Optional[str] = Query(None, description="Opaque cursor for forward pagination"),
    session: GraphSession = Depends(get_session),
):
    parsed_bbox = _parse_bbox(bbox)
    nodes, total, next_cursor = await asyncio.to_thread(
        session.paginate_nodes,
        node_type=type,
        search=search,
        skip=skip,
        limit=limit,
        cursor=cursor,
        bbox=parsed_bbox,
    )
    return NodeListResponse(
        nodes=[_node_response(node) for node in nodes],
        total=total,
        skip=skip,
        limit=limit,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get("/node/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: str,
    session: GraphSession = Depends(get_session),
):
    node = await asyncio.to_thread(session.get_node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return _node_response(node)


@router.get("/node/{node_id}/neighbors", response_model=list[NeighborResponse])
async def get_neighbors(
    node_id: str,
    depth: int = Query(1, ge=1, le=5),
    session: GraphSession = Depends(get_session),
):
    neighbors = await asyncio.to_thread(session.get_neighbors, node_id, depth)
    return [
        NeighborResponse(
            id=neighbor.get("id", ""),
            type=neighbor.get("type", ""),
            content=neighbor.get("content", ""),
            relationship=neighbor.get("relationship", ""),
            weight=neighbor.get("weight", 1.0),
            hop=neighbor.get("hop", 1),
        )
        for neighbor in neighbors
    ]


@router.get("/edges", response_model=EdgeListResponse)
async def list_edges(
    type: Optional[str] = Query(None, description="Filter by edge type"),
    source: Optional[str] = Query(None, description="Filter by source node ID"),
    target: Optional[str] = Query(None, description="Filter by target node ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    cursor: Optional[str] = Query(None, description="Opaque cursor for forward pagination"),
    session: GraphSession = Depends(get_session),
):
    edges, total, next_cursor = await asyncio.to_thread(
        session.paginate_edges,
        edge_type=type,
        source=source,
        target=target,
        skip=skip,
        limit=limit,
        cursor=cursor,
    )
    return EdgeListResponse(
        edges=[_edge_response(edge) for edge in edges],
        total=total,
        skip=skip,
        limit=limit,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


class _PathAlgorithm(str, Enum):
    bfs = "bfs"
    dijkstra = "dijkstra"


@router.get("/node/{node_id}/path", response_model=PathResponse)
async def find_path(
    node_id: str,
    target: str = Query(..., description="Target node ID"),
    algorithm: _PathAlgorithm = Query(_PathAlgorithm.bfs, description="Algorithm: bfs or dijkstra"),
    session: GraphSession = Depends(get_session),
):
    path_finder = session.path_finder
    if path_finder is None:
        raise HTTPException(status_code=503, detail="PathFinder not available; KG extras may not be installed.")

    graph_dict = await asyncio.to_thread(session.build_graph_dict)
    path_fn = (
        path_finder.dijkstra_shortest_path
        if algorithm == _PathAlgorithm.dijkstra
        else path_finder.bfs_shortest_path
    )
    try:
        result = await asyncio.to_thread(path_fn, graph_dict, node_id, target)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No path found from '{node_id}' to '{target}': {exc}")

    path_nodes = result.get("path", []) if isinstance(result, dict) else (result or [])
    total_weight = result.get("total_weight", 0.0) if isinstance(result, dict) else 0.0
    edge_ids = await asyncio.to_thread(session.resolve_path_edge_ids, path_nodes)

    return PathResponse(
        source=node_id,
        target=target,
        algorithm=algorithm.value,
        path=path_nodes,
        edge_ids=edge_ids,
        total_weight=total_weight,
    )


@router.post("/search", response_model=SearchResultResponse)
async def search_nodes(
    body: SearchRequest,
    session: GraphSession = Depends(get_session),
):
    results = await asyncio.to_thread(session.search, body.query, body.limit, body.filters)
    items = [
        SearchResultItem(node=_node_response(result.get("node", {})), score=result.get("score", 0.0))
        for result in results
    ]
    return SearchResultResponse(results=items, total=len(items), query=body.query)


@router.get("/stats", response_model=GraphStatsResponse)
async def graph_stats(
    session: GraphSession = Depends(get_session),
):
    stats = await asyncio.to_thread(session.get_stats)
    return GraphStatsResponse(**stats)
