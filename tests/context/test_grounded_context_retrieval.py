"""Grounded retrieval coordination: filtering before ranking and version gating."""

from copy import deepcopy

import pytest
from semantica.context import (
    AgentContext,
    ContextGraph,
    ContextRetriever,
    RetrievedContext,
    TruthMaintenanceContextFilter,
)
from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession
from semantica.utils.exceptions import ProcessingError, ValidationError
from semantica.vector_store import VectorStore

SESSION_ID = "employment-session-1"


class StaticVectorStore:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.calls = 0

    def search(self, *, query, limit):
        self.calls += 1
        return deepcopy(self.rows[:limit])


def row(identifier, fact, score, text):
    return {
        "id": identifier,
        "score": score,
        "content": text,
        "metadata": {
            "truth_maintenance": {
                "schema_version": 1,
                "session_id": SESSION_ID,
                "required_facts": [fact],
                "required_support_ids": [],
            }
        },
    }


def make_session(*rules):
    return TruthMaintenanceSession(rules=list(rules))


def make_gate(session):
    return TruthMaintenanceContextFilter(session, session_id=SESSION_ID)


def test_invalid_candidate_is_removed_before_top_k():
    session = make_session()
    session.apply(assertions=[FactSupport("live", "Current(x)")])
    store = StaticVectorStore([
        row("stale", "Old(x)", 0.99, "stale assertion"),
        row("live", "Current(x)", 0.6, "current assertion"),
    ])
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.retrieve("assertion", max_results=1, truth_filter=gate)
    assert [r.content for r in result] == ["current assertion"]
    assert len(store.rows) == 2
    assert (
        result[0].metadata["truth_maintenance_validation"]["version"]
        == session.version
    )


def test_duplicate_text_prefixes_are_both_kept():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    shared = "same first hundred characters " * 4
    store = StaticVectorStore([
        row("one", "A(x)", 0.8, shared + " tail one"),
        row("two", "A(x)", 0.7, shared + " tail two"),
    ])
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.retrieve("query", max_results=5, truth_filter=gate)
    assert sorted(r.content[-8:] for r in result) == ["tail one", "tail two"]


def test_same_graph_node_id_candidates_are_not_merged():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = make_gate(session)
    retriever = ContextRetriever(use_graph_expansion=False)

    def graph_candidate(node_id, extra_metadata, entities):
        return gate.filter_contexts(
            [RetrievedContext(
                content=f"node {node_id}",
                score=0.8,
                source=f"graph:{node_id}",
                metadata={
                    "node_id": node_id,
                    "truth_maintenance": {
                        "schema_version": 1,
                        "session_id": SESSION_ID,
                        "required_facts": ["A(x)"],
                        "required_support_ids": [],
                    },
                    **extra_metadata,
                },
                related_entities=entities,
            )],
            snapshot=gate.snapshot(),
        )[0]

    first = graph_candidate("n1", {"marker": "first"}, [{"id": "e1", "metadata": {
        "truth_maintenance": {
            "schema_version": 1,
            "session_id": SESSION_ID,
            "required_facts": [],
            "required_support_ids": ["s1"],
        }
    }}])
    second = graph_candidate("n1", {"marker": "second"}, [{"id": "e2", "metadata": {
        "truth_maintenance": {
            "schema_version": 1,
            "session_id": SESSION_ID,
            "required_facts": [],
            "required_support_ids": ["s1"],
        }
    }}])

    merged = retriever._rank_and_merge(
        [first, second], "query", merge_duplicates=False
    )
    assert len(merged) == 2
    markers = sorted(c.metadata["marker"] for c in merged)
    assert markers == ["first", "second"]
    entity_ids = {e["id"] for c in merged for e in c.related_entities}
    assert entity_ids == {"e1", "e2"}


def test_default_merge_duplicates_keeps_original_dedup():
    retriever = ContextRetriever(use_graph_expansion=False)
    first = RetrievedContext(
        content="shared content", score=0.9, source="vector:a"
    )
    second = RetrievedContext(
        content="shared content", score=0.5, source="vector:b"
    )
    merged = retriever._rank_and_merge([first, second], "query")
    assert len(merged) == 1


class MutatingVectorStore(StaticVectorStore):
    """Vector store whose search mutates the session mid-retrieval."""

    def __init__(self, rows, session, on_search):
        super().__init__(rows)
        self.session = session
        self.on_search = on_search

    def search(self, *, query, limit):
        results = super().search(query=query, limit=limit)
        self.on_search(self.session)
        return results


