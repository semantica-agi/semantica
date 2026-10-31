"""MuSiQue loader (multi-hop question answering).

Licence: CC BY 4.0 — read locally, never redistributed by the harness.
Get it from https://github.com/StonyBrookNLP/musique (``musique_ans_v1.0_dev.jsonl``).

Each JSONL line looks like::

    {"id": "...", "question": "...", "answer": "...",
     "answer_aliases": ["..."],
     "paragraphs": [{"idx": 0, "title": "...", "paragraph_text": "...",
                     "is_supporting": true}, ...],
     "question_decomposition": [...]}

``answer_aliases`` is folded into the gold answer list so a correct paraphrase
is not scored as a miss.
"""

from typing import List

from ..types import PER_CASE, BenchmarkCase, Dataset
from . import register_dataset
from ._io import as_answers, read_jsonl

_CITATION = "https://github.com/StonyBrookNLP/musique"


def _passages(paragraphs: List[dict]) -> List[str]:
    passages = []
    for para in paragraphs or []:
        title = para.get("title") or ""
        text = para.get("paragraph_text") or ""
        passages.append(f"{title}: {text}" if title else text)
    return passages


def load_musique(path: str, limit=None) -> Dataset:
    """Load a local MuSiQue JSONL file into a :class:`Dataset`."""
    cases: List[BenchmarkCase] = []
    for index, record in enumerate(read_jsonl(path)):
        question = record.get("question")
        answers = as_answers(record.get("answer"), record.get("answer_aliases"))
        if not question or not answers:
            continue
        cases.append(
            BenchmarkCase(
                case_id=str(record.get("id") or f"musique-{index}"),
                question=question,
                answers=answers,
                context=_passages(record.get("paragraphs")),
                metadata={
                    "decomposition": record.get("question_decomposition"),
                    "answerable": record.get("answerable"),
                },
            )
        )

    dataset = Dataset(
        name="musique",
        license="CC BY 4.0",
        scope=PER_CASE,
        cases=cases,
        version="ans-v1.0",
        source=_CITATION,
        notes="Answerable split; each question ships exactly its own paragraphs.",
    )
    return dataset.limit(limit)


register_dataset("musique", load_musique)
