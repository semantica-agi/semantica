"""
Ontology Hub routes: registry, URL/file loading, preview, creation, entity search, and SKOS.
"""

import os
import asyncio
import logging
import re
import socket
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Tuple, Union
from typing_extensions import Literal

import rdflib
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..session import GraphSession
from ..dependencies import get_session
from ..utils.rdf_parser import _safe_parse_rdf
from ...utils.exceptions import ProcessingError, ValidationError

# RDF imports
from rdflib import RDF, RDFS, OWL, SKOS
try:
    from rdflib.namespace import DCT, DC
except ImportError:
    # Fallback if DCT/DC not available
    DCT = None
    DC = None

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/ontology", tags=["ontology"])

_MAX_FETCH_BYTES = 20 * 1024 * 1024  # 20 MB

_CLASS_TYPES = frozenset({
    "owl:Class", "rdfs:Class",
    "http://www.w3.org/2002/07/owl#Class",
    "http://www.w3.org/2000/01/rdf-schema#Class",
})
_PROPERTY_TYPES = frozenset({
    "owl:ObjectProperty", "owl:DatatypeProperty", "owl:AnnotationProperty",
    "rdfs:Property",
    "http://www.w3.org/2002/07/owl#ObjectProperty",
    "http://www.w3.org/2002/07/owl#DatatypeProperty",
    "http://www.w3.org/2002/07/owl#AnnotationProperty",
})
_INDIVIDUAL_TYPES = frozenset({
    "owl:NamedIndividual",
    "http://www.w3.org/2002/07/owl#NamedIndividual",
})
_CONCEPT_TYPES = frozenset({
    "skos:Concept",
    "http://www.w3.org/2004/02/skos/core#Concept",
})
_SCHEME_TYPES = frozenset({
    "skos:ConceptScheme",
    "http://www.w3.org/2004/02/skos/core#ConceptScheme",
})
_ONTOLOGY_TYPES = frozenset({
    "owl:Ontology",
    "http://www.w3.org/2002/07/owl#Ontology",
}) | _SCHEME_TYPES

_SEARCHABLE_TYPES = _CLASS_TYPES | _PROPERTY_TYPES | _INDIVIDUAL_TYPES | _CONCEPT_TYPES | _SCHEME_TYPES

_URI_PREFIX_MAP = {
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "http://purl.org/dc/terms/": "dcterms:",
    "http://purl.org/dc/elements/1.1/": "dc:",
    "http://schema.org/": "schema:",
    "http://www.w3.org/ns/shacl#": "sh:",
}

