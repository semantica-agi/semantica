"""
Export tools — graph export (JSON/RDF/CSV/GraphML/Parquet) and provenance.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from ..schemas import EXPORT_GRAPH, GET_PROVENANCE
from ..session import get_graph, get_provenance_manager

log = logging.getLogger("semantica.mcp.tools.export")

_FORMAT_ALIASES: dict[str, str] = {
    "ttl": "turtle",
    "turtle": "turtle",
    "nt": "nt",
    "xml": "xml",
    "json-ld": "json-ld",
    "jsonld": "json-ld",
}


def handle_export_graph(args: dict) -> dict:
    """Export the knowledge graph to a structured format."""
    fmt = str(args.get("format", "json")).lower().strip()
    include_metadata = bool(args.get("include_metadata", True))
    try:
        graph = get_graph()

        if fmt == "json":
            nodes = list(graph.find_nodes())
            edges: list = []
            if hasattr(graph, "find_edges"):
                try:
                    edges = list(graph.find_edges())
                except Exception as exc:
                    log.debug("Failed to collect edges during JSON export; continuing with empty edges: %s", exc)
            payload: dict = {"nodes": nodes, "edges": edges}
            if include_metadata:
                payload["meta"] = {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "format": "json",
                }
            return {"format": "json", "data": payload}

        if fmt in ("csv",):
            nodes = list(graph.find_nodes())
            rows = []
            for n in nodes:
                rows.append(",".join([
                    str(n.get("id", "")),
                    str(n.get("label", "")),
                    str(n.get("type", "")),
                ]))
            header = "id,label,type"
            return {"format": "csv", "data": header + "\n" + "\n".join(rows)}

        if fmt in ("graphml",):
            # GraphMLExporter does not exist.  GraphExporter is the correct
            # class; it writes to a file and returns None, so we need a
            # temporary directory for safe cleanup regardless of success or
            # failure.
            #
            # export_knowledge_graph() is the required entry point because
            # to_kg_dict() returns {"entities": [...], "relationships": [...]}
            # while export() / _export_graphml() only consumes {"nodes": [...],
            # "edges": [...]}.  Calling export() directly therefore produces a
            # structurally-valid but empty GraphML document (zero nodes, zero
            # edges).  export_knowledge_graph() runs _convert_kg_to_graph()
            # first, which maps entities→nodes and relationships→edges.
            try:
                import tempfile
                from pathlib import Path
                from semantica.export import GraphExporter
                kg_dict = graph.to_kg_dict()
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir) / "export.graphml"
                    exporter = GraphExporter(format="graphml")
                    exporter.export_knowledge_graph(kg_dict, file_path=tmp_path)
                    data = tmp_path.read_text(encoding="utf-8")
                return {"format": "graphml", "data": data}
            except ImportError as exc:
                log.warning("GraphML export unavailable: %s", exc)
                return {"error": f"GraphML export unavailable: {exc}"}
            except Exception as exc:
                log.exception("GraphML export failed")
                return {"error": f"GraphML export failed: {exc}"}

        if fmt in ("parquet",):
            # ParquetExporter.export() writes to file(s) and returns None;
            # passing the ContextGraph object or using the return value as
            # data were both wrong.  export_knowledge_graph() is the correct
            # entry point for a full KG: it splits into _entities.parquet and
            # _relationships.parquet under a provided base path.  We read both
            # files and return them base64-encoded so the MCP client can
            # reconstruct them without a shared filesystem.
            try:
                import base64
                import tempfile
                from pathlib import Path
                try:
                    from semantica.export import ParquetExporter
                    exporter = ParquetExporter()
                except ImportError as exc:
                    log.warning("Parquet export unavailable: %s", exc)
                    return {"error": f"Parquet export unavailable (pyarrow not installed): {exc}"}
                kg_dict = graph.to_kg_dict()
                with tempfile.TemporaryDirectory() as tmpdir:
                    base_path = Path(tmpdir) / "kg"
                    exporter.export_knowledge_graph(kg_dict, base_path)
                    # Collect the produced files and return them as base64
                    files = {}
                    for p in sorted(Path(tmpdir).glob("*.parquet")):
                        files[p.name] = base64.b64encode(p.read_bytes()).decode("ascii")
                if not files:
                    return {"error": "Parquet export produced no files"}
                return {"format": "parquet", "data": files,
                        "encoding": "base64",
                        "note": "Each value is a base64-encoded Parquet file."}
            except Exception as exc:
                log.exception("Parquet export failed")
                return {"error": f"Parquet export failed: {exc}"}

        # RDF formats
        rdf_fmt = _FORMAT_ALIASES.get(fmt)
        if rdf_fmt:
            try:
                from semantica.export import RDFExporter
                # RDFExporter.export_to_rdf() expects the canonical kg dict
                # {"entities": [...], "relationships": [...]}, not a ContextGraph
                # object.  Convert before handing off; passing the raw graph
                # caused AttributeError: 'ContextGraph' object has no attribute
                # 'get' on every RDF format.
                rdf_str = RDFExporter().export_to_rdf(graph.to_kg_dict(), format=rdf_fmt)
                return {"format": rdf_fmt, "data": rdf_str}
            except Exception as exc:
                return {"error": f"RDF export failed: {exc}"}

        return {"error": f"Unsupported format '{fmt}'. Supported: json, csv, graphml, parquet, turtle, nt, xml, json-ld"}

    except Exception as exc:
        log.exception("export_graph failed")
        return {"error": str(exc)}


def handle_get_provenance(args: dict) -> dict:
    """Retrieve the provenance and lineage for a node.

    The advertised schema requires ``entity_id``. ``node_id`` is accepted as
    a compatibility alias for callers that discovered the old handler key
    (#1248).

    Provenance is read from the configured ``ProvenanceManager`` store
    (``SEMANTICA_PROVENANCE_DB`` / ``EXPLORER_PROVENANCE_DB``).  The response
    uses ``ok``, ``not_found``, ``not_configured``, ``invalid_store`` or
    ``integrity_failed``; arbitrary node metadata is never used as a
    provenance fallback (#2253).
    """
    # Prefer the public schema field; fall back to the legacy key.
    entity_id = str(args.get("entity_id") or "").strip()
    node_id = entity_id or str(args.get("node_id") or "").strip()
    if not node_id:
        return {"error": "entity_id is required", "provenance": []}
    include_metadata = bool(args.get("include_metadata", True))
    try:
        manager = get_provenance_manager()
        if manager is None:
            return {
                "node_id": node_id,
                "provenance": [],
                "count": 0,
                "lineage": [],
                "lineage_count": 0,
                "status": "not_configured",
            }

        # Read the lineage once and derive the current record from the same
        # snapshot. Reading get_provenance() separately could pair a stale
        # current record with a newer lineage during a concurrent update.
        lineage_result = manager.get_lineage(node_id) or {}
        entries = (
            lineage_result.get("lineage_chain")
            or lineage_result.get("entries")
            or []
        )
        current = []
        for entry in entries:
            if isinstance(entry, dict) and str(entry.get("entity_id")) == node_id:
                current = [entry]
                break

        # Compatibility fallback for managers whose lineage does not include
        # the queried entity. The real ProvenanceManager always includes it
        # first, so the normal path stays on one lineage snapshot.
        if not current:
            record = manager.get_provenance(node_id)
            if record is None:
                current = []
            elif isinstance(record, list):
                current = []
                for item in record:
                    if isinstance(item, dict):
                        current.append(item)
                        continue
                    to_dict = getattr(item, "to_dict", None)
                    if callable(to_dict):
                        converted = to_dict()
                        if isinstance(converted, dict):
                            current.append(converted)
            elif isinstance(record, dict):
                current = [record] if record else []
            else:
                to_dict = getattr(record, "to_dict", None)
                converted = to_dict() if callable(to_dict) else None
                current = [converted] if isinstance(converted, dict) else []

        integrity = lineage_result.get("integrity_verified")
        if integrity is False and (current or entries):
            status = "integrity_failed"
        elif current:
            status = "ok"
        else:
            status = "not_found"

        payload: dict = {
            "node_id": node_id,
            "provenance": current,
            "count": len(current),
            "lineage": entries,
            "lineage_count": len(entries),
            "status": status,
        }
        if entries:
            payload["integrity_verified"] = integrity
            payload["first_seen"] = lineage_result.get("first_seen")
            payload["last_updated"] = lineage_result.get("last_updated")
        if any(
            isinstance(item, dict) and item.get("invalidated")
            for item in current
        ):
            payload["invalidated"] = True

        if include_metadata:
            sources = set()
            source_documents = lineage_result.get("source_documents") or []
            if isinstance(source_documents, (list, tuple, set)):
                for source in source_documents:
                    if source:
                        sources.add(str(source))
            for item in current:
                if not isinstance(item, dict):
                    continue
                source = (
                    item.get("source_document")
                    or item.get("source")
                    or item.get("origin")
                )
                if source:
                    sources.add(str(source))
            payload["sources"] = sorted(sources)

        return payload
    except (OSError, sqlite3.DatabaseError, json.JSONDecodeError):
        log.warning("Configured provenance database is not readable")
        payload = {
            "node_id": node_id,
            "provenance": [],
            "count": 0,
            "lineage": [],
            "lineage_count": 0,
            "status": "invalid_store",
            "error": "Configured provenance database is not readable",
        }
        if include_metadata:
            payload["sources"] = []
        return payload
    except Exception as exc:
        log.exception("get_provenance failed")
        return {"error": str(exc), "provenance": []}


EXPORT_TOOLS = [
    {
        "name": "export_graph",
        "description": (
            "Export the Semantica knowledge graph to JSON, CSV, GraphML, Parquet, "
            "Turtle (RDF), N-Triples, RDF/XML, or JSON-LD."
        ),
        "inputSchema": EXPORT_GRAPH,
        "_handler": handle_export_graph,
    },
    {
        "name": "get_provenance",
        "description": (
            "Retrieve the latest provenance record and lineage for a node "
            "from the configured provenance database."
        ),
        "inputSchema": GET_PROVENANCE,
        "_handler": handle_get_provenance,
    },
]
