"""Targeted regression tests for all 13 Qodo review fixes on the Distance Intelligence PR."""
import re
import inspect


# ── bug_003: include_distance_metadata=False is the backward-compat default ───

def test_bug003_metadata_absent_by_default():
    from semantica.context.context_graph import ContextGraph
    g = ContextGraph()
    g.add_node("A", "test")
    g.add_node("B", "test")
    g.add_edge("A", "B", "related")
    neighbors = g.get_neighbors("A")
    assert len(neighbors) == 1
    assert "hop" in neighbors[0]
    assert "distance_band" not in neighbors[0], (
        f"distance_band should be absent by default; got keys: {list(neighbors[0].keys())}"
    )
    assert "confidence_decay" not in neighbors[0]
    assert "path_to_anchor" not in neighbors[0]


def test_bug003_metadata_present_with_flag():
    from semantica.context.context_graph import ContextGraph
    g = ContextGraph()
    g.add_node("A", "test")
    g.add_node("B", "test")
    g.add_edge("A", "B", "related")
    neighbors = g.get_neighbors("A", include_distance_metadata=True)
    assert len(neighbors) == 1
    assert "distance_band" in neighbors[0]
    assert "confidence_decay" in neighbors[0]
    assert "path_to_anchor" in neighbors[0]


def test_bug003_get_neighbor_distances_still_works():
    from semantica.context.context_graph import ContextGraph
    g = ContextGraph()
    g.add_node("A", "test")
    g.add_node("B", "test")
    g.add_edge("A", "B", "related", weight=0.9)
    nd = g.get_neighbor_distances("A")
    assert len(nd) == 1
    assert nd[0]["distance_band"] == "direct"
    assert abs(nd[0]["confidence_decay"] - 0.9) < 1e-9
    assert "path_to_anchor" in nd[0]


# ── bug_004: weakest_link standardized to edge_weight key ─────────────────────

def test_bug004_weakest_link_uses_edge_weight_key():
    from semantica.context.context_graph import ContextGraph
    from semantica.context.causal_analyzer import CausalChainAnalyzer
    g = ContextGraph()
    g.add_node("A", "decision")
    g.add_node("B", "decision")
    g.add_node("C", "decision")
    g.add_edge("A", "B", "causes", weight=0.8)
    g.add_edge("B", "C", "causes", weight=0.5)
    analyzer = CausalChainAnalyzer(g)
    report = analyzer.interpret_causal_distance("A", "C")
    wl = report.get("weakest_link")
    assert wl is not None, "weakest_link must be set for a 2-hop causal path"
    assert "edge_weight" in wl, f"Expected edge_weight key, got: {list(wl.keys())}"
    assert "weight" not in wl, f"Old key 'weight' should be absent; got: {list(wl.keys())}"
    assert wl["edge_weight"] == 0.5


def test_bug004_causal_distance_report_schema_validates():
    from semantica.explorer.schemas import CausalDistanceReport
    report = CausalDistanceReport(
        source_id="A",
        target_id="C",
        causal_path=["A", "B", "C"],
        causal_hop_count=2,
        intermediate_decisions=["B"],
        confidence_decay=0.4,
        weakest_link={"source": "A", "target": "B", "edge_weight": 0.5},
        interpretation="Test path",
    )
    assert report.weakest_link["edge_weight"] == 0.5


# ── qual_003: _distance_band static methods removed; classify_path_distance used ─

def test_qual003_distance_band_removed_from_causal_analyzer():
    from semantica.context.causal_analyzer import CausalChainAnalyzer
    assert not hasattr(CausalChainAnalyzer, "_distance_band")
    ca_src = inspect.getsource(CausalChainAnalyzer)
    assert "def _distance_band" not in ca_src
    assert "classify_path_distance" in ca_src


def test_qual003_distance_band_removed_from_agent_context():
    import semantica.context.agent_context as ac_mod
    ac_src = inspect.getsource(ac_mod)
    assert "def _distance_band" not in ac_src
    assert "classify_path_distance" in ac_src


# ── bug_005: timedelta arithmetic — no timetuple reconstruction ───────────────

def test_bug005_no_timetuple_hack_in_distance_history():
    from semantica.explorer.routes import temporal
    src = inspect.getsource(temporal.distance_history)
    assert "timetuple" not in src, "Old timetuple hack should be gone"
    assert "__import__" not in src, "Dynamic import hack should be gone"
    assert "timedelta(seconds" in src