def test_fact_change_during_search_raises_processing_error():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    store = MutatingVectorStore(
        [row("live", "A(x)", 0.9, "live")],
        session,
        lambda s: s.apply(retractions=["s1"]),
    )
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    with pytest.raises(ProcessingError):
        retriever.retrieve("query", max_results=5, truth_filter=gate)


def test_support_only_change_during_search_raises_processing_error():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    store = MutatingVectorStore(
        [row("live", "A(x)", 0.9, "live")],
        session,
        lambda s: s.apply(
            assertions=[FactSupport("s2", "A(x)")], retractions=["s1"]
        ),
    )
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    with pytest.raises(ProcessingError):
        retriever.retrieve("query", max_results=5, truth_filter=gate)


def test_noop_apply_during_search_succeeds():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    store = MutatingVectorStore(
        [row("live", "A(x)", 0.9, "live")],
        session,
        lambda s: s.apply(assertions=[]),
    )
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.retrieve("query", max_results=5, truth_filter=gate)
    assert [r.content for r in result] == ["live"]


def test_failed_apply_during_search_does_not_fail_retrieval():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])

    def failed_apply(s):
        with pytest.raises(ValidationError):
            s.apply(assertions=[FactSupport("bad", "NotAFact")])

    store = MutatingVectorStore(
        [row("live", "A(x)", 0.9, "live")], session, failed_apply
    )
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.retrieve("query", max_results=5, truth_filter=gate)
    assert [r.content for r in result] == ["live"]


def test_rerank_embed_callback_change_raises_processing_error():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])

    class EmbeddingMutatingStore(StaticVectorStore):
        def embed(self, text):
            session.apply(retractions=["s1"])
            return [0.1, 0.2]

    store = EmbeddingMutatingStore([row("live", "A(x)", 0.9, "live")])
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    with pytest.raises(ProcessingError):
        retriever.retrieve("query", max_results=5, truth_filter=gate)


def test_invalid_truth_filter_type_raises_validation_error():
    store = StaticVectorStore([])
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    with pytest.raises(ValidationError):
        retriever.retrieve("query", max_results=5, truth_filter="gate")


def test_filter_none_matches_default_behavior():
    rows = [
        {"id": "a", "score": 0.9, "content": "first", "metadata": {}},
        {"id": "b", "score": 0.4, "content": "second", "metadata": {}},
    ]
    default_results = ContextRetriever(
        vector_store=StaticVectorStore(rows), use_graph_expansion=False
    ).retrieve("query", max_results=5)
    none_results = ContextRetriever(
        vector_store=StaticVectorStore(rows), use_graph_expansion=False
    ).retrieve("query", max_results=5, truth_filter=None)
    assert [r.content for r in default_results] == [r.content for r in none_results]


def test_all_invalid_candidates_return_empty_without_recall():
    session = make_session()
    store = StaticVectorStore([
        row("stale1", "Old(x)", 0.99, "stale one"),
        row("stale2", "Gone(x)", 0.9, "stale two"),
    ])
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    assert retriever.retrieve("query", max_results=5, truth_filter=gate) == []
    assert store.calls == 1


def test_old_validation_stamp_is_overwritten_by_current_check():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    session.apply(retractions=["s1"])
    session.apply(assertions=[FactSupport("s2", "A(x)")])
    stale_row = row("live", "A(x)", 0.9, "live")
    stale_row["metadata"]["truth_maintenance_validation"] = {
        "session_id": "someone-else",
        "version": 99,
    }
    store = StaticVectorStore([stale_row])
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.retrieve("query", max_results=5, truth_filter=gate)
    assert result[0].metadata["truth_maintenance_validation"] == {
        "session_id": SESSION_ID,
        "version": session.version,
    }


def test_empty_store_returns_empty_list():
    session = make_session()
    store = StaticVectorStore([])
    gate = make_gate(session)
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    assert retriever.retrieve("query", max_results=5, truth_filter=gate) == []


class ExplodingLLM:
    """LLM fake; any call means the entry point failed to reject first."""

    def generate(self, prompt):
        raise AssertionError("llm provider must not be called")


