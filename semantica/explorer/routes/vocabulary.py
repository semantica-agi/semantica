"""
Vocabulary routes for SKOS scheme discovery, hierarchy browsing, and import.
"""

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile

from ..dependencies import get_session
from ..schemas import ConceptNode, ConceptSummary, VocabularyImportResponse, VocabularyScheme
from ..session import GraphSession
from ..utils.rdf_parser import parse_skos_file

router = APIRouter(prefix="/api/vocabulary", tags=["Vocabulary"])

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_EXTENSIONS = frozenset({".ttl", ".rdf", ".owl", ".xml", ".jsonld", ".json-ld", ".json"})


def _concept_summary(node: dict, scheme_uri: Optional[str] = None, parent_uri: Optional[str] = None) -> ConceptSummary:
    properties = node.get("properties", {})
    alt_labels = properties.get("alt_labels") or []
    if isinstance(alt_labels, str):
        alt_labels = [alt_labels]
    return ConceptSummary(
        uri=node.get("id", ""),
        pref_label=properties.get("pref_label") or properties.get("content", node.get("content", node.get("id", ""))),
        alt_labels=list(alt_labels),
        description=properties.get("description"),
        notation=properties.get("notation"),
        scheme_uri=scheme_uri,
        parent_uri=parent_uri,
    )


def _collect_scheme_members(edges: List[dict], scheme_uri: str) -> set[str]:
    members: set[str] = set()
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type")
        if target == scheme_uri and edge_type in {"skos:inScheme", "skos:topConceptOf"}:
            members.add(source)
        elif source == scheme_uri and edge_type == "skos:hasTopConcept":
            members.add(target)
    return members


def _collect_parent_map(member_ids: set[str], edges: List[dict]) -> Dict[str, str]:
    parent_by_child: Dict[str, str] = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type")
        if source not in member_ids or target not in member_ids:
            continue
        if edge_type == "skos:broader":
            parent_by_child.setdefault(source, target)
        elif edge_type == "skos:narrower":
            parent_by_child.setdefault(target, source)
    return parent_by_child


def _build_hierarchy(concepts: Dict[str, ConceptSummary], parent_by_child: Dict[str, str]) -> List[ConceptNode]:
    children_by_parent: Dict[str, List[str]] = defaultdict(list)
    for child_uri, parent_uri in parent_by_child.items():
        if child_uri != parent_uri:
            children_by_parent[parent_uri].append(child_uri)

    def attach(uri: str, trail: set[str]) -> ConceptNode:
        concept = concepts[uri]
        child_nodes = [
            attach(child_uri, trail | {uri})
            for child_uri in sorted(children_by_parent.get(uri, []))
            if child_uri not in trail
        ]
        return ConceptNode(
            uri=concept.uri,
            pref_label=concept.pref_label,
            alt_labels=concept.alt_labels,
            description=concept.description,
            notation=concept.notation,
            scheme_uri=concept.scheme_uri,
            parent_uri=concept.parent_uri,
            children=child_nodes or None,
        )

    root_ids = [uri for uri in sorted(concepts.keys()) if uri not in parent_by_child]
    if not root_ids:
        root_ids = sorted(concepts.keys())
    return [attach(uri, {uri}) for uri in root_ids]


@router.get("/schemes", response_model=List[VocabularyScheme])
async def list_schemes(
    session: GraphSession = Depends(get_session),
):
    nodes, _ = await asyncio.to_thread(
        session.get_nodes,
        node_type="skos:ConceptScheme",
        skip=0,
        limit=999_999,
    )
    return [
        VocabularyScheme(
            uri=node.get("id", ""),
            label=node.get("properties", {}).get("content", node.get("content", node.get("id", ""))),
            description=node.get("properties", {}).get("description"),
        )
        for node in nodes
    ]


@router.get("/concepts", response_model=List[ConceptSummary])
async def list_concepts(
    scheme: str = Query(..., description="ConceptScheme URI"),
    search: Optional[str] = Query(None, description="Filter concepts by label or metadata"),
    session: GraphSession = Depends(get_session),
):
    nodes, _ = await asyncio.to_thread(
        session.get_nodes,
        node_type="skos:Concept",
        search=search,
        skip=0,
        limit=999_999,
    )
    edges, _ = await asyncio.to_thread(session.get_edges, skip=0, limit=999_999)

    member_ids = _collect_scheme_members(edges, scheme)
    parent_by_child = _collect_parent_map(member_ids, edges)

    concepts = []
    for node in nodes:
        node_id = node.get("id")
        if node_id not in member_ids:
            continue
        concepts.append(_concept_summary(node, scheme_uri=scheme, parent_uri=parent_by_child.get(node_id)))

    return sorted(concepts, key=lambda concept: (concept.pref_label.lower(), concept.uri))


@router.get("/hierarchy", response_model=List[ConceptNode])
async def get_hierarchy(
    scheme: str = Query(..., description="ConceptScheme URI"),
    session: GraphSession = Depends(get_session),
):
    nodes, _ = await asyncio.to_thread(
        session.get_nodes,
        node_type="skos:Concept",
        skip=0,
        limit=999_999,
    )
    edges, _ = await asyncio.to_thread(session.get_edges, skip=0, limit=999_999)

    member_ids = _collect_scheme_members(edges, scheme)
    parent_by_child = _collect_parent_map(member_ids, edges)

    concepts: Dict[str, ConceptSummary] = {}
    for node in nodes:
        node_id = node.get("id")
        if node_id not in member_ids:
            continue
        concepts[node_id] = _concept_summary(
            node,
            scheme_uri=scheme,
            parent_uri=parent_by_child.get(node_id),
        )

    return _build_hierarchy(concepts, parent_by_child)


@router.post("/import", response_model=VocabularyImportResponse)
async def import_vocabulary(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    format: Optional[str] = Form(None),
    session: GraphSession = Depends(get_session),
):
    if file is None and not text:
        raise HTTPException(status_code=422, detail="Provide either a vocabulary file or raw RDF text.")

    filename = file.filename if file else None
    if file is not None:
        if filename:
            import os as _os
            ext = _os.path.splitext(filename.lower())[1]
            if ext not in _ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
                )
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Upload exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
    else:
        encoded = text.encode("utf-8")
        if len(encoded) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Text payload exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
        content = encoded

    parse_format = (format or "").strip().lower() or None
    if parse_format is None:
        if filename:
            lower_name = filename.lower()
            if lower_name.endswith((".rdf", ".owl", ".xml")):
                parse_format = "xml"
            elif lower_name.endswith((".jsonld", ".json-ld", ".json")):
                parse_format = "json-ld"
            else:
                parse_format = "turtle"
        else:
            parse_format = "turtle"

    try:
        nodes, edges = await asyncio.to_thread(parse_skos_file, content, parse_format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    nodes_added = await asyncio.to_thread(session.add_nodes, nodes)
    edges_added = await asyncio.to_thread(session.add_edges, edges)

    return VocabularyImportResponse(
        status="success",
        filename=filename,
        nodes_added=nodes_added,
        edges_added=edges_added,
        format=parse_format,
    )
