"""
Analytics routes for graph metrics and validation.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_session
from ..schemas import AnalyticsResponse, ValidationIssue, ValidationReportResponse
from ..session import GraphSession

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    metrics: Optional[str] = Query(
        None,
        description="Comma-separated metrics to compute: centrality,community,connectivity",
    ),
    session: GraphSession = Depends(get_session),
):
    requested = set((metrics or "centrality,community,connectivity").split(","))
    graph_dict = await asyncio.to_thread(session.build_graph_dict)
    result: dict = {}

    if "centrality" in requested and session.centrality is not None:
        try:
            result["centrality"] = await asyncio.to_thread(
                session.centrality.calculate_degree_centrality,
                graph_dict,
            )
        except Exception as exc:
            result["centrality"] = {"error": str(exc)}

    if "community" in requested and session.community is not None:
        try:
            result["community"] = await asyncio.to_thread(
                session.community.detect_communities,
                graph_dict,
            )
        except Exception as exc:
            result["community"] = {"error": str(exc)}

    if "connectivity" in requested and session.connectivity is not None:
        try:
            result["connectivity"] = await asyncio.to_thread(
                session.connectivity.analyze_connectivity,
                graph_dict,
            )
        except Exception as exc:
            result["connectivity"] = {"error": str(exc)}

    return AnalyticsResponse(**result)


@router.get("/validation", response_model=ValidationReportResponse)
async def validate_graph(
    session: GraphSession = Depends(get_session),
):
    validator = session.validator
    if validator is None:
        return ValidationReportResponse(valid=True, error_count=0, warning_count=0, issues=[])

    graph_dict = await asyncio.to_thread(session.build_graph_dict)
    try:
        report = await asyncio.to_thread(validator.validate, graph_dict)
    except Exception as exc:
        return ValidationReportResponse(
            valid=False,
            error_count=1,
            issues=[ValidationIssue(severity="error", message=str(exc))],
        )

    if isinstance(report, dict):
        valid = report.get("valid", True)
        errors = report.get("errors", [])
        warnings = report.get("warnings", [])
    else:
        valid = getattr(report, "valid", True)
        errors = getattr(report, "errors", [])
        warnings = getattr(report, "warnings", [])

    issues = [ValidationIssue(severity="error", message=str(error)) for error in (errors or [])]
    issues.extend(ValidationIssue(severity="warning", message=str(warning)) for warning in (warnings or []))

    return ValidationReportResponse(
        valid=valid,
        error_count=len(errors or []),
        warning_count=len(warnings or []),
        issues=issues,
    )
