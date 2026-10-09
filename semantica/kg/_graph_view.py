"""Internal graph view helpers shared by KG analytics modules."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass
class GraphView:
    """Normalized node and edge view used by graph analytics."""

    nodes: List[Any]
    edges: List[Tuple[Any, Any]]


def build_graph_view(graph: Any) -> GraphView:
    """Build a graph view without dropping explicitly declared nodes.

    Graph analytics accepts graph dictionaries, ContextGraph-like objects, and
    NetworkX graphs. Nodes declared without an incident edge remain in the
    returned view so callers can choose how to handle isolated nodes.
    """
    nodes: List[Any] = []
    edges: List[Tuple[Any, Any]] = []
    seen_nodes: Set[Any] = set()
    seen_edges: Set[Tuple[Any, Any]] = set()

    def add_node(value: Any) -> Optional[Any]:
        node_id = _node_id(value)
        if node_id is None or node_id == "":
            return None
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            nodes.append(node_id)
        return node_id

    for node in _extract_nodes(graph):
        add_node(node)

    for raw_edge in _extract_edges(graph):
        edge = _edge_endpoints(raw_edge)
        if edge is None:
            continue
        source, target = edge
        source = add_node(source)
        target = add_node(target)
        if source is None or target is None:
            continue
        if (source, target) not in seen_edges:
            seen_edges.add((source, target))
            edges.append((source, target))

    return GraphView(nodes=nodes, edges=edges)


def build_adjacency(graph: Any, directed: bool = False) -> Dict[Any, List[Any]]:
    """Build an adjacency list while preserving isolated graph nodes."""
    view = build_graph_view(graph)
    adjacency: Dict[Any, List[Any]] = {node: [] for node in view.nodes}

    for source, target in view.edges:
        if target not in adjacency[source]:
            adjacency[source].append(target)
        if not directed and source not in adjacency[target]:
            adjacency[target].append(source)

    return adjacency


def _extract_nodes(graph: Any) -> Iterable[Any]:
    if isinstance(graph, dict):
        raw_nodes: List[Any] = []
        for key in ("entities", "nodes"):
            values = graph.get(key, [])
            if isinstance(values, dict):
                raw_nodes.extend(values.keys())
            elif values:
                raw_nodes.extend(values)
        return raw_nodes

    raw_nodes = getattr(graph, "nodes", None)
    if callable(raw_nodes):
        return raw_nodes()
    if isinstance(raw_nodes, dict):
        return raw_nodes.keys()
    if raw_nodes is not None:
        return raw_nodes

    get_nodes = getattr(graph, "get_nodes", None)
    if callable(get_nodes):
        return get_nodes()
    return []


def _extract_edges(graph: Any) -> Iterable[Any]:
    if isinstance(graph, dict):
        raw_edges: List[Any] = []
        for key in ("relationships", "edges"):
            values = graph.get(key, [])
            if values:
                raw_edges.extend(values)
        return raw_edges

    raw_edges: List[Any] = []
    relationships = getattr(graph, "relationships", None)
    if relationships is not None:
        raw_edges.extend(relationships)
    edges = getattr(graph, "edges", None)
    if callable(edges):
        raw_edges.extend(edges())
    elif edges is not None:
        raw_edges.extend(edges)
    if raw_edges:
        return raw_edges

    get_relationships = getattr(graph, "get_relationships", None)
    if callable(get_relationships):
        return get_relationships()
    return []


def _edge_endpoints(edge: Any) -> Optional[Tuple[Any, Any]]:
    if isinstance(edge, (tuple, list)) and len(edge) >= 2:
        return edge[0], edge[1]

    if isinstance(edge, dict):
        source = _first_value(
            edge,
            "source",
            "source_id",
            "subject",
            "start",
            "start_id",
            "from",
            "src",
            "START_ID",
            ":START_ID",
        )
        target = _first_value(
            edge,
            "target",
            "target_id",
            "object",
            "end",
            "end_id",
            "to",
            "dst",
            "END_ID",
            ":END_ID",
        )
    else:
        source = _first_attribute(
            edge,
            "source_id",
            "source",
            "subject",
            "start",
            "start_id",
            "from_id",
        )
        target = _first_attribute(
            edge,
            "target_id",
            "target",
            "object",
            "end",
            "end_id",
            "to_id",
        )

    if source is None or target is None:
        return None
    return source, target


def _edge_type_of(edge: Any) -> Any:
    """Read an edge's relationship type from a mapping or an object."""
    if isinstance(edge, dict):
        return _first_value(
            edge, "type", "edge_type", "relationship_type", "relationship"
        )
    return _first_attribute(
        edge, "edge_type", "type", "relationship_type", "relationship"
    )


