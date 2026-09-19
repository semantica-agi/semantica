# -*- coding: utf-8 -*-
"""方剂骨架结构匹配基元（PRD-0014 R2 / tcm-cdss #87）。

溯源问题的本体是结构："这张处方是哪个方化裁的"。平铺药名集合交集
只能回答"重合 N 味"（半截话），结构匹配回答"认出了哪个骨架、缺了
哪味、加了哪味"——与医师化裁溯源的领域原生形态一致。

纯算法基元：candidates（候选方组成）由调用方（tcm-cdss 业务编排层）
从图谱 Formula 子图查询提供，本模块不做任何 IO。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 溯源档药味等同组（lineage-level equivalence）：同一药材的不同炮制/商品
# 规格在"方骨架识别"语境下视为同源。注意：这是溯源档口径，不得用于
# 规则层配伍禁忌/剂量审核的药味归一。
DEFAULT_EQUIVALENCE: dict[str, str] = {
    "红参": "人参",
    "生晒参": "人参",
    "炙甘草": "甘草",
    "制附子": "附子",
}


@dataclass
class SkeletonMatch:
    """单个候选方的骨架识别结果。"""

    formula: str
    containment: float  # |comp∩rx| / |comp|
    matched: list[str] = field(default_factory=list)  # comp ∩ rx（等同归一后）
    missing: list[str] = field(default_factory=list)  # comp - rx（缺味：疑减味或归一断点）
    added: list[str] = field(default_factory=list)  # rx - comp（加味）
    full: bool = True  # missing 为空（整方全中）
    dose_diff: dict | None = None  # 阶段二：剂量比例比对（compare_doses 输出）


def _canon(h: str, equivalence: dict[str, str]) -> str:
    return equivalence.get(h, h)


def match_formula_skeletons(
    rx_herbs: list[str] | set[str],
    candidates: dict[str, list[str] | set[str]],
    *,
    max_missing: int = 1,
    min_hits: int = 2,
    top_n: int = 5,
    equivalence: dict[str, str] | None = None,
) -> list[SkeletonMatch]:
    """处方药味集 vs 候选方组成的最大骨架匹配。

    rx_herbs: 处方药味（调用方已完成确定性归一的正名空间）
    candidates: 方名 -> 组成药味（如图谱 Formula 子图）
    max_missing: 缺味容忍（骨架不完整仍可识别，缺味列表显式带出）
    min_hits: 最少命中味数（防 1 味偶然重合刷榜）
    equivalence: 溯源档药味等同映射（rx 侧写法 → 方剂组成侧写法），
        None 时用 DEFAULT_EQUIVALENCE；传 {} 关闭等同归一。

    返回按（命中味数降序, containment 降序, 方名升序）的 top_n——确定性、
    可复现。骨架规模优先：4 味整方（附子泻心汤）应压过 2 味偶然全中的
    小方（大黄甘草汤），否则溯源榜被琐碎小方刷屏。
    调用方展示时必须保留"溯源档"分级口径，不得作为药证证据。
    """
    eq = DEFAULT_EQUIVALENCE if equivalence is None else equivalence
    rx = {_canon(h, eq) for h in rx_herbs if h}
    out: list[SkeletonMatch] = []
    for name, comp in candidates.items():
        comp_set = {_canon(h, eq) for h in comp if h}
        if not comp_set:
            continue
        matched = comp_set & rx
        if len(matched) < min_hits:
            continue
        missing = sorted(comp_set - rx)
        if len(missing) > max_missing:
            continue
        out.append(
            SkeletonMatch(
                formula=name,
                containment=round(len(matched) / len(comp_set), 4),
                matched=sorted(matched),
                missing=missing,
                added=sorted(rx - comp_set),
                full=not missing,
            )
        )
    out.sort(key=lambda m: (-len(m.matched), -m.containment, m.formula))
    return out[:top_n]


def compare_doses(
    rx_doses: dict[str, float],
    formula_doses: dict[str, float],
    matched_herbs: list[str],
    *,
    ratio_tolerance: float = 0.5,
) -> dict:
    """剂量比例比对（阶段二，PRD-0014 R2）：同药异方靠君臣（剂量主次）区分。

    rx_doses / formula_doses: 药味 -> 克数（调用方负责从 dose_text 解析）
    ratio_tolerance: 单药比例相对偏差容忍带（|rx/comp - 1| <= tol 视为一致）

    输出：{"compared": [...], "juncture_agree": bool|None}
    juncture = 双方最大剂量药（君药近似）：一致/不一致/数据不足（None）。
    """
    compared = []
    for h in sorted(matched_herbs):
        a, b = rx_doses.get(h), formula_doses.get(h)
        if a and b:
            compared.append({"herb": h, "rx": a, "formula": b, "ratio": round(a / b, 3),
                             "in_tolerance": abs(a / b - 1) <= ratio_tolerance})
    rx_junct = max(rx_doses, key=lambda k: rx_doses[k]) if rx_doses else None
    f_junct = max(formula_doses, key=lambda k: formula_doses[k]) if formula_doses else None
    juncture_agree = None
    if rx_junct and f_junct:
        eq = DEFAULT_EQUIVALENCE
        juncture_agree = _canon(rx_junct, eq) == _canon(f_junct, eq)
    return {"compared": compared, "juncture_agree": juncture_agree}
