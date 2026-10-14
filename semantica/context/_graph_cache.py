"""Session-local caching of a persisted ContextGraph's file revision."""

from __future__ import annotations

import json
import os
import stat
from copy import deepcopy
from typing import Any, Callable, Mapping, NamedTuple, Optional


class _FileRevision(NamedTuple):
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


class _PublicationUnverified(ValueError):
    """The destination may have changed, but its publication is not accepted."""


class _PersistedGraphCache:
    """Publish a replacement graph only after a complete, stable native load.

    File metadata detects native atomic replacements without reading or
    hashing the whole graph on every query. It is not a multi-writer lock or
    an admission policy for externally restored historical files.
    """

    def __init__(self) -> None:
        self.graph: Optional[Any] = None
        self.path: Optional[str] = None
        self.revision: Optional[_FileRevision] = None
        self._reload_required = False

    @staticmethod
    def _revision(path: str) -> Optional[_FileRevision]:
        try:
            source = os.stat(path)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(source.st_mode):
            raise OSError("The configured graph source is not a regular file.")
        return _FileRevision(
            source.st_dev,
            source.st_ino,
            source.st_size,
            source.st_mtime_ns,
            source.st_ctime_ns,
        )

    def get_graph(self, graph: Optional[Any], path: str) -> Any:
        """Return the cached graph or load its changed configured source."""
        if graph is not self.graph:
            # Preserve the entry points' explicit reset/injected-graph behavior.
            self.graph = graph
            self.path = None
            self.revision = None
            self._reload_required = False

        revision = self._revision(path) if path else None
        if (
            graph is not None
            and self.path == path
            and self.revision == revision
            and not self._reload_required
        ):
            return graph
        if graph is not None and self.path is None and not path:
            self.path = path
            return graph

        populated = self.path == path and (
            self._reload_required
            or (self.revision is not None and self.revision.size > 0)
        )
        if path and populated and (revision is None or revision.size == 0):
            raise ValueError(
                "A populated graph source is missing or empty; "
                "repair it before retrying."
            )

        from .context_graph import ContextGraph

        candidate = ContextGraph(advanced_analytics=True)
        if path:
            if revision is not None and revision.size > 0:
                candidate.load_from_file(path)
            if self._revision(path) != revision:
                raise ValueError(
                    "The graph source changed while loading; retry after it is stable."
                )

        self.graph = candidate
        self.path = path
        self.revision = revision
        self._reload_required = False
        return candidate

    @staticmethod
    def _snapshot(graph: Any) -> dict:
        """Detach the native JSON persistence fields, including link identity."""
        data = {
            "graph_id": graph.graph_id,
            "nodes": [node.to_dict() for node in graph.nodes.values()],
            "edges": [edge.to_dict() for edge in graph.edges],
            "links": [
                {
                    "link_id": link_id,
                    "source_node_id": source,
                    "target_node_id": target,
                    "other_graph_id": other.graph_id,
                }
                for link_id, (other, source, target) in graph._linked_graphs.items()
            ],
        }
        # The native JSON writer omits unresolved links. Refuse before saving,
        # rather than erase links merely because this session reloaded them.
        if graph._unresolved_links:
            raise ValueError("Resolve cross-graph links before persisting the graph.")
        return json.loads(json.dumps(deepcopy(data), ensure_ascii=False))

    def save_graph(self, graph: Any, path: str) -> None:
        """Adopt only a stable revision containing the complete native snapshot."""
        if (
            graph is not self.graph
            or path != self.path
            or self._reload_required
            or self._revision(path) != self.revision
        ):
            raise ValueError(
                "The graph source changed before saving; retry after reloading it."
            )
        expected = self._snapshot(graph)
        if self._revision(path) != self.revision:
            raise ValueError(
                "The graph source changed before saving; retry after reloading it."
            )
        try:
            graph.save_to_file(path)
        except Exception as exc:
            self._reload_required = True
            try:
                unchanged = self._revision(path) == self.revision
            except Exception as revision_exc:
                raise _PublicationUnverified(
                    f"Native save failed ({exc}); destination revision unavailable "
                    f"({revision_exc})."
                ) from exc
            if not unchanged:
                raise _PublicationUnverified(
                    "The native save failed after the destination changed."
                ) from exc
            self._reload_required = False
            raise
        self._reload_required = True
        try:
            verified_revision = self._revision(path)
            with open(path, "r", encoding="utf-8") as source:
                published = json.load(source)
            if (
                verified_revision is None
                or self._revision(path) != verified_revision
                or published != expected
                or self._snapshot(graph) != expected
            ):
                raise ValueError("The saved graph differs from its stable snapshot.")
        except Exception as exc:
            raise _PublicationUnverified(str(exc)) from exc
        # Do not stat again: a later publication must be noticed by get_graph.
        self.revision = verified_revision
        self._reload_required = False


