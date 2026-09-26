"""Registration and view-alignment behavior of the artifact index."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from semantica.context import TruthSnapshotProvider
from semantica.context._context_dependencies import evaluate_artifact
from semantica.context.context_artifact_index import ContextArtifactIndex
from semantica.context.grounded_context_types import (
    ContextDependencies,
    ContextReadView,
    SnapshotStamp,
)
from semantica.reasoning import FactSupport, TruthMaintenanceSession
from semantica.utils.exceptions import ValidationError

from tests.context.grounded_helpers import artifact

NAMESPACE = "rag-test"


def session_with_view(*assertions):
    session = TruthMaintenanceSession(rules=[])
    if assertions:
        session.apply(assertions=list(assertions))
    provider = TruthSnapshotProvider(session, namespace=NAMESPACE)
    return session, provider, provider.capture()


def test_source_loss_invalidates_citation_and_its_summary_but_not_fact_text():
    session, provider, before = session_with_view(
        FactSupport("s1", "A(x)"), FactSupport("s2", "A(x)")
    )
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(
        artifact(
            before,
            "cite-s1",
            kind="citation",
            facts=(),
            supports=("s1",),
            policy="dependencies",
        )
    )
    index.register(
        artifact(before, "cited-summary", policy="dependencies", citations=("cite-s1",))
    )
    index.register(artifact(before, "fact-only", policy="dependencies"))
    assert not index.reconcile(before)
    session.apply(retractions=["s1"])
    report = index.reconcile(provider.capture())
    assert report.invalidated_ids == ("cite-s1", "cited-summary")
    assert report.reactivated_ids == ()
    reasons = {e.object_id: e.reason for e in report.exclusions}
    assert reasons == {
        "cite-s1": "missing_support",
        "cited-summary": "invalid_citation",
    }
    assert "A(x)" in session.facts


def test_snapshot_policy_summary_is_invalidated_by_pure_addition():
    session, provider, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(artifact(view, "snap-summary"))
    assert not index.reconcile(view)
    session.apply(assertions=[FactSupport("s2", "B(x)")])
    report = index.reconcile(provider.capture())
    assert report.invalidated_ids == ("snap-summary",)
    reasons = {e.object_id: e.reason for e in report.exclusions}
    assert reasons == {"snap-summary": "snapshot_mismatch"}


def test_dependencies_policy_artifact_reactivates_when_support_returns():
    session, provider, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(
        artifact(view, "dep-summary", policy="dependencies", facts=(), supports=("s1",))
    )
    assert not index.reconcile(view)
    session.apply(retractions=["s1"])
    report = index.reconcile(provider.capture())
    assert report.invalidated_ids == ("dep-summary",)
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    report = index.reconcile(provider.capture())
    assert report.reactivated_ids == ("dep-summary",)
    assert report.invalidated_ids == ()


def test_duplicate_registration_is_idempotent_but_changes_are_rejected():
    _, _, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    original = artifact(view, "summary-v1")
    index.register(original)
    revision = index.revision
    index.register(original)
    assert index.revision == revision
    assert len(index.snapshot().artifacts) == 1
    for mutated in (
        replace(original, content="different"),
        replace(original, validity_policy="dependencies"),
        replace(original, dependencies=ContextDependencies(frozenset({"B(x)"}))),
    ):
        with pytest.raises(ValidationError):
            index.register(mutated)
    assert index.revision == revision


def test_registration_rejects_bad_references_without_touching_revision():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    view = TruthSnapshotProvider(session, namespace=NAMESPACE).capture()
    foreign_view = TruthSnapshotProvider(
        TruthMaintenanceSession(rules=[]), namespace="other"
    ).capture()
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(
        artifact(
            view,
            "cite-s1",
            kind="citation",
            facts=(),
            supports=("s1",),
            policy="dependencies",
        )
    )
    index.register(artifact(view, "a-summary", policy="dependencies"))
    revision = index.revision
    bad_artifacts = [
        # citations must use the dependencies policy and name a support id
        artifact(
            view,
            "bad-snap-citation",
            kind="citation",
            facts=(),
            supports=("s1",),
            policy="snapshot",
        ),
        artifact(
            view,
            "bad-fact-citation",
            kind="citation",
            facts=("A(x)",),
            policy="dependencies",
        ),
        # a citation must not reference other artifacts
        artifact(
            view,
            "bad-citing-citation",
            kind="citation",
            facts=(),
            supports=("s1",),
            policy="dependencies",
            citations=("cite-s1",),
        ),
        # summaries may only cite known citations
        artifact(view, "bad-unknown-citation", citations=("ghost",)),
        artifact(view, "bad-summary-citation", citations=("a-summary",)),
        # at least one fact or support must be declared
        artifact(view, "bad-empty-deps", facts=(), supports=()),
        # built_from must belong to the index namespace
        artifact(foreign_view, "bad-namespace"),
    ]
    for bad in bad_artifacts:
        with pytest.raises(ValidationError):
            index.register(bad)
    with pytest.raises(ValidationError):
        index.register(artifact(view, "bad id"))
    with pytest.raises(ValidationError):
        index.register("not-an-artifact")
    assert index.revision == revision
    assert len(index.snapshot().artifacts) == 2


def test_reconcile_rejects_historical_or_foreign_views():
    session, provider, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(artifact(view, "summary-v1"))
    assert not index.reconcile(view)
    moment = datetime(2026, 9, 23, tzinfo=timezone.utc)
    temporal_stamp = SnapshotStamp(
        namespace=NAMESPACE,
        source_kind="temporal",
        graph_revision=0,
        valid_at=moment,
        known_at=moment,
    )
    historical = ContextReadView(
        stamp=temporal_stamp,
        read_kind="historical",
        facts=frozenset(),
        active_supports=(),
    )
    with pytest.raises(ValidationError):
        index.reconcile(historical)
    foreign = TruthSnapshotProvider(
        TruthMaintenanceSession(rules=[]), namespace="other"
    ).capture()
    with pytest.raises(ValidationError):
        index.reconcile(foreign)
    with pytest.raises(ValidationError):
        index.reconcile("not-a-view")


def test_new_registration_is_evaluated_against_a_repeated_view():
    _, _, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(artifact(view, "fact-only", policy="dependencies"))
    assert not index.reconcile(view)
    index.register(
        artifact(view, "missing-fact", policy="dependencies", facts=("B(x)",))
    )
    report = index.reconcile(view)
    assert report.invalidated_ids == ("missing-fact",)
    reasons = {e.object_id: e.reason for e in report.exclusions}
    assert reasons == {"missing-fact": "missing_fact"}


def test_skipped_intermediate_views_reconcile_on_the_net_result():
    session, provider, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(
        artifact(view, "dep-summary", policy="dependencies", facts=(), supports=("s1",))
    )
    index.register(artifact(view, "snap-summary"))
    assert not index.reconcile(view)
    session.apply(retractions=["s1"])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    report = index.reconcile(provider.capture())
    assert report.reactivated_ids == ()
    assert report.invalidated_ids == ("snap-summary",)
    assert "dep-summary" not in report.invalidated_ids


def test_reconcile_never_changes_the_registry_revision():
    session, provider, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(artifact(view, "summary-v1"))
    revision = index.revision
    assert not index.reconcile(view)
    session.apply(retractions=["s1"])
    report = index.reconcile(provider.capture())
    assert report.invalidated_ids == ("summary-v1",)
    assert not index.reconcile(provider.capture())
    assert index.revision == revision


def test_evaluate_artifact_reason_codes():
    session, provider, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(
        artifact(
            view,
            "cite-s1",
            kind="citation",
            facts=(),
            supports=("s1",),
            policy="dependencies",
        )
    )
    index.register(
        artifact(view, "cited-summary", policy="dependencies", citations=("cite-s1",))
    )
    index.register(artifact(view, "snap-summary"))
    index.register(
        artifact(view, "needs-facts", policy="dependencies", facts=("A(x)", "B(x)"))
    )
    index.register(
        artifact(
            view, "needs-supports", policy="dependencies", facts=(), supports=("s2",)
        )
    )
    registry = index.snapshot()

    assert evaluate_artifact("cite-s1", registry=registry, view=view) is None
    assert evaluate_artifact("cited-summary", registry=registry, view=view) is None
    assert evaluate_artifact("snap-summary", registry=registry, view=view) is None
    assert (
        evaluate_artifact("ghost", registry=registry, view=view) == "unknown_artifact"
    )
    assert (
        evaluate_artifact("needs-facts", registry=registry, view=view) == "missing_fact"
    )
    assert (
        evaluate_artifact("needs-supports", registry=registry, view=view)
        == "missing_support"
    )

    # A pure addition keeps every dependency but moves the snapshot stamp.
    session.apply(assertions=[FactSupport("s2", "A(x)")])
    later = provider.capture()
    assert (
        evaluate_artifact("snap-summary", registry=registry, view=later)
        == "snapshot_mismatch"
    )
    assert evaluate_artifact("cited-summary", registry=registry, view=later) is None

    # Losing the cited support invalidates the citation and its summary.
    session.apply(retractions=["s1"])
    final = provider.capture()
    assert (
        evaluate_artifact("cite-s1", registry=registry, view=final) == "missing_support"
    )
    assert (
        evaluate_artifact("cited-summary", registry=registry, view=final)
        == "invalid_citation"
    )


def test_evaluate_artifact_reports_wrong_namespace_before_missing_facts():
    _, _, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(artifact(view, "summary-v1", policy="dependencies", facts=("B(x)",)))
    registry = index.snapshot()
    moment = datetime(2026, 9, 23, tzinfo=timezone.utc)
    foreign_view = ContextReadView(
        stamp=SnapshotStamp(namespace="other", source_kind="session", version=0),
        read_kind="live",
        facts=frozenset(),
        active_supports=(),
    )
    temporal_view = ContextReadView(
        stamp=SnapshotStamp(
            namespace=NAMESPACE,
            source_kind="temporal",
            graph_revision=0,
            valid_at=moment,
            known_at=moment,
        ),
        read_kind="live",
        facts=frozenset({"A(x)"}),
        active_supports=(FactSupport("s1", "A(x)"),),
    )
    assert (
        evaluate_artifact("summary-v1", registry=registry, view=foreign_view)
        == "wrong_namespace"
    )
    assert (
        evaluate_artifact("summary-v1", registry=registry, view=temporal_view)
        == "wrong_namespace"
    )


def test_evaluate_artifact_type_errors_raise_validation_error():
    _, _, view = session_with_view(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(artifact(view, "summary-v1"))
    registry = index.snapshot()
    with pytest.raises(ValidationError):
        evaluate_artifact(123, registry=registry, view=view)
    with pytest.raises(ValidationError):
        evaluate_artifact("summary-v1", registry="registry", view=view)
    with pytest.raises(ValidationError):
        evaluate_artifact("summary-v1", registry=registry, view="view")
