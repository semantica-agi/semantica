"""HotPotQA loader (multi-hop reading comprehension).

Licence: CC BY-SA 4.0 — the harness reads a local copy, never redistributes it.
Get it from https://hotpotqa.github.io/ (``hotpot_dev_distractor_v1.json`` is
the usual evaluation file) or the ``hotpot_qa`` dataset on Hugging Face.

Two shapes are accepted, because the official JSON and the Hugging Face export
disagree about how context is nested:

official::

    {"_id": ..., "question": ..., "answer": ...,
     "context": [["Title", ["sent 1", "sent 2"]], ...]}

Hugging Face::

    {"id": ..., "question": ..., "answer": ...,
     "context": {"title": [...], "sentences": [["sent 1"], ["sent 2"]]}}

Both collapse to the same ``context`` list of ``"Title: sent. sent."``
passages, so downstream systems see one format.
"""

from typing import Any, List, Optional

from ..types import PER_CASE, BenchmarkCase, Dataset
from . import register_dataset
from ._io import as_list, as_answers, read_json

_CITATION = "https://hotpotqa.github.io/"


def _passages(context: Any, titles: Any = None, sentences: Any = None) -> List[str]:
    """Normalize either context shape into ``["Title: text", ...]``."""
    passages: List[str] = []

    if isinstance(context, dict):
        # Hugging Face: {"title": [...], "sentences": [[...], ...]}
        titles = context.get("title") or []
        sentences = context.get("sentences") or []
        for title, sents in zip(titles, sentences):
            text = " ".join(str(s) for s in as_list(sents))
            passages.append(f"{title}: {text}" if title else text)
        return passages

    for entry in as_list(context):
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            title, sents = entry
            text = " ".join(str(s) for s in as_list(sents))
        else:
            title, text = "", str(entry)
        passages.append(f"{title}: {text}" if title else text)
    return passages


def load_hotpotqa(path: str, limit: Optional[int] = None) -> Dataset:
    """Load a local HotPotQA JSON file into a :class:`Dataset`."""
    raw = read_json(path)
    records = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
    if isinstance(records, dict):
        # Some exports wrap the questions in a single dict of id -> record.
        records = list(records.values())

    cases: List[BenchmarkCase] = []
    for index, record in enumerate(records):
        answers = as_answers(record.get("answer"), record.get("answers"))
        if not answers or not record.get("question"):
            continue
        case_id = str(record.get("_id") or record.get("id") or f"hotpotqa-{index}")
        cases.append(
            BenchmarkCase(
                case_id=case_id,
                question=record["question"],
                answers=answers,
                context=_passages(record.get("context")),
                metadata={
                    "type": record.get("type"),
                    "level": record.get("level"),
                    "supporting_facts": record.get("supporting_facts"),
                },
            )
        )

    dataset = Dataset(
        name="hotpotqa",
        license="CC BY-SA 4.0",
        scope=PER_CASE,
        cases=cases,
        version="distractor-v1",
        source=_CITATION,
        notes="Distractor setting: each question ships its own 10-paragraph bundle.",
    )
    return dataset.limit(limit)


register_dataset("hotpotqa", load_hotpotqa)
