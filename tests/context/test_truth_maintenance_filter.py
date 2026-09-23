"""Pure filtering contract for truth maintenance context dependencies."""


from copy import deepcopy

import pytest
from semantica.context import RetrievedContext, TruthMaintenanceContextFilter
from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession
from semantica.utils.exceptions import ProcessingError, ValidationError

SESSION_ID = "employment-session-1"


def item(facts, supports=(), text="Alice is eligible"):
    return RetrievedContext(
        content=text,
        score=0.9,
        source="vector:cached",
        metadata={
            "truth_maintenance": {
                "schema_version": 1,
                "session_id": SESSION_ID,
                "required_facts": list(facts),
                "required_support_ids": list(supports),
            }
        },
    )


def make_session(*rules):
    return TruthMaintenanceSession(rules=list(rules))


def test_last_support_withdrawal_excludes_cached_conclusion():
    session = make_session(Rule("ab", "ab", ["A(?x)"], "B(?x)"))
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    cached = item(["B(x)"])
    session.apply(assertions=[FactSupport("old", "A(x)")])
    assert len(gate.filter_contexts([cached], snapshot=gate.snapshot())) == 1
    session.apply(retractions=["old"])
    assert gate.filter_contexts([cached], snapshot=gate.snapshot()) == []


def test_source_replacement_invalidates_citation_but_keeps_fact():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    session.apply(assertions=[FactSupport("old", "A(x)")])
    session.apply(
        assertions=[FactSupport("new", "A(x)")], retractions=["old"]
    )
    results = gate.filter_contexts(
        [
            item(["A(x)"], text="A holds"),
            item(["A(x)"], supports=["old"], text="A according to old"),
        ],
        snapshot=gate.snapshot(),
    )
    assert [r.content for r in results] == ["A holds"]


# --- constructor validation ---


def test_constructor_rejects_non_session():
    with pytest.raises(ValidationError):
        TruthMaintenanceContextFilter(object(), session_id=SESSION_ID)


def test_constructor_rejects_blank_session_id():
    session = make_session()
    with pytest.raises(ValidationError):
        TruthMaintenanceContextFilter(session, session_id="")
    with pytest.raises(ValidationError):
        TruthMaintenanceContextFilter(session, session_id="  ")


def test_session_id_is_read_only():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    with pytest.raises(AttributeError):
        gate.session_id = "other"


# --- schema validation ---


