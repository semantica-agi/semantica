"""
SPARQL routes backed by an in-memory rdflib projection of the current graph.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional

import rdflib
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_session
from ..session import GraphSession

router = APIRouter(prefix="/api/sparql", tags=["Power User Tools"])

_ALLOWED_QUERY_TYPES = re.compile(
    r"^\s*(SELECT|ASK|CONSTRUCT|DESCRIBE)\b",
    re.IGNORECASE,
)


def _is_read_only_query(query: str) -> bool:
    """Return True only for SELECT / ASK / CONSTRUCT / DESCRIBE queries."""
    return bool(_ALLOWED_QUERY_TYPES.match(query))


class SparqlRequest(BaseModel):
    query: str


class SparqlResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    total: int
    truncated: bool = False  # True when _SPARQL_MAX_ROWS was hit
    error: Optional[str] = None
    error_line: Optional[int] = None
    error_column: Optional[int] = None


NS = rdflib.Namespace("http://semantica.local/entity/")
PROP = rdflib.Namespace("http://semantica.local/prop/")


def _build_rdflib_graph(session: GraphSession) -> rdflib.Graph:
    graph = rdflib.Graph()
    graph.bind("ent", NS)
    graph.bind("prop", PROP)

    nodes, _ = session.get_nodes(skip=0, limit=999_999)
    edges, _ = session.get_edges(skip=0, limit=999_999)

    for node in nodes:
        subject = NS[str(node.get("id", ""))]
        node_type = node.get("type", "Entity")
        graph.add((subject, rdflib.RDF.type, NS[node_type]))

        content = node.get("content", "")
        if content:
            graph.add((subject, rdflib.RDFS.label, rdflib.Literal(content)))

        for key, value in node.get("properties", {}).items():
            if key in {"content", "valid_from", "valid_until"}:
                continue
            graph.add((subject, PROP[key], rdflib.Literal(value)))

    for edge in edges:
        source = NS[str(edge.get("source", ""))]
        target = NS[str(edge.get("target", ""))]
        relationship = edge.get("type", "relatedTo")
        graph.add((source, PROP[relationship], target))

    return graph


_SPARQL_MAX_ROWS = 5_000     # hard cap on returned rows
_SPARQL_TIMEOUT_S = 30       # seconds before abandoning the await
_SPARQL_MAX_CONCURRENT = 4   # semaphore: max simultaneous executions

# Semaphore caps how many graph.query calls run concurrently so that
# timed-out threads (which keep running in the pool) cannot crowd out
# other requests by exhausting the default ThreadPoolExecutor workers.
_sparql_semaphore = asyncio.Semaphore(_SPARQL_MAX_CONCURRENT)


@router.post("", response_model=SparqlResponse)
async def execute_sparql(
    req: SparqlRequest,
    session: GraphSession = Depends(get_session),
):
    if not _is_read_only_query(req.query):
        return SparqlResponse(
            columns=[],
            rows=[],
            total=0,
            error="Only SELECT, ASK, CONSTRUCT, and DESCRIBE queries are permitted.",
        )

    graph = await asyncio.to_thread(_build_rdflib_graph, session)

    async with _sparql_semaphore:
        try:
            query_results = await asyncio.wait_for(
                asyncio.to_thread(graph.query, req.query),
                timeout=_SPARQL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            return SparqlResponse(
                columns=[],
                rows=[],
                total=0,
                error=f"Query timed out after {_SPARQL_TIMEOUT_S} seconds.",
            )
        except Exception as exc:
            error = str(exc)
            line_match = re.search(r"line[\s:]+(\d+)", error, re.IGNORECASE)
            column_match = re.search(r"col(?:umn)?[\s:]+(\d+)", error, re.IGNORECASE)
            return SparqlResponse(
                columns=[],
                rows=[],
                total=0,
                error=error,
                error_line=int(line_match.group(1)) if line_match else None,
                error_column=int(column_match.group(1)) if column_match else None,
            )

    columns = [str(var) for var in query_results.vars] if query_results.vars else []
    rows: List[Dict[str, Any]] = []
    for row in query_results:
        if len(rows) >= _SPARQL_MAX_ROWS:
            break
        row_data = {}
        for index, column in enumerate(columns):
            value = row[index]
            row_data[column] = str(value) if value is not None else None
        rows.append(row_data)

    truncated = len(rows) == _SPARQL_MAX_ROWS
    return SparqlResponse(columns=columns, rows=rows, total=len(rows), truncated=truncated)
