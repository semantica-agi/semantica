# -*- coding: utf-8 -*-
"""方剂骨架结构匹配基元测试（PRD-0014 R2 / tcm-cdss #87）。

锚定案例：附子泻心汤与理中丸合方加减（王付经方医案）——
平铺交集只能给"重合 7 味"，骨架匹配应识别出两个整方结构。
"""

from semantica.formula_structure import compare_doses, match_formula_skeletons

CANDIDATES = {
    "附子泻心汤": ["大黄", "黄芩", "黄连", "附子"],
    "理中丸": ["人参", "白术", "干姜", "甘草"],
    "半夏泻心汤": ["半夏", "黄芩", "干姜", "人参", "甘草", "黄连", "大枣"],
    "三黄泻心汤": ["大黄", "黄芩", "黄连"],
    "麻黄汤": ["麻黄", "桂枝", "杏仁", "甘草"],
}

# 本案处方（图谱正名空间；干姜在部署实况中因归一失败缺席）
RX_FULL = ["大黄", "黄连", "黄芩", "附子", "干姜", "红参", "白术", "炙甘草"]
RX_DEPLOY = [h for h in RX_FULL if h != "干姜"]  # 干姜归一失败 → 缺席


def test_full_case_recognizes_both_formulas():
    ms = match_formula_skeletons(RX_FULL, CANDIDATES, max_missing=0)
    names = [m.formula for m in ms]
    assert "附子泻心汤" in names and "理中丸" in names
    for m in ms:
        assert m.full and m.containment == 1.0


def test_deploy_case_flags_missing_herb():
    ms = match_formula_skeletons(RX_DEPLOY, CANDIDATES, max_missing=1)
    by = {m.formula: m for m in ms}
    assert by["附子泻心汤"].full  # 4/4 全中，不受干姜影响
    assert not by["理中丸"].full and by["理中丸"].missing == ["干姜"]
    assert by["理中丸"].containment == 0.75


def test_equivalence_maps_treated_variants():
    ms = match_formula_skeletons(RX_FULL, {"理中丸": CANDIDATES["理中丸"]}, max_missing=0)
    assert ms and ms[0].matched == ["人参", "干姜", "甘草", "白术"]  # 红参→人参、炙甘草→甘草


def test_min_hits_blocks_casual_overlap():
    ms = match_formula_skeletons(["大黄"], {"三黄泻心汤": CANDIDATES["三黄泻心汤"]}, min_hits=2)
    assert ms == []


def test_ranking_deterministic_skeleton_size_first():
    ms = match_formula_skeletons(RX_FULL, CANDIDATES, max_missing=1, top_n=5)
    # 骨架规模优先：4 味整方（附子泻心汤/理中丸）居首，3 味三黄泻心汤随后，
    # 半夏泻心汤缺 2 味（半夏+大枣）被 max_missing 正确排除，麻黄汤 1 味命中
    # 被 min_hits 挡下
    assert {ms[0].formula, ms[1].formula} == {"附子泻心汤", "理中丸"}
    assert ms[2].formula == "三黄泻心汤"
    assert all(m.formula not in ("半夏泻心汤", "麻黄汤") for m in ms)
    keys = [(-len(m.matched), -m.containment, m.formula) for m in ms]
    assert keys == sorted(keys)


def test_compare_doses_juncture_and_tolerance():
    d = compare_doses(
        rx_doses={"大黄": 6.0, "黄连": 3.0, "黄芩": 3.0},
        formula_doses={"大黄": 6.0, "黄连": 3.0, "黄芩": 3.0},
        matched_herbs=["大黄", "黄连", "黄芩"],
    )
    assert d["juncture_agree"] is True  # 君药同为大黄（泻心汤结构）
    d2 = compare_doses(
        rx_doses={"厚朴": 8.0, "大黄": 4.0},
        formula_doses={"厚朴": 4.0, "大黄": 12.0},
        matched_herbs=["厚朴", "大黄"],
        ratio_tolerance=0.5,
    )
    assert d2["juncture_agree"] is False  # 小承气（君大黄） vs 厚朴三物（君厚朴）方向反转
    assert all(not c["in_tolerance"] for c in d2["compared"])
