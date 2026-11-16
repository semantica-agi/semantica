"""Reason-code and legacy-equivalence tests for pure dependency validation.

The pure ``evaluate_candidate`` helper must reuse the exact annotation schema
of the legacy ``TruthMaintenanceContextFilter`` while reporting stable
exclusion reasons against an immutable :class:`ContextReadView`.
"""

import pytest
from semantica.context import (
    TruthMaintenanceContextFilter,
    TruthSnapshotProvider,
)
from semantica.context._context_dependencies import evaluate_candidate
from semantica.context.context_retriever import RetrievedContext
from semantica.reasoning import FactSupport, TruthMaintenanceSession
from semantica.utils.exceptions import ValidationError

NAMESPACE = "rag-test"
_MISSING = object()


def valid_annotation(namespace=NAMESPACE, fact="A(x)", supports=()):
    return {
        "schema_version": 1,
        "session_id": namespace,
        "required_facts": [fact] if fact is not None else [],
        "required_support_ids": list(supports),
    }


def candidate(
    annotation=_MISSING,
    *,
    content="A applies to x",
    entities=None,
    relationships=None,
    extra_metadata=None,
    metadata=None,
):
    if metadata is not None:
        return RetrievedContext(
            content=content,
            score=0.9,
            metadata=metadata,
            related_entities=entities or [],
            related_relationships=relationships or [],
        )
    built = {} if annotation is _MISSING else {"truth_maintenance": annotation}
    if extra_metadata:
        built.update(extra_metadata)
    return RetrievedContext(
        content=content,
        score=0.9,
        metadata=built,
        related_entities=entities or [],
        related_relationships=relationships or [],
    )


def attached_candidate(namespace=NAMESPACE, *, attachments):
    return candidate(
        valid_annotation(namespace, fact=None, supports=["s1"]),
        relationships=attachments,
    )


def session_view(*assertions):
    session = TruthMaintenanceSession(rules=[])
    if assertions:
        session.apply(assertions=list(assertions))
    return session, TruthSnapshotProvider(session, namespace=NAMESPACE).capture()


def test_missing_fact_is_a_candidate_exclusion():
    session = TruthMaintenanceSession(rules=[])
    view = TruthSnapshotProvider(session, namespace=NAMESPACE).capture()
    assert (
        evaluate_candidate(candidate(valid_annotation()), view=view) == "missing_fact"
    )


def test_satisfied_dependencies_pass():
    _, view = session_view(FactSupport("s1", "A(x)"))
    assert (
        evaluate_candidate(
            candidate(valid_annotation(fact="A(x)", supports=["s1"])), view=view
        )
        is None
    )


def test_support_only_candidate_passes_when_support_is_active():
    _, view = session_view(FactSupport("s1", "A(x)"))
    assert (
        evaluate_candidate(
            candidate(valid_annotation(fact=None, supports=["s1"])), view=view
        )
        is None
    )


def test_missing_support_is_a_candidate_exclusion():
    _, view = session_view(FactSupport("s1", "A(x)"))
    assert (
        evaluate_candidate(
            candidate(valid_annotation(fact=None, supports=["s2"])), view=view
        )
        == "missing_support"
    )


@pytest.mark.parametrize("metadata", [None, 123, "annotated"])
def test_unannotated_or_non_dict_metadata_is_missing_annotation(metadata):
    _, view = session_view(FactSupport("s1", "A(x)"))
    assert (
        evaluate_candidate(candidate(metadata=metadata), view=view)
        == "missing_annotation"
    )


@pytest.mark.parametrize(
    "annotation",
    [
        123,
        None,
        ["schema_version"],
        {**valid_annotation(), "extra_key": "value"},
        {k: v for k, v in valid_annotation().items() if k != "required_support_ids"},
        {**valid_annotation(), "schema_version": 2},
        {**valid_annotation(), "schema_version": "1"},
        {**valid_annotation(), "schema_version": True},
        {**valid_annotation(), "session_id": ""},
        {**valid_annotation(), "session_id": " rag"},
        {**valid_annotation(), "session_id": None},
        {**valid_annotation(), "session_id": 42},
        {**valid_annotation(), "required_facts": "A(x)"},
        {**valid_annotation(), "required_facts": 7},
        {**valid_annotation(), "required_support_ids": "s1"},
        {**valid_annotation(fact=None), "required_support_ids": []},
        {**valid_annotation(), "required_facts": [123]},
        {**valid_annotation(), "required_support_ids": [123]},
        {**valid_annotation(), "required_support_ids": [""]},
        {**valid_annotation(), "required_support_ids": [" s1"]},
    ],
)
def test_schema_violations_are_invalid_annotation(annotation):
    _, view = session_view(FactSupport("s1", "A(x)"))
    assert evaluate_candidate(candidate(annotation), view=view) == "invalid_annotation"


