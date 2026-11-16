"""Grounded context filtering against truth maintenance snapshots.

This module validates cached retrieved context items against an immutable
:class:`~semantica.reasoning.TruthMaintenanceSnapshot` before they are ranked
or merged. Candidates whose declared dependencies are no longer supported by
the session are removed, while program-integration errors (wrong argument
types, stale snapshots) raise explicit exceptions.

The filter is deliberately decoupled from the retrieval stack: it only sees
candidates plus a snapshot that the caller obtained from the same filter.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from semantica.reasoning import TruthMaintenanceSession, TruthMaintenanceSnapshot
from semantica.utils.exceptions import ProcessingError, ValidationError

from ._context_dependencies import (
    _validated_attachments,
    _validated_dependencies,
)

if TYPE_CHECKING:  # pragma: no cover - import kept out of runtime cycle
    from .context_retriever import RetrievedContext


class TruthMaintenanceContextFilter:
    """Validate retrieved context dependencies against truth snapshots.

    The filter is bound to one :class:`TruthMaintenanceSession` and one
    ``session_id``. ``filter_contexts`` performs pure candidate validation
    against a snapshot; it never reads the live session state while the
    session may still be mutating. ``assert_current`` closes the race window
    by re-checking the session version after retrieval completed.
    """

    def __init__(
        self,
        session: TruthMaintenanceSession,
        *,
        session_id: str,
    ):
        if not isinstance(session, TruthMaintenanceSession):
            raise ValidationError(
                "session must be a TruthMaintenanceSession instance",
                validation_context={"session_type": type(session).__name__},
            )
        if (
            not isinstance(session_id, str)
            or not session_id
            or session_id.strip() != session_id
        ):
            raise ValidationError(
                "session_id must be a non-empty string without surrounding whitespace",
                validation_context={"session_id": session_id},
            )
        self._session = session
        self._session_id = session_id

    @property
    def session_id(self) -> str:
        """Identity of the truth maintenance session this filter guards."""

        return self._session_id

    def snapshot(self) -> TruthMaintenanceSnapshot:
        """Return an immutable snapshot of the bound session."""

        return self._session.snapshot()

    def filter_contexts(
        self,
        candidates: Iterable[Any],
        *,
        snapshot: TruthMaintenanceSnapshot,
    ) -> list[RetrievedContext]:
        """Return the grounded subset of ``candidates``.

        Each candidate must be a :class:`RetrievedContext`. Its root
        annotation and the annotation of every graph attachment must validate
        and be fully supported by ``snapshot``. Passing candidates are returned
        as deep copies stamped with the actual validation credentials;
        originals are never modified. Invalid annotations remove the whole
        candidate without failing the call.
        """

        from .context_retriever import RetrievedContext

        active_ids = frozenset(
            support.support_id for support in snapshot.active_supports
        )
        results: list[RetrievedContext] = []
        for candidate in candidates:
            if not isinstance(candidate, RetrievedContext):
                raise ValidationError(
                    "candidates must be RetrievedContext instances",
                    validation_context={"candidate_type": type(candidate).__name__},
                )
            if self._candidate_is_grounded(
                candidate, snapshot=snapshot, active_ids=active_ids
            ):
                copied = deepcopy(candidate)
                copied.metadata["truth_maintenance_validation"] = {
                    "session_id": self._session_id,
                    "version": snapshot.version,
                }
                results.append(copied)
        return results

    def assert_current(self, snapshot: TruthMaintenanceSnapshot) -> None:
        """Raise ``ProcessingError`` if the session moved past ``snapshot``."""

        current_version = self._session.version
        if snapshot.version != current_version:
            raise ProcessingError(
                "truth maintenance session changed during retrieval; "
                "snapshot is stale",
                processing_context={
                    "expected": snapshot.version,
                    "actual": current_version,
                },
                expected=snapshot.version,
                actual=current_version,
            )

    def _candidate_is_grounded(
        self,
        candidate: RetrievedContext,
        *,
        snapshot: TruthMaintenanceSnapshot,
        active_ids: frozenset,
    ) -> bool:
        try:
            root_metadata = candidate.metadata
            if not isinstance(root_metadata, dict):
                # A malformed store record must remove only this candidate,
                # never abort the whole filtered retrieval.
                return False
            root_facts, root_supports, root_namespace = _validated_dependencies(
                root_metadata.get("truth_maintenance")
            )
            entity_facts, entity_supports, entity_ns = _validated_attachments(
                candidate.related_entities
            )
            rel_facts, rel_supports, rel_ns = _validated_attachments(
                candidate.related_relationships
            )
        except ValueError:
            return False

        for declared in (root_namespace,) + entity_ns + rel_ns:
            if declared != self._session_id:
                return False

        required_facts = root_facts | entity_facts | rel_facts
        required_supports = root_supports | entity_supports | rel_supports
        if not required_facts.issubset(snapshot.facts):
            return False
        if not required_supports.issubset(active_ids):
            return False
        return True
