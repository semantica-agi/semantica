"""
Tests for AgnoKnowledgeGraph — relational AgentKnowledge with GraphRAG.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub agno
# ---------------------------------------------------------------------------
def _stub_agno() -> None:
    if "agno" in sys.modules:
        return

    agno = types.ModuleType("agno")

    # agno.knowledge.base
    knowledge_pkg = types.ModuleType("agno.knowledge")
    knowledge_base = types.ModuleType("agno.knowledge.base")

    class AgentKnowledge:
        def __init__(self, *a, **kw): ...  # noqa: E704
        def search(self, query, num_documents=None, filters=None): return []  # noqa: E704

    knowledge_base.AgentKnowledge = AgentKnowledge  # type: ignore
    knowledge_pkg.base = knowledge_base
    agno.knowledge = knowledge_pkg  # type: ignore

    # agno.document.base
    document_pkg = types.ModuleType("agno.document")
    document_base = types.ModuleType("agno.document.base")

    class Document:
        def __init__(self, content="", id=None, name=None, meta_data=None):
            self.content = content
            self.id = id
            self.name = name
            self.meta_data = meta_data or {}

    document_base.Document = Document  # type: ignore
    document_pkg.base = document_base
    agno.document = document_pkg  # type: ignore

    for name, mod in [
        ("agno", agno),
        ("agno.knowledge", knowledge_pkg),
        ("agno.knowledge.base", knowledge_base),
        ("agno.document", document_pkg),
        ("agno.document.base", document_base),
    ]:
        sys.modules.setdefault(name, mod)


_stub_agno()

from integrations.agno.knowledge_graph import AgnoKnowledgeGraph  # noqa: E402


class _FakeNER:
    def extract_entities(self, text):
        e = MagicMock()
        e.name = "FakeEntity"
        e.type = "ORG"
        e.confidence = 0.9
        return [e]


class _FakeRelExtractor:
    def extract_relations(self, text, entities=None):
        r = MagicMock()
        r.source = "FakeEntity"
        r.type = "RELATED_TO"
        r.target = "OtherEntity"
        r.confidence = 0.8
        return [r]


class _FakeGraphBuilder:
    def build(self, sources):
        return MagicMock()


class _DataclassNER:
    """Returns Semantica's real ``Entity`` dataclass shape (text/label, no name)."""

    def extract_entities(self, text):
        from semantica.semantic_extract.types import Entity

        return [Entity(text="Tesla", label="ORG", start_char=0, end_char=5)]


class _DataclassRelExtractor:
    """Returns Semantica's real ``Relation`` dataclass shape (subject/object)."""

    def extract_relations(self, text, entities=None):
        from semantica.semantic_extract.types import Entity, Relation

        return [
            Relation(
                subject=Entity(text="Tesla", label="ORG", start_char=0, end_char=5),
                predicate="FOUNDED_BY",
                object=Entity(text="Elon Musk", label="PERSON", start_char=17, end_char=26),
            )
        ]


class _CapturingGraphBuilder:
    def __init__(self):
        self.sources = None

    def build(self, sources):
        self.sources = sources
        return MagicMock()


class _FakeContextGraph:
    def find_nodes(self, label=None):
        node = MagicMock()
        node.label = label or "Node"
        node.node_type = "Entity"
        return [node]


class TestAgnoKnowledgeGraphInit(unittest.TestCase):

    def test_creates_with_defaults(self):
        kg = AgnoKnowledgeGraph()
        self.assertIsNotNone(kg)

    def test_creates_with_custom_components(self):
        kg = AgnoKnowledgeGraph(
            graph_builder=_FakeGraphBuilder(),
            ner_extractor=_FakeNER(),
            relation_extractor=_FakeRelExtractor(),
            context_graph=_FakeContextGraph(),
        )
        self.assertIsNotNone(kg)

    def test_num_documents_default(self):
        kg = AgnoKnowledgeGraph(num_documents=10)
        self.assertEqual(kg.num_documents, 10)


