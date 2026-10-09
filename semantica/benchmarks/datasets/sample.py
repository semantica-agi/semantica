"""A tiny bundled dataset so benchmarks run offline (CI, smoke tests).

This is not a real benchmark: it is six hand-written questions with their
evidence passages, embedded as a Python literal so no data file has to be
shipped or downloaded. It exists so ``python -m semantica.benchmarks run`` has
something to chew on in a fresh checkout, and so the harness has an end-to-end
test that never touches the network.

The evidence is written so that the sentence carrying the answer is also the
sentence that shares the most content words with the question. That keeps the
default *extractive* reader (which has no model — see
:func:`semantica.benchmarks.text.best_sentence`) above a trivial floor, so the
smoke test can assert that retrieval plus scoring actually did something. It
inherits the weaknesses of any extractive reader: predictions are whole
sentences, so ``normalized_exact_match`` stays at zero here even when the answer
is present. Plug in a real reader (``reader=`` on any system) for QA-grade
numbers.
"""

from typing import List, Optional

from ..types import PER_CASE, BenchmarkCase, Dataset
from . import register_dataset

# (question, gold answer, accepted aliases, evidence passages)
_CASES = [
    (
        "Who wrote the novel Neuromancer?",
        "William Gibson",
        ["Gibson", "William Ford Gibson"],
        [
            "The novel Neuromancer was written by William Gibson and published "
            "in 1984.",
            "Neuromancer won the Nebula Award and helped define the cyberpunk genre.",
            "William Gibson was born in Conway, South Carolina in 1948.",
        ],
    ),
    (
        "Which country was the telephone inventor born in?",
        "Scotland",
        ["Scottish"],
        [
            "The telephone inventor Alexander Graham Bell was born in Scotland "
            "in 1847.",
            "The telephone was patented in the United States in 1876.",
            "Bell later emigrated to Canada and then to the United States.",
        ],
    ),
    (
        "How many strings does a standard cello have?",
        "four",
        ["4"],
        [
            "A standard cello has four strings, tuned in fifths.",
            "A cello is larger than a violin and smaller than a double bass.",
            "Yo-Yo Ma is a cellist known for his recordings of the Bach cello suites.",
        ],
    ),
    (
        "Which ocean lies off the coast of Queensland?",
        "Coral Sea",
        ["the Coral Sea"],
        [
            "The Coral Sea lies off the coast of Queensland, Australia.",
            "Queensland is a state in the north-east of Australia.",
            "The Great Barrier Reef is a coral reef system in that sea.",
        ],
    ),
    (
        "Who founded the company that makes the iPhone?",
        "Steve Jobs",
        ["Steven Jobs", "Jobs"],
        [
            "The company that makes the iPhone, Apple, was founded by Steve "
            "Jobs in 1976.",
            "The iPhone was released by Apple in 2007.",
            "Apple is headquartered in Cupertino, California.",
        ],
    ),
    (
        "In which country was the painter of The Persistence of Memory born?",
        "Spain",
        ["Spanish"],
        [
            "The painter of The Persistence of Memory, Salvador Dali, was born "
            "in Spain in 1904.",
            "The Persistence of Memory is a 1931 painting by Salvador Dali.",
            "Dali later worked in Paris and in the United States.",
        ],
    ),
]


def load_sample(limit: Optional[int] = None) -> Dataset:
    """Return the bundled offline sample dataset."""
    cases: List[BenchmarkCase] = []
    for index, (question, answer, aliases, context) in enumerate(_CASES):
        answers = [answer] + [a for a in aliases if a != answer]
        cases.append(
            BenchmarkCase(
                case_id=f"sample-{index:03d}",
                question=question,
                answers=answers,
                context=list(context),
                metadata={"kind": "extractive-smoke"},
            )
        )
    dataset = Dataset(
        name="sample",
        license="CC0-1.0 (hand-written for this repo)",
        scope=PER_CASE,
        cases=cases,
        version="1",
        source="in-repo",
        notes="Synthetic smoke-test set; not a published benchmark.",
    )
    return dataset.limit(limit)


register_dataset("sample", load_sample)
