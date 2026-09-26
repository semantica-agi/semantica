"""Internal graph view helpers shared by KG analytics modules."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


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


def graph_node_ids(graph: Any) -> List[Any]:
    """Return the node ids of any supported graph.

    NetworkX exposes ``nodes`` as a callable view, while
    :class:`~semantica.context.context_graph.ContextGraph` exposes it as a
    mapping keyed by node id.
    """
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
    is ``node_type``.
    """
    node_data = graph.nodes[node]
    if isinstance(node_data, dict):
        return node_data.get("label") or node_data.get("type")
    for attribute in ("node_type", "label", "type"):
        label = getattr(node_data, attribute, None)
        if label:
            return label
    return None


def edge_types_between(graph: Any, source: Any, target: Any) -> Optional[Set[Any]]:
    """Collect the relationship types of every edge between two nodes.

    Returns ``None`` when the graph exposes no edge types at all, because a
    caller cannot classify a link it has no metadata for. An empty set means the
    two nodes are joined by edges that declare no type. Callers keep the
    neighbour on ``None`` and apply the filter to a set.

    ``ContextGraph`` keeps parallel edges and its ``get_edge_data()`` returns
    only the first one, so the edge list is the only view that shows them all.
    NetworkX returns plain attributes for a simple graph and a key-to-attributes
    mapping for a multigraph.
    """
    edges = getattr(graph, "edges", None)
    if isinstance(edges, (list, tuple)) and any(
        hasattr(edge, "source_id") for edge in edges
    ):
        types: Set[Any] = set()
        for edge in edges:
            src = getattr(edge, "source_id", None)
            dst = getattr(edge, "target_id", None)
            if (src == source and dst == target) or (
                src == target and dst == source
            ):
                edge_type = getattr(edge, "edge_type", None)
                if edge_type:
                    types.add(edge_type)
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