class _GraphMutation:
    """Journal owned native events without claiming a callback's independent work.

    The existing graph lock serializes native writers. Reentrant audit callbacks
    still run unchanged; their nodes, edges and conflicting fields are not owned
    by this operation. External audit effects are never claimed to be reversible.
    """

    def __init__(
        self,
        graph: Any,
        path: str,
        updates: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ) -> None:
        self.graph = graph
        self.path = path
        self.updates = updates or {}

    def __enter__(self) -> "_GraphMutation":
        self.graph._lock.acquire()
        try:
            self.recording = False
            if not self.path:
                return self
            if self.graph._suspend_mutation_callback:
                raise ValueError("Persistence refused: native callbacks are suspended.")
            self.nodes_before = dict(self.graph.nodes)
            self.decisions_before = deepcopy(getattr(self.graph, "_decisions", {}))
            self.temporal_before = list(getattr(self.graph, "_temporal_index", []))
            self.buckets_before = {
                name: {
                    key: set(bucket)
                    for key, bucket in getattr(self.graph, name).items()
                }
                for name in ("node_type_index", "_decision_index", "_entity_index")
                if hasattr(self.graph, name)
            }
            self.list_keys_before = {
                name: set(getattr(self.graph, name))
                for name in ("edge_type_index", "_adjacency")
            }
            self.attributes = {
                node_id: {
                    name: (getattr(node, name), deepcopy(getattr(node, name)))
                    for name in ("properties", "metadata")
                }
                for node_id in self.updates
                if (node := self.graph.nodes.get(node_id)) is not None
            }
            self.updates = deepcopy(self.updates)
            self.owned_nodes: dict = {}
            self.owned_edges: dict = {}
            self.capture_error: Optional[Exception] = None
            self.rollback_error: Optional[Exception] = None
            self.rolled_back: Optional[bool] = None
            self.foreign_nodes: set = set()
            self.forwarding = 0
            self.callback = self.graph.mutation_callback
            self.binding = self._observe
            self.graph.mutation_callback = self.binding
            self.recording = True
            return self
        except BaseException:
            self.graph._lock.release()
            raise

    def _observe(self, operation: str, entity_id: str, payload: dict) -> None:
        if self.recording and not self.forwarding:
            try:
                if operation == "ADD_NODE":
                    node = self.graph.nodes[entity_id]
                    self.owned_nodes[entity_id] = (node, deepcopy(node))
                elif operation == "ADD_EDGE":
                    edge = self.graph._edge_index[entity_id]
                    self.owned_edges[entity_id] = (edge, deepcopy(edge))
                elif operation != "UPDATE_NODE" or entity_id not in self.updates:
                    raise ValueError(
                        "The operation emitted an unowned native mutation."
                    )
            except Exception as exc:
                # Native APIs swallow callback errors, so admission needs a latch.
                self.capture_error = exc
        elif operation in {"ADD_NODE", "UPDATE_NODE"}:
            # UPDATE_NODE emits the full node, not the fields written. A nested
            # same-value write is still foreign, so protect the overlapping node.
            self.foreign_nodes.add(entity_id)
        if self.callback is not None:
            self.forwarding += 1
            try:
                self.callback(operation, entity_id, payload)
            finally:
                self.forwarding -= 1

    def save(self, save_graph: Callable[[Any, str], None], path: str) -> None:
        """Stop ownership recording before the native publication boundary."""
        if (
            self.capture_error is not None
            or self.graph.mutation_callback is not self.binding
            or self.graph._suspend_mutation_callback
        ):
            raise ValueError("Persistence refused: mutation ownership is incomplete.")
        self.recording = False
        save_graph(self.graph, path)

    def _restore_membership(self, name: str, node_id: str) -> None:
        buckets = getattr(self.graph, name)
        before = self.buckets_before.get(name, {})
        for key in set(buckets) | set(before):
            if node_id in before.get(key, ()):
                buckets[key].add(node_id)
            elif key in buckets:
                buckets[key].discard(node_id)
            if key in buckets and not buckets[key] and key not in before:
                del buckets[key]

    def rollback(self) -> bool:
        """Restore still-owned changes; preserve conflicts and report partial undo."""
        if self.rolled_back is not None:
            return self.rolled_back
        try:
            return self._rollback()
        except Exception as exc:
            self.rollback_error = exc
            self.rolled_back = False
            return False

    def _rollback(self) -> bool:
        self.recording = False
        graph = self.graph
        complete = (
            self.capture_error is None and graph.mutation_callback is self.binding
        )
        for edge_id, (edge, snapshot) in reversed(list(self.owned_edges.items())):
            current = graph._edge_index.get(edge_id)
            if current is None:
                continue
            if current is not edge or current != snapshot:
                complete = False
                continue
            graph._drop_edge_from_indexes(edge)
            graph._edge_index.pop(edge_id)
        restored = set()
        affected = set(self.owned_nodes) | set(self.attributes)
        removable_decisions = {
            node_id
            for node_id, (node, snapshot) in self.owned_nodes.items()
            if graph.nodes.get(node_id) is node and node == snapshot
        }
        for node_id, (node, snapshot) in reversed(list(self.owned_nodes.items())):
            current = graph.nodes.get(node_id)
            original = self.nodes_before.get(node_id)
            if current is None and original is None:
                restored.add(node_id)
                continue
            if (
                current is not node
                or current != snapshot
                or node_id in self.foreign_nodes
            ):
                complete = False
                continue
            if original is not None:
                graph.nodes[node_id] = original
            elif (
                any(
                    e.source_id == node_id or e.target_id == node_id
                    for e in graph.edges
                )
                or graph._cross_graph_links_for(node_id)
                or (
                    getattr(graph, "_entity_index", {}).get(node_id, set())
                    - removable_decisions
                )
            ):
                complete = False
                continue
            else:
                graph._drop_node_from_indexes(node_id)
            self._restore_membership("node_type_index", node_id)
            restored.add(node_id)
        for node_id, maps in self.attributes.items():
            node = graph.nodes.get(node_id)
            if node is not self.nodes_before[node_id] or node_id in self.foreign_nodes:
                complete = False
                continue
            processed = set()
            exact = True
            for name, (original_map, before) in maps.items():
                current = getattr(node, name)
                if current is not original_map:
                    exact = False
                    continue
                if id(current) in processed:
                    continue
                processed.add(id(current))
                for key, expected in self.updates[node_id].items():
                    if key not in current or current[key] != expected:
                        exact = False
                        continue
                    if key in before:
                        current[key] = before[key]
                    else:
                        del current[key]
                if current != before:
                    exact = False
            if exact:
                restored.add(node_id)
            else:
                complete = False
        for node_id in affected:
            if node_id not in restored:
                current = graph.nodes.get(node_id)
                for node_type, bucket in list(graph.node_type_index.items()):
                    if current is None or node_type != current.node_type:
                        bucket.discard(node_id)
                        if (
                            not bucket
                            and node_type not in self.buckets_before["node_type_index"]
                        ):
                            del graph.node_type_index[node_type]
                if current is not None:
                    graph.node_type_index[current.node_type].add(node_id)
            if node_id in restored and hasattr(graph, "_decisions"):
                if node_id in self.decisions_before:
                    graph._decisions[node_id] = self.decisions_before[node_id]
                else:
                    graph._decisions.pop(node_id, None)
                for name in ("_decision_index", "_entity_index"):
                    self._restore_membership(name, node_id)
                graph._temporal_index = [
                    row for row in graph._temporal_index if row[0] != node_id
                ] + [row for row in self.temporal_before if row[0] == node_id]
            elif node_id in getattr(graph, "_decisions", {}) or (
                (node := graph.nodes.get(node_id)) is not None
                and (node.node_type or "").lower() == "decision"
            ):
                graph._sync_decision_from_node(node_id)
        if hasattr(graph, "_temporal_index"):
            order = {row[0]: i for i, row in enumerate(self.temporal_before)}
            graph._temporal_index.sort(
                key=lambda row: (-row[1], order.get(row[0], len(order)))
            )
        for name, keys in self.list_keys_before.items():
            buckets = getattr(graph, name)
            for key in set(buckets) - keys:
                if not buckets[key]:
                    del buckets[key]
            for key in keys:
                buckets.setdefault(key, [])
        self.rolled_back = complete
        return complete

    def failure(self, exc: Exception) -> str:
        """Keep publication and in-memory rollback acceptance separate."""
        complete = self.rollback()
        detail = f"{exc}"
        if self.rollback_error is not None:
            detail += f"; rollback failed: {self.rollback_error}"
        if isinstance(exc, _PublicationUnverified):
            status = "mutation rolled back" if complete else "rollback incomplete"
            return f"Publication unverified: {detail}; in-memory {status}."
        if not complete:
            return f"Mutation refused: in-memory rollback incomplete: {detail}"
        return f"Mutation rolled back: could not persist graph: {detail}"

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if self.path:
                if exc_type is not None:
                    self.rollback()
        finally:
            if self.path:
                if self.graph.mutation_callback is self.binding:
                    self.graph.mutation_callback = self.callback
            self.graph._lock.release()