class ExplodingRetriever:
    """Retriever fake; any call means the entry point failed to reject first."""

    def retrieve(self, *args, **kwargs):
        raise AssertionError("retriever must not be called")

    def query_with_reasoning(self, *args, **kwargs):
        raise AssertionError("retriever must not be called")


class ExplodingMemory:
    """Memory fake; any call means the entry point failed to reject first."""

    def retrieve(self, *args, **kwargs):
        raise AssertionError("memory store must not be called")


class StaticMemoryStore:
    """Memory source fake returning plain dict rows."""

    def __init__(self, rows):
        self.rows = deepcopy(rows)

    def retrieve(self, *, query, max_results):
        return deepcopy(self.rows[:max_results])


class MutatingMemoryStore(StaticMemoryStore):
    """Memory source fake whose retrieve mutates the session mid-retrieval."""

    def __init__(self, rows, session, on_retrieve):
        super().__init__(rows)
        self.session = session
        self.on_retrieve = on_retrieve

    def retrieve(self, *, query, max_results):
        results = super().retrieve(query=query, max_results=max_results)
        self.on_retrieve(self.session)
        return results


class StaticGraphStore:
    """Graph source fake: root row plus neighbor rows with annotations."""

    def __init__(self, root_row, neighbors):
        self.root_row = deepcopy(root_row)
        self.neighbors = deepcopy(neighbors)

    def query(self, query):
        return [deepcopy(self.root_row)]

    def get_neighbors(self, node_id, *, hops):
        return deepcopy(self.neighbors)


class MutatingGraphStore(StaticGraphStore):
    """Graph source fake whose query mutates the session mid-retrieval."""

    def __init__(self, root_row, neighbors, session, on_query):
        super().__init__(root_row, neighbors)
        self.session = session
        self.on_query = on_query

    def query(self, query):
        results = super().query(query)
        self.on_query(self.session)
        return results


def make_agent_context(with_graph):
    # Built without a graph so construction stays hermetic in environments
    # where optional KG embedding dependencies are absent; the graph branch
    # is enabled afterwards together with the injected fake retriever.
    context = AgentContext(
        vector_store=VectorStore(backend="inmemory", dimension=64),
        knowledge_graph=None,
        decision_tracking=True,
        kg_algorithms=False,
        vector_store_features=False,
    )
    if with_graph:
        context.knowledge_graph = ContextGraph()
    return context


def test_retriever_query_with_reasoning_rejects_truth_filter():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    retriever = ContextRetriever(
        vector_store=StaticVectorStore([row("live", "A(x)", 0.9, "live")]),
        use_graph_expansion=False,
    )
    with pytest.raises(ValidationError):
        retriever.query_with_reasoning(
            "query",
            llm_provider=ExplodingLLM(),
            max_results=5,
            truth_filter=make_gate(session),
        )


def test_agent_context_retrieve_rejects_truth_filter_with_graph():
    context = make_agent_context(with_graph=True)
    context._retriever = ExplodingRetriever()
    with pytest.raises(ValidationError):
        context.retrieve("query", truth_filter=make_gate(make_session()))


def test_agent_context_retrieve_rejects_truth_filter_without_graph():
    context = make_agent_context(with_graph=False)
    context._memory = ExplodingMemory()
    with pytest.raises(ValidationError):
        context.retrieve("query", truth_filter=make_gate(make_session()))


def test_agent_context_query_with_reasoning_rejects_truth_filter():
    context = make_agent_context(with_graph=True)
    context._retriever = ExplodingRetriever()
    with pytest.raises(ValidationError):
        context.query_with_reasoning(
            "query",
            llm_provider=ExplodingLLM(),
            truth_filter=make_gate(make_session()),
        )


def test_search_delegates_truth_filter():
    session = make_session()
    session.apply(assertions=[FactSupport("live", "Current(x)")])
    store = StaticVectorStore([
        row("stale", "Old(x)", 0.99, "stale assertion"),
        row("live", "Current(x)", 0.6, "current assertion"),
    ])
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.search(
        "assertion", max_results=1, truth_filter=make_gate(session)
    )
    assert [r.content for r in result] == ["current assertion"]


def test_vector_search_delegates_truth_filter():
    session = make_session()
    session.apply(assertions=[FactSupport("live", "Current(x)")])
    store = StaticVectorStore([
        row("stale", "Old(x)", 0.99, "stale assertion"),
        row("live", "Current(x)", 0.6, "current assertion"),
    ])
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    result = retriever.vector_search(
        "assertion", max_results=1, truth_filter=make_gate(session)
    )
    assert [r.content for r in result] == ["current assertion"]


