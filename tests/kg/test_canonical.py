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
    # review 定案顺序：先翻 pending 状态（防孤儿锚点）→ 再建锚点
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


# ---- PRD-0021 R3：rejected 粘滞 + 别名注册表泛化 + 归并回写 ----

def test_record_pending_rejected_is_sticky():
    """重导入已否决词不复活回 open（裁决终态粘滞）。"""
    g = StubGraph(rows=[{"raw": "无名方", "status": "rejected", "freq": 2}])
    res = make_resolver(graph=g)
    row = res.record_pending("无名方", "formula")
    assert row["status"] == "rejected"
    q, _ = g.queries[0]
    assert "IN ['promoted', 'rejected']" in q
    assert "freq = coalesce(p.freq, 0) + 1" in q  # 频次照常累计（复审信号）


def test_register_alias_all_term_types():
    """别名注册表泛化：全部 term_type 可注册，identity/空值拒绝。"""
    res = make_resolver()
    assert res.register_alias("therapy_method", "健脾和胃法", "健脾和胃") is True
    assert res.register_alias("syndrome", "气虚证", "气虚") is True
    assert res.register_alias("disease", "胃脘痛", "胃痛") is True
    assert res.land("健脾和胃法", "therapy_method").anchor == "健脾和胃"
    # 拒绝项：identity、空值、未知类型
    assert res.register_alias("herb", "白芍", "白芍") is False
    assert res.register_alias("herb", "", "白芍") is False
    assert res.register_alias("pulse", "浮脉", "浮") is False


def test_load_aliases_from_graph_hydrates_l1():
    """图内锚点 aliases 属性水合进 L1（归并回写后的再导入命中通道）。"""
    g = StubGraph(rows=[
        {"tt": "therapy_method", "name": "健脾", "aliases": ["健脾法", "助运"]},
        {"tt": "syndrome", "name": "气虚", "aliases": ["气虚证"]},
        {"tt": "herb", "name": "白芍", "aliases": ["白芍"]},  # identity 剔除
    ])
    res = make_resolver(graph=g)
    n = res.load_aliases_from_graph()
    assert n == 3
    assert res.land("健脾法", "therapy_method").anchor == "健脾"
    assert res.land("助运", "therapy_method").anchor == "健脾"
    assert res.land("气虚证", "syndrome").anchor == "气虚"
    q, _ = g.queries[0]
    assert "a.aliases IS NOT NULL" in q


def test_load_aliases_does_not_overwrite_existing():
    """既有条目胜（种子归一表不被图状态覆写）。"""
    g = StubGraph(rows=[{"tt": "herb", "name": "白芍", "aliases": ["元胡"]}])
    res = make_resolver(graph=g)  # 元胡 → 延胡索（种子表既有）
    res.load_aliases_from_graph()
    assert res.land("元胡", "herb").anchor == "延胡索"


def test_merge_pending_flips_and_writes_alias():
    """归并：翻状态 + promoted_to + 锚点别名回写（幂等去重）。"""
    g = StubGraph(rows=[{"raw": "健脾法", "status": "promoted", "promoted_to": "健脾", "anchor": "健脾"}])
    res = make_resolver(graph=g)
    out = res.merge_pending("健脾法", "therapy_method", "健脾")
    assert out["status"] == "promoted" and out["promoted_to"] == "健脾"
    q, params = g.queries[0]
    assert "MATCH (a:Canonical {name: $canonical})" in q
    assert "p.status = 'promoted', p.promoted_to = $canonical" in q
    assert "$raw IN coalesce(a.aliases, [])" in q  # 幂等：已存在不重复追加
    assert params == {"raw": "健脾法", "tt": "therapy_method", "canonical": "健脾"}


def test_merge_pending_not_found_keeps_decision():
    """锚点/pending 行缺失：不翻状态（决策不丢失），返回 not_found。"""
    g = StubGraph(rows=[])
    res = make_resolver(graph=g)
    out = res.merge_pending("幽灵词", "therapy_method", "不存在的锚点")
    assert out["status"] == "not_found"


def test_merge_pending_requires_canonical():
    import pytest

    res = make_resolver(graph=StubGraph())
    with pytest.raises(ValueError):
        res.merge_pending("x", "therapy_method", "  ")
