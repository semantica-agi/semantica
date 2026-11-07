"""Validation helpers for SKOS graph relationships."""

from collections import defaultdict
from typing import Iterable, Mapping


_HIERARCHY_EDGE_TYPES = frozenset({"skos:broader", "skos:narrower"})


def is_skos_hierarchy_edge(edge: Mapping[str, object]) -> bool:
    """Return whether an edge uses a SKOS hierarchy predicate."""
    if not isinstance(edge, Mapping):
        return False
    return any(
        edge.get(key) in _HIERARCHY_EDGE_TYPES
        for key in ("type", "edge_type", "relationship", "predicate", "relation")
    )


def _child_parent(edge: Mapping[str, object]) -> tuple[str, str] | None:
    """Normalize a SKOS hierarchy edge to a ``(child, parent)`` pair, or ``None``."""
    if not isinstance(edge, Mapping) or not is_skos_hierarchy_edge(edge):
        return None
    edge_type = next(
        (
            edge.get(key)
            for key in ("type", "edge_type", "relationship", "predicate", "relation")
            if edge.get(key) in _HIERARCHY_EDGE_TYPES
        ),
        None,
    )
    if edge_type not in _HIERARCHY_EDGE_TYPES:
        return None

    # ``or`` rather than ``dict.get(key, fallback)``: the primary key can be
    # present and empty (a mapper that emits source=None), which the graph's
    # own endpoint normalisation treats as "use the fallback".
    raw_source = edge.get("source") or edge.get("source_id")
    raw_target = edge.get("target") or edge.get("target_id")
    if raw_source is None or raw_target is None:
        return None
    source = str(raw_source).strip()
    target = str(raw_target).strip()
    if not source or not target:
        return None

    return (source, target) if edge_type == "skos:broader" else (target, source)


def validate_skos_hierarchy(
    new_edges: Iterable[Mapping[str, object]],
    existing_edges: Iterable[Mapping[str, object]] = (),
    *,
    strict: bool = False,
) -> None:
    """Raise ``ValueError`` when adding ``new_edges`` would introduce a cycle.

    ``skos:broader`` points from a concept to its parent while
    ``skos:narrower`` expresses the same relationship in the opposite
    direction. Both forms are normalized to child-to-parent adjacency before
    cycle detection.

    ``existing_edges`` supplies the SKOS hierarchy edges already persisted in
    the graph so that cycles spanning old and new edges are still caught.

    Edges that use a hierarchy predicate but carry no usable ``source`` or
    ``target`` are skipped by default, which is the behaviour the tests have
    pinned since the function was added. Pass ``strict=True`` to turn that into
    a ``ValueError`` instead: a batch from a mapper that forgot to fill the
    endpoints is a caller error, and skipping it reports a malformed input as a
    validated hierarchy. Edges that are not hierarchy edges at all are always
    ignored.

    ``strict`` recognises the endpoints under the names ``source`` and
    ``source_id`` (and ``target`` / ``target_id``). The graph write layer also
    accepts ``from``, ``to``, ``:START_ID`` and other spellings; an edge that
    uses one of those is read by the write layer but looks endpoint-less here,
    so it raises under ``strict``. Callers that pass raw, unmapped edges should
    normalise the endpoint field names first.

    Note that an edge counts as a hierarchy edge when any of ``type``,
    ``edge_type``, ``relationship``, ``predicate`` or ``relation`` carries a
    SKOS hierarchy value. An edge that pairs a hierarchy predicate in one of
    those fields with an unrelated value in another is therefore treated as a
    hierarchy edge, and under ``strict`` it raises if it has no endpoints.
    Only the concepts touched by ``new_edges`` are checked, though: a cycle
    that already exists entirely within ``existing_edges`` must not block an
    unrelated write elsewhere in the graph.
    """
    parents: dict[str, set[str]] = defaultdict(set)
    for edge in existing_edges:
        pair = _child_parent(edge)
        if pair is not None:
            parents[pair[0]].add(pair[1])

    touched: set[str] = set()
    for edge in new_edges:
        pair = _child_parent(edge)
        if pair is None:
            if strict and is_skos_hierarchy_edge(edge):
                raise ValueError(
                    "SKOS hierarchy edge is missing source or target: %r" % (dict(edge),)
                )
            continue
        child, parent = pair
        parents[child].add(parent)
        touched.add(child)
        touched.add(parent)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(concept: str) -> None:
        if concept in visiting:
            raise ValueError(f"SKOS hierarchy contains a cycle involving '{concept}'.")
        if concept in visited:
            return

        visiting.add(concept)
        for parent in parents.get(concept, ()):
            visit(parent)
        visiting.remove(concept)
        visited.add(concept)

    for concept in touched:
        visit(concept)
