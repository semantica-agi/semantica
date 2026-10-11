"""Session-local caching of a persisted ContextGraph's file revision."""

from __future__ import annotations

import os
import stat
from typing import Any, NamedTuple, Optional


class _FileRevision(NamedTuple):
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


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

        revision = self._revision(path) if path else None
        if graph is not None and self.path == path and self.revision == revision:
            return graph
        if graph is not None and self.path is None and not path:
            self.path = path
            return graph

        populated = (
            self.path == path and self.revision is not None and self.revision.size > 0
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
        return candidate
