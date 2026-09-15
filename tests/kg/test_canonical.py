"""AnchorResolver 落位协议单测（ADR-0015 基元侧，PRD-0008 S1 / #49）。

四级协议各路径 + 变体两级挂靠 + PendingTerm 生命周期 + Neo4jStore
约束基元（merge_anchor/ensure_unique_constraint 用 stub driver 验证
Cypher 形状——真实图行为由仓库侧集成环境覆盖）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from semantica.kg.canonical import (
    MODE_DERIVES,
    MODE_IDENTITY,
    VIA_NORMALIZATION,
    VIA_PENDING,
    VIA_VARIANT_PATTERN,
    VIA_VOCABULARY,
    AnchorResolver,
)


class StubGraph:
    """记录 Cypher 调用的假图（返回单行固定记录）。"""

    def __init__(self, rows: List[Dict[str, Any]] | None = None):
        self.queries: List[tuple[str, Dict[str, Any]]] = []
        self.rows = rows or []

    def info(self, *a, **k):
        pass

    def execute_query(self, query: str, parameters: Dict[str, Any] | None = None):
        self.queries.append((query, parameters or {}))
        return {"success": True, "records": self.rows, "keys": []}

    def merge_anchor(self, labels, name, **kwargs):
        self.queries.append(("merge_anchor", {"labels": labels, "name": name, **kwargs}))
        return {"name": name}


def make_resolver(**kwargs) -> AnchorResolver:
    base = dict(
        alias_map={"herb": {"元胡": "延胡索", "白芍药": "白芍"}},
        vocab={"herb": {"延胡索", "白芍", "黄芪"},
               "syndrome": {"脾肾阳虚", "膀胱虚寒"},
               "therapy_method": {"健脾", "和胃"}},
        formula_roster={
            "四物汤": {"当归", "川芎", "白芍", "熟地黄"},
            "半夏泻心汤": {"半夏", "黄芩", "干姜", "人参", "黄连", "大枣", "甘草"},
        },
    )
    base.update(kwargs)
    return AnchorResolver(**base)


# ---- 四级协议 ----

def test_level1_normalization_alias_hit():
    r = make_resolver().land("元胡", "herb")
    assert r.anchor == "延胡索" and r.via == VIA_NORMALIZATION and r.mode == MODE_IDENTITY
    assert not r.pending


def test_level2_vocabulary_hit():
    r = make_resolver().land("黄芪", "herb")
    assert r.anchor == "黄芪" and r.via == VIA_VOCABULARY and not r.pending


def test_level3a_variant_pattern_derives():
    r = make_resolver().land("半夏泻心汤加减", "formula")
    assert r.anchor == "半夏泻心汤" and r.via == VIA_VARIANT_PATTERN
    assert r.mode == MODE_DERIVES
    assert r.detail["variant_suffix"] == "加减"


def test_level3a_pattern_unknown_base_falls_to_pending():
    # 模式命中但基础方不在名册 → 不臆造挂靠，落 PendingTerm
    r = make_resolver().land("无名神方加味", "formula")
    assert r.anchor is None and r.via == VIA_PENDING and r.pending


def test_level4_pending_and_zizifang_never_attaches():
    res = make_resolver()
    r = res.land("自拟方", "formula")
    assert r.pending and r.anchor is None
    # 自拟方不在名册也不构成变体名 → 药集相似也不给自动落位（仅候选）
    cands = res.attach_by_composition("自拟方", {"半夏", "黄芩", "干姜", "人参", "黄连", "大枣", "甘草"})
    assert cands and cands[0]["formula"] == "半夏泻心汤" and cands[0]["jaccard"] == 1.0


def test_level3b_composition_similarity_threshold():
    res = make_resolver(derives_jaccard_threshold=0.8)
    # 3 味重叠 1 味多（Jaccard = 3/5 = 0.6）→ 不入候选
    assert res.attach_by_composition("X", {"当归", "川芎", "白芍", "阿胶"}) == []
    # 全同 → Jaccard 1.0
    cands = res.attach_by_composition("X", {"当归", "川芎", "白芍", "熟地黄"})
    assert len(cands) == 1 and cands[0]["jaccard"] == 1.0
    assert cands[0]["missing_from_record"] == [] and cands[0]["extra_in_record"] == []


def test_land_empty_term():
    r = make_resolver().land("", "herb")
    assert r.anchor is None and r.pending


def test_alias_is_type_scoped():
    # herb 别名不得泄漏到 syndrome 词表
    r = make_resolver().land("元胡", "syndrome")
    assert r.pending


# ---- PendingTerm 生命周期 ----

def test_record_pending_requires_graph():
    try:
        make_resolver().record_pending("白芍药", "herb")
        assert False, "应抛 RuntimeError"
    except RuntimeError:
        pass


def test_record_pending_upsert_query_shape():
    g = StubGraph(rows=[{"raw": "白芍药", "freq": 2, "status": "open", "samples": ["REC-1"]}])
    res = make_resolver(graph=g)
    row = res.record_pending("白芍药", "herb", sample="REC-1", batch="med-verified-v6")
    assert row["freq"] == 2
    q, params = g.queries[0]
    assert "MERGE (p:PendingTerm {raw: $raw, term_type: $tt})" in q
    assert params == {"raw": "白芍药", "tt": "herb", "sample": "REC-1", "batch": "med-verified-v6"}


def test_promote_pending_marks_first_then_merges_anchor():
    g = StubGraph(rows=[{"raw": "白芍药", "status": "promoted", "promoted_to": "白芍"}])
    res = make_resolver(graph=g)
    row = res.promote_pending("白芍药", "herb", "白芍", anchor_props={"standard": "药典2020"})
    assert row["status"] == "promoted"
    q, params = g.queries[0]
    assert "SET p.status = 'promoted', p.promoted_to = $canonical" in q
    assert params["canonical"] == "白芍"
    anchor_call = g.queries[1]
    assert anchor_call[0] == "merge_anchor"
    assert anchor_call[1]["labels"] == ["Herb", "Canonical"]
    assert anchor_call[1]["name"] == "白芍"


def test_promote_pending_requires_canonical():
    try:
        make_resolver(graph=StubGraph()).promote_pending("x", "herb", " ")
        assert False
    except ValueError:
        pass


def test_reject_pending_query_shape():
    g = StubGraph(rows=[{"raw": "无名神方", "status": "rejected"}])
    res = make_resolver(graph=g)
    row = res.reject_pending("无名神方", "formula", reason="非规范写法")
    assert row["status"] == "rejected"
    q, params = g.queries[0]
    assert "SET p.status = 'rejected', p.reject_reason = $reason" in q


def test_list_pending_filters():
    g = StubGraph(rows=[{"raw": "谷芽", "freq": 170}])
    res = make_resolver(graph=g)
    rows = res.list_pending(term_type="herb", min_freq=10)
    assert rows[0]["raw"] == "谷芽"
    q, params = g.queries[0]
    assert "p.term_type = $tt" in q and params["minFreq"] == 10


# ---- Neo4jStore 基元（Cypher 形状） ----

def test_merge_anchor_query_shape():
    from semantica.graph_store.neo4j_store import Neo4jStore

    store = Neo4jStore.__new__(Neo4jStore)  # 跳过 __init__（无驱动依赖）
    store.logger = StubGraph()  # logger duck-typing
    captured: Dict[str, Any] = {}

    def _fake_execute(query, parameters=None, **options):
        captured["query"] = query
        return {"success": True, "records": [{"props": {"name": "白芍"}}], "keys": ["props"]}

    store.execute_query = _fake_execute
    props = {"standard": "药典2020", "term_type": "herb"}
    store.merge_anchor(labels=["Herb", "Canonical"], name="白芍", extra_props=props)
    q = captured["query"]
    assert "MERGE (n:Herb:Canonical {name: $name})" in q
    assert "n.standard = $standard" in q and "ON MATCH" not in q

    # on_match_set 分支
    store.merge_anchor(labels=["Herb", "Canonical"], name="白芍",
                       extra_props={"superseded_by": "X"}, on_match_set=["superseded_by"])
    assert "ON MATCH SET n.superseded_by = $superseded_by" in captured["query"]


def test_ensure_unique_constraint_query_shape():
    from semantica.graph_store.neo4j_store import Neo4jStore

    store = Neo4jStore.__new__(Neo4jStore)
    store.logger = StubGraph()
    captured: Dict[str, Any] = {}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def run(self, q, p=None):
            captured["query"] = q

    store.get_session = lambda **kw: _Session()
    store.ensure_unique_constraint("Canonical", "name")
    assert ("CREATE CONSTRAINT uniq_Canonical_name IF NOT EXISTS "
            "FOR (n:Canonical) REQUIRE n.name IS UNIQUE") in captured["query"]