# ── sec_001: node_subset capped at 200 ────────────────────────────────────────

def test_sec001_node_subset_limit_constant_exists():
    from semantica.explorer.routes.export_import import _DISTANCE_EXPORT_MAX_NODES
    assert _DISTANCE_EXPORT_MAX_NODES == 200


def test_sec001_export_endpoint_validates_subset_size():
    from semantica.explorer.routes import export_import
    src = inspect.getsource(export_import.export_distance_enriched)
    assert "_DISTANCE_EXPORT_MAX_NODES" in src
    assert "status_code=413" in src


# ── sec_002: distance matrix upper-triangle only ──────────────────────────────

def test_sec002_distance_matrix_upper_triangle_loop():
    from semantica.explorer.routes import graph
    src = inspect.getsource(graph.distance_matrix)
    assert "range(i + 1, n)" in src, "Should use upper-triangle loop"
    assert "matrix[j][i]" in src, "Should mirror lower triangle"


# ── bug_006: O(L) edge weight index built once ────────────────────────────────

def test_bug006_edge_weight_index_built_once():
    from semantica.explorer.routes import graph
    src = inspect.getsource(getattr(graph, "_find_path_impl", graph.find_path))
    assert "edge_weight_index" in src
    assert "for edge in edge_data:" not in src, "Old O(E*L) loop should be gone"


# ── bug_007: original result id not overwritten ───────────────────────────────

def test_bug007_original_id_not_overwritten():
    from semantica.context import agent_context
    src = inspect.getsource(agent_context.AgentContext._apply_proximity_metadata)
    assert (
        '"graph_node_id": result_id' in src
        or "'graph_node_id': result_id" in src
    )
    assert '"id": result_id' not in src, "id should not be overwritten by result_id"


# ── qual_002: no bare except:pass in enrichment blocks ───────────────────────

def test_qual002_no_bare_except_pass_in_find_path():
    from semantica.explorer.routes import graph
    src = inspect.getsource(getattr(graph, "_find_path_impl", graph.find_path))
    bare_pass = re.findall(r"except Exception:\s*\n\s*pass", src)
    assert not bare_pass, f"Found bare except:pass: {bare_pass}"
    assert "logger.debug" in src


# ── TypeScript fixes — checked via raw file reads ─────────────────────────────

TS_BEHAVIOR = (
    r"c:\Users\Mohd Kaif\semantica\explorer\src\workspaces"
    r"\GraphWorkspace\behaviors\pathHighlightBehavior.ts"
)
TS_WORKSPACE = (
    r"c:\Users\Mohd Kaif\semantica\explorer\src\workspaces"
    r"\GraphWorkspace\GraphWorkspace.tsx"
)


def test_bug008_sweep_generation_counter():
    with open(TS_BEHAVIOR, encoding="utf-8") as fh:
        src = fh.read()
    assert "sweepGeneration" in src, "Generation counter variable must exist"
    assert "gen !== sweepGeneration" in src, "Stale-callback guard must exist"
    assert "sweepGeneration++" in src, "Counter must be incremented on cancel"


def test_bug001_semantic_neighborhood_uses_top_k():
    with open(TS_WORKSPACE, encoding="utf-8") as fh:
        src = fh.read()
    assert (
        "top_k=50" in src or 'top_k: "50"' in src
    ), "Should use top_k (not limit) to match backend param"
    idx = src.find("semantic-neighborhood?")
    snippet = src[idx: idx + 100]
    assert "limit=" not in snippet, f"Found 'limit=' in URL snippet: {snippet!r}"


def test_bug002_semantic_neighborhood_response_type_complete():
    with open(TS_WORKSPACE, encoding="utf-8") as fh:
        src = fh.read()
    assert "anchor_node: string" in src
    assert "hop_distance?" in src


def test_qual001_ego_heatmap_merged_into_single_effect():
    with open(TS_WORKSPACE, encoding="utf-8") as fh:
        src = fh.read()
    assert "egoModeEnabled, egoMaxHops, heatmapEnabled, selectedNodeId" in src, (
        "Combined dep array must be present"
    )
    # The old separate dep arrays must not exist
    assert "], [egoModeEnabled, egoMaxHops, selectedNodeId]" not in src
    assert "], [heatmapEnabled, selectedNodeId]" not in src