def invalid_annotation(**overrides):
    base = {
        "schema_version": 1,
        "session_id": SESSION_ID,
        "required_facts": ["A(x)"],
        "required_support_ids": [],
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "annotation",
    [
        pytest.param(
            {k: v for k, v in invalid_annotation().items() if k != "schema_version"},
            id="missing-field",
        ),
        pytest.param(
            invalid_annotation() | {"extra": 1},
            id="extra-field",
        ),
        pytest.param(
            invalid_annotation(schema_version=True),
            id="bool-schema-version",
        ),
        pytest.param(
            invalid_annotation(schema_version=2),
            id="unknown-schema-version",
        ),
        pytest.param(
            invalid_annotation(session_id="other-session"),
            id="wrong-session",
        ),
        pytest.param(
            invalid_annotation(required_facts="A(x)"),
            id="facts-not-list",
        ),
        pytest.param(
            invalid_annotation(required_support_ids="old"),
            id="supports-not-list",
        ),
        pytest.param(
            invalid_annotation(required_facts=[], required_support_ids=[]),
            id="both-empty",
        ),
        pytest.param(
            invalid_annotation(required_facts=[None]),
            id="non-string-fact",
        ),
        pytest.param(
            invalid_annotation(required_facts=[["A(x)"]]),
            id="nested-fact",
        ),
        pytest.param(
            invalid_annotation(
                required_facts=[],
                required_support_ids=["gone"],
            ),
            id="unknown-support-id",
        ),
    ],
)
def test_invalid_annotation_removes_candidate(annotation):
    session = make_session()
    session.apply(assertions=[FactSupport("old", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = RetrievedContext(
        content="stale", score=0.9, metadata={"truth_maintenance": annotation}
    )
    assert gate.filter_contexts([candidate], snapshot=gate.snapshot()) == []


def test_missing_truth_maintenance_metadata_removes_candidate():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    plain = RetrievedContext(content="no annotations", score=0.5)
    assert gate.filter_contexts([plain], snapshot=gate.snapshot()) == []


def test_non_dict_truth_maintenance_metadata_removes_candidate():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = RetrievedContext(
        content="broken", score=0.5, metadata={"truth_maintenance": "yes"}
    )
    assert gate.filter_contexts([candidate], snapshot=gate.snapshot()) == []


def test_non_retrieved_context_candidate_raises():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    with pytest.raises(ValidationError):
        gate.filter_contexts([object()], snapshot=gate.snapshot())


def test_whitespace_fact_is_normalized():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = item(["  A( x )  "])
    results = gate.filter_contexts([candidate], snapshot=gate.snapshot())
    assert len(results) == 1


def test_duplicate_dependencies_are_normalized():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = item(["A(x)", "A(x)"], supports=["s1", "s1"])
    results = gate.filter_contexts([candidate], snapshot=gate.snapshot())
    assert len(results) == 1


# --- dependency semantics ---


def test_and_semantics_requires_every_fact():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    both = item(["A(x)", "B(x)"])
    assert gate.filter_contexts([both], snapshot=gate.snapshot()) == []


def test_or_via_multiple_rules_keeps_conclusion():
    session = make_session(
        Rule("ab", "ab", ["A(?x)"], "B(?x)"),
        Rule("cb", "cb", ["C(?x)"], "B(?x)"),
    )
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    cached = item(["B(x)"])
    session.apply(assertions=[FactSupport("c1", "C(x)")])
    assert len(gate.filter_contexts([cached], snapshot=gate.snapshot())) == 1


def test_direct_assertion_and_derived_fact_together():
    session = make_session(Rule("ab", "ab", ["A(?x)"], "B(?x)"))
    session.apply(assertions=[FactSupport("a1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = item(["A(x)", "B(x)"])
    results = gate.filter_contexts([candidate], snapshot=gate.snapshot())
    assert len(results) == 1


def test_retract_then_reactivate_restores_candidate():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = item(["A(x)"])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    assert len(gate.filter_contexts([candidate], snapshot=gate.snapshot())) == 1
    session.apply(retractions=["s1"])
    assert gate.filter_contexts([candidate], snapshot=gate.snapshot()) == []
    session.apply(assertions=[FactSupport("s2", "A(x)")])
    assert len(gate.filter_contexts([candidate], snapshot=gate.snapshot())) == 1


# --- graph bundle handling ---


def attachment(metadata=None):
    return {"id": "n1", "content": "node", "metadata": metadata or {}}


def bundle(root_metadata, related_entities):
    return RetrievedContext(
        content="root",
        score=0.9,
        metadata=root_metadata,
        related_entities=related_entities,
    )


def test_graph_bundle_requires_every_attachment_annotation():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    root = {"truth_maintenance": invalid_annotation()}
    valid_attachment = attachment(
        {"truth_maintenance": invalid_annotation(
            required_facts=[], required_support_ids=["s1"])}
    )
    unannotated_attachment = attachment()
    assert gate.filter_contexts(
        [bundle(root, [valid_attachment, unannotated_attachment])],
        snapshot=gate.snapshot(),
    ) == []
    assert len(
        gate.filter_contexts(
            [bundle(root, [valid_attachment])], snapshot=gate.snapshot()
        )
    ) == 1


def test_graph_bundle_stale_attachment_removes_whole_candidate():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    root = {"truth_maintenance": invalid_annotation()}
    stale_attachment = attachment(
        {"truth_maintenance": invalid_annotation(
            required_facts=["Old(x)"], required_support_ids=[])}
    )
    assert gate.filter_contexts(
        [bundle(root, [stale_attachment])], snapshot=gate.snapshot()
    ) == []


def test_graph_bundle_non_list_related_fields_remove_candidate():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    candidate = RetrievedContext(
        content="root",
        score=0.9,
        metadata={"truth_maintenance": invalid_annotation()},
        related_entities="not-a-list",
    )
    assert gate.filter_contexts([candidate], snapshot=gate.snapshot()) == []


def test_graph_bundle_member_without_metadata_dict_removes_candidate():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    root = {"truth_maintenance": invalid_annotation()}
    bad_member = attachment()
    bad_member.pop("metadata")
    assert gate.filter_contexts(
        [bundle(root, [bad_member])], snapshot=gate.snapshot()
    ) == []


# --- copy semantics ---


def test_passing_candidate_is_deep_copied_and_stamped():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    original = item(["A(x)"])
    results = gate.filter_contexts([original], snapshot=gate.snapshot())
    assert len(results) == 1
    stamped = results[0]
    assert stamped is not original
    assert stamped.metadata is not original.metadata
    assert stamped.metadata["truth_maintenance_validation"] == {
        "session_id": SESSION_ID,
        "version": session.version,
    }
    # Original is untouched by stamping and by later mutation of the copy.
    assert "truth_maintenance_validation" not in original.metadata
    stamped.metadata["truth_maintenance"]["session_id"] = "tampered"
    stamped.content = "tampered"
    assert original.metadata["truth_maintenance"]["session_id"] == SESSION_ID
    assert original.content == "Alice is eligible"


def test_old_validation_stamp_is_overwritten_not_trusted():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    original = item(["A(x)"])
    original.metadata["truth_maintenance_validation"] = {
        "session_id": "someone-else",
        "version": 99,
    }
    results = gate.filter_contexts([original], snapshot=gate.snapshot())
    assert results[0].metadata["truth_maintenance_validation"] == {
        "session_id": SESSION_ID,
        "version": session.version,
    }


def test_related_attachments_are_copied_not_shared():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    annotated = attachment(
        {"truth_maintenance": invalid_annotation(
            required_facts=[], required_support_ids=["s1"])}
    )
    entities = [deepcopy(annotated)]
    original = RetrievedContext(
        content="root",
        score=0.9,
        metadata={"truth_maintenance": invalid_annotation()},
        related_entities=entities,
        related_relationships=[deepcopy(annotated)],
    )
    results = gate.filter_contexts([original], snapshot=gate.snapshot())
    stamped = results[0]
    assert stamped.related_entities is not original.related_entities
    assert stamped.related_entities[0] is not original.related_entities[0]
    stamped.related_entities[0]["content"] = "tampered"
    assert original.related_entities[0]["content"] == "node"


def test_score_and_fields_are_preserved():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    original = item(["A(x)"], text="kept text")
    original.score = 0.42
    original.source = "graph:expanded"
    results = gate.filter_contexts([original], snapshot=gate.snapshot())
    stamped = results[0]
    assert stamped.score == 0.42
    assert stamped.source == "graph:expanded"
    assert stamped.content == "kept text"


# --- snapshot delegation and version gate ---


def test_snapshot_delegates_to_session():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    snap = gate.snapshot()
    assert snap == session.snapshot()


def test_assert_current_accepts_matching_version():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    gate.assert_current(gate.snapshot())


def test_assert_current_raises_processing_error_on_version_change():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    stale = gate.snapshot()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    with pytest.raises(ProcessingError) as excinfo:
        gate.assert_current(stale)
    details = excinfo.value.details if hasattr(excinfo.value, "details") else {}
    assert details.get("expected") == stale.version
    assert details.get("actual") == session.version


def test_assert_current_noop_apply_does_not_bump_version():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    snap = gate.snapshot()
    session.apply(assertions=[])
    gate.assert_current(snap)


def test_empty_input_returns_empty_list():
    session = make_session()
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    assert gate.filter_contexts([], snapshot=gate.snapshot()) == []


# --- malformed root metadata ---


@pytest.mark.parametrize(
    "broken_metadata",
    [None, ["truth_maintenance"], 42],
    ids=["none", "list", "int"],
)
def test_non_dict_root_metadata_removes_candidate_without_raising(broken_metadata):
    # A store record whose top-level metadata is not a dict must remove only
    # that candidate; the malformed record must never abort the whole call.
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = TruthMaintenanceContextFilter(session, session_id=SESSION_ID)
    broken = item(["A(x)"], text="broken record")
    broken.metadata = broken_metadata
    valid = item(["A(x)"], text="valid record")
    results = gate.filter_contexts([broken, valid], snapshot=gate.snapshot())
    assert [r.content for r in results] == ["valid record"]
