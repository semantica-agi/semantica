"""Semantic ranking in the MCP server: find_precedents re-ranking and search_knowledge."""

import importlib.util

import pytest

from semantica import mcp_server
from semantica.context import ContextGraph
from semantica.mcp_server import semantic

HAS_FASTEMBED = importlib.util.find_spec("fastembed") is not None


@pytest.fixture
def graph(monkeypatch):
    g = ContextGraph()
    monkeypatch.setattr(mcp_server, "_get_graph", lambda: g)
    g.record_decision(
        category="storage",
        scenario="Choose table format for ADS phase 1B: StarRocks native tables vs Apache Iceberg",
        reasoning="parallel ingestion until December",
        outcome="pending",
        confidence=0.5,
    )
    g.record_decision(
        category="tooling",
        scenario="Pick a formatter for the Scala monorepo",
        reasoning="consistent style",
        outcome="scalafmt",
        confidence=0.9,
    )
    g.add_node(
        "finding:1",
        "Finding",
        "StarRocks mapper rejects mistyped column values instead of writing nulls",
    )
    g.add_node("finding:2", "Finding", "Team lunch moved to Thursday")
    return g


def test_search_knowledge_requires_query(graph):
    assert "error" in mcp_server._tool_search_knowledge({})


def test_lexical_fallback_when_disabled(graph, monkeypatch):
    monkeypatch.setenv("SEMANTICA_SEMANTIC_SEARCH", "false")
    out = mcp_server._tool_find_precedents(
        {"scenario": "Scala formatter", "max_results": 2}
    )
    assert out["method"] == "lexical"
    res = mcp_server._tool_search_knowledge(
        {"query": "mapper column values", "node_types": ["Finding"]}
    )
    assert res["method"] == "lexical"
    assert res["results"][0]["id"] == "finding:1"


@pytest.mark.skipif(not HAS_FASTEMBED, reason="embeddings-local extra not installed")
def test_paraphrase_finds_precedent(graph, monkeypatch):
    monkeypatch.delenv("SEMANTICA_SEMANTIC_SEARCH", raising=False)
    if not semantic.describe()["semantic"]:
        pytest.skip("embedding model unavailable (offline)")
    out = mcp_server._tool_find_precedents(
        {
            "scenario": "which lakehouse storage layer should the analytics data store use",
            "max_results": 2,
        }
    )
    assert out["method"] == "semantic+lexical"
    assert "Iceberg" in out["precedents"][0]["decision"]["scenario"]


@pytest.mark.skipif(not HAS_FASTEMBED, reason="embeddings-local extra not installed")
def test_search_knowledge_semantic(graph):
    if not semantic.describe()["semantic"]:
        pytest.skip("embedding model unavailable (offline)")
    res = mcp_server._tool_search_knowledge(
        {
            "query": "bad data types are refused when loading rows",
            "node_types": ["Finding"],
            "limit": 2,
        }
    )
    assert res["method"] == "semantic"
    assert res["results"][0]["id"] == "finding:1"


def test_file_history_walks_incoming_edges(graph):
    graph.add_node("pr:https://x/pull/1", "PullRequest", "pr 1", merged="2026-11-20")
    graph.add_node("file:repo:src/mapper.py", "CodeFile", "src/mapper.py")
    graph.add_edge("pr:https://x/pull/1", "file:repo:src/mapper.py", "CHANGED")
    graph.add_edge("finding:1", "pr:https://x/pull/1", "SOURCE")
    out = mcp_server._tool_file_history(
        {"repo": "repo", "paths": ["src/mapper.py", "missing.py"]}
    )
    known, missing = out["files"]
    assert known["known"] and known["knowledge_from_prs"] == ["finding:1"]
    assert missing == {"file": "file:repo:missing.py", "known": False}
    assert [k["id"] for k in out["knowledge"]] == ["finding:1"]
