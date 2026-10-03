"""Assembly, budget and citation behavior of the grounded context assembler."""

import dataclasses

import pytest
from semantica.context import TruthSnapshotProvider
from semantica.context.context_artifact_index import ContextArtifactIndex
from semantica.context.context_retriever import ContextRetriever
from semantica.context.grounded_context import GroundedContextAssembler
from semantica.reasoning import FactSupport, TruthMaintenanceSession
from semantica.utils.exceptions import ProcessingError, ValidationError

from tests.context.grounded_helpers import (
    StaticVectorStore,
    artifact,
    retriever,
    stored_row,
)

NAMESPACE = "rag-test"


def session_with_provider(*assertions):
    session = TruthMaintenanceSession(rules=[])
    if assertions:
        session.apply(assertions=list(assertions))
    provider = TruthSnapshotProvider(session, namespace=NAMESPACE)
    return session, provider


def registered_pair(provider, *, summary_id="summary-v1"):
    """Register one citation and one summary citing it; return (index, artifacts)."""

    view = provider.capture()
    index = ContextArtifactIndex(namespace=NAMESPACE)
    citation = artifact(
        view,
        "cite-s1",
        kind="citation",
        facts=(),
        supports=("s1",),
        policy="dependencies",
        content="HR revision 1",
    )
    summary = artifact(view, summary_id, citations=("cite-s1",), policy="dependencies")
    index.register(citation)
    index.register(summary)
    return index, citation, summary


def test_budget_never_keeps_summary_without_its_citation():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    view = provider.capture()
    index = ContextArtifactIndex(namespace=NAMESPACE)
    citation = artifact(
        view,
        "cite-s1",
        kind="citation",
        facts=(),
        supports=("s1",),
        policy="dependencies",
        content="HR revision 1",
    )
    summary = artifact(view, citations=("cite-s1",))
    index.register(citation)
    index.register(summary)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary)]), provider=provider, artifacts=index
    )
    result = builder.assemble("query", max_context_chars=len("[b1] " + summary.content))
    assert result.text == ""
    assert result.blocks == result.citations == ()
    assert any(e.reason == "budget_exceeded" for e in result.exclusions)


def test_update_during_retrieval_aborts_assembly():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    summary = artifact(provider.capture())
    index = ContextArtifactIndex(namespace=NAMESPACE)
    index.register(summary)
    search = retriever([stored_row(summary)], lambda: session.apply(retractions=["s1"]))
    builder = GroundedContextAssembler(search, provider=provider, artifacts=index)
    with pytest.raises(ProcessingError):
        builder.assemble("query")


def test_invalid_high_scoring_candidate_is_excluded_before_top_k():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    ghost_row = {
        "id": "ghost",
        "content": "tampered",
        "score": 0.95,
        "metadata": {"grounded_artifact_id": "ghost"},
    }
    rows = [ghost_row, stored_row(summary, score=0.8)]
    builder = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )
    result = builder.assemble("query", max_results=1)
    assert [block.content for block in result.blocks] == [summary.content]
    assert ("ghost", "unknown_artifact") in [
        (e.object_id, e.reason) for e in result.exclusions
    ]


def test_provider_is_captured_once_and_registry_snapshotted_once():
    class CountingProvider(TruthSnapshotProvider):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.captures = 0

        def capture(self, *args, **kwargs):
            self.captures += 1
            return super().capture(*args, **kwargs)

    class CountingIndex(ContextArtifactIndex):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.snapshots = 0

        def snapshot(self):
            self.snapshots += 1
            return super().snapshot()

    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    provider = CountingProvider(session, namespace=NAMESPACE)
    index = CountingIndex(namespace=NAMESPACE)
    index.register(artifact(provider.capture()))
    builder = GroundedContextAssembler(
        retriever([stored_row(index.snapshot().artifacts[0])]),
        provider=provider,
        artifacts=index,
    )
    builder.assemble("query")
    assert provider.captures == 2  # one in the test, exactly one in assemble
    assert index.snapshots == 2  # one in the test, exactly one in assemble


def test_store_rows_are_never_mutated_by_assembly():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    original_rows = [stored_row(summary), stored_row(citation)]
    store = StaticVectorStore(original_rows)
    builder = GroundedContextAssembler(
        ContextRetriever(vector_store=store, use_graph_expansion=False),
        provider=provider,
        artifacts=index,
    )
    builder.assemble("query")
    assert store.rows == original_rows


def test_tampered_content_is_rejected_as_content_mismatch():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    row = stored_row(summary)
    row["content"] = "tampered body"
    builder = GroundedContextAssembler(
        retriever([row]), provider=provider, artifacts=index
    )
    result = builder.assemble("query")
    assert result.blocks == ()
    assert (summary.artifact_id, "content_mismatch") in [
        (e.object_id, e.reason) for e in result.exclusions
    ]


