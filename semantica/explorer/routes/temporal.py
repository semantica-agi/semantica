"""
Temporal routes for snapshots, diffs, and pattern detection.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, UTC
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..dependencies import get_session
from ..schemas import TemporalDiffResponse, TemporalPatternResponse
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