@dataclass
class EdgeTypeIndex:
    """The declared edge types of a graph's edge list, read once.

    ``typed`` records whether any edge record declares a type at all;
    ``by_pair`` maps each ``(source, target)`` to the types declared from
    ``source`` to ``target``; ``untyped`` holds every ``(source, target)``
    joined by at least one edge that declares no type. A ``ContextGraph``
    answers for a pair as a whole, so its index leaves ``untyped`` empty.
    """

    typed: bool
    by_pair: Dict[Tuple[Any, Any], Set[Any]]
    untyped: Set[Tuple[Any, Any]]


def _context_edges(graph: Any) -> Optional[Sequence[Any]]:
    """Return a ``ContextGraph``-style edge list, or ``None`` for other graphs."""
    edges = getattr(graph, "edges", None)
    if isinstance(edges, (list, tuple)) and any(
        hasattr(edge, "source_id") for edge in edges
    ):
        return edges
    return None


def build_edge_type_index(graph: Any) -> Optional[EdgeTypeIndex]:
    """Read a graph's edge records once for repeated type lookups.

    A caller that classifies many links passes the result to
    :func:`edge_types_between`, so the edge list is scanned once per graph
    instead of once per link. A plain graph dictionary and a ``ContextGraph``
    are indexed; any other graph is answered through ``get_edge_data()`` and
    gets ``None``.
    """
    if not isinstance(graph, dict):
        context_edges = _context_edges(graph)
        if context_edges is None:
            return None
        context_by_pair: Dict[Tuple[Any, Any], Set[Any]] = {}
        for edge in context_edges:
            edge_type = getattr(edge, "edge_type", None)
            if not edge_type:
                continue
            endpoints = (
                getattr(edge, "source_id", None),
                getattr(edge, "target_id", None),
            )
            try:
                context_by_pair.setdefault(endpoints, set()).add(edge_type)
            except TypeError:
                continue
        return EdgeTypeIndex(
            typed=bool(context_by_pair), by_pair=context_by_pair, untyped=set()
        )

    edges = _extract_edges(graph)
    by_pair: Dict[Tuple[Any, Any], Set[Any]] = {}
    untyped: Set[Tuple[Any, Any]] = set()
    typed = False
    for edge in edges:
        edge_type = _edge_type_of(edge)
        if edge_type:
            typed = True
        endpoints = _edge_endpoints(edge)
        if endpoints is None:
            continue
        try:
            if edge_type:
                by_pair.setdefault(endpoints, set()).add(edge_type)
            else:
                untyped.add(endpoints)
        except TypeError:
            # An unhashable endpoint never equals a node id, which is always
            # hashable, so it could not have matched a lookup anyway.
            continue
    return EdgeTypeIndex(typed=typed, by_pair=by_pair, untyped=untyped)


def _dict_edge_types(
    graph: Dict[str, Any],
    source: Any,
    target: Any,
    directed: bool,
    index: Optional[EdgeTypeIndex] = None,
) -> Optional[Set[Any]]:
    """Collect the types of every declared edge between two nodes.

    Returns ``None`` when an edge joining the pair declares no type, matching
    :func:`edge_types_between`: a caller filtering on relationship types has
    nothing to classify that link with and keeps it. The decision is made per
    edge, so typed records elsewhere in the graph do not change it.
    """
    if index is None:
        index = build_edge_type_index(graph)
    if not index.typed:
        return None
    if (source, target) in index.untyped or (
        not directed and (target, source) in index.untyped
    ):
        return None

    types: Set[Any] = set(index.by_pair.get((source, target), ()))
    if not directed:
        types |= index.by_pair.get((target, source), set())
    return types


def _node_id(value: Any) -> Any:
    if isinstance(value, dict):
        value = _first_value(
            value, "id", "node_id", "entity_id", "key", "name", "text"
        )
    elif not isinstance(value, (str, int, float, bool, bytes, tuple)):
        value = _first_attribute(
            value, "node_id", "id", "entity_id", "key", "name", "text"
        )

    if value is None:
        return None
    try:
        hash(value)
    except TypeError:
        return str(value)
    return value