def test_unregistered_artifact_id_is_unknown_artifact():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    row = {
        "id": "ghost",
        "content": "A applies to x",
        "score": 0.9,
        "metadata": {"grounded_artifact_id": "ghost"},
    }
    index = ContextArtifactIndex(namespace=NAMESPACE)
    builder = GroundedContextAssembler(
        retriever([row]), provider=provider, artifacts=index
    )
    result = builder.assemble("query")
    assert result.blocks == ()
    assert ("ghost", "unknown_artifact") in [
        (e.object_id, e.reason) for e in result.exclusions
    ]


def test_unannotated_legacy_candidate_is_missing_annotation():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    row = {
        "id": "plain",
        "content": "plain legacy text",
        "score": 0.9,
        "metadata": {},
    }
    builder = GroundedContextAssembler(
        retriever([row]), provider=provider, artifacts=index
    )
    result = builder.assemble("query")
    assert result.blocks == ()
    assert any(e.reason == "missing_annotation" for e in result.exclusions)


def test_citation_artifact_is_rejected_as_body_text():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    builder = GroundedContextAssembler(
        retriever([stored_row(citation)]), provider=provider, artifacts=index
    )
    result = builder.assemble("query")
    assert result.blocks == ()
    assert (citation.artifact_id, "invalid_annotation") in [
        (e.object_id, e.reason) for e in result.exclusions
    ]


def test_two_blocks_share_one_citation_label():
    session, provider = session_with_provider(
        FactSupport("s1", "A(x)"), FactSupport("s2", "B(y)")
    )
    index, citation, summary = registered_pair(provider)
    summary_b = artifact(
        provider.capture(),
        "summary-b",
        facts=("B(y)",),
        content="B applies to y",
        policy="dependencies",
        citations=("cite-s1",),
    )
    index.register(summary_b)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary), stored_row(summary_b)]),
        provider=provider,
        artifacts=index,
    )
    result = builder.assemble("query")
    assert len(result.blocks) == 2
    assert len(result.citations) == 1
    assert result.citations[0].label == "c1"
    assert result.citations[0].artifact_id == citation.artifact_id
    assert result.text.count("[c1]") == 3  # two body markers plus the footnote
    assert result.text.count("Sources:\n[c1]") == 1


def test_exact_budget_boundary_is_accepted():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    view = provider.capture()
    index = ContextArtifactIndex(namespace=NAMESPACE)
    summary = artifact(view, "plain-summary", policy="dependencies")
    index.register(summary)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary)]), provider=provider, artifacts=index
    )
    exact = len("[b1] " + summary.content)
    result = builder.assemble("query", max_context_chars=exact)
    assert result.text == "[b1] " + summary.content
    assert len(result.blocks) == 1


@pytest.mark.parametrize("max_results", [1, 5])
def test_oversized_block_is_skipped_and_smaller_blocks_still_fit(max_results):
    session, provider = session_with_provider(
        FactSupport("s1", "A(x)"), FactSupport("s2", "B(y)")
    )
    view = provider.capture()
    index = ContextArtifactIndex(namespace=NAMESPACE)
    big = artifact(
        view, "big-summary", facts=("A(x)",), content="A" * 120, policy="dependencies"
    )
    small = artifact(
        view, "small-summary", facts=("B(y)",), content="B" * 10, policy="dependencies"
    )
    index.register(big)
    index.register(small)
    rows = [stored_row(big, score=0.95), stored_row(small, score=0.8)]
    builder = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )
    result = builder.assemble("query", max_results=max_results, max_context_chars=30)
    assert [block.content for block in result.blocks] == [small.content]
    assert (big.artifact_id, "budget_exceeded") in [
        (e.object_id, e.reason) for e in result.exclusions
    ]


def test_zero_budget_returns_empty_context_with_view_identity():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary)]), provider=provider, artifacts=index
    )
    result = builder.assemble("query", max_context_chars=0)
    assert result.text == ""
    assert result.blocks == result.citations == ()
    assert result.stamp == provider.capture().stamp
    assert result.artifact_revision == index.revision


def test_invalid_arguments_raise_validation_error():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary)]), provider=provider, artifacts=index
    )
    with pytest.raises(ValidationError):
        builder.assemble("")
    with pytest.raises(ValidationError):
        builder.assemble("   ")
    with pytest.raises(ValidationError):
        builder.assemble(123)
    with pytest.raises(ValidationError):
        builder.assemble("query", max_results=0)
    with pytest.raises(ValidationError):
        builder.assemble("query", max_results=True)
    with pytest.raises(ValidationError):
        builder.assemble("query", max_context_chars=-1)
    with pytest.raises(ValidationError):
        builder.assemble("query", max_context_chars=True)


def test_no_valid_candidates_returns_empty_context():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index = ContextArtifactIndex(namespace=NAMESPACE)
    builder = GroundedContextAssembler(
        retriever([]), provider=provider, artifacts=index
    )
    result = builder.assemble("query")
    assert result.text == ""
    assert result.blocks == result.citations == result.exclusions == ()