def test_wrong_namespace_annotation():
    _, view = session_view(FactSupport("s1", "A(x)"))
    assert (
        evaluate_candidate(
            candidate(valid_annotation(namespace="other-session")), view=view
        )
        == "wrong_namespace"
    )


def test_bad_graph_attachment_is_invalid_annotation():
    _, view = session_view(FactSupport("s1", "A(x)"))
    good_member = {"metadata": {"truth_maintenance": valid_annotation(fact=None)}}
    bad_cases = [
        {"id": "not-a-list"},
        [123],
        [{"id": "missing-metadata"}],
        [{"metadata": {}}],
        [{"metadata": {"truth_maintenance": 123}}],
        [good_member, {"metadata": {}}],
    ]
    for attachments in bad_cases:
        assert (
            evaluate_candidate(attached_candidate(attachments=attachments), view=view)
            == "invalid_annotation"
        )


def test_valid_graph_attachment_dependencies_are_merged():
    _, view = session_view(FactSupport("s1", "A(x)"))
    attachments = [
        {
            "metadata": {
                "truth_maintenance": valid_annotation(fact=None, supports=["s1"])
            }
        }
    ]
    assert (
        evaluate_candidate(attached_candidate(attachments=attachments), view=view)
        is None
    )


def test_graph_attachment_missing_fact_is_reported_as_missing_fact():
    _, view = session_view(FactSupport("s1", "A(x)"))
    attachments = [{"metadata": {"truth_maintenance": valid_annotation(fact="B(x)")}}]
    assert (
        evaluate_candidate(attached_candidate(attachments=attachments), view=view)
        == "missing_fact"
    )


def test_stale_validation_stamp_does_not_change_the_verdict():
    _, view = session_view(FactSupport("s1", "A(x)"))
    stamp = {"session_id": NAMESPACE, "version": 999}
    passing = candidate(
        valid_annotation(fact="A(x)", supports=["s1"]),
        extra_metadata={"truth_maintenance_validation": stamp},
    )
    assert evaluate_candidate(passing, view=view) is None
    foreign_stamp = {"session_id": "other-session", "version": 0}
    assert (
        evaluate_candidate(
            candidate(
                valid_annotation(fact="A(x)", supports=["s1"]),
                extra_metadata={"truth_maintenance_validation": foreign_stamp},
            ),
            view=view,
        )
        is None
    )
    failing = candidate(
        valid_annotation(fact="B(x)"),
        extra_metadata={"truth_maintenance_validation": stamp},
    )
    assert evaluate_candidate(failing, view=view) == "missing_fact"


@pytest.mark.parametrize("bad_candidate", [None, "candidate", {"content": "x"}])
def test_caller_type_errors_raise_validation_error(bad_candidate):
    _, view = session_view(FactSupport("s1", "A(x)"))
    with pytest.raises(ValidationError):
        evaluate_candidate(bad_candidate, view=view)


@pytest.mark.parametrize("bad_view", [None, "view", {"stamp": {}}])
def test_view_type_errors_raise_validation_error(bad_view):
    good = candidate(valid_annotation(fact="A(x)", supports=["s1"]))
    with pytest.raises(ValidationError):
        evaluate_candidate(good, view=bad_view)


def test_verdicts_match_the_legacy_filter():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    legacy = TruthMaintenanceContextFilter(session, session_id=NAMESPACE)
    snapshot = legacy.snapshot()
    view = TruthSnapshotProvider(session, namespace=NAMESPACE).capture()

    passing = candidate(
        valid_annotation(fact="A(x)", supports=["s1"]), content="passing"
    )
    missing_fact = candidate(valid_annotation(fact="B(x)"), content="missing-fact")
    invalid = candidate(123, content="invalid")
    wrong_ns = candidate(
        valid_annotation(namespace="other-session"), content="wrong-ns"
    )
    unannotated = candidate(content="unannotated")

    candidates = [passing, missing_fact, invalid, wrong_ns, unannotated]
    kept = legacy.filter_contexts(candidates, snapshot=snapshot)
    assert [item.content for item in kept] == [passing.content]

    expected = {
        passing.content: None,
        missing_fact.content: "missing_fact",
        invalid.content: "invalid_annotation",
        wrong_ns.content: "wrong_namespace",
        unannotated.content: "missing_annotation",
    }
    for item in candidates:
        verdict = evaluate_candidate(item, view=view)
        legacy_kept = item.content in {kept_item.content for kept_item in kept}
        assert (verdict is None) == legacy_kept
        if verdict is not None:
            assert verdict == expected[item.content]