class TestAgnoKnowledgeGraphLoad(unittest.TestCase):

    def setUp(self):
        self.kg = AgnoKnowledgeGraph(
            graph_builder=_FakeGraphBuilder(),
            ner_extractor=_FakeNER(),
            relation_extractor=_FakeRelExtractor(),
            context_graph=_FakeContextGraph(),
        )

    def test_load_texts(self):
        self.kg.load(texts=["Alice works at Acme Corp.", "Bob is the CEO."])
        self.assertEqual(len(self.kg._docs), 2)

    def test_load_texts_multiple_calls_accumulate(self):
        self.kg.load(texts=["First batch"])
        self.kg.load(texts=["Second batch"])
        self.assertEqual(len(self.kg._docs), 2)

    def test_load_recreate_clears_docs(self):
        self.kg.load(texts=["Old doc"])
        self.kg.load(texts=["New doc"], recreate=True)
        self.assertEqual(len(self.kg._docs), 1)

    def test_load_documents(self):
        doc = MagicMock()
        doc.content = "Agno is a multi-agent framework."
        doc.name = "agno_intro"
        self.kg.load_documents([doc])
        self.assertEqual(len(self.kg._docs), 1)

    def test_ingest_stores_entities(self):
        self.kg._ingest_text("Tesla was founded by Elon Musk.", source="test")
        stored = self.kg._docs[-1]
        self.assertIn("entities", stored)
        self.assertTrue(len(stored["entities"]) > 0)


class TestAgnoKnowledgeGraphSearch(unittest.TestCase):

    def setUp(self):
        self.kg = AgnoKnowledgeGraph(
            graph_builder=_FakeGraphBuilder(),
            ner_extractor=_FakeNER(),
            relation_extractor=_FakeRelExtractor(),
            context_graph=_FakeContextGraph(),
        )
        self.kg.load(texts=[
            "Machine learning is a subset of artificial intelligence.",
            "Python is a popular programming language.",
            "Neural networks are inspired by the human brain.",
        ])

    def test_search_returns_list(self):
        results = self.kg.search("machine learning")
        self.assertIsInstance(results, list)

    def test_search_returns_agno_documents(self):
        results = self.kg.search("python", num_documents=2)
        self.assertTrue(len(results) <= 2)
        for doc in results:
            self.assertTrue(hasattr(doc, "content"))

    def test_search_empty_kg_returns_empty(self):
        kg = AgnoKnowledgeGraph(
            graph_builder=_FakeGraphBuilder(),
            ner_extractor=_FakeNER(),
            relation_extractor=_FakeRelExtractor(),
            context_graph=_FakeContextGraph(),
        )
        results = kg.search("anything")
        self.assertEqual(results, [])

    def test_search_num_documents_respected(self):
        results = self.kg.search("a", num_documents=1)
        self.assertTrue(len(results) <= 1)

    def test_get_graph_context(self):
        ctx = self.kg.get_graph_context("FakeEntity")
        self.assertIsInstance(ctx, str)


class TestAgnoKnowledgeGraphPathLoading(unittest.TestCase):
    """Test path-based loading with a temporary file."""

    def test_load_missing_path_warns(self):
        kg = AgnoKnowledgeGraph(
            graph_builder=_FakeGraphBuilder(),
            ner_extractor=_FakeNER(),
            relation_extractor=_FakeRelExtractor(),
            context_graph=_FakeContextGraph(),
        )
        # Should not raise even for non-existent path
        kg.load(path="/nonexistent/path/xyz")
        self.assertEqual(len(kg._docs), 0)

    def test_load_file(self):
        import tempfile, os

        kg = AgnoKnowledgeGraph(
            graph_builder=_FakeGraphBuilder(),
            ner_extractor=_FakeNER(),
            relation_extractor=_FakeRelExtractor(),
            context_graph=_FakeContextGraph(),
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test document content for loading.")
            tmp_path = f.name

        try:
            kg.load(path=tmp_path)
            self.assertEqual(len(kg._docs), 1)
        finally:
            os.unlink(tmp_path)


class TestAgnoKnowledgeGraphDataclassShapes(unittest.TestCase):
    """Real Semantica ``Entity``/``Relation`` dataclasses (text/label,
    subject/object) instead of MagicMock-shaped fakes."""

    def test_ingest_text_reads_entity_text(self):
        builder = _CapturingGraphBuilder()
        kg = AgnoKnowledgeGraph(
            graph_builder=builder,
            ner_extractor=_DataclassNER(),
            relation_extractor=_DataclassRelExtractor(),
            context_graph=_FakeContextGraph(),
        )
        kg._ingest_text("Tesla was founded by Elon Musk.", source="test")
        self.assertEqual(builder.sources[0]["entities"], ["Tesla"])


if __name__ == "__main__":
    unittest.main()