def test_graph_search_delegates_truth_filter():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    graph = StaticGraphStore(
        row("live", "A(x)", 0.9, "root content"),
        [row("n1", "A(x)", 0.5, "neighbor")],
    )
    retriever = ContextRetriever(knowledge_graph=graph, use_graph_expansion=True)
    result = retriever.graph_search(
        "query", max_results=5, truth_filter=make_gate(session)
    )
    assert [r.content for r in result] == ["root content"]
    assert result[0].source == "graph:live"
    assert (
        result[0].metadata["truth_maintenance_validation"]["version"]
        == session.version
    )


def test_memory_source_candidates_are_filtered():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    memory = StaticMemoryStore([
        row("stale", "Old(x)", 0.99, "stale memory"),
        row("live", "A(x)", 0.6, "live memory"),
    ])
    retriever = ContextRetriever(memory_store=memory, use_graph_expansion=False)
    result = retriever.retrieve(
        "query", max_results=5, truth_filter=make_gate(session)
    )
    assert [r.content for r in result] == ["live memory"]
    assert result[0].source == "memory:live"
    assert (
        result[0].metadata["truth_maintenance_validation"]["version"]
        == session.version
    )


def test_graph_root_with_unsupported_neighbor_dependency_is_excluded():
    # A root whose attachment annotation declares an unsupported fact is
    # excluded as a whole: PR2 does not trim attachments and keep the root.
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    graph = StaticGraphStore(
        row("live", "A(x)", 0.9, "root content"),
        [row("n1", "Missing(x)", 0.5, "neighbor")],
    )
    retriever = ContextRetriever(knowledge_graph=graph, use_graph_expansion=True)
    assert (
        retriever.retrieve(
            "query", max_results=5, truth_filter=make_gate(session)
        )
        == []
    )


def test_graph_search_does_not_invent_annotations_from_node_id():
    # Unannotated graph nodes are excluded: node_id is not a trust signal and
    # PR2 does not auto-annotate nodes during retrieval.
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    unannotated_root = {
        "id": "plain",
        "type": "fact",
        "score": 0.9,
        "content": "plain content",
        "metadata": {},
    }
    graph = StaticGraphStore(unannotated_root, [])
    retriever = ContextRetriever(knowledge_graph=graph, use_graph_expansion=True)
    assert (
        retriever.graph_search(
            "query", max_results=5, truth_filter=make_gate(session)
        )
        == []
    )


@pytest.mark.parametrize("source_kind", ["vector", "memory", "graph"])
@pytest.mark.parametrize("apply_kind", ["noop", "failed", "retraction"])
def test_apply_state_during_multi_source_retrieval(source_kind, apply_kind):
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = make_gate(session)

    if apply_kind == "noop":

        def mutate(target_session):
            target_session.apply(assertions=[])

    elif apply_kind == "failed":

        def mutate(target_session):
            with pytest.raises(ValidationError):
                target_session.apply(assertions=[FactSupport("bad", "NotAFact")])

    else:

        def mutate(target_session):
            target_session.apply(retractions=["s1"])

    live_row = row("live", "A(x)", 0.9, "live")
    if source_kind == "vector":
        retriever = ContextRetriever(
            vector_store=MutatingVectorStore([live_row], session, mutate),
            use_graph_expansion=False,
        )
    elif source_kind == "memory":
        retriever = ContextRetriever(
            memory_store=MutatingMemoryStore([live_row], session, mutate),
            use_graph_expansion=False,
        )
    else:
        retriever = ContextRetriever(
            knowledge_graph=MutatingGraphStore(live_row, [], session, mutate),
            use_graph_expansion=True,
        )

    if apply_kind == "retraction":
        with pytest.raises(ProcessingError):
            retriever.retrieve("query", max_results=5, truth_filter=gate)
    else:
        result = retriever.retrieve("query", max_results=5, truth_filter=gate)
        assert [r.content for r in result] == ["live"]


class RecordingLLM:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return "recorded"


