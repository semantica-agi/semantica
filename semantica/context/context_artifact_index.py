"""Registry of immutable summaries and citations aligned to read views.

The index stores immutable content versions plus the reverse indices needed to
align derived availability to a new :class:`ContextReadView` incrementally.
Reconciliation never mutates registered content: it only reports which
artifacts became invalid or valid again on the supplied view.
"""

from __future__ import annotations

import re

from semantica.context._context_dependencies import evaluate_artifact
from semantica.context.grounded_context_types import (
    ArtifactInvalidationReport,
    ArtifactRegistrySnapshot,
    ContextReadView,
    Exclusion,
    GroundedArtifact,
)
from semantica.utils.exceptions import ValidationError

_ARTIFACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ContextArtifactIndex:
    """Register immutable artifacts and align them against read views."""

    def __init__(self, *, namespace: str):
        if (
            not isinstance(namespace, str)
            or not namespace
            or namespace.strip() != namespace
        ):
            raise ValidationError(
                "namespace must be a non-empty string without surrounding "
                "whitespace",
                validation_context={"namespace": namespace},
            )
        self._namespace = namespace
        self._artifacts: dict[str, GroundedArtifact] = {}
        self._revision = 0
        self._last_view: ContextReadView | None = None
        self._eligible: dict[str, bool] = {}
        self._fact_index: dict[str, set[str]] = {}
        self._support_index: dict[str, set[str]] = {}
        self._citation_users: dict[str, set[str]] = {}
        self._snapshot_ids: set[str] = set()
        self._pending: set[str] = set()

    @property
    def revision(self) -> int:
        """Content revision; only new registrations increase it."""

        return self._revision

    def snapshot(self) -> ArtifactRegistrySnapshot:
        """Return a detached copy of every registered artifact."""

        return ArtifactRegistrySnapshot(
            namespace=self._namespace,
            revision=self._revision,
            artifacts=tuple(self._artifacts.values()),
        )

    def register(self, artifact: GroundedArtifact) -> None:
        """Register one immutable content version.

        Registering the exact same artifact again is a no-op. A different
        artifact under a known ``artifact_id`` is rejected: updates must use a
        new id. Only a successful registration of new content increments
        ``revision``.
        """

        if not isinstance(artifact, GroundedArtifact):
            raise ValidationError(
                "artifact must be a GroundedArtifact instance",
                validation_context={"artifact_type": type(artifact).__name__},
            )
        if not _ARTIFACT_ID_PATTERN.match(artifact.artifact_id):
            raise ValidationError(
                "artifact_id must match [A-Za-z0-9_.:-]+",
                validation_context={"artifact_id": artifact.artifact_id},
            )
        if artifact.built_from.namespace != self._namespace:
            raise ValidationError(
                "artifact built_from namespace does not match the index " "namespace",
                validation_context={
                    "index_namespace": self._namespace,
                    "artifact_namespace": artifact.built_from.namespace,
                },
            )
        if not artifact.dependencies:
            raise ValidationError(
                "an artifact must declare at least one fact or support id"
            )
        if artifact.kind == "citation":
            if artifact.validity_policy != "dependencies":
                raise ValidationError("citations must use the dependencies policy")
            if not artifact.dependencies.required_support_ids:
                raise ValidationError("a citation must name at least one support id")
            if artifact.citation_ids:
                raise ValidationError("a citation must not reference other artifacts")
        else:
            for cited_id in artifact.citation_ids:
                cited = self._artifacts.get(cited_id)
                if cited is None:
                    raise ValidationError(
                        "summaries may only cite registered citations",
                        validation_context={"cited_id": cited_id},
                    )
                if cited.kind != "citation":
                    raise ValidationError(
                        "summaries must not cite other summaries",
                        validation_context={"cited_id": cited_id},
                    )
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None:
            if existing == artifact:
                return
            raise ValidationError(
                "artifact_id is already registered with different content; "
                "register a new artifact_id instead",
                validation_context={"artifact_id": artifact.artifact_id},
            )
        self._artifacts[artifact.artifact_id] = artifact
        for fact in artifact.dependencies.required_facts:
            self._fact_index.setdefault(fact, set()).add(artifact.artifact_id)
        for support_id in artifact.dependencies.required_support_ids:
            self._support_index.setdefault(support_id, set()).add(artifact.artifact_id)
        for cited_id in artifact.citation_ids:
            self._citation_users.setdefault(cited_id, set()).add(artifact.artifact_id)
        if artifact.validity_policy == "snapshot":
            self._snapshot_ids.add(artifact.artifact_id)
        self._pending.add(artifact.artifact_id)
        self._revision += 1

    def reconcile(self, view: ContextReadView) -> ArtifactInvalidationReport:
        """Align derived availability to ``view`` and report the changes.

        The report is computed against the full authoritative view, never
        against individual mutations, so skipping intermediate views still
        yields the correct net result. Results are staged and published in one
        step; a failure never leaves partial state behind.
        """

        if not isinstance(view, ContextReadView):
            raise ValidationError(
                "view must be a ContextReadView instance",
                validation_context={"view_type": type(view).__name__},
            )
        if view.read_kind == "historical":
            raise ValidationError(
                "reconcile requires a live view; historical reads use pure "
                "validation"
            )
        if view.stamp.namespace != self._namespace:
            raise ValidationError(
                "view namespace does not match the index namespace",
                validation_context={
                    "index_namespace": self._namespace,
                    "view_namespace": view.stamp.namespace,
                },
            )
        registry = self.snapshot()
        new_eligibility: dict[str, bool] = {}
        invalidated: list[str] = []
        reactivated: list[str] = []
        exclusions: list[Exclusion] = []
        for artifact_id in sorted(self._affected_ids(view)):
            reason = evaluate_artifact(artifact_id, registry=registry, view=view)
            new_eligibility[artifact_id] = reason is None
            if reason is not None:
                exclusions.append(Exclusion(object_id=artifact_id, reason=reason))
                if self._eligible.get(artifact_id) is not False:
                    invalidated.append(artifact_id)
            elif self._eligible.get(artifact_id) is False:
                reactivated.append(artifact_id)
        self._last_view = view
        self._eligible.update(new_eligibility)
        self._pending.clear()
        return ArtifactInvalidationReport(
            stamp=view.stamp,
            invalidated_ids=tuple(sorted(invalidated)),
            reactivated_ids=tuple(sorted(reactivated)),
            exclusions=tuple(exclusions),
        )

    def _affected_ids(self, view: ContextReadView) -> set[str]:
        """IDs whose verdict may have changed between the last view and ``view``."""

        if self._last_view is None:
            affected = set(self._artifacts)
        else:
            old_view = self._last_view
            affected = set(self._pending)
            for fact in old_view.facts ^ view.facts:
                affected.update(self._fact_index.get(fact, ()))
            for support_id in old_view.support_ids ^ view.support_ids:
                affected.update(self._support_index.get(support_id, ()))
            if old_view.stamp.source_kind != view.stamp.source_kind:
                affected.update(self._artifacts)
            elif old_view.stamp != view.stamp:
                affected.update(self._snapshot_ids)
        for artifact_id in tuple(affected):
            affected.update(self._citation_users.get(artifact_id, ()))
        return affected
