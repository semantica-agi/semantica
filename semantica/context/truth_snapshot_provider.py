"""Capture one consistent read view of a truth maintenance source.

A provider turns a :class:`~semantica.reasoning.TruthMaintenanceSession` or a
:class:`~semantica.reasoning.TemporalTruthMaintenanceAdapter` into immutable
:class:`ContextReadView` values. Capturing never mutates the source and never
re-derives facts: live reads reuse the source's own snapshot machinery, and
historical reads are recomputed only for the explicit coordinates the caller
asked about.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from semantica.reasoning import (
    TemporalTruthMaintenanceAdapter,
    TruthMaintenanceSession,
)
from semantica.utils.exceptions import ProcessingError, ValidationError

from .grounded_context_types import ContextReadView, SnapshotStamp

__all__ = ["TruthSnapshotProvider"]


class TruthSnapshotProvider:
    """Produce and freshness-check stamped read views of one truth source."""

    def __init__(self, source: Any, *, namespace: str) -> None:
        if not isinstance(namespace, str):
            raise ValidationError(
                f"namespace must be a string, got {type(namespace).__name__}"
            )
        if not namespace or namespace != namespace.strip():
            raise ValidationError(
                f"namespace must be non-empty and stripped, got {namespace!r}"
            )
        if not isinstance(
            source, (TruthMaintenanceSession, TemporalTruthMaintenanceAdapter)
        ):
            raise ValidationError(
                "source must be a TruthMaintenanceSession or a "
                f"TemporalTruthMaintenanceAdapter, got {type(source).__name__}"
            )
        self._provider_id = uuid4().hex
        self._source = source
        self._namespace = namespace
        self._source_kind = (
            "temporal"
            if isinstance(source, TemporalTruthMaintenanceAdapter)
            else "session"
        )

    @property
    def namespace(self) -> str:
        """Namespace every view captured from this provider is stamped with."""
        return self._namespace

    @property
    def source_kind(self) -> str:
        """Which kind of truth source this provider wraps."""
        return self._source_kind

    def capture(
        self,
        *,
        valid_at: Any | None = None,
        known_at: Any | None = None,
    ) -> ContextReadView:
        """Capture one immutable read view at explicit temporal coordinates.

        Session sources accept no coordinates. Temporal sources accept either
        no coordinate (the current live view) or both coordinates (a
        recomputed historical view); a single coordinate is rejected.
        """
        if self._source_kind == "session":
            if valid_at is not None or known_at is not None:
                raise ValidationError(
                    "temporal coordinates do not belong to a session capture"
                )
            return self._capture_session()
        if (valid_at is None) != (known_at is None):
            raise ValidationError(
                "temporal captures need both valid_at and known_at or neither"
            )
        if valid_at is None:
            snapshot = self._source.snapshot()
            return self._view_from_temporal(snapshot, "live")
        snapshot = self._source.query_at(valid_at=valid_at, known_at=known_at)
        return self._view_from_temporal(snapshot, "historical")

    def assert_current(self, view: Any) -> None:
        """Raise unless ``view`` still describes the current source state.

        Staleness of an already captured view raises :class:`ProcessingError`;
        anything that is not a matching view of this provider raises
        :class:`ValidationError`.
        """
        if not isinstance(view, ContextReadView):
            raise ValidationError(
                f"view must be a ContextReadView, got {type(view).__name__}"
            )
        if view.stamp.namespace != self._namespace:
            raise ValidationError(
                f"view namespace {view.stamp.namespace!r} does not match "
                f"provider namespace {self._namespace!r}"
            )
        if view.stamp.source_kind != self._source_kind:
            raise ValidationError(
                f"view source_kind {view.stamp.source_kind!r} does not match "
                f"provider source_kind {self._source_kind!r}"
            )
        if view.stamp.provider_id != self._provider_id:
            raise ValidationError("view belongs to a different provider instance")
        if self._source_kind == "session":
            if view.stamp.version != self._source.version:
                raise ProcessingError(
                    "session view is stale: captured version "
                    f"{view.stamp.version} no longer matches {self._source.version}"
                )
            return
        if view.read_kind == "historical":
            # Historical identities ignore live cursor movement: only a
            # revision of the retained evidence invalidates the archive.
            if view.stamp.graph_revision != self._source.graph_revision:
                raise ProcessingError(
                    "historical view is stale: graph revision "
                    f"{view.stamp.graph_revision} no longer matches "
                    f"{self._source.graph_revision}"
                )
            return
        current = self._source.snapshot()
        if (
            view.stamp.graph_revision != current.graph_revision
            or view.stamp.valid_at != current.valid_at
            or view.stamp.known_at != current.known_at
        ):
            raise ProcessingError(
                "live temporal view is stale: captured identity "
                f"{view.stamp.graph_revision}/{view.stamp.valid_at}/"
                f"{view.stamp.known_at} no longer matches "
                f"{current.graph_revision}/{current.valid_at}/{current.known_at}"
            )

    def _capture_session(self) -> ContextReadView:
        state = self._source.snapshot()
        stamp = SnapshotStamp(
            namespace=self._namespace,
            provider_id=self._provider_id,
            source_kind="session",
            version=state.version,
        )
        return ContextReadView(
            stamp=stamp,
            read_kind="live",
            facts=state.facts,
            active_supports=state.active_supports,
        )

    def _view_from_temporal(self, snapshot: Any, read_kind: str) -> ContextReadView:
        stamp = SnapshotStamp(
            namespace=self._namespace,
            provider_id=self._provider_id,
            source_kind="temporal",
            graph_revision=snapshot.graph_revision,
            valid_at=snapshot.valid_at,
            known_at=snapshot.known_at,
        )
        return ContextReadView(
            stamp=stamp,
            read_kind=read_kind,
            facts=snapshot.facts,
            active_supports=snapshot.active_supports,
        )