def test_registration_during_retrieval_aborts_assembly():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    later = artifact(
        provider.capture(),
        "late-summary",
        content="late arrival",
        policy="dependencies",
    )

    def register_mid_flight():
        index.register(later)

    builder = GroundedContextAssembler(
        retriever([stored_row(summary)], register_mid_flight),
        provider=provider,
        artifacts=index,
    )
    with pytest.raises(ProcessingError):
        builder.assemble("query")


def test_returned_context_is_frozen():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary)]), provider=provider, artifacts=index
    )
    result = builder.assemble("query")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.text = "rewritten"


def test_invalidated_summary_disappears_with_its_citation():
    session, provider = session_with_provider(
        FactSupport("s1", "A(x)"), FactSupport("s2", "A(x)")
    )
    index, citation, summary = registered_pair(provider)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary)]), provider=provider, artifacts=index
    )
    before = builder.assemble("query")
    assert len(before.blocks) == 1
    assert len(before.citations) == 1
    assert "[c1]" in before.text
    session.apply(retractions=["s1"])
    after = builder.assemble("query")
    assert after.blocks == after.citations == ()
    assert "HR revision 1" not in after.text


def ordinary_row(provider, *, content="Original source", score=0.9):
    record = artifact(
        provider.capture(),
        "source",
        content=content,
        supports=("s1",),
        policy="dependencies",
    )
    row = stored_row(record, score=score)
    del row["metadata"]["grounded_artifact_id"]
    return row


def test_ordinary_candidate_keeps_source_without_citations_or_store_writes():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    row = ordinary_row(provider)
    local = retriever([row])
    builder = GroundedContextAssembler(
        local, provider=provider, artifacts=ContextArtifactIndex(namespace=NAMESPACE)
    )
    result = builder.assemble("query")
    assert result.text == "[b1] Original source"
    assert result.blocks[0].source == "vector:source"
    assert result.blocks[0].citation_ids == ()
    assert result.citations == result.exclusions == ()
    assert local.vector_store.rows == [row]


def test_ordinary_candidate_mixes_with_registered_summary():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    index, citation, summary = registered_pair(provider)
    builder = GroundedContextAssembler(
        retriever([stored_row(summary, score=0.5), ordinary_row(provider)]),
        provider=provider,
        artifacts=index,
    )
    result = builder.assemble("query")
    assert [block.source for block in result.blocks] == ["vector:source", "summary-v1"]
    assert result.blocks[0].citation_ids == ()
    assert result.blocks[1].citation_ids == ("cite-s1",)
    assert result.text == (
        "[b1] Original source\n\n[b2] A applies to x (sources: [c1])"
        "\n\nSources:\n[c1] HR revision 1"
    )


def test_ordinary_support_retraction_is_filtered_before_top_k():
    session, provider = session_with_provider(
        FactSupport("s1", "A(x)"), FactSupport("s2", "A(x)")
    )
    stale = ordinary_row(provider, score=1.0)
    current = ordinary_row(provider, content="Current source", score=0.5)
    current["metadata"]["truth_maintenance"]["required_support_ids"] = ["s2"]
    session.apply(retractions=["s1"])
    builder = GroundedContextAssembler(
        retriever([stale, current]),
        provider=provider,
        artifacts=ContextArtifactIndex(namespace=NAMESPACE),
    )
    result = builder.assemble("query", max_results=1)
    assert result.text == "[b1] Current source"
    assert [(e.object_id, e.reason) for e in result.exclusions] == [
        ("candidate:1", "missing_support")
    ]


def test_ordinary_budget_exclusion_keeps_pre_ranking_candidate_id():
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    builder = GroundedContextAssembler(
        retriever(
            [
                ordinary_row(provider, content="Small", score=0.5),
                ordinary_row(provider, content="Too long for this budget", score=1.0),
            ]
        ),
        provider=provider,
        artifacts=ContextArtifactIndex(namespace=NAMESPACE),
    )
    result = builder.assemble(
        "query", max_results=1, max_context_chars=len("[b1] Small")
    )
    assert result.text == "[b1] Small"
    assert [(e.object_id, e.reason) for e in result.exclusions] == [
        ("candidate:2", "budget_exceeded")
    ]


@pytest.mark.parametrize("with_candidates", [False, True])
def test_mismatched_registry_namespace_fails_before_retrieval(with_candidates):
    session, provider = session_with_provider(FactSupport("s1", "A(x)"))
    local = retriever([ordinary_row(provider)] if with_candidates else [])
    builder = GroundedContextAssembler(
        local, provider=provider, artifacts=ContextArtifactIndex(namespace="other")
    )
    with pytest.raises(ValidationError, match="namespace"):
        builder.assemble("query")
    assert local.vector_store.calls == 0