_FORMAT_ALIASES: Dict[str, str] = {
    "ttl": "turtle",
    "rdf": "xml",
    "owl": "xml",
    "jsonld": "json-ld",
    "json": "json-ld",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OntologyEntry(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    format: str = "unknown"
    status: Literal["published", "draft", "external"] = "external"
    source_url: Optional[str] = None
    version: Optional[str] = None
    class_count: int = 0
    concept_count: int = 0
    property_count: int = 0
    loaded_at: str = ""
    enabled: bool = True
    tags: List[str] = Field(default_factory=list)


class OntologyPreview(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    namespace: Optional[str] = None
    version: Optional[str] = None
    license: Optional[str] = None
    format: str
    estimated_triples: int = 0
    source_url: Optional[str] = None


class LoadOntologyRequest(BaseModel):
    url: Optional[str] = None
    content: Optional[str] = None
    format: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PreviewOntologyRequest(BaseModel):
    url: Optional[str] = None
    content: Optional[str] = None
    format: Optional[str] = None


class CreateOntologyRequest(BaseModel):
    mode: Literal["scratch", "data", "text"] = "scratch"
    namespace: str
    name: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    sample_data: Optional[str] = None
    schema_text: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class OntologySearchResult(BaseModel):
    uri: str
    label: str
    type: str
    entity_type: str
    definition: Optional[str] = None
    source_ontology: Optional[str] = None
    namespace_prefix: Optional[str] = None


class EntityDetailResponse(BaseModel):
    uri: str
    label: str
    type: str
    entity_type: str
    definition: Optional[str] = None
    source_ontology: Optional[str] = None
    superclasses: List[str] = Field(default_factory=list)
    subclasses: List[str] = Field(default_factory=list)
    domain: List[str] = Field(default_factory=list)
    range: List[str] = Field(default_factory=list)
    instance_count: int = 0
    properties: Dict[str, Any] = Field(default_factory=dict)


class SKOSScheme(BaseModel):
    uri: str
    title: str
    description: Optional[str] = None
    concept_count: int = 0


class SKOSConceptDetail(BaseModel):
    uri: str
    pref_label: str
    alt_labels: List[str] = Field(default_factory=list)
    hidden_labels: List[str] = Field(default_factory=list)
    definition: Optional[str] = None
    scope_note: Optional[str] = None
    editorial_note: Optional[str] = None
    broader: List[str] = Field(default_factory=list)
    narrower: List[str] = Field(default_factory=list)
    related: List[str] = Field(default_factory=list)
    exact_match: List[str] = Field(default_factory=list)
    close_match: List[str] = Field(default_factory=list)
    broad_match: List[str] = Field(default_factory=list)
    narrow_match: List[str] = Field(default_factory=list)
    scheme_uri: Optional[str] = None


class SKOSConceptSearchRequest(BaseModel):
    query: str
    scheme_uri: Optional[str] = None


class LoadOntologyResponse(BaseModel):
    status: str = "success"
    uri: str
    name: str
    nodes_added: int = 0
    edges_added: int = 0
    format: str = "unknown"


class ToggleResponse(BaseModel):
    uri: str
    enabled: bool


class RefreshResponse(BaseModel):
    status: str = "success"
    uri: str
    nodes_added: int = 0
    edges_added: int = 0


# ---------------------------------------------------------------------------
# Draft, Proposal, and Version Schemas
# ---------------------------------------------------------------------------

class DraftDiff(BaseModel):
    added_classes: List[str] = Field(default_factory=list)
    removed_classes: List[str] = Field(default_factory=list)
    modified_classes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    added_properties: List[str] = Field(default_factory=list)
    removed_properties: List[str] = Field(default_factory=list)
    modified_properties: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    added_restrictions: List[Dict[str, Any]] = Field(default_factory=list)
    removed_restrictions: List[Dict[str, Any]] = Field(default_factory=list)
    added_axioms: List[Dict[str, Any]] = Field(default_factory=list)
    removed_axioms: List[Dict[str, Any]] = Field(default_factory=list)
    annotation_changes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class DraftRequest(BaseModel):
    ontology_uri: str
    diff: DraftDiff
    author: str
    summary: Optional[str] = None
    timestamp: Optional[str] = None


class DraftResponse(BaseModel):
    draft_id: str
    ontology_uri: str
    diff: DraftDiff
    author: str
    summary: Optional[str] = None
    created_at: str
    updated_at: str


class ProposalState(BaseModel):
    state: Literal["draft", "proposed", "approved", "published", "rejected"]


class ProposalRequest(BaseModel):
    draft_id: str
    ontology_uri: str
    summary: str
    reviewer: Optional[str] = None


class ProposalResponse(BaseModel):
    proposal_id: str
    draft_id: str
    ontology_uri: str
    summary: str
    author: str
    reviewer: Optional[str] = None
    state: Literal["draft", "proposed", "approved", "published", "rejected"]
    impact_analysis: Dict[str, Any] = Field(default_factory=dict)
    shacl_validation: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    comments: List[Dict[str, Any]] = Field(default_factory=list)


class CommentRequest(BaseModel):
    element_uri: str
    text: str
    author: str


class VersionEntry(BaseModel):
    version_id: str
    ontology_uri: str
    state: Literal["draft", "published"]
    author: str
    date: str
    diff_summary: Dict[str, Any] = Field(default_factory=dict)


class VersionCompareRequest(BaseModel):
    version1: str
    version2: str


class VersionCompareResponse(BaseModel):
    version1: str
    version2: str
    metadata_changes: Dict[str, Any] = Field(default_factory=dict)
    class_changes: Dict[str, Any] = Field(default_factory=dict)
    property_changes: Dict[str, Any] = Field(default_factory=dict)
    restriction_changes: Dict[str, Any] = Field(default_factory=dict)
    axiom_changes: Dict[str, Any] = Field(default_factory=dict)


class AlignmentRequest(BaseModel):
    source_uri: str
    target_uri: str
    predicate: str


class AlignmentResponse(BaseModel):
    source: str
    predicate: str
    target: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_registry(request: Request) -> Dict[str, OntologyEntry]:
    if not hasattr(request.app.state, "ontology_registry"):
        request.app.state.ontology_registry = {}
    return request.app.state.ontology_registry


def _get_drafts(request: Request) -> Dict[str, DraftResponse]:
    if not hasattr(request.app.state, "ontology_drafts"):
        request.app.state.ontology_drafts = {}
    return request.app.state.ontology_drafts


def _get_proposals(request: Request) -> Dict[str, ProposalResponse]:
    if not hasattr(request.app.state, "ontology_proposals"):
        request.app.state.ontology_proposals = {}
    return request.app.state.ontology_proposals


def _get_versions(request: Request) -> Dict[str, List[VersionEntry]]:
    if not hasattr(request.app.state, "ontology_versions"):
        request.app.state.ontology_versions = {}
    return request.app.state.ontology_versions


def _uri_to_prefix(uri: str) -> str:
    for base, prefix in _URI_PREFIX_MAP.items():
        if uri.startswith(base):
            return prefix + uri[len(base):]
    return uri


def _classify_node_type(node_type: str) -> str:
    if node_type in _CLASS_TYPES:
        return "class"
    if node_type in _PROPERTY_TYPES:
        return "property"
    if node_type in _INDIVIDUAL_TYPES:
        return "individual"
    if node_type in _CONCEPT_TYPES:
        return "concept"
    if node_type in _SCHEME_TYPES:
        return "scheme"
    if node_type in _ONTOLOGY_TYPES:
        return "ontology"
    return "unknown"


def _node_label(node: Dict[str, Any]) -> str:
    props = node.get("properties", {})
    return (
        props.get("pref_label")
        or props.get("rdfs:label")
        or props.get("skos:prefLabel")
        or props.get("label")
        or props.get("content")
        or node.get("content", "")
        or node.get("id", "")
    )


def _convert_ontology_to_graph(ontology_dict: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Convert OntologyIngestor ontology dict to graph nodes and edges."""
    nodes = []
    edges = []
    
    # Add ontology node
    ontology_uri = ontology_dict.get("uri", f"temp:{uuid.uuid4().hex[:12]}")
    nodes.append({
        "id": ontology_uri,
        "type": "owl:Ontology",
        "content": ontology_dict.get("name", "Ontology"),
        "properties": {
            "rdfs:label": ontology_dict.get("name", "Ontology"),
            "rdfs:comment": ontology_dict.get("description", ""),
            "uri": ontology_uri,
        },
    })
    
    # Add class nodes
    for cls in ontology_dict.get("classes", []):
        cls_uri = cls.get("uri", f"temp:class:{uuid.uuid4().hex[:12]}")
        node = {
            "id": cls_uri,
            "type": "owl:Class",
            "content": cls.get("name", cls.get("label", "")),
            "properties": {
                "rdfs:label": cls.get("label", cls.get("name", "")),
                "rdfs:comment": cls.get("description", ""),
                "uri": cls_uri,
            },
        }
        nodes.append(node)
        
        # Add subclass edges
        for parent in cls.get("parents", []):
            edges.append({
                "source": cls_uri,
                "target": parent,
                "type": "rdfs:subClassOf",
                "weight": 1.0,
            })
    
    # Add property nodes and edges
    for prop in ontology_dict.get("properties", []):
        prop_uri = prop.get("uri", f"temp:prop:{uuid.uuid4().hex[:12]}")
        node = {
            "id": prop_uri,
            "type": f"owl:{prop.get('type', 'Object').title()}Property",
            "content": prop.get("name", prop.get("label", "")),
            "properties": {
                "rdfs:label": prop.get("label", prop.get("name", "")),
                "rdfs:comment": prop.get("description", ""),
                "uri": prop_uri,
            },
        }
        nodes.append(node)
        
        # Add domain and range edges
        if prop.get("domain"):
            edges.append({
                "source": prop_uri,
                "target": prop["domain"],
                "type": "rdfs:domain",
                "weight": 1.0,
            })
        if prop.get("range"):
            edges.append({
                "source": prop_uri,
                "target": prop["range"],
                "type": "rdfs:range",
                "weight": 1.0,
            })
    
    return nodes, edges


def _extract_namespace(uri: str) -> Optional[str]:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"
    return None


def _detect_format(content: str) -> str:
    stripped = content.strip()[:500]
    if stripped.startswith("{") or stripped.startswith("["):
        return "json-ld"
    if stripped.startswith("<"):
        return "xml"
    if "@prefix" in stripped or "@base" in stripped:
        return "turtle"
    # N-Triples blank-node subject: "_:word <predicate-uri> ..."
    # URI-subject N-Triples ("<uri> <uri>") are already caught by the XML
    # branch above, so only the blank-node form needs to be checked here.
    # Plain string ops avoid the polynomial regex that CodeQL flags (py/polynomial-redos).
    if stripped.startswith("_:") and " <" in stripped:
        return "nt"
    return "turtle"


def _normalize_format(fmt: Optional[str]) -> str:
    if not fmt:
        return "turtle"
    lower = fmt.strip().lower()
    return _FORMAT_ALIASES.get(lower, lower)


def _validate_fetch_url(url: str) -> None:
    """Reject non-HTTP(S) schemes and private/loopback/link-local targets."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="Only http and https URLs are allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="Invalid URL: missing hostname.")
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail=f"Cannot resolve hostname '{hostname}': {exc}") from exc
    for _family, _type, _proto, _canonname, sockaddr in addrinfos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(
                status_code=422,
                detail="Fetching from private, loopback, or reserved network addresses is not allowed.",
            )


def _fetch_url_sync(url: str) -> bytes:
    _validate_fetch_url(url)
    import requests as _req
    try:
        resp = _req.get(
            url,
            headers={"Accept": "text/turtle, application/rdf+xml, application/ld+json, */*;q=0.1"},
            timeout=30,
            stream=True,
            allow_redirects=True,
        )
        resp.raise_for_status()
        chunks: List[bytes] = []
        total = 0
        for chunk in resp.iter_content(65536):
            total += len(chunk)
            if total > _MAX_FETCH_BYTES:
                raise HTTPException(status_code=413, detail="Remote resource exceeds 20 MB limit.")
            chunks.append(chunk)
        return b"".join(chunks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch {url}: {exc}") from exc


def _parse_rdf_sync(content: bytes, fmt: str) -> tuple:
    """Return (nodes, edges, metadata). Raises HTTPException on failure."""
    try:
        import rdflib
    except ImportError:
        raise HTTPException(status_code=501, detail="rdflib is not installed.")

    fmt_map = {
        "turtle": "turtle", "xml": "xml", "nt": "nt",
        "json-ld": "json-ld", "n3": "n3",
    }
    parse_fmt = fmt_map.get(fmt, "turtle")

    g = rdflib.Graph()
    try:
        _safe_parse_rdf(g, content, parse_fmt)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"RDF parse error: {exc}") from exc

    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    RDF = rdflib.RDF
    RDFS = rdflib.RDFS
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    DCT = rdflib.Namespace("http://purl.org/dc/terms/")
    DC = rdflib.Namespace("http://purl.org/dc/elements/1.1/")

    metadata: Dict[str, Any] = {}

    for subj in g.subjects(RDF.type, OWL.Ontology):
        metadata["uri"] = str(subj)
        for pred, obj in g.predicate_objects(subj):
            p = str(pred)
            if p in {str(RDFS.label), str(DCT.title), str(DC.title)}:
                metadata.setdefault("name", str(obj))
            elif p in {str(RDFS.comment), str(DCT.description), str(DC.description)}:
                metadata.setdefault("description", str(obj))
            elif p == str(OWL.versionInfo):
                metadata.setdefault("version", str(obj))
            elif p in {str(DCT.license), str(DC.rights)}:
                metadata.setdefault("license", str(obj))
        break

    if "uri" not in metadata:
        for subj in g.subjects(RDF.type, SKOS.ConceptScheme):
            metadata["uri"] = str(subj)
            for pred, obj in g.predicate_objects(subj):
                p = str(pred)
                if p in {str(SKOS.prefLabel), str(DCT.title), str(DC.title)}:
                    metadata.setdefault("name", str(obj))
                elif p in {str(SKOS.definition), str(DCT.description)}:
                    metadata.setdefault("description", str(obj))
            break

    if "uri" not in metadata:
        metadata["uri"] = f"urn:semantica:onto:{uuid.uuid4().hex[:8]}"
    metadata.setdefault("name", metadata["uri"].rsplit("/", 1)[-1].rsplit("#", 1)[-1] or "Unnamed")
    metadata["triple_count"] = len(g)

    # Collect literal properties per subject
    literal_props: Dict[str, Dict[str, str]] = {}
    for subj, pred, obj in g:
        if isinstance(subj, rdflib.BNode) or not isinstance(obj, rdflib.Literal):
            continue
        sid = str(subj)
        pk = _uri_to_prefix(str(pred))
        literal_props.setdefault(sid, {})[pk] = str(obj)

    # Build nodes from rdf:type statements
    seen_ids: set = set()
    nodes: List[Dict[str, Any]] = []
    for subj, _, type_obj in g.triples((None, RDF.type, None)):
        if isinstance(subj, rdflib.BNode):
            continue
        sid = str(subj)
        ntype = _uri_to_prefix(str(type_obj))
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        props = dict(literal_props.get(sid, {}))
        props["uri"] = sid
        label = (
            props.get("rdfs:label")
            or props.get("skos:prefLabel")
            or props.get("dcterms:title")
            or sid.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        )
        nodes.append({"id": sid, "type": ntype, "content": label, "properties": props})

    # Build edges from non-literal object statements
    edges: List[Dict[str, Any]] = []
    for subj, pred, obj in g:
        if isinstance(subj, rdflib.BNode) or isinstance(obj, (rdflib.Literal, rdflib.BNode)):
            continue
        edges.append({
            "source": str(subj),
            "target": str(obj),
            "type": _uri_to_prefix(str(pred)),
            "weight": 1.0,
        })

    return nodes, edges, metadata


# ---------------------------------------------------------------------------
# Registry endpoints (all specific paths before wildcard)
# ---------------------------------------------------------------------------

@router.get("/registry", response_model=List[OntologyEntry])
async def list_registry(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    session: GraphSession = Depends(get_session),
):
    registry = _get_registry(request)

    # Discover ontology-type nodes from live graph not yet registered
    all_nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)

    # Count entity types per ontology URI via scheme_uri property
    class_counts: Dict[str, int] = {}
    concept_counts: Dict[str, int] = {}
    prop_counts: Dict[str, int] = {}
    implicit: Dict[str, Dict[str, Any]] = {}

    for node in all_nodes:
        ntype = node.get("type", "")
        nid = node.get("id", "")
        etype = _classify_node_type(ntype)
        scheme_uri = node.get("properties", {}).get("scheme_uri") or node.get("properties", {}).get("uri")

        if etype == "ontology" or etype == "scheme":
            if nid and nid not in registry:
                implicit[nid] = node
        elif scheme_uri:
            if etype == "class":
                class_counts[scheme_uri] = class_counts.get(scheme_uri, 0) + 1
            elif etype == "concept":
                concept_counts[scheme_uri] = concept_counts.get(scheme_uri, 0) + 1
            elif etype == "property":
                prop_counts[scheme_uri] = prop_counts.get(scheme_uri, 0) + 1

    result: List[OntologyEntry] = []

    def _matches(name: str, uri: str, desc: str) -> bool:
        if not q:
            return True
        ql = q.lower()
        return any(ql in t.lower() for t in [name, uri, desc] if t)

    for entry in registry.values():
        if status and entry.status != status:
            continue
        if format and entry.format.lower() != format.lower():
            continue
        if not _matches(entry.name, entry.uri, entry.description or ""):
            continue
        updated = entry.model_copy(update={
            "class_count": class_counts.get(entry.uri, entry.class_count),
            "concept_count": concept_counts.get(entry.uri, entry.concept_count),
            "property_count": prop_counts.get(entry.uri, entry.property_count),
        })
        result.append(updated)

    for nid, node in implicit.items():
        props = node.get("properties", {})
        name = _node_label(node) or nid
        if not _matches(name, nid, props.get("description", "")):
            continue
        result.append(OntologyEntry(
            uri=nid,
            name=name,
            description=props.get("description"),
            format=props.get("format", "unknown"),
            status="external",
            version=props.get("version") or props.get("owl:versionInfo"),
            class_count=class_counts.get(nid, 0),
            concept_count=concept_counts.get(nid, 0),
            property_count=prop_counts.get(nid, 0),
            loaded_at=props.get("loaded_at", ""),
            enabled=True,
        ))

    return result


@router.post("/preview", response_model=OntologyPreview)
async def preview_ontology(body: PreviewOntologyRequest):
    if not body.url and not body.content:
        raise HTTPException(status_code=422, detail="Provide either url or content.")

    if body.url:
        raw = await asyncio.to_thread(_fetch_url_sync, body.url)
        content_str = raw.decode("utf-8", errors="replace")
    else:
        content_str = body.content or ""

    fmt = _normalize_format(body.format) if body.format else _detect_format(content_str)

    try:
        _, _, metadata = await asyncio.to_thread(
            _parse_rdf_sync, content_str.encode("utf-8"), fmt
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse ontology: {exc}") from exc

    return OntologyPreview(
        uri=metadata.get("uri", ""),
        name=metadata.get("name", ""),
        description=metadata.get("description"),
        namespace=_extract_namespace(metadata.get("uri", "")),
        version=metadata.get("version"),
        license=metadata.get("license"),
        format=fmt,
        estimated_triples=metadata.get("triple_count", 0),
        source_url=body.url,
    )


@router.post("/load", response_model=LoadOntologyResponse)
async def load_ontology(
    request: Request,
    body: LoadOntologyRequest,
    session: GraphSession = Depends(get_session),
):
    if not body.url and not body.content:
        raise HTTPException(status_code=422, detail="Provide either url or content.")

    if body.url:
        raw = await asyncio.to_thread(_fetch_url_sync, body.url)
        content_str = raw.decode("utf-8", errors="replace")
    else:
        content_str = body.content or ""

    fmt = _normalize_format(body.format) if body.format else _detect_format(content_str)

    try:
        # Try to use OntologyIngestor for proper parsing and conversion
        from ...ingest.ontology_ingestor import OntologyIngestor
        from tempfile import NamedTemporaryFile
        
        ingestor = OntologyIngestor()
        
        # Write content to temporary file for ingestion
        with NamedTemporaryFile(mode='w', suffix=f'.{fmt}', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(content_str)
            temp_path = temp_file.name
        
        try:
            # Use OntologyIngestor to parse and convert
            ontology_data = await asyncio.to_thread(
                ingestor.ingest_ontology,
                temp_path,
                format=fmt
            )
            
            # Convert to graph nodes/edges using ontology data
            nodes, edges = await asyncio.to_thread(
                _convert_ontology_to_graph,
                ontology_data.data
            )
            
            # Add nodes and edges to session
            nodes_added = await asyncio.to_thread(session.add_nodes, nodes)
            edges_added = await asyncio.to_thread(session.add_edges, edges)
            
            # Register in registry
            registry = _get_registry(request)
            ontology_uri = ontology_data.data.get("uri", f"temp:{uuid.uuid4().hex[:12]}")
            registry[ontology_uri] = OntologyEntry(
                uri=ontology_uri,
                name=ontology_data.data.get("name", "Imported Ontology"),
                description=ontology_data.data.get("description"),
                format=fmt,
                status="loaded",
                version=ontology_data.data.get("version", "1.0"),
                class_count=len([n for n in nodes if n.get("type") in _CLASS_TYPES]),
                concept_count=len([n for n in nodes if n.get("type") in _CONCEPT_TYPES]),
                property_count=len([n for n in nodes if n.get("type") in _PROPERTY_TYPES]),
                loaded_at=datetime.now(UTC).isoformat(),
                enabled=True,
                tags=body.tags,
                source_url=body.url,
            )
            
            return LoadOntologyResponse(
                uri=ontology_uri,
                name=ontology_data.data.get("name", "Imported Ontology"),
                nodes_added=nodes_added,
                edges_added=edges_added,
                format=fmt,
            )
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as ingest_exc:
        logger.warning(f"OntologyIngestor failed, falling back to basic parsing: {ingest_exc}")
        
        # Fallback to basic parsing
        nodes, edges, metadata = await asyncio.to_thread(
            _parse_rdf_sync, content_str.encode("utf-8"), fmt
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse ontology: {exc}") from exc

    # Fallback path - use basic parsing
    nodes_added = await asyncio.to_thread(session.add_nodes, nodes)
    edges_added = await asyncio.to_thread(session.add_edges, edges)

    registry = _get_registry(request)
    ontology_uri = metadata.get("uri", f"temp:{uuid.uuid4().hex[:12]}")
    registry[ontology_uri] = OntologyEntry(
        uri=ontology_uri,
        name=metadata.get("name", "Imported Ontology"),
        description=metadata.get("description"),
        format=fmt,
        status="loaded",
        version=metadata.get("version", "1.0"),
        class_count=sum(1 for n in nodes if n.get("type") in _CLASS_TYPES),
        concept_count=sum(1 for n in nodes if n.get("type") in _CONCEPT_TYPES),
        property_count=sum(1 for n in nodes if n.get("type") in _PROPERTY_TYPES),
        loaded_at=datetime.now(UTC).isoformat(),
        enabled=True,
        tags=body.tags,
        source_url=body.url,
    )

    return LoadOntologyResponse(
        uri=ontology_uri,
        name=metadata.get("name", "Imported Ontology"),
        nodes_added=nodes_added,
        edges_added=edges_added,
        format=fmt,
    )


@router.post("/create", response_model=LoadOntologyResponse)
async def create_ontology(
    request: Request,
    body: CreateOntologyRequest,
    session: GraphSession = Depends(get_session),
):
    """Create ontology from scratch, sample data, or text using OntologyEngine."""
    ns = body.namespace.rstrip("/#")
    onto_uri = f"{ns}#ontology"
    
    # Initialize OntologyEngine with session's graph store
    engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
    if body.provider or body.model:
        engine_config["provider"] = body.provider
        engine_config["model"] = body.model
    
    nodes: List[Dict[str, Any]] = [{
        "id": onto_uri,
        "type": "owl:Ontology",
        "content": body.name,
        "properties": {
            "rdfs:label": body.name,
            "rdfs:comment": body.description or "",
            "namespace": body.namespace,
        },
    }]
    edges: List[Dict[str, Any]] = []

    if body.mode == "data" and body.sample_data:
        try:
            from ...ontology import OntologyEngine
            engine = OntologyEngine(**engine_config)
            result = await asyncio.to_thread(engine.from_data, body.sample_data)
            
            # Convert OntologyEngine result to graph nodes/edges
            if isinstance(result, dict):
                for cls in result.get("classes", []):
                    cls_uri = f"{ns}/{cls.get('name', uuid.uuid4().hex[:6])}"
                    nodes.append({
                        "id": cls_uri,
                        "type": "owl:Class",
                        "content": cls.get("name", ""),
                        "properties": {
                            "rdfs:label": cls.get("name", ""),
                            "rdfs:comment": cls.get("description", ""),
                        },
                    })
                
                # Add property edges
                for prop in result.get("properties", []):
                    prop_uri = f"{ns}/{prop.get('name', uuid.uuid4().hex[:6])}"
                    domain_uri = f"{ns}/{prop.get('domain', '')}"
                    range_uri = f"{ns}/{prop.get('range', '')}"
                    
                    nodes.append({
                        "id": prop_uri,
                        "type": "owl:ObjectProperty",
                        "content": prop.get("name", ""),
                        "properties": {"rdfs:label": prop.get("name", "")},
                    })
                    
                    if domain_uri:
                        edges.append({
                            "source": prop_uri,
                            "target": domain_uri,
                            "type": "rdfs:domain",
                            "weight": 1.0,
                        })
                    if range_uri:
                        edges.append({
                            "source": prop_uri,
                            "target": range_uri,
                            "type": "rdfs:range",
                            "weight": 1.0,
                        })
                
                # Add subclass edges
                for cls in result.get("classes", []):
                    cls_uri = f"{ns}/{cls.get('name', '')}"
                    for parent in cls.get("superclasses", []):
                        parent_uri = f"{ns}/{parent}"
                        edges.append({
                            "source": cls_uri,
                            "target": parent_uri,
                            "type": "rdfs:subClassOf",
                            "weight": 1.0,
                        })
            
            logger.info(f"Generated ontology from sample data with {len(nodes)} nodes, {len(edges)} edges")
            
        except Exception as exc:
            logger.exception("Failed to generate ontology from sample data; falling back to minimal ontology.")
            logger.warning(f"OntologyEngine.from_data error: {exc}")

    elif body.mode == "text" and body.schema_text:
        try:
            from ...ontology import OntologyEngine
            engine = OntologyEngine(**engine_config)
            result = await asyncio.to_thread(engine.from_text, body.schema_text, provider=body.provider, model=body.model)
            
            # Convert OntologyEngine result to graph nodes/edges
            if isinstance(result, dict):
                for cls in result.get("classes", []):
                    cls_uri = f"{ns}/{cls.get('name', uuid.uuid4().hex[:6])}"
                    nodes.append({
                        "id": cls_uri,
                        "type": "owl:Class",
                        "content": cls.get("name", ""),
                        "properties": {
                            "rdfs:label": cls.get("name", ""),
                            "rdfs:comment": cls.get("description", ""),
                        },
                    })
                
                # Add property edges
                for prop in result.get("properties", []):
                    prop_uri = f"{ns}/{prop.get('name', uuid.uuid4().hex[:6])}"
                    domain_uri = f"{ns}/{prop.get('domain', '')}"
                    range_uri = f"{ns}/{prop.get('range', '')}"
                    
                    nodes.append({
                        "id": prop_uri,
                        "type": "owl:ObjectProperty",
                        "content": prop.get("name", ""),
                        "properties": {"rdfs:label": prop.get("name", "")},
                    })
                    
                    if domain_uri:
                        edges.append({
                            "source": prop_uri,
                            "target": domain_uri,
                            "type": "rdfs:domain",
                            "weight": 1.0,
                        })
                    if range_uri:
                        edges.append({
                            "source": prop_uri,
                            "target": range_uri,
                            "type": "rdfs:range",
                            "weight": 1.0,
                        })
                
                # Add subclass edges
                for cls in result.get("classes", []):
                    cls_uri = f"{ns}/{cls.get('name', '')}"
                    for parent in cls.get("superclasses", []):
                        parent_uri = f"{ns}/{parent}"
                        edges.append({
                            "source": cls_uri,
                            "target": parent_uri,
                            "type": "rdfs:subClassOf",
                            "weight": 1.0,
                        })
            
            logger.info(f"Generated ontology from text with {len(nodes)} nodes, {len(edges)} edges")
            
        except Exception as exc:
            logger.exception("Failed to generate ontology from schema text; falling back to minimal ontology.")
            logger.warning(f"OntologyEngine.from_text error: {exc}")

    nodes_added = await asyncio.to_thread(session.add_nodes, nodes)
    edges_added = await asyncio.to_thread(session.add_edges, edges)

    registry = _get_registry(request)
    registry[onto_uri] = OntologyEntry(
        uri=onto_uri,
        name=body.name,
        description=body.description,
        format="turtle",
        status="draft",
        version="0.1.0",
        class_count=sum(1 for n in nodes if n.get("type") == "owl:Class"),
        loaded_at=datetime.now(UTC).isoformat(),
        enabled=True,
        tags=body.tags,
    )

    return LoadOntologyResponse(
        uri=onto_uri, name=body.name,
        nodes_added=nodes_added, edges_added=edges_added, format="turtle",
    )


@router.get("/search", response_model=List[OntologySearchResult])
async def search_entities(
    q: str = Query(..., min_length=1),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    session: GraphSession = Depends(get_session),
):
    # Use the session's indexed search; over-fetch to allow post-filtering by entity type
    raw_hits = await asyncio.to_thread(session.search, q, limit * 6)
    results: List[OntologySearchResult] = []

    for hit in raw_hits:
        node = hit.get("node", hit)  # session.search returns {"node": ..., "score": ...}
        ntype = node.get("type", "")
        if ntype not in _SEARCHABLE_TYPES:
            continue
        etype = _classify_node_type(ntype)
        if entity_type and etype != entity_type:
            continue

        label = _node_label(node)
        props = node.get("properties", {})
        definition = (
            props.get("rdfs:comment")
            or props.get("skos:definition")
            or props.get("description")
        )

        results.append(OntologySearchResult(
            uri=node.get("id", ""),
            label=label,
            type=ntype,
            entity_type=etype,
            definition=definition,
            source_ontology=props.get("scheme_uri"),
            namespace_prefix=_extract_namespace(node.get("id", "")),
        ))
        if len(results) >= limit:
            break

    return results


@router.get("/entity/{entity_uri:path}", response_model=EntityDetailResponse)
async def get_entity_detail(
    entity_uri: str,
    session: GraphSession = Depends(get_session),
):
    node = await asyncio.to_thread(session.get_node, entity_uri)
    if node is None:
        raise HTTPException(status_code=404, detail="Entity not found.")

    props = node.get("properties", {})
    ntype = node.get("type", "")
    label = _node_label(node)
    definition = props.get("rdfs:comment") or props.get("skos:definition") or props.get("description")

    out_edges, _ = await asyncio.to_thread(session.get_edges, source=entity_uri, skip=0, limit=9999)
    in_edges, _ = await asyncio.to_thread(session.get_edges, target=entity_uri, skip=0, limit=9999)

    superclasses = [e["target"] for e in out_edges if e.get("type") in {"rdfs:subClassOf", "skos:broader"}]
    subclasses = [e["source"] for e in in_edges if e.get("type") in {"rdfs:subClassOf", "skos:broader"}]
    domain = [e["target"] for e in out_edges if e.get("type") == "rdfs:domain"]
    range_ = [e["target"] for e in out_edges if e.get("type") == "rdfs:range"]

    all_nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
    instance_count = sum(1 for n in all_nodes if n.get("type") == entity_uri)

    return EntityDetailResponse(
        uri=entity_uri, label=label,
        type=ntype, entity_type=_classify_node_type(ntype),
        definition=definition,
        source_ontology=props.get("scheme_uri"),
        superclasses=superclasses, subclasses=subclasses,
        domain=domain, range=range_,
        instance_count=instance_count, properties=props,
    )


@router.get("/skos/schemes", response_model=List[SKOSScheme])
async def list_skos_schemes(session: GraphSession = Depends(get_session)):
    """List SKOS concept schemes using OntologyEngine.list_vocabularies()."""
    try:
        from ...ontology import OntologyEngine
        
        # Initialize OntologyEngine with session's graph store
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Use OntologyEngine.list_vocabularies
        vocabularies = await asyncio.to_thread(engine.list_vocabularies)
        
        # Count concepts per scheme
        all_nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
        concept_counts: Dict[str, int] = {}
        for node in all_nodes:
            scheme_uri = node.get("properties", {}).get("scheme_uri")
            if scheme_uri and node.get("type") in _CONCEPT_TYPES:
                concept_counts[scheme_uri] = concept_counts.get(scheme_uri, 0) + 1
        
        return [
            SKOSScheme(
                uri=vocab["uri"],
                title=vocab["label"] or vocab["uri"].rsplit("/", 1)[-1].rsplit("#", 1)[-1],
                description=None,
                concept_count=concept_counts.get(vocab["uri"], 0),
            )
            for vocab in vocabularies
        ]
    except Exception as exc:
        logger.warning(f"OntologyEngine.list_vocabularies failed, falling back to session: {exc}")
        # Fallback to session-based implementation
        nodes, _ = await asyncio.to_thread(
            session.get_nodes, node_type="skos:ConceptScheme", skip=0, limit=999_999
        )
        all_edges, _ = await asyncio.to_thread(session.get_edges, skip=0, limit=999_999)
        concept_counts: Dict[str, int] = {}
        for edge in all_edges:
            if edge.get("type") in {"skos:inScheme", "skos:topConceptOf"}:
                concept_counts[edge["target"]] = concept_counts.get(edge["target"], 0) + 1
            elif edge.get("type") == "skos:hasTopConcept":
                concept_counts[edge["source"]] = concept_counts.get(edge["source"], 0) + 1

        result = []
        for node in nodes:
            props = node.get("properties", {})
            nid = node.get("id", "")
            result.append(SKOSScheme(
                uri=nid,
                title=_node_label(node),
                description=props.get("description") or props.get("skos:definition"),
                concept_count=concept_counts.get(nid, 0),
            ))
        return result


@router.post("/skos/search", response_model=List[OntologySearchResult])
async def search_skos_concepts(
    body: SKOSConceptSearchRequest,
    session: GraphSession = Depends(get_session),
):
    """Search SKOS concepts using OntologyEngine.search_concepts()."""
    try:
        from ...ontology import OntologyEngine
        
        # Initialize OntologyEngine with session's graph store
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Use OntologyEngine.search_concepts
        concepts = await asyncio.to_thread(
            engine.search_concepts,
            body.query,
            scheme_uri=body.scheme_uri
        )
        
        return [
            OntologySearchResult(
                uri=concept["uri"],
                label=concept["label"],
                type="skos:Concept",
                entity_type="concept",
                definition=None,
                source_ontology=body.scheme_uri,
                namespace_prefix=_extract_namespace(concept["uri"]),
            )
            for concept in concepts
        ]
    except Exception as exc:
        logger.warning(f"OntologyEngine.search_concepts failed, using fallback: {exc}")
        # Fallback to session-based search
        raw_hits = await asyncio.to_thread(session.search, body.query, 300)
        results: List[OntologySearchResult] = []

        for hit in raw_hits:
            node = hit.get("node", hit)
            ntype = node.get("type", "")
            if ntype not in _CONCEPT_TYPES:
                continue
            if body.scheme_uri:
                scheme = node.get("properties", {}).get("scheme_uri")
                if scheme != body.scheme_uri:
                    continue

            label = _node_label(node)
            props = node.get("properties", {})
            definition = (
                props.get("rdfs:comment")
                or props.get("skos:definition")
                or props.get("description")
            )

            results.append(OntologySearchResult(
                uri=node.get("id", ""),
                label=label,
                type=ntype,
                entity_type="concept",
                definition=definition,
                source_ontology=props.get("scheme_uri"),
                namespace_prefix=_extract_namespace(node.get("id", "")),
            ))
            if len(results) >= 50:
                break

        return results


@router.get("/skos/concept/{concept_uri:path}", response_model=SKOSConceptDetail)
async def get_skos_concept(
    concept_uri: str,
    session: GraphSession = Depends(get_session),
):
    """Get SKOS concept detail using OntologyEngine.list_concepts() and search_concepts()."""
    try:
        from ...ontology import OntologyEngine
        
        # Initialize OntologyEngine with session's graph store
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Try to get scheme_uri from node first
        node = await asyncio.to_thread(session.get_node, concept_uri)
        if node is None:
            raise HTTPException(status_code=404, detail="Concept not found.")
        
        scheme_uri = node.get("properties", {}).get("scheme_uri")
        
        # Use OntologyEngine.list_concepts if scheme_uri is known
        if scheme_uri:
            concepts = await asyncio.to_thread(engine.list_concepts, scheme_uri)
            concept_data = next((c for c in concepts if c["uri"] == concept_uri), None)
            
            if concept_data:
                return SKOSConceptDetail(
                    uri=concept_data["uri"],
                    pref_label=concept_data["pref_label"],
                    alt_labels=concept_data.get("alt_labels", []),
                    hidden_labels=[],
                    definition=None,
                    scope_note=None,
                    editorial_note=None,
                    broader=[],
                    narrower=[],
                    related=[],
                    exact_match=[],
                    close_match=[],
                    broad_match=[],
                    narrow_match=[],
                    scheme_uri=scheme_uri,
                )
        
        # Fallback to session-based implementation
        props = node.get("properties", {})
        out_edges, _ = await asyncio.to_thread(session.get_edges, source=concept_uri, skip=0, limit=9999)
        in_edges, _ = await asyncio.to_thread(session.get_edges, target=concept_uri, skip=0, limit=9999)

        def collect_out(rel: str) -> List[str]:
            return [e["target"] for e in out_edges if e.get("type") == rel]

        def collect_in(rel: str) -> List[str]:
            return [e["source"] for e in in_edges if e.get("type") == rel]

        pref_label = props.get("pref_label") or props.get("skos:prefLabel") or _node_label(node)
        alt_labels = props.get("alt_labels") or props.get("skos:altLabel") or []
        if isinstance(alt_labels, str):
            alt_labels = [alt_labels]
        hidden_labels = props.get("skos:hiddenLabel") or []
        if isinstance(hidden_labels, str):
            hidden_labels = [hidden_labels]

        if not scheme_uri:
            candidates = collect_out("skos:inScheme") or collect_out("skos:topConceptOf")
            scheme_uri = candidates[0] if candidates else None

        return SKOSConceptDetail(
            uri=concept_uri,
            pref_label=pref_label,
            alt_labels=list(alt_labels),
            hidden_labels=list(hidden_labels),
            definition=props.get("definition") or props.get("skos:definition"),
            scope_note=props.get("skos:scopeNote"),
            editorial_note=props.get("skos:editorialNote"),
            broader=collect_out("skos:broader") + collect_in("skos:narrower"),
            narrower=collect_out("skos:narrower") + collect_in("skos:broader"),
            related=collect_out("skos:related"),
            exact_match=collect_out("skos:exactMatch"),
            close_match=collect_out("skos:closeMatch"),
            broad_match=collect_out("skos:broadMatch"),
            narrow_match=collect_out("skos:narrowMatch"),
            scheme_uri=scheme_uri,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"OntologyEngine SKOS methods failed, using fallback: {exc}")
        # Fallback to session-based implementation
        node = await asyncio.to_thread(session.get_node, concept_uri)
        if node is None:
            raise HTTPException(status_code=404, detail="Concept not found.")

        props = node.get("properties", {})
        out_edges, _ = await asyncio.to_thread(session.get_edges, source=concept_uri, skip=0, limit=9999)
        in_edges, _ = await asyncio.to_thread(session.get_edges, target=concept_uri, skip=0, limit=9999)

        def collect_out(rel: str) -> List[str]:
            return [e["target"] for e in out_edges if e.get("type") == rel]

        def collect_in(rel: str) -> List[str]:
            return [e["source"] for e in in_edges if e.get("type") == rel]

        pref_label = props.get("pref_label") or props.get("skos:prefLabel") or _node_label(node)
        alt_labels = props.get("alt_labels") or props.get("skos:altLabel") or []
        if isinstance(alt_labels, str):
            alt_labels = [alt_labels]
        hidden_labels = props.get("skos:hiddenLabel") or []
        if isinstance(hidden_labels, str):
            hidden_labels = [hidden_labels]

        scheme_uri = props.get("scheme_uri")
        if not scheme_uri:
            candidates = collect_out("skos:inScheme") or collect_out("skos:topConceptOf")
            scheme_uri = candidates[0] if candidates else None

        return SKOSConceptDetail(
            uri=concept_uri,
            pref_label=pref_label,
            alt_labels=list(alt_labels),
            hidden_labels=list(hidden_labels),
            definition=props.get("definition") or props.get("skos:definition"),
            scope_note=props.get("skos:scopeNote"),
            editorial_note=props.get("skos:editorialNote"),
            broader=collect_out("skos:broader") + collect_in("skos:narrower"),
            narrower=collect_out("skos:narrower") + collect_in("skos:broader"),
            related=collect_out("skos:related"),
            exact_match=collect_out("skos:exactMatch"),
            close_match=collect_out("skos:closeMatch"),
            broad_match=collect_out("skos:broadMatch"),
            narrow_match=collect_out("skos:narrowMatch"),
            scheme_uri=scheme_uri,
        )


# ---------------------------------------------------------------------------
# Wildcard management endpoints (must come after specific routes)
# ---------------------------------------------------------------------------

@router.delete("/{ontology_uri:path}")
async def remove_ontology(ontology_uri: str, request: Request):
    registry = _get_registry(request)
    if ontology_uri not in registry:
        raise HTTPException(status_code=404, detail="Ontology not found in registry.")
    del registry[ontology_uri]
    return {"status": "removed", "uri": ontology_uri}


@router.patch("/{ontology_uri:path}/toggle", response_model=ToggleResponse)
async def toggle_ontology(ontology_uri: str, request: Request):
    registry = _get_registry(request)
    if ontology_uri not in registry:
        raise HTTPException(status_code=404, detail="Ontology not found in registry.")
    entry = registry[ontology_uri]
    entry.enabled = not entry.enabled
    return ToggleResponse(uri=ontology_uri, enabled=entry.enabled)


@router.post("/{ontology_uri:path}/refresh", response_model=RefreshResponse)
async def refresh_ontology(
    ontology_uri: str,
    request: Request,
    session: GraphSession = Depends(get_session),
):
    registry = _get_registry(request)
    if ontology_uri not in registry:
        raise HTTPException(status_code=404, detail="Ontology not found in registry.")
    entry = registry[ontology_uri]
    if not entry.source_url:
        raise HTTPException(status_code=422, detail="No source URL to refresh from.")

    raw = await asyncio.to_thread(_fetch_url_sync, entry.source_url)
    content_str = raw.decode("utf-8", errors="replace")

    try:
        nodes, edges, _ = await asyncio.to_thread(
            _parse_rdf_sync, content_str.encode("utf-8"), entry.format
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Refresh parse error: {exc}") from exc

    nodes_added = await asyncio.to_thread(session.add_nodes, nodes)
    edges_added = await asyncio.to_thread(session.add_edges, edges)
    entry.loaded_at = datetime.now(UTC).isoformat()

    return RefreshResponse(uri=ontology_uri, nodes_added=nodes_added, edges_added=edges_added)


# ---------------------------------------------------------------------------
# Draft endpoints
# ---------------------------------------------------------------------------

@router.patch("/draft", response_model=DraftResponse)
async def save_draft(
    request: Request,
    body: DraftRequest,
):
    """Stage editor diffs as a draft with ChangeLogEntry metadata."""
    drafts = _get_drafts(request)
    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    # Create ChangeLogEntry for audit trail
    try:
        from ...change_management.change_log import ChangeLogEntry
        change_log = ChangeLogEntry.create_now(
            author=body.author,
            description=body.summary or f"Draft changes for {body.ontology_uri}",
            change_id=draft_id
        )
    except Exception as exc:
        logger.warning(f"Failed to create ChangeLogEntry: {exc}")
        change_log = None

    draft = DraftResponse(
        draft_id=draft_id,
        ontology_uri=body.ontology_uri,
        diff=body.diff,
        author=body.author,
        summary=body.summary,
        created_at=now,
        updated_at=now,
    )
    drafts[draft_id] = draft
    return draft


@router.get("/drafts/{ontology_uri:path}", response_model=List[DraftResponse])
async def list_drafts(
    ontology_uri: str,
    request: Request,
):
    """Get staged draft diffs for an ontology."""
    drafts = _get_drafts(request)
    return [d for d in drafts.values() if d.ontology_uri == ontology_uri]


@router.get("/draft/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: str,
    request: Request,
):
    """Get a specific draft by ID."""
    drafts = _get_drafts(request)
    if draft_id not in drafts:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return drafts[draft_id]


# ---------------------------------------------------------------------------
# Proposal endpoints
# ---------------------------------------------------------------------------

@router.post("/propose", response_model=ProposalResponse)
async def submit_proposal(
    request: Request,
    body: ProposalRequest,
    session: GraphSession = Depends(get_session),
):
    """Submit a change proposal with impact analysis and SHACL pre-validation."""
    drafts = _get_drafts(request)
    proposals = _get_proposals(request)

    if body.draft_id not in drafts:
        raise HTTPException(status_code=404, detail="Draft not found.")

    draft = drafts[body.draft_id]
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    # Compute impact analysis using VersionManager.diff_ontologies and OntologyEngine
    impact_analysis = {}
    shacl_validation = {}

    try:
        from ...ontology import OntologyEngine
        from ...change_management.ontology_version_manager import VersionManager
        
        # Build ontology dicts from draft diff for comparison
        base_ontology = {"uri": body.ontology_uri, "classes": [], "properties": []}
        target_ontology = {
            "uri": body.ontology_uri,
            "classes": [{"uri": uri} for uri in draft.diff.added_classes],
            "properties": [{"uri": uri} for uri in draft.diff.added_properties],
        }
        
        # Use VersionManager.diff_ontologies for structured diff
        version_manager = VersionManager(
            store=session.graph.store if hasattr(session.graph, "store") else None
        )
        diff_result = await asyncio.to_thread(
            version_manager.diff_ontologies,
            base_ontology,
            target_ontology
        )
        
        # Use OntologyEngine for validation and SHACL
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Run validation if available
        validation_results = {}
        try:
            val_res = await asyncio.to_thread(engine.validate, target_ontology)
            validation_results = {
                "valid": getattr(val_res, "valid", getattr(val_res, "is_valid", False)),
                "consistent": getattr(val_res, "consistent", True),
                "satisfiable": getattr(val_res, "satisfiable", True),
                "errors": getattr(val_res, "errors", []),
                "warnings": getattr(val_res, "warnings", [])
            }
        except Exception as val_exc:
            logger.warning(f"Validation failed: {val_exc}")
            validation_results = {"error": str(val_exc)}
        
        # SHACL pre-validation using OntologyEngine.validate_graph
        if engine.store:
            try:
                # Generate SHACL from target ontology
                shacl_shapes = await asyncio.to_thread(
                    engine.to_shacl,
                    target_ontology,
                    format="turtle"
                )
                
                # Validate current graph data against new SHACL shapes
                all_nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
                graph_data = {"nodes": all_nodes}
                
                validation_report = await asyncio.to_thread(
                    engine.validate_graph,
                    graph_data,
                    ontology=target_ontology,
                    explain=True
                )
                
                shacl_validation = {
                    "status": "validated",
                    "conforms": getattr(validation_report, "conforms", True),
                    "violations": [
                        {
                            "message": v.message,
                            "severity": v.severity,
                            "focus_node": v.focus_node,
                        }
                        for v in getattr(validation_report, "violations", [])
                    ]
                }
            except Exception as shacl_exc:
                logger.warning(f"SHACL pre-validation failed: {shacl_exc}")
                shacl_validation = {"status": "error", "error": str(shacl_exc)}
        else:
            shacl_validation = {"status": "skipped", "reason": "No store configured"}
        
        impact_analysis = {
            "diff": diff_result,
            "validation_results": validation_results,
            "class_adds": len(draft.diff.added_classes),
            "class_removals": len(draft.diff.removed_classes),
            "property_changes": len(draft.diff.added_properties) + len(draft.diff.removed_properties),
            "restriction_changes": len(draft.diff.added_restrictions) + len(draft.diff.removed_restrictions),
        }
            
    except Exception as exc:
        logger.warning(f"Impact analysis failed: {exc}")
        impact_analysis = {"error": str(exc)}
        shacl_validation = {"status": "error", "error": str(exc)}

    proposal = ProposalResponse(
        proposal_id=proposal_id,
        draft_id=body.draft_id,
        ontology_uri=body.ontology_uri,
        summary=body.summary,
        author=draft.author,
        reviewer=body.reviewer,
        state="proposed",
        impact_analysis=impact_analysis,
        shacl_validation=shacl_validation,
        created_at=now,
        updated_at=now,
        comments=[],
    )
    proposals[proposal_id] = proposal
    return proposal


@router.get("/proposals", response_model=List[ProposalResponse])
async def list_proposals(
    request: Request,
    ontology_uri: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """List proposals with optional filters."""
    proposals = _get_proposals(request)
    result = list(proposals.values())

    if ontology_uri:
        result = [p for p in result if p.ontology_uri == ontology_uri]
    if state:
        result = [p for p in result if p.state == state]

    return result


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    request: Request,
):
    """Get proposal detail."""
    proposals = _get_proposals(request)
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return proposals[proposal_id]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    request: Request,
):
    """Approve a proposal."""
    proposals = _get_proposals(request)
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    proposal = proposals[proposal_id]
    proposal.state = "approved"
    proposal.updated_at = datetime.now(UTC).isoformat()
    return {"status": "approved", "proposal_id": proposal_id}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    request: Request,
):
    """Reject a proposal (can return to draft)."""
    proposals = _get_proposals(request)
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    proposal = proposals[proposal_id]
    proposal.state = "rejected"
    proposal.updated_at = datetime.now(UTC).isoformat()
    return {"status": "rejected", "proposal_id": proposal_id}


@router.post("/proposals/{proposal_id}/publish")
async def publish_proposal(
    proposal_id: str,
    request: Request,
    session: GraphSession = Depends(get_session),
):
    """Publish an approved proposal using VersionManager.create_version()."""
    proposals = _get_proposals(request)
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    proposal = proposals[proposal_id]

    if proposal.state != "approved":
        raise HTTPException(status_code=400, detail="Only approved proposals can be published.")

    drafts = _get_drafts(request)
    if proposal.draft_id not in drafts:
        raise HTTPException(status_code=404, detail="Draft not found.")
    draft = drafts[proposal.draft_id]

    # Apply draft diff to live graph
    nodes_added = 0
    edges_added = 0

    # Add new classes
    for class_uri in draft.diff.added_classes:
        node = {
            "id": class_uri,
            "type": "owl:Class",
            "content": class_uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1],
            "properties": {"rdfs:label": class_uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]},
        }
        nodes_added += await asyncio.to_thread(session.add_nodes, [node])

    # Build ontology dict for version creation
    ontology_dict = {
        "uri": proposal.ontology_uri,
        "classes": [{"uri": uri} for uri in draft.diff.added_classes],
        "properties": [{"uri": uri} for uri in draft.diff.added_properties],
        "diff": draft.diff.model_dump(),
    }

    # Create version record using VersionManager
    try:
        from ...change_management.ontology_version_manager import VersionManager
        from ...ontology import OntologyEngine
        
        # Initialize VersionManager with proper config
        version_manager = VersionManager(
            store=session.graph.store if hasattr(session.graph, "store") else None
        )
        
        # Generate version string based on existing versions
        versions = _get_versions(request)
        existing_versions = versions.get(proposal.ontology_uri, [])
        version_num = len(existing_versions) + 1
        version_str = f"1.{version_num}.0"
        
        version_record = version_manager.create_version(
            version=version_str,
            ontology=ontology_dict,
            changes=[proposal.summary],
        )
        
        # Store version in app state
        if proposal.ontology_uri not in versions:
            versions[proposal.ontology_uri] = []
        
        versions[proposal.ontology_uri].append({
            "version_id": version_str,
            "ontology_uri": proposal.ontology_uri,
            "state": "published",
            "author": proposal.author,
            "date": datetime.now(UTC).isoformat(),
            "diff_summary": draft.diff.model_dump(),
        })
        
        logger.info(f"Created version {version_str} for ontology {proposal.ontology_uri}")
        
    except Exception as exc:
        logger.warning(f"VersionManager.create_version failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Version creation failed: {exc}") from exc

    proposal.state = "published"
    proposal.updated_at = datetime.now(UTC).isoformat()

    return {
        "status": "published",
        "proposal_id": proposal_id,
        "version": version_str,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
    }


@router.post("/proposals/{proposal_id}/comment")
async def add_comment(
    proposal_id: str,
    body: CommentRequest,
    request: Request,
):
    """Add inline comment to a proposal."""
    proposals = _get_proposals(request)
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    proposal = proposals[proposal_id]
    comment = {
        "id": f"comment_{uuid.uuid4().hex[:8]}",
        "element_uri": body.element_uri,
        "text": body.text,
        "author": body.author,
        "created_at": datetime.now(UTC).isoformat(),
    }
    proposal.comments.append(comment)
    proposal.updated_at = datetime.now(UTC).isoformat()
    return {"status": "commented", "comment_id": comment["id"]}


# ---------------------------------------------------------------------------
# Version endpoints
# ---------------------------------------------------------------------------

@router.get("/versions/{ontology_uri:path}", response_model=List[VersionEntry])
async def list_versions(
    ontology_uri: str,
    request: Request,
):
    """List version history for an ontology."""
    versions = _get_versions(request)
    return versions.get(ontology_uri, [])


@router.post("/versions/{ontology_uri:path}/compare", response_model=VersionCompareResponse)
async def compare_versions(
    ontology_uri: str,
    body: VersionCompareRequest,
    request: Request,
    session: GraphSession = Depends(get_session),
):
    """Compare two ontology versions using VersionManager.compare_versions()."""
    try:
        from ...change_management.ontology_version_manager import VersionManager
        
        # Initialize VersionManager with session's graph store
        version_manager = VersionManager(
            store=session.graph.store if hasattr(session.graph, "store") else None
        )
        
        # Get version data from app state
        versions = _get_versions(request)
        ontology_versions = versions.get(ontology_uri, [])
        
        # Find version records
        v1_record = next((v for v in ontology_versions if v.version_id == body.version1), None)
        v2_record = next((v for v in ontology_versions if v.version_id == body.version2), None)
        
        if not v1_record or not v2_record:
            raise HTTPException(status_code=404, detail="One or both versions not found.")
        
        # Build ontology dicts from version records
        v1_dict = {
            "uri": ontology_uri,
            "version": body.version1,
            "classes": [],
            "properties": [],
            "diff": v1_record.diff_summary,
        }
        v2_dict = {
            "uri": ontology_uri,
            "version": body.version2,
            "classes": [],
            "properties": [],
            "diff": v2_record.diff_summary,
        }
        
        # Use VersionManager.diff_ontologies for structured comparison
        diff_result = await asyncio.to_thread(
            version_manager.diff_ontologies,
            v1_dict,
            v2_dict
        )
        
        # Use VersionManager.compare_versions for metadata comparison
        comparison = await asyncio.to_thread(
            version_manager.compare_versions,
            body.version1,
            body.version2
        )
        
        return VersionCompareResponse(
            version1=body.version1,
            version2=body.version2,
            metadata_changes=comparison.get("metadata_changes", {}),
            class_changes={
                "added": diff_result.get("added_classes", []),
                "removed": diff_result.get("removed_classes", []),
                "changed": diff_result.get("changed_classes", []),
            },
            property_changes={
                "added": diff_result.get("added_properties", []),
                "removed": diff_result.get("removed_properties", []),
                "changed": diff_result.get("changed_properties", []),
            },
            restriction_changes={
                "added": diff_result.get("added_axioms", []),
                "removed": diff_result.get("removed_axioms", []),
                "changed": diff_result.get("changed_axioms", []),
            },
            axiom_changes={
                "added": diff_result.get("added_axioms", []),
                "removed": diff_result.get("removed_axioms", []),
                "changed": diff_result.get("changed_axioms", []),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Version comparison failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Version comparison failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Alignment endpoints using OntologyEngine
# ---------------------------------------------------------------------------

@router.post("/alignments", response_model=AlignmentResponse)
async def create_alignment(
    body: AlignmentRequest,
    session: GraphSession = Depends(get_session),
):
    """Create an alignment between two ontology entities using OntologyEngine.create_alignment."""
    try:
        from ...ontology import OntologyEngine
        
        # Initialize OntologyEngine with session's graph store
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Use OntologyEngine.create_alignment
        await asyncio.to_thread(
            engine.create_alignment,
            body.source_uri,
            body.target_uri,
            body.predicate
        )
        
        return AlignmentResponse(
            source=body.source_uri,
            predicate=body.predicate,
            target=body.target_uri,
        )
    except Exception as exc:
        logger.error(f"Failed to create alignment: {exc}")
        raise HTTPException(status_code=500, detail=f"Alignment creation failed: {exc}") from exc


@router.get("/alignments/{entity_uri:path}", response_model=List[AlignmentResponse])
async def get_alignments(
    entity_uri: str,
    session: GraphSession = Depends(get_session),
):
    """Get all alignments for an entity using OntologyEngine.get_alignments."""
    try:
        from ...ontology import OntologyEngine
        
        # Initialize OntologyEngine with session's graph store
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Use OntologyEngine.get_alignments
        alignments = await asyncio.to_thread(engine.get_alignments, entity_uri)
        
        return [
            AlignmentResponse(
                source=align.get("source", ""),
                predicate=align.get("predicate", ""),
                target=align.get("target", ""),
            )
            for align in alignments
        ]
    except Exception as exc:
        logger.error(f"Failed to get alignments: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to get alignments: {exc}") from exc


@router.get("/alignments", response_model=List[AlignmentResponse])
async def list_alignments(
    ontology_uri: Optional[str] = Query(None),
    session: GraphSession = Depends(get_session),
):
    """List all alignments, optionally filtered by ontology URI using OntologyEngine.list_alignments."""
    try:
        from ...ontology import OntologyEngine
        
        # Initialize OntologyEngine with session's graph store
        engine_config = {"store": session.graph.store if hasattr(session.graph, "store") else None}
        engine = OntologyEngine(**engine_config)
        
        # Use OntologyEngine.list_alignments
        alignments = await asyncio.to_thread(engine.list_alignments, ontology_uri=ontology_uri)
        
        return [
            AlignmentResponse(
                source=align.get("source", ""),
                predicate=align.get("predicate", ""),
                target=align.get("target", ""),
            )
            for align in alignments
        ]
    except Exception as exc:
        logger.error(f"Failed to list alignments: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to list alignments: {exc}") from exc