def _first_value(mapping: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _first_attribute(value: Any, *names: str) -> Any:
    for name in names:
        attribute = getattr(value, name, None)
        if attribute not in (None, ""):
            return attribute
    return None


def _label_of(node_data: Any) -> Optional[str]:
    """Read a node label from a mapping entry or a node object."""
    if isinstance(node_data, dict):
        return _first_value(node_data, "label", "type", "node_type")
    return _first_attribute(node_data, "node_type", "label", "type")


def _dict_node_label(graph: Dict[str, Any], node: Any) -> Optional[str]:
    """Read a node's label out of a plain graph dictionary."""
    mapping = graph.get("nodes")
    if isinstance(mapping, dict) and node in mapping:
        return _label_of(mapping[node])

    for value in _extract_nodes(graph):
        if _node_id(value) == node:
            return _label_of(value)
    return None


def graph_node_ids(graph: Any) -> List[Any]:
    """Return the node ids of any supported graph.

    NetworkX exposes ``nodes`` as a callable view, while
    :class:`~semantica.context.context_graph.ContextGraph` exposes it as a
    mapping keyed by node id. A plain ``{"entities": [...], "relationships":
    [...]}`` mapping declares its nodes under ``entities``/``nodes`` instead, so
    it is read through the same view builder the rest of the analytics use.
    """
    if isinstance(graph, dict):
        return list(build_graph_view(graph).nodes)

    nodes = getattr(graph, "nodes", None)
    if nodes is None:
        return []
    if callable(nodes):
        return list(nodes())
    return list(nodes)


def graph_node_label(graph: Any, node: Any) -> Optional[str]:
    """Read a node's label from either a mapping or an object.

    NetworkX stores node attributes in a dict, while ``ContextGraph`` stores a
    :class:`~semantica.context.context_graph.ContextNode` dataclass whose label
    is ``node_type``. A plain graph dictionary keeps its entities under
    ``entities``/``nodes``, so the label comes from the matching entry.
    """
    if isinstance(graph, dict):
        return _dict_node_label(graph, node)

    return _label_of(graph.nodes[node])


def edge_types_between(
    graph: Any,
    source: Any,
    target: Any,
    directed: bool = False,
    edge_types: Optional[EdgeTypeIndex] = None,
) -> Optional[Set[Any]]:
    """Collect the relationship types of every edge between two nodes.

    Returns ``None`` when the graph exposes no edge types at all, because a
    caller cannot classify a link it has no metadata for. Callers keep the
    neighbour on ``None`` and apply the filter to a set.

    A plain graph dictionary is read through its ``relationships``/``edges``
    entries and decides per edge: when an edge joining the pair declares no
    type the result is ``None``, so that link is kept, while a pair joined only
    by typed edges gets the set of their types. A ``ContextGraph`` or NetworkX
    graph still answers for the pair as a whole: an empty set means the two
    nodes are joined by edges that declare no type, and the filter drops them.

    ``directed`` narrows the edge-list lookup to edges that leave ``source`` and
    enter ``target``. The default reads the pair as undirected, which is what a
    community detector wants; a caller walking an outgoing adjacency list has to
    pass ``directed=True``, or a reverse edge of another type reads as a match.
    The NetworkX lookup further down is keyed by the direction it is called with
    already, so the flag changes nothing there.

    ``ContextGraph`` keeps parallel edges and its ``get_edge_data()`` returns
    only the first one, so the edge list is the only view that shows them all.
    NetworkX returns plain attributes for a simple graph and a key-to-attributes
    mapping for a multigraph.

    ``edge_types`` is an optional :func:`build_edge_type_index` result for a
    plain graph dictionary or a ``ContextGraph``. A caller classifying many
    links builds it once, so the lookup does not rescan the edge list for every
    pair.
    """
    if isinstance(graph, dict):
        return _dict_edge_types(graph, source, target, directed, edge_types)

    # Only a ContextGraph has an index here; it answers for the pair as a
    # whole, so a pair joined by untyped edges gets an empty set.
    index = edge_types if edge_types is not None else build_edge_type_index(graph)
    if index is not None:
        types: Set[Any] = set(index.by_pair.get((source, target), ()))
        if not directed:
            types |= index.by_pair.get((target, source), set())
        return types

    if hasattr(graph, "get_edge_data"):
        data = graph.get_edge_data(source, target)
        if not isinstance(data, dict) or not data:
            return set()
        is_multigraph = getattr(graph, "is_multigraph", None)
        if callable(is_multigraph) and is_multigraph():
            candidates = data.values()
        else:
            candidates = [data]
        types = set()
        for attributes in candidates:
            if isinstance(attributes, dict):
                edge_type = attributes.get("type") or attributes.get(
                    "relationship"
                )
                if edge_type:
                    types.add(edge_type)
        return types

    return None
