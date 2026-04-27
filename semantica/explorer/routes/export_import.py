"""
Import and export routes for graph datasets.
"""

import csv
import io
import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from ..dependencies import get_session
from ..schemas import DistanceExportRequest, ExportRequest, ImportResponse
from ..session import GraphSession

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Export / Import"])

_IMPORT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
# Only formats that the import handler actually parses.
# Do not add extensions here unless a corresponding parsing branch exists below.
_ALLOWED_IMPORT_EXTENSIONS = frozenset({".json", ".csv"})


def _import_response(nodes_added: int, edges_added: int, message: str = "Import successful") -> ImportResponse:
    return ImportResponse(
        status="success",
        message=message,
        nodes_added=nodes_added,
        edges_added=edges_added,
        nodes_imported=nodes_added,
        edges_imported=edges_added,
    )


@router.post("/api/import", response_model=ImportResponse)
async def import_file(
    file: UploadFile = File(...),
    session: GraphSession = Depends(get_session),
):
    import os as _os
    filename = (file.filename or "").lower()
    ext = _os.path.splitext(filename)[1]
    if ext not in _ALLOWED_IMPORT_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_IMPORT_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > _IMPORT_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {_IMPORT_MAX_BYTES // (1024 * 1024)} MB limit.",
        )

    if filename.endswith(".json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON file: {exc}") from exc

        if isinstance(data, list):
            if data and any(key in data[0] for key in {"source", "source_id", "target", "target_id", "START_ID", "END_ID"}):
                raw_nodes = []
                raw_edges = data
            else:
                raw_nodes = data
                raw_edges = []
        elif isinstance(data, dict):
            raw_nodes = data.get("nodes", data.get("entities", []))
            raw_edges = data.get("edges", data.get("relationships", []))
        else:
            raise HTTPException(status_code=422, detail="JSON import expects an object or array payload")

        nodes = []
        for raw_node in raw_nodes:
            if "properties" in raw_node:
                nodes.append(raw_node)
                continue
            metadata = raw_node.get("metadata", {}) or {}
            nodes.append(
                {
                    "id": str(raw_node.get("id", raw_node.get("_id", raw_node.get("node_id", "")))),
                    "type": raw_node.get("type", "entity"),
                    "properties": {
                        "content": raw_node.get("text", raw_node.get("content", raw_node.get("id", ""))),
                        **metadata,
                    },
                }
            )

        edges = []
        for raw_edge in raw_edges:
            source = raw_edge.get("source") or raw_edge.get("source_id") or raw_edge.get("start") or raw_edge.get("start_id") or raw_edge.get("START_ID")
            target = raw_edge.get("target") or raw_edge.get("target_id") or raw_edge.get("end") or raw_edge.get("end_id") or raw_edge.get("END_ID")
            if not source or not target:
                continue
            edge_properties = raw_edge.get("metadata", raw_edge.get("properties", {})) or {}
            edges.append(
                {
                    "id": raw_edge.get("id", raw_edge.get("edge_id")),
                    "familyId": raw_edge.get("familyId", raw_edge.get("family_id")),
                    "source_id": str(source),
                    "target_id": str(target),
                    "type": raw_edge.get("type", raw_edge.get("relationship", "related_to")),
                    "weight": float(raw_edge.get("weight", 1.0)),
                    "properties": edge_properties,
                    "valid_from": raw_edge.get("valid_from", edge_properties.get("valid_from")),
                    "valid_until": raw_edge.get("valid_until", edge_properties.get("valid_until")),
                }
            )

        nodes_added = session.add_nodes(nodes)
        edges_added = session.add_edges(edges)
        return _import_response(nodes_added, edges_added)

    if filename.endswith(".csv"):
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="CSV file must be UTF-8 encoded") from exc

        reader = csv.DictReader(io.StringIO(decoded))
        nodes = []
        edges = []
        for row in reader:
            source = row.get("source") or row.get("source_id") or row.get(":START_ID") or row.get("START_ID")
            target = row.get("target") or row.get("target_id") or row.get(":END_ID") or row.get("END_ID")
            node_id = row.get("id") or row.get("node_id") or row.get(":ID") or row.get("_id") or row.get("ID")

            if source and target:
                edge_props = {
                    key: value
                    for key, value in row.items()
                    if key not in {
                        "id",
                        "edge_id",
                        "familyId",
                        "family_id",
                        "source",
                        "source_id",
                        "target",
                        "target_id",
                        "type",
                        "relationship",
                        "weight",
                        ":START_ID",
                        "START_ID",
                        ":END_ID",
                        "END_ID",
                        ":TYPE",
                    }
                }
                edges.append(
                    {
                        "id": row.get("id") or row.get("edge_id"),
                        "familyId": row.get("familyId") or row.get("family_id"),
                        "source_id": str(source),
                        "target_id": str(target),
                        "type": row.get("type") or row.get("relationship") or row.get(":TYPE") or "related_to",
                        "weight": float(row.get("weight", 1.0) or 1.0),
                        "properties": edge_props,
                    }
                )
            elif node_id:
                node_props = {
                    key: value
                    for key, value in row.items()
                    if key not in {"id", "node_id", "type", "label", ":ID", "_id", "ID", ":LABEL"}
                }
                nodes.append(
                    {
                        "id": str(node_id),
                        "type": row.get("type") or row.get("label") or row.get(":LABEL") or "entity",
                        "properties": node_props,
                    }
                )

        if not nodes and not edges:
            raise HTTPException(
                status_code=422,
                detail="No valid nodes or edges could be parsed from the CSV payload.",
            )

        nodes_added = session.add_nodes(nodes)
        edges_added = session.add_edges(edges)
        return _import_response(nodes_added, edges_added)

    raise HTTPException(
        status_code=422,
        detail=f"Unsupported file type '{_os.path.splitext(filename)[1]}'. Allowed: {sorted(_ALLOWED_IMPORT_EXTENSIONS)}",
    )


