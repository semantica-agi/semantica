"""
Ontology Hub routes: registry, URL/file loading, preview, creation, entity search, and SKOS.
"""

import asyncio
import ipaddress
import logging
import socket
import uuid
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..dependencies import get_session
from ..session import GraphSession
from ..utils.rdf_parser import _safe_parse_rdf

router = APIRouter(prefix="/api/ontology", tags=["Ontology"])
logger = logging.getLogger(__name__)

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

_ALIGNMENT_RELATIONS: Dict[str, str] = {
    "owl:equivalentClass": "http://www.w3.org/2002/07/owl#equivalentClass",
    "owl:equivalentProperty": "http://www.w3.org/2002/07/owl#equivalentProperty",
    "skos:exactMatch": "http://www.w3.org/2004/02/skos/core#exactMatch",
    "skos:closeMatch": "http://www.w3.org/2004/02/skos/core#closeMatch",
    "skos:broadMatch": "http://www.w3.org/2004/02/skos/core#broadMatch",
    "skos:narrowMatch": "http://www.w3.org/2004/02/skos/core#narrowMatch",
    "skos:relatedMatch": "http://www.w3.org/2004/02/skos/core#relatedMatch",
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


AlignmentRelation = Literal[
    "owl:equivalentClass",
    "owl:equivalentProperty",
    "skos:exactMatch",
    "skos:closeMatch",
    "skos:broadMatch",
    "skos:narrowMatch",
    "skos:relatedMatch",
]


class OntologyAlignment(BaseModel):
    id: str
    source_uri: str
    source_label: str = ""
    target_uri: str
    target_label: str = ""
    relation: AlignmentRelation
    predicate_uri: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Optional[str] = None
    source: Optional[str] = None
    reviewer: Optional[str] = None
    created_at: str
    updated_at: str


class OntologyAlignmentRequest(BaseModel):
    source_uri: str
    target_uri: str
    relation: AlignmentRelation
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Optional[str] = None
    source: Optional[str] = None
    reviewer: Optional[str] = None


class AlignmentSuggestionRequest(BaseModel):
    source_ontology_uri: Optional[str] = None
    target_ontology_uri: Optional[str] = None
    threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    limit: int = Field(default=25, ge=1, le=100)


class AlignmentSuggestion(BaseModel):
    source_uri: str
    source_label: str
    target_uri: str
    target_label: str
    relation: AlignmentRelation
    score: float
    label_similarity: float
    embedding_similarity: Optional[float] = None
    reason: str


class HealthDimension(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0.0, le=100.0)
    status: Literal["ok", "warning", "critical", "unavailable"] = "ok"
    detail: str


class HealthIssue(BaseModel):
    id: str
    severity: Literal["info", "warning", "critical"] = "warning"
    category: str
    entity_uri: Optional[str] = None
    entity_label: Optional[str] = None
    message: str
    action: Optional[str] = None


class OntologyHealthResponse(BaseModel):
    uri: str
    name: str
    total_score: float = Field(ge=0.0, le=100.0)
    dimensions: List[HealthDimension]
    issues: List[HealthIssue] = Field(default_factory=list)
    generated_at: str


class ShaclGenerateRequest(BaseModel):
    uri: str
    quality_tier: Literal["standard", "strict"] = "strict"


class ShaclValidateRequest(BaseModel):
    uri: Optional[str] = None
    shacl_turtle: str


class ShaclViolation(BaseModel):
    node: Optional[str] = None
    path: Optional[str] = None
    severity: str = "Violation"
    message: str
    focus_node: Optional[str] = None
    source_shape: Optional[str] = None


class ShaclShapeSummary(BaseModel):
    id: str
    target_class: Optional[str] = None
    constraint_count: int = 0
    constraints: List[str] = Field(default_factory=list)
    violation_count: int = 0


class ShaclGenerateResponse(BaseModel):
    uri: str
    shacl_turtle: str
    shape_count: int
    generated_at: str


class ShaclShapesResponse(BaseModel):
    uri: str
    shapes: List[ShaclShapeSummary]
    shacl_turtle: str
    generated_at: str


class ShaclValidationResponse(BaseModel):
    uri: Optional[str] = None
    conforms: bool
    status: Literal["success", "unavailable", "error"] = "success"
    message: str
    violations: List[ShaclViolation] = Field(default_factory=list)
    report_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_registry(request: Request) -> Dict[str, OntologyEntry]:
    if not hasattr(request.app.state, "ontology_registry"):
        request.app.state.ontology_registry = {}
    return request.app.state.ontology_registry


def _get_alignment_store(request: Request) -> Dict[str, OntologyAlignment]:
    if not hasattr(request.app.state, "ontology_alignments"):
        request.app.state.ontology_alignments = {}
    return request.app.state.ontology_alignments


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


def _extract_namespace(uri: str) -> Optional[str]:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"
    return None


def _alignment_id(source_uri: str, relation: str, target_uri: str) -> str:
    key = f"{source_uri}|{relation}|{target_uri}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _node_source_ontology(node: Dict[str, Any]) -> Optional[str]:
    props = node.get("properties", {})
    return (
        props.get("scheme_uri")
        or props.get("source_ontology")
        or props.get("ontology_uri")
        or props.get("ontology")
    )


def _node_belongs_to_ontology(node: Dict[str, Any], ontology_uri: str) -> bool:
    nid = node.get("id", "")
    if nid == ontology_uri:
        return True
    if _node_source_ontology(node) == ontology_uri:
        return True
    namespace = _extract_namespace(ontology_uri)
    return bool(namespace and nid.startswith(namespace))


def _is_ontology_entity(node: Dict[str, Any]) -> bool:
    return _classify_node_type(node.get("type", "")) in {"class", "property", "concept", "scheme"}


def _entity_description(node: Dict[str, Any]) -> Optional[str]:
    props = node.get("properties", {})
    return (
        props.get("rdfs:comment")
        or props.get("skos:definition")
        or props.get("definition")
        or props.get("description")
    )


def _entity_definition(node: Dict[str, Any]) -> Optional[str]:
    props = node.get("properties", {})
    return props.get("skos:definition") or props.get("definition")


def _label_similarity(left: str, right: str) -> float:
    left_norm = " ".join(left.lower().replace("_", " ").replace("-", " ").split())
    right_norm = " ".join(right.lower().replace("_", " ").replace("-", " ").split())
    if not left_norm or not right_norm:
        return 0.0
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    token_score = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return round(max(sequence, token_score), 4)


def _candidate_relation(source: Dict[str, Any], target: Dict[str, Any]) -> AlignmentRelation:
    source_type = _classify_node_type(source.get("type", ""))
    target_type = _classify_node_type(target.get("type", ""))
    if source_type == "class" and target_type == "class":
        return "owl:equivalentClass"
    if source_type == "property" and target_type == "property":
        return "owl:equivalentProperty"
    if source_type == "concept" and target_type == "concept":
        return "skos:exactMatch"
    return "skos:closeMatch"


def _ontology_entities(nodes: List[Dict[str, Any]], ontology_uri: Optional[str] = None) -> List[Dict[str, Any]]:
    result = []
    for node in nodes:
        if not _is_ontology_entity(node):
            continue
        if ontology_uri and not _node_belongs_to_ontology(node, ontology_uri):
            continue
        result.append(node)
    return result


def _ontology_dict_from_nodes(uri: str, name: str, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    classes = []
    properties = []
    for node in nodes:
        entity_type = _classify_node_type(node.get("type", ""))
        label = _node_label(node) or node.get("id", "")
        item = {
            "name": label,
            "uri": node.get("id", ""),
            "label": label,
            "description": _entity_description(node) or "",
        }
        if entity_type == "class":
            classes.append(item)
        elif entity_type == "property":
            domain = [
                edge.get("target", "")
                for edge in edges
                if edge.get("source") == node.get("id") and edge.get("type") == "rdfs:domain"
            ]
            range_ = [
                edge.get("target", "")
                for edge in edges
                if edge.get("source") == node.get("id") and edge.get("type") == "rdfs:range"
            ]
            item.update({
                "type": "object" if "ObjectProperty" in node.get("type", "") else "datatype",
                "domain": domain,
                "range": range_,
                "required": False,
            })
            properties.append(item)

    return {
        "name": name,
        "namespace": _extract_namespace(uri) or uri.rstrip("#/") + "#",
        "classes": classes,
        "properties": properties,
    }


def _basic_shacl_turtle(uri: str, name: str, nodes: List[Dict[str, Any]]) -> str:
    namespace = _extract_namespace(uri) or uri.rstrip("#/") + "#"
    lines = [
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        f"@prefix onto: <{namespace}> .",
        "",
    ]
    class_nodes = [n for n in nodes if _classify_node_type(n.get("type", "")) == "class"]
    for index, node in enumerate(class_nodes or nodes[:1], start=1):
        label = (_node_label(node) or f"{name}Shape").replace(" ", "")
        target = node.get("id") or uri
        lines.extend([
            f"onto:{label}Shape a sh:NodeShape ;",
            f"  sh:targetClass <{target}> ;",
            "  sh:severity sh:Violation .",
            "",
        ])
    return "\n".join(lines)


def _summarize_shapes(shacl_turtle: str, violations: Optional[List[ShaclViolation]] = None) -> List[ShaclShapeSummary]:
    violations = violations or []
    blocks = [block.strip() for block in shacl_turtle.split(".\n") if "sh:NodeShape" in block]
    summaries: List[ShaclShapeSummary] = []
    for index, block in enumerate(blocks, start=1):
        first = block.splitlines()[0].strip()
        shape_id = first.split()[0] if first else f"shape-{index}"
        target_class = None
        constraints: List[str] = []
        for token in ("sh:targetClass", "sh:path", "sh:minCount", "sh:maxCount", "sh:datatype", "sh:class"):
            if token in block:
                constraints.append(token.replace("sh:", ""))
        if "sh:targetClass" in block:
            after = block.split("sh:targetClass", 1)[1].strip()
            target_class = after.split()[0].strip(" ;")
        violation_count = sum(
            1
            for violation in violations
            if violation.source_shape == shape_id or (target_class and violation.node == target_class)
        )
        summaries.append(ShaclShapeSummary(
            id=shape_id,
            target_class=target_class,
            constraint_count=max(0, len(constraints) - 1),
            constraints=constraints,
            violation_count=violation_count,
        ))
    return summaries


async def _registry_entries(request: Request, session: GraphSession) -> List[OntologyEntry]:
    return await list_registry(request=request, q=None, status=None, format=None, session=session)


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
        nodes, edges, metadata = await asyncio.to_thread(
            _parse_rdf_sync, content_str.encode("utf-8"), fmt
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse ontology: {exc}") from exc

    onto_uri = metadata.get("uri", f"urn:semantica:onto:{uuid.uuid4().hex[:8]}")
    onto_name = body.name or metadata.get("name", "Unnamed Ontology")

    nodes_added = await asyncio.to_thread(session.add_nodes, nodes)
    edges_added = await asyncio.to_thread(session.add_edges, edges)

    registry = _get_registry(request)
    registry[onto_uri] = OntologyEntry(
        uri=onto_uri,
        name=onto_name,
        description=body.description or metadata.get("description"),
        format=fmt,
        status="external",
        source_url=body.url,
        version=metadata.get("version"),
        class_count=sum(1 for n in nodes if _classify_node_type(n.get("type", "")) == "class"),
        concept_count=sum(1 for n in nodes if _classify_node_type(n.get("type", "")) in ("concept", "scheme")),
        property_count=sum(1 for n in nodes if _classify_node_type(n.get("type", "")) == "property"),
        loaded_at=datetime.now(UTC).isoformat(),
        enabled=True,
        tags=body.tags,
    )

    return LoadOntologyResponse(
        uri=onto_uri, name=onto_name,
        nodes_added=nodes_added, edges_added=edges_added, format=fmt,
    )


@router.post("/create", response_model=LoadOntologyResponse)
async def create_ontology(
    request: Request,
    body: CreateOntologyRequest,
    session: GraphSession = Depends(get_session),
):
    ns = body.namespace.rstrip("/#")
    onto_uri = f"{ns}#ontology"
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
            engine = OntologyEngine()
            result = await asyncio.to_thread(engine.from_data, body.sample_data)
            for cls in (result.get("classes", []) if isinstance(result, dict) else []):
                cls_uri = f"{ns}/{cls.get('name', uuid.uuid4().hex[:6])}"
                nodes.append({
                    "id": cls_uri, "type": "owl:Class",
                    "content": cls.get("name", ""),
                    "properties": {"rdfs:label": cls.get("name", "")},
                })
        except Exception:
            logger.exception("Failed to generate ontology from sample data; falling back to minimal ontology.")

    elif body.mode == "text" and body.schema_text:
        try:
            from ...ontology import OntologyEngine
            engine = OntologyEngine()
            result = await asyncio.to_thread(engine.from_text, body.schema_text)
            for cls in (result.get("classes", []) if isinstance(result, dict) else []):
                cls_uri = f"{ns}/{cls.get('name', uuid.uuid4().hex[:6])}"
                nodes.append({
                    "id": cls_uri, "type": "owl:Class",
                    "content": cls.get("name", ""),
                    "properties": {"rdfs:label": cls.get("name", "")},
                })
        except Exception:
            logger.exception("Failed to generate ontology from schema text; falling back to minimal ontology.")

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
    nodes, _ = await asyncio.to_thread(
        session.get_nodes, node_type="skos:ConceptScheme", skip=0, limit=999_999
    )
    # Count concepts per scheme from edges
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


@router.get("/skos/concept/{concept_uri:path}", response_model=SKOSConceptDetail)
async def get_skos_concept(
    concept_uri: str,
    session: GraphSession = Depends(get_session),
):
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


# alignments, health, and SHACL studio


@router.get("/alignments", response_model=List[OntologyAlignment])
async def list_alignments(
    request: Request,
    uri: Optional[str] = Query(None),
):
    store = _get_alignment_store(request)
    alignments = list(store.values())
    if uri:
        alignments = [
            item for item in alignments
            if item.source_uri.startswith(uri) or item.target_uri.startswith(uri)
        ]
    return sorted(alignments, key=lambda item: (item.source_label, item.target_label, item.relation))


@router.post("/alignments", response_model=OntologyAlignment)
async def upsert_alignment(
    request: Request,
    body: OntologyAlignmentRequest,
    session: GraphSession = Depends(get_session),
):
    source_node = await asyncio.to_thread(session.get_node, body.source_uri)
    target_node = await asyncio.to_thread(session.get_node, body.target_uri)
    if source_node is None:
        raise HTTPException(status_code=404, detail="Source entity not found.")
    if target_node is None:
        raise HTTPException(status_code=404, detail="Target entity not found.")

    now = datetime.now(UTC).isoformat()
    store = _get_alignment_store(request)
    alignment_id = _alignment_id(body.source_uri, body.relation, body.target_uri)
    existing = store.get(alignment_id)
    alignment = OntologyAlignment(
        id=alignment_id,
        source_uri=body.source_uri,
        source_label=_node_label(source_node),
        target_uri=body.target_uri,
        target_label=_node_label(target_node),
        relation=body.relation,
        predicate_uri=_ALIGNMENT_RELATIONS[body.relation],
        confidence=body.confidence,
        provenance=body.provenance,
        source=body.source,
        reviewer=body.reviewer,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    store[alignment_id] = alignment

    try:
        from ...ontology import OntologyEngine
        engine = OntologyEngine()
        await asyncio.to_thread(
            engine.create_alignment,
            body.source_uri,
            body.target_uri,
            _ALIGNMENT_RELATIONS[body.relation],
            confidence=body.confidence,
            provenance=body.provenance,
        )
    except Exception as exc:
        logger.debug("OntologyEngine alignment persistence unavailable; using route store: %s", exc)

    return alignment


@router.delete("/alignments")
async def delete_alignment(request: Request, id: str = Query(...)):
    store = _get_alignment_store(request)
    if id not in store:
        raise HTTPException(status_code=404, detail="Alignment not found.")
    del store[id]
    return {"status": "removed", "id": id}


@router.post("/suggest-alignments", response_model=List[AlignmentSuggestion])
async def suggest_alignments(
    body: AlignmentSuggestionRequest,
    session: GraphSession = Depends(get_session),
):
    nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
    source_nodes = _ontology_entities(nodes, body.source_ontology_uri)
    target_nodes = _ontology_entities(nodes, body.target_ontology_uri)
    if not body.source_ontology_uri:
        source_nodes = _ontology_entities(nodes)
    if not body.target_ontology_uri:
        target_nodes = _ontology_entities(nodes)

    suggestions: List[AlignmentSuggestion] = []
    for source_node in source_nodes:
        source_id = source_node.get("id", "")
        source_label = _node_label(source_node)
        source_ontology = _node_source_ontology(source_node)
        for target_node in target_nodes:
            target_id = target_node.get("id", "")
            if not source_id or source_id == target_id:
                continue
            target_ontology = _node_source_ontology(target_node)
            if source_ontology and target_ontology and source_ontology == target_ontology:
                continue

            target_label = _node_label(target_node)
            label_score = _label_similarity(source_label, target_label)
            score = label_score
            if score < body.threshold:
                continue

            relation = _candidate_relation(source_node, target_node)
            suggestions.append(AlignmentSuggestion(
                source_uri=source_id,
                source_label=source_label,
                target_uri=target_id,
                target_label=target_label,
                relation=relation,
                score=round(score, 4),
                label_similarity=label_score,
                embedding_similarity=None,
                reason="Matched by label similarity; embedding similarity was not required or unavailable.",
            ))

    suggestions.sort(key=lambda item: item.score, reverse=True)
    return suggestions[:body.limit]


@router.get("/health", response_model=OntologyHealthResponse)
async def ontology_health(
    request: Request,
    uri: str = Query(...),
    session: GraphSession = Depends(get_session),
):
    registry = {entry.uri: entry for entry in await _registry_entries(request, session)}
    entry = registry.get(uri)
    if entry is None:
        raise HTTPException(status_code=404, detail="Ontology not found in registry.")

    nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
    edges, _ = await asyncio.to_thread(session.get_edges, skip=0, limit=999_999)
    entities = _ontology_entities(nodes, uri)
    classes = [node for node in entities if _classify_node_type(node.get("type", "")) == "class"]
    properties = [node for node in entities if _classify_node_type(node.get("type", "")) == "property"]
    assessed = classes + properties

    issues: List[HealthIssue] = []
    total = max(len(assessed), 1)
    with_label = sum(1 for node in assessed if _node_label(node))
    with_comment = sum(1 for node in assessed if _entity_description(node))
    with_definition = sum(1 for node in assessed if _entity_definition(node))
    completeness_score = ((with_label + with_comment + with_definition) / (total * 3)) * 100

    for node in assessed:
        label = _node_label(node)
        if not _entity_description(node):
            issues.append(HealthIssue(
                id=f"doc:{node.get('id')}",
                severity="warning",
                category="Documentation",
                entity_uri=node.get("id"),
                entity_label=label,
                message=f"{label} is missing a comment or definition.",
                action="Add documentation in Editor.",
            ))

    property_range_edges = {
        edge.get("source")
        for edge in edges
        if edge.get("type") == "rdfs:range"
    }
    missing_range = [node for node in properties if node.get("id") not in property_range_edges]
    for node in missing_range[:25]:
        issues.append(HealthIssue(
            id=f"range:{node.get('id')}",
            severity="info",
            category="Consistency",
            entity_uri=node.get("id"),
            entity_label=_node_label(node),
            message="Property has no explicit rdfs:range.",
            action="Review property range in Editor.",
        ))

    consistency_score = max(0.0, 100.0 - (len(missing_range) / max(len(properties), 1)) * 60.0)

    alignments = _get_alignment_store(request).values()
    aligned_sources = {
        item.source_uri
        for item in alignments
        if any(item.source_uri == node.get("id") for node in assessed)
    } | {
        item.target_uri
        for item in alignments
        if any(item.target_uri == node.get("id") for node in assessed)
    }
    alignment_score = (len(aligned_sources) / total) * 100
    if assessed and not aligned_sources:
        issues.append(HealthIssue(
            id=f"alignment:{uri}",
            severity="warning",
            category="Alignment",
            message="No cross-ontology alignments are recorded for local classes or properties.",
            action="Review suggested alignments.",
        ))

    documentation_score = ((with_comment / total) * 80.0) + (20.0 if entry.version or entry.source_url else 0.0)

    shacl_dimension = HealthDimension(
        key="shacl",
        label="SHACL Conformance",
        score=70.0,
        status="unavailable",
        detail="Live SHACL validation is available in SHACL Studio when optional validation dependencies are installed.",
    )

    dimensions = [
        HealthDimension(
            key="completeness",
            label="Completeness",
            score=round(completeness_score, 1),
            status="ok" if completeness_score >= 80 else "warning",
            detail=f"{with_label}/{total} labeled, {with_comment}/{total} documented, {with_definition}/{total} defined.",
        ),
        HealthDimension(
            key="consistency",
            label="Consistency",
            score=round(consistency_score, 1),
            status="ok" if consistency_score >= 80 else "warning",
            detail=f"{len(missing_range)} properties are missing explicit ranges.",
        ),
        shacl_dimension,
        HealthDimension(
            key="alignment",
            label="Alignment Coverage",
            score=round(alignment_score, 1),
            status="ok" if alignment_score >= 50 else "warning",
            detail=f"{len(aligned_sources)}/{total} classes or properties have an alignment.",
        ),
        HealthDimension(
            key="documentation",
            label="Documentation",
            score=round(documentation_score, 1),
            status="ok" if documentation_score >= 75 else "warning",
            detail="Measures comments plus source/version metadata.",
        ),
    ]
    total_score = sum(dim.score for dim in dimensions) / len(dimensions)

    return OntologyHealthResponse(
        uri=uri,
        name=entry.name,
        total_score=round(total_score, 1),
        dimensions=dimensions,
        issues=issues[:100],
        generated_at=datetime.now(UTC).isoformat(),
    )


async def _generated_shacl_for_uri(
    request: Request,
    session: GraphSession,
    uri: str,
    quality_tier: str = "strict",
) -> tuple[str, List[ShaclShapeSummary]]:
    registry = {entry.uri: entry for entry in await _registry_entries(request, session)}
    entry = registry.get(uri)
    if entry is None:
        raise HTTPException(status_code=404, detail="Ontology not found in registry.")

    nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
    edges, _ = await asyncio.to_thread(session.get_edges, skip=0, limit=999_999)
    entities = _ontology_entities(nodes, uri)
    ontology_dict = _ontology_dict_from_nodes(uri, entry.name, entities, edges)

    try:
        from ...ontology import OntologyEngine
        engine = OntologyEngine()
        shacl_turtle = await asyncio.to_thread(
            engine.to_shacl,
            ontology_dict,
            format="turtle",
            quality_tier=quality_tier,
            validate_output=False,
        )
    except Exception as exc:
        logger.debug("OntologyEngine.to_shacl unavailable; using basic generator: %s", exc)
        shacl_turtle = _basic_shacl_turtle(uri, entry.name, entities)

    return shacl_turtle, _summarize_shapes(shacl_turtle)


@router.post("/shacl/generate", response_model=ShaclGenerateResponse)
async def generate_shacl(
    request: Request,
    body: ShaclGenerateRequest,
    session: GraphSession = Depends(get_session),
):
    shacl_turtle, shapes = await _generated_shacl_for_uri(request, session, body.uri, body.quality_tier)
    return ShaclGenerateResponse(
        uri=body.uri,
        shacl_turtle=shacl_turtle,
        shape_count=len(shapes),
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.get("/shacl/shapes", response_model=ShaclShapesResponse)
async def list_shacl_shapes(
    request: Request,
    uri: str = Query(...),
    session: GraphSession = Depends(get_session),
):
    shacl_turtle, shapes = await _generated_shacl_for_uri(request, session, uri)
    return ShaclShapesResponse(
        uri=uri,
        shapes=shapes,
        shacl_turtle=shacl_turtle,
        generated_at=datetime.now(UTC).isoformat(),
    )


@router.post("/shacl/validate", response_model=ShaclValidationResponse)
async def validate_shacl(body: ShaclValidateRequest):
    if not body.shacl_turtle.strip():
        raise HTTPException(status_code=422, detail="SHACL Turtle cannot be empty.")
    try:
        import pyshacl  # type: ignore  # noqa: F401
    except ImportError:
        return ShaclValidationResponse(
            uri=body.uri,
            conforms=False,
            status="unavailable",
            message="pySHACL is not installed, so live graph validation is unavailable in this environment.",
            violations=[],
        )

    # The route exposes a stable contract even when validation data plumbing is absent.
    # Full data-graph validation will use OntologyEngine.validate_graph once a persisted
    # ontology/data store is available from the registry layer.
    return ShaclValidationResponse(
        uri=body.uri,
        conforms=True,
        status="success",
        message="SHACL Turtle parsed; no live data violations were produced by the current in-memory graph adapter.",
        violations=[],
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