def test_agent_receives_no_withdrawn_conclusion():
    session = TruthMaintenanceSession(rules=[
        Rule("employment", "employment", ["Employed(?x)"], "Eligible(?x)"),
    ])
    session.apply(assertions=[FactSupport("v1", "Employed(Alice)")])
    store = StaticVectorStore([
        row("cached", "Eligible(Alice)", 0.9, "Alice is eligible"),
    ])
    retriever = ContextRetriever(vector_store=store, use_graph_expansion=False)
    gate = make_gate(session)
    llm = RecordingLLM()

    def answer():
        checked = retriever.retrieve("eligibility", truth_filter=gate)
        context = "\n".join(result.content for result in checked)
        return llm.generate("Use only this checked context:\n" + context)

    answer()
    session.apply(retractions=["v1"])
    answer()
    assert "Alice is eligible" in llm.prompts[0]
    assert "Alice is eligible" not in llm.prompts[1]
    assert store.rows[0]["content"] == "Alice is eligible"
    assert store.calls == 2


def graph_annotation(fact="A(x)", supports=()):
    return {
        "schema_version": 1,
        "session_id": SESSION_ID,
        "required_facts": [fact],
        "required_support_ids": list(supports),
    }


def test_dict_graph_prose_only_describes_relationships_the_filter_validates():
    # The filter validates at most 10 relationship attachments, so the
    # rendered prose must not describe relationships beyond that cap:
    # content and validated attachments have to stay aligned.
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = make_gate(session)

    entities = [
        {
            "id": "hub",
            "name": "hub",
            "type": "fact",
            "metadata": {"truth_maintenance": graph_annotation()},
        }
    ]
    relationships = []
    for i in range(10):
        spoke = f"spoke{i}"
        entities.append(
            {
                "id": spoke,
                "name": spoke,
                "type": "fact",
                "metadata": {"truth_maintenance": graph_annotation()},
            }
        )
        relationships.append(
            {
                "source": "hub",
                "target": spoke,
                "type": "capped",
                "metadata": {"truth_maintenance": graph_annotation()},
            }
        )
    entities.append(
        {
            "id": "overflow",
            "name": "overflow",
            "type": "fact",
            "metadata": {"truth_maintenance": graph_annotation()},
        }
    )
    relationships.append(
        {
            "source": "hub",
            "target": "overflow",
            "type": "overflowed",
            "metadata": {"truth_maintenance": graph_annotation()},
        }
    )

    retriever = ContextRetriever(
        knowledge_graph={"entities": entities, "relationships": relationships},
        use_graph_expansion=True,
    )
    result = retriever.graph_search("hub", max_results=5, truth_filter=gate)

    assert len(result) == 1
    candidate = result[0]
    assert len(candidate.related_relationships) == 10
    assert "overflow" not in candidate.content


def test_context_graph_annotations_survive_query_and_neighbor_paths():
    # End-to-end through a real ContextGraph: add_node stores the
    # annotation in node properties, query() exposes it via to_dict()
    # (properties key), and get_neighbors entries must carry a metadata
    # dict so the filter can validate neighbor attachments instead of
    # dropping every graph candidate.
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = make_gate(session)

    graph = ContextGraph()
    graph.add_node(
        "root", "fact", "root content", truth_maintenance=graph_annotation()
    )
    graph.add_node(
        "neighbor",
        "fact",
        "neighbor content",
        truth_maintenance=graph_annotation(),
    )
    graph.add_edge("root", "neighbor", "supports")

    retriever = ContextRetriever(knowledge_graph=graph, use_graph_expansion=True)
    result = retriever.graph_search("root", max_results=5, truth_filter=gate)

    assert len(result) == 1
    stamped = result[0]
    assert stamped.source == "graph:root"
    assert stamped.content == "root content"
    assert (
        stamped.metadata["truth_maintenance_validation"]["version"]
        == session.version
    )
    assert stamped.related_entities[0]["id"] == "neighbor"


def test_context_graph_stale_neighbor_annotation_excludes_candidate():
    session = make_session()
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    gate = make_gate(session)

    graph = ContextGraph()
    graph.add_node(
        "root", "fact", "root content", truth_maintenance=graph_annotation()
    )
    graph.add_node(
        "neighbor",
        "fact",
        "neighbor content",
        truth_maintenance=graph_annotation(fact="Missing(x)"),
    )
    graph.add_edge("root", "neighbor", "supports")

    retriever = ContextRetriever(knowledge_graph=graph, use_graph_expansion=True)
    assert (
        retriever.graph_search("root", max_results=5, truth_filter=gate) == []
    )