@router.post("/api/export")
async def export_graph(
    body: ExportRequest,
    session: GraphSession = Depends(get_session),
):
    fmt = body.format.lower()
    graph_dict = session.build_graph_dict(body.node_ids)

    if fmt == "json":
        content = json.dumps(graph_dict, indent=2, default=str)
        media_type = "application/json"
        extension = "json"
    elif fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["kind", "id", "familyId", "type", "content", "source", "target", "weight"])
        for node in graph_dict.get("entities", []):
            writer.writerow(["node", node.get("id"), "", node.get("type"), node.get("text"), "", "", ""])
        for edge in graph_dict.get("relationships", []):
            writer.writerow([
                "edge",
                edge.get("id"),
                edge.get("familyId"),
                edge.get("type"),
                "",
                edge.get("source"),
                edge.get("target"),
                edge.get("metadata", {}).get("weight", edge.get("weight", "")),
            ])

        content = output.getvalue()
        media_type = "text/csv"
        extension = "csv"
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported export format '{fmt}'")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="semantica_export.{extension}"'},
    )


_DISTANCE_EXPORT_MAX_NODES = 200


@router.post("/api/export/distance-enriched")
async def export_distance_enriched(
    body: DistanceExportRequest,
    session: GraphSession = Depends(get_session),
):
    """FR-10 — Export pairwise distance metrics as CSV or JSONL for ML pipelines."""
    if body.node_subset and len(body.node_subset) > _DISTANCE_EXPORT_MAX_NODES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"node_subset exceeds limit: {len(body.node_subset)} nodes requested; "
                f"maximum is {_DISTANCE_EXPORT_MAX_NODES}."
            ),
        )

    import asyncio

    from ...export.distance_exporter import DistanceExporter

    exporter = DistanceExporter(session.graph)

    if body.format == "csv":
        content = await asyncio.to_thread(
            exporter.to_csv_string,
            include=body.include,
            node_subset=body.node_subset,
        )
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="distances.csv"'},
        )
    else:
        content = await asyncio.to_thread(
            exporter.to_jsonl_string,
            include=body.include,
            node_subset=body.node_subset,
        )
        return Response(
            content=content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="distances.jsonl"'},
        )
