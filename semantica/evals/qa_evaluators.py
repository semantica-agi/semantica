"""QA-style evaluators: SQuAD-normalized token F1 and exact match.

Reading-comprehension and open-domain QA suites (SQuAD, HotPotQA, MuSiQue,
Natural Questions, ...) all score free-form answers with the same recipe:
lowercase the text, drop punctuation and articles, collapse whitespace, then
compare the predicted and gold answers as token bags. ``token_f1`` and
``normalized_exact_match`` implement exactly that normalization, so the numbers
they produce line up with the published baselines for those datasets instead of
drifting because of casing or trailing periods.

Both accept ``expected`` as either a single gold string or a list of acceptable
golds (these datasets routinely ship several alternatives); the score is the
best match over the gold set, which is also the standard convention.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from .registry import register
from .types import EvalMetric

_ARTICLE_RE = re.compile(r"\b(a|an|the)\b")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_answer(text: Any) -> str:
    """Apply the SQuAD answer normalization to ``text``.

    Lowercases, **deletes** punctuation (the official SQuAD recipe removes it
    rather than replacing it with a space, so ``"U.S."`` and ``"US"`` become the
    same token), removes articles (a/an/the) and collapses runs of whitespace.
    Kept as a public helper so callers can reuse the exact normalization the
    evaluators apply.
    """
    text = str(text).lower()
    text = _PUNCT_RE.sub("", text)
    text = _ARTICLE_RE.sub(" ", text)
    return " ".join(text.split())


def _as_golds(expected: Any) -> Tuple[List[str], str]:
    """Return ``(golds, error)``; ``error`` is "" when ``expected`` is usable."""
    if expected is None:
        return [], "expected is required (a gold answer or list of golds)"
    if isinstance(expected, str):
        return [expected], ""
    if isinstance(expected, (list, tuple, set)):
        golds = [g for g in expected if isinstance(g, str)]
        if not golds:
            return [], "expected list contains no string answers"
        return golds, ""
    return [], (
        f"expected must be a string or list of strings, got {type(expected).__name__}"
    )


def _pair_overlap(gold: str, pred: str) -> Tuple[int, int, int]:
    """Return ``(overlap, len(pred), len(gold))`` over normalized token bags."""
    pred_tokens = normalize_answer(pred).split()
    gold_tokens = normalize_answer(gold).split()
    overlap = sum((Counter(pred_tokens) & Counter(gold_tokens)).values())
    return overlap, len(pred_tokens), len(gold_tokens)


def _f1(pred: str, gold: str) -> float:
    """Token F1 between one prediction and one gold (SQuAD `f1_score`)."""
    overlap, n_pred, n_gold = _pair_overlap(gold, pred)
    if n_pred == 0 or n_gold == 0:
        # If either side is empty the only way to score is exact emptiness.
        return 1.0 if n_pred == n_gold else 0.0
    if overlap == 0:
        return 0.0
    precision = overlap / n_pred
    recall = overlap / n_gold
    return 2 * precision * recall / (precision + recall)


@register("token_f1")
def token_f1(actual, expected=None, config=None, **kwargs):
    """SQuAD-normalized token F1 between ``actual`` and the best gold.

    ``expected`` may be a single gold string or a list of acceptable golds.
    Passes when the best F1 reaches ``threshold`` (default 0.0, i.e. any
    non-zero overlap) — mirroring ``rouge``. The raw F1 is always reported as
    ``score``, which is what benchmark aggregation reads.
    """
    cfg = config or {}
    threshold = cfg.get("threshold", 0.0)
    golds, error = _as_golds(expected)
    if error:
        return EvalMetric(0.0, False, {"error": error})
    if actual is None:
        return EvalMetric(0.0, False, {"error": "actual is required"})

    scores: Dict[str, float] = {g: _f1(str(actual), g) for g in golds}
    best_gold, best = max(scores.items(), key=lambda kv: kv[1])
    return EvalMetric(
        score=best,
        passed=best > 0.0 and best >= threshold,
        meta={"f1": best, "best_gold": best_gold, "threshold": threshold},
    )


@register("normalized_exact_match")
def normalized_exact_match(actual, expected=None, config=None, **kwargs):
    """Exact match after SQuAD normalization, against any gold.

    Passes (score 1.0) when the normalized prediction equals the normalization
    of any gold; 0.0 otherwise. This is the datasets' "EM" column.
    """
    golds, error = _as_golds(expected)
    if error:
        return EvalMetric(0.0, False, {"error": error})
    if actual is None:
        return EvalMetric(0.0, False, {"error": "actual is required"})

    normalized = normalize_answer(actual)
    matched = next((g for g in golds if normalize_answer(g) == normalized), None)
    return EvalMetric(
        score=1.0 if matched is not None else 0.0,
        passed=matched is not None,
        meta={} if matched is not None else {
            "reason": f"normalized {normalized!r} matched no gold",
        },
    )
