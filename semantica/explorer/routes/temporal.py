"""
Temporal routes for snapshots, diffs, and pattern detection.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone, UTC
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..dependencies import get_session
from ..schemas import (
    DistanceEvent,
    DistanceHistoryResponse,
    DistanceSnapshot,
    TemporalDiffResponse,
    TemporalPatternResponse,
)
from ..session import GraphSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/temporal", tags=["Temporal"])


class TemporalSnapshotFastResponse(BaseModel):
    timestamp: str
    active_node_ids: List[str]
    active_node_count: int


class TemporalBoundsResponse(BaseModel):
    min: Optional[str] = None
    max: Optional[str] = None


def _parse_flexible_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d{4}", text):
        text = f"{text}-01-01"
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError) as exc:
        logger.warning("Malformed temporal value %r; treating node as always active (%s)", value, exc)
        return None


def _parse_query_dt(value: str) -> datetime:
    parsed = _parse_flexible_dt(value)
    if parsed is None:
        logger.warning("Could not parse timestamp %r; defaulting to utcnow()", value)
        return datetime.now(UTC).replace(tzinfo=None)
    return parsed


@router.get("/snapshot", response_model=TemporalSnapshotFastResponse)
async def temporal_snapshot(
    at: Optional[str] = Query(None, description="ISO datetime or year; defaults to now"),
    session: GraphSession = Depends(get_session),
):
    at_time = _parse_query_dt(at) if at else datetime.now(UTC).replace(tzinfo=None)
    active_nodes = await asyncio.to_thread(session.get_active_nodes, at_time=at_time)
    active_ids = [node.get("id") for node in active_nodes if node.get("id")]
    return TemporalSnapshotFastResponse(
        timestamp=at_time.isoformat(),
        active_node_ids=active_ids,
        active_node_count=len(active_ids),
    )


@router.get("/diff", response_model=TemporalDiffResponse)
async def temporal_diff(
    from_time: str = Query(..., description="Start ISO datetime"),
    to_time: str = Query(..., description="End ISO datetime"),
    session: GraphSession = Depends(get_session),
):
    start = _parse_query_dt(from_time)
    end = _parse_query_dt(to_time)

    active_start, active_end = await asyncio.gather(
        asyncio.to_thread(session.get_active_nodes, at_time=start),
        asyncio.to_thread(session.get_active_nodes, at_time=end),
    )

    start_ids = {node.get("id") for node in active_start}
    end_ids = {node.get("id") for node in active_end}
    return TemporalDiffResponse(
        from_time=start.isoformat(),
        to_time=end.isoformat(),
        added_nodes=sorted(end_ids - start_ids),
        removed_nodes=sorted(start_ids - end_ids),
    )


@router.get("/patterns", response_model=TemporalPatternResponse)
async def temporal_patterns(
    session: GraphSession = Depends(get_session),
):
    try:
        from ...kg import TemporalPatternDetector

        detector = TemporalPatternDetector()
        graph_dict = await asyncio.to_thread(session.build_graph_dict)
        patterns = await asyncio.to_thread(detector.detect_temporal_patterns, graph_dict)
        if isinstance(patterns, dict):
            patterns = patterns.get("patterns", [])
        return TemporalPatternResponse(patterns=patterns if isinstance(patterns, list) else [])
    except ImportError:
        return TemporalPatternResponse(patterns=[])
    except Exception as exc:
        logger.warning("temporal_patterns failed: %s", exc, exc_info=True)
        return TemporalPatternResponse(patterns=[])


@router.get("/bounds", response_model=TemporalBoundsResponse)
async def temporal_bounds(
    session: GraphSession = Depends(get_session),
):
    bounds = await asyncio.to_thread(session.get_temporal_bounds)
    return TemporalBoundsResponse(**bounds)


@router.get("/distance-history", response_model=DistanceHistoryResponse)
async def distance_history(
    source: str = Query(..., description="Source node ID"),
    target: str = Query(..., description="Target node ID"),
    metric: str = Query("hops", description="Distance metric: hops | weighted"),
    session: GraphSession = Depends(get_session),
):
    """FR-9 — Track distance changes between two nodes across temporal snapshots."""
    from ...utils.helpers import classify_path_distance

    bounds = await asyncio.to_thread(session.get_temporal_bounds)
    min_bound_str = bounds.get("min")
    max_bound_str = bounds.get("max")

    if not min_bound_str or not max_bound_str:
        # No temporal data — return current-only snapshot
        pf = session.path_finder
        hop_count: Optional[int] = None
        if pf is not None:
            try:
                graph_dict = await asyncio.to_thread(session.build_graph_dict)
                path_fn = pf.dijkstra_shortest_path if metric == "weighted" else pf.bfs_shortest_path
                result = await asyncio.to_thread(path_fn, graph_dict, source, target)
                path_nodes = result.get("path", []) if isinstance(result, dict) else (result or [])
                hop_count = len(path_nodes) - 1 if path_nodes else None
            except Exception:
                pass
        now = datetime.now(UTC).replace(tzinfo=None)
        snap = DistanceSnapshot(
            timestamp=now,
            hop_count=hop_count,
            distance_band=classify_path_distance(hop_count) if hop_count is not None else "distant",
        )
        return DistanceHistoryResponse(
            source_id=source, target_id=target, metric=metric,
            history=[snap], events=[],
        )

    min_bound = _parse_query_dt(min_bound_str)
    max_bound = _parse_query_dt(max_bound_str)

    # Sample up to 10 snapshots evenly between min and max
    total_seconds = max(1, int((max_bound - min_bound).total_seconds()))
    step = total_seconds / min(10, total_seconds)
    sample_times = [
        min_bound + timedelta(seconds=int(i * step))
        for i in range(11)
    ]

    pf = session.path_finder
    history: List[DistanceSnapshot] = []
    events: List[DistanceEvent] = []
    prev_hop: Optional[int] = None

    for sample_time in sample_times:
        active_nodes = await asyncio.to_thread(session.get_active_nodes, at_time=sample_time)
        active_ids = {n.get("id") for n in active_nodes if n.get("id")}
        hop_count = None
        if source in active_ids and target in active_ids and pf is not None:
            try:
                graph_dict = await asyncio.to_thread(
                    session.build_graph_dict, list(active_ids)
                )
                path_fn = pf.dijkstra_shortest_path if metric == "weighted" else pf.bfs_shortest_path
                result = await asyncio.to_thread(path_fn, graph_dict, source, target)
                path_nodes = result.get("path", []) if isinstance(result, dict) else (result or [])
                hop_count = len(path_nodes) - 1 if path_nodes else None
            except Exception:
                pass

        band = classify_path_distance(hop_count) if hop_count is not None else "distant"
        snap = DistanceSnapshot(timestamp=sample_time, hop_count=hop_count, distance_band=band)
        history.append(snap)

        # Detect events relative to previous snapshot
        if prev_hop is not None or hop_count is not None:
            if prev_hop is None and hop_count is not None:
                events.append(DistanceEvent(
                    timestamp=sample_time,
                    event_type="reconnected",
                    hop_count_before=None,
                    hop_count_after=hop_count,
                    description=f"Nodes reconnected at {hop_count} hop(s) on {sample_time.date()}.",
                ))
            elif prev_hop is not None and hop_count is None:
                events.append(DistanceEvent(
                    timestamp=sample_time,
                    event_type="disconnected",
                    hop_count_before=prev_hop,
                    hop_count_after=None,
                    description=f"Nodes became unreachable on {sample_time.date()}.",
                ))
            elif prev_hop is not None and hop_count is not None and hop_count != prev_hop:
                etype = "convergence" if hop_count < prev_hop else "divergence"
                events.append(DistanceEvent(
                    timestamp=sample_time,
                    event_type=etype,
                    hop_count_before=prev_hop,
                    hop_count_after=hop_count,
                    description=(
                        f"Nodes {etype}d from {prev_hop} hops to {hop_count} hops "
                        f"on {sample_time.date()}."
                    ),
                ))
        prev_hop = hop_count

    return DistanceHistoryResponse(
        source_id=source, target_id=target, metric=metric,
        history=history, events=events,
    )
