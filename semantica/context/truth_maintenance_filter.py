"""Grounded context filtering against truth maintenance snapshots.

This module validates cached :class:`~semantica.context.context_retriever.RetrievedContext`
items against an immutable :class:`~semantica.reasoning.TruthMaintenanceSnapshot`
before they are ranked or merged. Candidates whose declared dependencies are no
longer supported by the session are removed, while program-integration errors
(wrong argument types, stale snapshots) raise explicit exceptions.

The filter is deliberately decoupled from the retrieval stack: it only sees
candidates plus a snapshot that the caller obtained from the same filter.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any, List, Tuple

from semantica.reasoning import TruthMaintenanceSession, TruthMaintenanceSnapshot
from semantica.reasoning._truth_maintenance_validation import validate_fact_text
from semantica.utils.exceptions import ProcessingError, ValidationError

if TYPE_CHECKING:  # pragma: no cover - import kept out of runtime cycle
    from .context_retriever import RetrievedContext

_ANNOTATION_SCHEMA_VERSION = 1
_ANNOTATION_KEYS = frozenset(
    {
        "schema_version",
        "session_id",
        "required_facts",
        "required_support_ids",
    }
)


def _validated_dependencies(
    annotation: Any,
    *,
    filter_session_id: str,
) -> Tuple[frozenset, frozenset]:
    """Validate a ``truth_maintenance`` annotation and normalize its sets.

    Returns the normalized (facts, support_ids) pair. Any violation of the
    schema raises ``ValueError``; the caller translates that into per-candidate
    exclusion.
    """

    if not isinstance(annotation, dict):
        raise ValueError("truth_maintenance annotation must be a dict")
    keys = set(annotation.keys())
    if keys != set(_ANNOTATION_KEYS):
        raise ValueError(
            "truth_maintenance annotation must contain exactly "
            "schema_version, session_id, required_facts, "
            "required_support_ids"
        )

    schema_version = annotation["schema_version"]
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError("schema_version must be an integer")
    if schema_version != _ANNOTATION_SCHEMA_VERSION:
        raise ValueError("unsupported truth_maintenance schema_version")

    session_id = annotation["session_id"]
    if not isinstance(session_id, str) or not session_id or session_id.strip() != session_id:
        raise ValueError("session_id must be a non-empty string without surrounding whitespace")
    if session_id != filter_session_id:
        raise ValueError("annotation belongs to a different truth maintenance session")

    raw_facts = annotation["required_facts"]
    raw_supports = annotation["required_support_ids"]
    for raw_value in (raw_facts, raw_supports):
        if not isinstance(raw_value, list):
            raise ValueError("dependency lists must be lists")
    if not raw_facts and not raw_supports:
        raise ValueError("at least one required fact or support id must be declared")

    facts = set()
    for raw_fact in raw_facts:
        if not isinstance(raw_fact, str):
            raise ValueError("required_facts entries must be strings")
        try:
            facts.add(validate_fact_text(raw_fact))
        except ValidationError as exc:
            raise ValueError(f"invalid required fact: {exc.message}") from exc

    support_ids = set()
    for raw_support in raw_supports:
        if not isinstance(raw_support, str):
            raise ValueError("required_support_ids entries must be strings")
        if not raw_support or raw_support.strip() != raw_support:
            raise ValueError(
                "support ids must be non-empty strings without surrounding whitespace"
            )
        support_ids.add(raw_support)

    return frozenset(facts), frozenset(support_ids)


def _attachment_metadata(member: Any) -> Any:
    """Return the metadata dict of a graph attachment member."""

    if not isinstance(member, dict):
        raise ValueError("graph attachments must be dicts")
    metadata = member.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("graph attachments must carry a metadata dict")
    return metadata


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
        if not isinstance(session_id, str) or not session_id or session_id.strip() != session_id:
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
    ) -> List[RetrievedContext]:
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
        results: List[RetrievedContext] = []
        for candidate in candidates:
            if not isinstance(candidate, RetrievedContext):
                raise ValidationError(
                    "candidates must be RetrievedContext instances",
                    validation_context={"candidate_type": type(candidate).__name__},
                )
            if self._candidate_is_grounded(candidate, snapshot=snapshot, active_ids=active_ids):
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
            root_facts, root_supports = _validated_dependencies(
                root_metadata.get("truth_maintenance"),
                filter_session_id=self._session_id,
            )
            entity_facts, entity_supports = self._validate_attachments(
                candidate.related_entities
            )
            rel_facts, rel_supports = self._validate_attachments(
                candidate.related_relationships
            )
        except ValueError:
            return False

        required_facts = root_facts | entity_facts | rel_facts
        required_supports = root_supports | entity_supports | rel_supports
        if not required_facts.issubset(snapshot.facts):
            return False
        if not required_supports.issubset(active_ids):
            return False
        return True

    def _validate_attachments(
        self, attachments: Any
    ) -> Tuple[frozenset, frozenset]:
        """Validate attachment annotations and accumulate their dependencies."""

        facts: set = set()
        support_ids: set = set()
        if not isinstance(attachments, Sequence) or isinstance(
            attachments, (str, bytes, bytearray)
        ):
            raise ValueError("graph attachments must be lists")
        for member in attachments:
            metadata = _attachment_metadata(member)
            member_facts, member_supports = _validated_dependencies(
                metadata.get("truth_maintenance"),
                filter_session_id=self._session_id,
            )
            facts.update(member_facts)
            support_ids.update(member_supports)
        return frozenset(facts), frozenset(support_ids)