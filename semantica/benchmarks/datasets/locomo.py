"""LoCoMo loader (very long-term conversational memory) — adapter only.

Licence: **CC BY-NC 4.0** — non-commercial. The harness only *reads* a copy the
user obtained themselves and never redistributes it. Because the licence is
restrictive, this loader is shipped as an adapter without any bundled data and
is deliberately excluded from the default dataset set: pass
``--dataset locomo --data locomo=/path/to/locomo10.json`` explicitly if you have
accepted the terms.

Source: https://github.com/snap-research/locomo (``data/locomo10.json``).

Shape of each sample::

    {"sample_id": "conv-26",
     "conversation": {"speaker_a": ..., "speaker_b": ...,
                      "session_1": [{"speaker":..., "dia_id":..., "text":...}],
                      "session_1_date_time": ..., "session_2": [...], ...},
     "qa": [{"question": ..., "answer": ..., "evidence": [...],
             "category": 1, "adversarial_answer": ...}, ...]}

Scope is ``corpus``: every session of a conversation is ingested once, and all
of that conversation's questions then query the same long-lived memory. That is
what makes LoCoMo a memory benchmark rather than a reading-comprehension one.

Categories: 1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop, 5 adversarial.
"""

from typing import List, Optional

from ..types import CORPUS, BenchmarkCase, Dataset
from . import register_dataset
from ._io import as_answers, read_json

_CITATION = "https://github.com/snap-research/locomo"

CATEGORY_NAMES = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}


def _sessions(conversation: dict) -> List[str]:
    """Flatten a conversation's sessions into dated, speaker-prefixed lines."""
    if not isinstance(conversation, dict):
        return []

    def session_number(key: str) -> int:
        suffix = key.rsplit("_", 1)[-1]
        return int(suffix) if suffix.isdigit() else 0

    # Session keys look like "session_1"; "session_1_date_time" holds the date.
    session_ids = sorted(
        (
            key
            for key in conversation
            if key.startswith("session_") and not key.endswith("_date_time")
        ),
        key=session_number,
    )

    lines: List[str] = []
    for session_id in session_ids:
        date = conversation.get(f"{session_id}_date_time")
        if date:
            lines.append(f"[{date}]")
        for turn in conversation.get(session_id) or []:
            if not isinstance(turn, dict):
                continue
            speaker = turn.get("speaker") or turn.get("role") or ""
            text = turn.get("text") or turn.get("content") or ""
            lines.append(f"{speaker}: {text}" if speaker else str(text))
    return lines


def load_locomo(
    path: str,
    limit: Optional[int] = None,
    categories: Optional[List[int]] = None,
) -> Dataset:
    """Load a local ``locomo10.json`` into a corpus-scoped :class:`Dataset`.

    ``categories`` optionally keeps only the given question categories (e.g.
    ``[1, 2, 4]`` to drop the adversarial and open-domain splits).
    """
    raw = read_json(path)
    samples = raw if isinstance(raw, list) else [raw]

    cases: List[BenchmarkCase] = []
    for sample_index, sample in enumerate(samples):
        sample_id = str(sample.get("sample_id") or f"locomo-{sample_index}")
        lines = _sessions(sample.get("conversation") or {})

        for qa_index, qa in enumerate(sample.get("qa") or []):
            question = qa.get("question")
            category = qa.get("category")
            if not question:
                continue
            if categories is not None and category not in categories:
                continue

            # Category 5 questions are adversarial: they carry a
            # tempting-but-wrong ``adversarial_answer`` alongside the real gold
            # ``answer``. The distractor is kept in metadata only — it must never
            # enter the gold list, or the harness would credit a system for
            # falling for the trap. Questions with no real ``answer`` are
            # skipped rather than scored against the distractor.
            answers = as_answers(qa.get("answer"))
            if not answers:
                continue

            cases.append(
                BenchmarkCase(
                    case_id=f"{sample_id}-q{qa_index:04d}",
                    question=question,
                    answers=answers,
                    # The same conversation serves every question of a sample;
                    # the runner de-duplicates when it builds the corpus, so
                    # sharing the list object here costs nothing.
                    context=lines,
                    metadata={
                        "sample_id": sample_id,
                        "category": category,
                        "category_name": CATEGORY_NAMES.get(category, "unknown"),
                        "evidence": qa.get("evidence"),
                        "adversarial_answer": qa.get("adversarial_answer"),
                    },
                )
            )

    dataset = Dataset(
        name="locomo",
        license="CC BY-NC 4.0 (NON-COMMERCIAL)",
        scope=CORPUS,
        cases=cases,
        version="locomo10",
        source=_CITATION,
        # Each sample is a *separate* long conversation with its own questions;
        # the runner must give every conversation its own memory instead of
        # merging all ten into one blob.
        group_by="sample_id",
        notes=(
            "Non-commercial licence: results from this dataset must not be "
            "used commercially. Adapter only; no data is bundled."
        ),
    )
    return dataset.limit(limit)


register_dataset("locomo", load_locomo)
