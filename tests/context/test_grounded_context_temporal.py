"""End-to-end temporal acceptance tests for grounded context assembly.

These tests consume only the public stack built across the four prior tasks:
a real temporal adapter ingests a revised evidence history, the provider
captures live and historical views of it, and the assembler renders grounded
context from registered summaries and citations. A late correction must
remove superseded content from the current answer while historical
coordinates still reproduce what was known at the time.
"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from semantica.context import (
    ContextArtifactIndex,
    GroundedContextAssembler,
    TruthSnapshotProvider,
)
from semantica.reasoning import Rule, TemporalTruthMaintenanceAdapter
from semantica.utils.exceptions import ProcessingError
from tests.context.grounded_helpers import artifact, retriever, stored_row

NAMESPACE = "temporal-rag"
QUESTION = "Is Alice eligible?"
CITATION_CONTENT = "HR record hr-v1 states Alice is employed at Acme"


def at(day):
    return datetime(2026, 9, day, tzinfo=timezone.utc)


def rules():
    return [Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")]


def employment_record():
    return {
        "source": "alice",
        "target": "acme",
        "type": "EMPLOYED_BY",
        "valid_from": at(1),
        "valid_until": at(30),
        "recorded_at": at(1),
        "metadata": {
            "truth_maintenance": {
                "support_id": "hr-v1",
                "fact": "Employed(Alice)",
            }
        },
    }


def temporal_graph():
    return {
        "entities": [{"id": "alice"}, {"id": "acme"}],
        "relationships": [employment_record()],
    }


def corrected_graph():
    """hr-v1 is superseded on 9/20 by a correction valid only until 9/10."""

    revised = deepcopy(temporal_graph())
    revised["relationships"][0]["superseded_at"] = "2026-09-20"
    replacement = deepcopy(employment_record())
    replacement["valid_until"] = "2026-09-10"
    replacement["recorded_at"] = "2026-09-20"
    replacement["metadata"]["truth_maintenance"]["support_id"] = "hr-v2"
    revised["relationships"].append(replacement)
    return revised


def alternative_source_graph():
    """hr-v3 re-asserts the employment once hr-v1 is superseded."""

    revised = deepcopy(temporal_graph())
    revised["relationships"][0]["superseded_at"] = "2026-09-20"
    alternative = deepcopy(employment_record())
    alternative["recorded_at"] = "2026-09-20"
    alternative["metadata"]["truth_maintenance"]["support_id"] = "hr-v3"
    revised["relationships"].append(alternative)
    return revised


def late_arrival_graph():
    """Retained new evidence that bumps the revision without new live facts."""

    revised = corrected_graph()
    revised["relationships"].append(
        {
            "source": "alice",
            "target": "acme",
            "type": "PROMOTED_TO",
            "valid_from": at(25),
            "valid_until": at(30),
            "recorded_at": at(25),
            "metadata": {
                "truth_maintenance": {
                    "support_id": "hr-v4",
                    "fact": "Senior(Alice)",
                }
            },
        }
    )
    return revised


def synced_adapter():
    adapter = TemporalTruthMaintenanceAdapter(rules=rules())
    adapter.sync(temporal_graph(), valid_at="2026-09-15", known_at="2026-09-15")
    return adapter


def build_stack(adapter):
    """Provider + index with one hr-v1 citation and one cited summary."""

    provider = TruthSnapshotProvider(adapter, namespace=NAMESPACE)
    index = ContextArtifactIndex(namespace=NAMESPACE)
    view = provider.capture()
    citation = artifact(
        view,
        "cite-hr-v1",
        content=CITATION_CONTENT,
        kind="citation",
        facts=(),
        supports=("hr-v1",),
        policy="dependencies",
    )
    summary = artifact(
        view,
        "summary-alice",
        content="Alice is eligible.",
        facts=("Eligible(Alice)",),
        citations=("cite-hr-v1",),
        policy="dependencies",
    )
    index.register(citation)
    index.register(summary)
    rows = [stored_row(citation), stored_row(summary)]
    return provider, index, rows


def live_state(adapter):
    return (
        adapter.facts,
        adapter.version,
        adapter.graph_revision,
        adapter.valid_at,
        adapter.known_at,
    )


# -- current and historical reads around one correction ---------------------


def test_current_assembly_before_correction_contains_summary_and_citation():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )

    bundle = assembler.assemble(QUESTION)

    assert bundle.text == (
        "[b1] Alice is eligible. (sources: [c1])\n\n"
        "Sources:\n"
        f"[c1] {CITATION_CONTENT}"
    )
    assert [block.source for block in bundle.blocks] == ["summary-alice"]
    assert [citation.artifact_id for citation in bundle.citations] == ["cite-hr-v1"]
    assert bundle.stamp.graph_revision == 1
    assert bundle.artifact_revision == 2
    # The citation row itself must never become a body block.
    assert [(e.object_id, e.reason) for e in bundle.exclusions] == [
        ("cite-hr-v1", "invalid_annotation")
    ]


def test_correction_empties_current_assembly():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )

    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    bundle = assembler.assemble(QUESTION)
    assert bundle.text == ""
    assert bundle.blocks == ()
    assert bundle.citations == ()
    assert {(e.object_id, e.reason) for e in bundle.exclusions} == {
        ("cite-hr-v1", "invalid_annotation"),
        ("summary-alice", "missing_fact"),
    }


def test_historical_read_still_reproduces_the_superseded_answer():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )
    before = assembler.assemble(QUESTION).text
    assert "Alice is eligible." in before

    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    historical = assembler.assemble(
        QUESTION, valid_at="2026-09-15", known_at="2026-09-15"
    )
    assert historical.text == before
    assert historical.stamp.valid_at == at(15)
    assert historical.stamp.known_at == at(15)


def test_historical_read_after_the_correction_became_known_is_empty():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )

    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    bundle = assembler.assemble(QUESTION, valid_at="2026-09-15", known_at="2026-09-20")
    assert bundle.text == ""
    assert bundle.blocks == ()
    assert bundle.citations == ()


def test_historical_reads_leave_adapter_and_index_state_untouched():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )
    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    settled = index.reconcile(provider.capture())
    assert sorted(settled.invalidated_ids) == ["cite-hr-v1", "summary-alice"]
    before = live_state(adapter)

    old_view = assembler.assemble(
        QUESTION, valid_at="2026-09-15", known_at="2026-09-15"
    )
    empty_view = assembler.assemble(
        QUESTION, valid_at="2026-09-15", known_at="2026-09-20"
    )
    assert "Alice is eligible." in old_view.text
    assert empty_view.text == ""

    assert live_state(adapter) == before
    report = index.reconcile(provider.capture())
    assert report.invalidated_ids == ()
    assert report.reactivated_ids == ()
    assert report.exclusions == ()


# -- expiry, alternative sources and mid-assembly revisions ----------------


def test_real_expiry_through_advance_empties_current_assembly():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )
    assert "Alice is eligible." in assembler.assemble(QUESTION).text

    adapter.advance(valid_at="2026-09-30", known_at="2026-09-30")

    bundle = assembler.assemble(QUESTION)
    assert bundle.text == ""
    assert bundle.blocks == ()
    assert bundle.citations == ()


def test_alternative_source_restores_the_fact_only_summary():
    adapter = synced_adapter()
    provider = TruthSnapshotProvider(adapter, namespace=NAMESPACE)
    index = ContextArtifactIndex(namespace=NAMESPACE)
    view = provider.capture()
    citation = artifact(
        view,
        "cite-hr-v1",
        content=CITATION_CONTENT,
        kind="citation",
        facts=(),
        supports=("hr-v1",),
        policy="dependencies",
    )
    cited = artifact(
        view,
        "summary-cited",
        content="Alice is eligible per the HR record.",
        facts=("Eligible(Alice)",),
        citations=("cite-hr-v1",),
        policy="dependencies",
    )
    fact_only = artifact(
        view,
        "summary-facts",
        content="Alice is eligible.",
        facts=("Eligible(Alice)",),
        policy="dependencies",
    )
    index.register(citation)
    index.register(cited)
    index.register(fact_only)
    rows = [stored_row(cited), stored_row(fact_only)]
    assembler = GroundedContextAssembler(
        retriever(rows), provider=provider, artifacts=index
    )

    before = assembler.assemble(QUESTION)
    assert "per the HR record" in before.text
    assert before.text.count("(sources: [") == 1

    adapter.sync(
        alternative_source_graph(), valid_at="2026-09-15", known_at="2026-09-20"
    )

    after = assembler.assemble(QUESTION)
    # The fact survives through hr-v3, so the facts-only summary stays; the
    # citation-bound summary correctly does not, because hr-v1 is superseded.
    assert after.text == "[b1] Alice is eligible."
    assert [block.source for block in after.blocks] == ["summary-facts"]
    assert after.citations == ()
    assert [(e.object_id, e.reason) for e in after.exclusions] == [
        ("summary-cited", "invalid_citation")
    ]


def test_live_cursor_movement_during_a_historical_assembly_is_allowed():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    def move_cursor():
        adapter.advance(valid_at="2026-09-25", known_at="2026-09-25")

    assembler = GroundedContextAssembler(
        retriever(rows, on_search=move_cursor), provider=provider, artifacts=index
    )

    bundle = assembler.assemble(QUESTION, valid_at="2026-09-15", known_at="2026-09-15")

    assert "Alice is eligible." in bundle.text
    assert adapter.valid_at == at(25)
    assert adapter.known_at == at(25)


def test_new_retained_evidence_during_a_historical_assembly_fails():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    def add_evidence():
        adapter.sync(late_arrival_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    assembler = GroundedContextAssembler(
        retriever(rows, on_search=add_evidence), provider=provider, artifacts=index
    )

    with pytest.raises(ProcessingError):
        assembler.assemble(QUESTION, valid_at="2026-09-15", known_at="2026-09-15")


# -- the exact prompt a model receives --------------------------------------


class RecordingModel:
    """A stand-in model that can only record the prompts it receives."""

    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return "recorded"


def deliver(builder, model, question, **coordinates):
    bundle = builder.assemble(question, **coordinates)
    prompt = "Context:\n" + bundle.text + "\n\nQuestion:\n" + question
    return model.generate(prompt)


def test_model_prompt_tracks_the_correction_without_touching_the_store():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    retrieval = retriever(rows)
    assembler = GroundedContextAssembler(retrieval, provider=provider, artifacts=index)
    model = RecordingModel()
    original_rows = deepcopy(retrieval.vector_store.rows)

    answer = deliver(assembler, model, QUESTION)

    assert answer == "recorded"
    assert "Alice is eligible." in model.prompts[0]
    assert CITATION_CONTENT in model.prompts[0]
    assert "Sources:" in model.prompts[0]

    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    deliver(assembler, model, QUESTION)

    assert len(model.prompts) == 2
    assert model.prompts[1] == "Context:\n\n\nQuestion:\n" + QUESTION
    assert "Alice is eligible." not in model.prompts[1]
    assert "HR record hr-v1" not in model.prompts[1]
    assert "Sources:" not in model.prompts[1]
    assert retrieval.vector_store.rows == original_rows


def test_generate_is_not_called_when_assembly_fails():
    adapter = synced_adapter()
    provider, index, rows = build_stack(adapter)
    adapter.sync(corrected_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    def add_evidence():
        adapter.sync(late_arrival_graph(), valid_at="2026-09-15", known_at="2026-09-20")

    assembler = GroundedContextAssembler(
        retriever(rows, on_search=add_evidence), provider=provider, artifacts=index
    )
    model = RecordingModel()

    with pytest.raises(ProcessingError):
        deliver(assembler, model, QUESTION)

    assert model.prompts == []
