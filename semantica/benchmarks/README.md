# Benchmarks

Run memory systems over question-answering benchmarks and score them the same
way, so a number from this harness and a number from `semantica.evals` mean the
same thing.

This is phase 1. It is a working harness with adapters, not a leaderboard: no
dataset ships with it beyond a tiny hand-written smoke set, and no result table
is published yet.

## Run it

Nothing needs installing for the offline sample:

```bash
python -m semantica.benchmarks list
python -m semantica.benchmarks run --dataset sample --system lexical --system semantica
```

Datasets that are too large to vendored are read from a local file you obtained
yourself:

```bash
python -m semantica.benchmarks run \
  --dataset hotpotqa --data hotpotqa=/path/to/hotpot_dev_distractor_v1.json \
  --system lexical --limit 200 --markdown report.md
```

The harness never downloads anything. Each loader documents its own licence and
expects the file's usual upstream format.

## Datasets

| name | shape | scope | licence | upstream | note |
| --- | --- | --- | --- | --- | --- |
| `sample` | 6 questions | per case | CC0-1.0 | bundled, `datasets/sample.py` | hand-written, for smoke tests |
| `hotpotqa` | official JSON or HF export | per case | CC BY-SA 4.0 | https://hotpotqa.github.io/ | distractor setting |
| `musique` | JSONL | per case | CC BY 4.0 | https://github.com/StonyBrookNLP/musique | answerable split |
| `locomo` | `locomo10.json` | corpus | CC BY-NC 4.0 | https://github.com/snap-research/locomo/blob/main/LICENSE.txt | **non-commercial**, adapter only |

Each licence was checked against its upstream on 2026-10-01. One thing worth
knowing: the `hotpotqa/hotpot` code repository is Apache-2.0, but the dataset
itself is CC BY-SA 4.0. This harness reads only the data file, so the dataset
terms are the ones that apply here.

`locomo` is deliberately excluded from defaults. Its licence is non-commercial,
so shipping its data inside this repo would pass that restriction on to everyone
who clones it. The loader stays so you can point it at your own copy.

## Scope

A dataset is either `per_case` or `corpus`, and the difference is who owns the
memory.

- `per_case` — each question comes with its own passages. The system is reset
  and fed only those passages before answering. This is reading comprehension,
  and it is what HotPotQA and MuSiQue measure.
- `corpus` — every passage is ingested once and then all questions query the
  same long-lived memory. This is what LoCoMo measures, and it is the setting a
  memory system should actually be judged in.

Getting this wrong flatters a system: a retrieval index rebuilt per question can
look strong on `per_case` while having no memory at all.

## Systems

| name | backed by | availability |
| --- | --- | --- |
| `lexical` | in-repo BM25 + sentence pick | always |
| `semantica` | `semantica.context.AgentMemory` | always |
| `mem0` | `mem0` | needs the package |
| `graphiti` | `graphiti-core` + a configured client | needs the package and a client |
| `cognee` | `cognee` | needs the package |

Importing this package imports none of the vendor SDKs. A missing backend is
recorded as a skipped row and the rest of the run continues; `--strict` turns
that into a failure instead, which is what CI wants.

The three hosted adapters take an injected client, so your own credentials never
have to live in this repo or in a test.

## Scoring

Predictions go to `semantica.evals.evaluate`, not to a private copy of the
metrics. The primary metric is `token_f1` (SQuAD-style normalization), reported
next to `normalized_exact_match`.

Every system defaults to the same dependency-free extractive reader: the
sentence with the most question-word overlap. That is deliberate, because it
keeps the *retrieval* layer the only thing that differs between systems unless
you supply a real reader with `reader=`. It is also why the sample dataset's
exact-match column is zero: predictions are whole sentences, and a whole
sentence is not a short answer.

## Add your own

A system is anything that implements four methods:

```python
class MemorySystem(Protocol):
    name: str
    def reset(self) -> None: ...
    def ingest(self, passages, *, case_id="") -> None: ...
    def answer(self, question, *, case_id="") -> str: ...
```

Register it with `register_system`, or hand an instance in directly with
`run_benchmark(..., system_options={"name": {...}})`.

A dataset is a `Dataset` of `BenchmarkCase`. Put a loader next to the existing
ones and call `register_dataset`.
