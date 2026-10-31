"""Tests for the phase-1 benchmark harness (``semantica.benchmarks``).

Everything here must run offline: the harness ships one hand-written sample
dataset and every other loader is exercised against small inline temp files, so
the suite never touches the network or a vendor SDK.
"""
import json

import pytest

from semantica.benchmarks import (
    CORPUS,
    PER_CASE,
    get_system,
    list_datasets,
    list_systems,
    load_dataset,
    run_benchmark,
)
from semantica.benchmarks import text as bt
from semantica.benchmarks.datasets import get_loader
from semantica.benchmarks.systems import SystemUnavailable, register_system
from semantica.benchmarks.types import BenchmarkCase, BenchmarkReport, Dataset


class _RecordingMemory:
    """A memory system that records what each group wrote and read.

    Used to prove the runner keeps separate memories apart: ``reset`` drops the
    current memory, ``ingest`` replaces it, and every answer snapshots it.
    """

    def __init__(self):
        self.memory = []
        self.ingest_log = []
        self.answers = []
        self.last_retrieved = []

    def reset(self):
        self.memory = []
        self.last_retrieved = []

    def ingest(self, passages, *, case_id=""):
        self.memory = [str(p) for p in passages]
        self.ingest_log.append((case_id, list(self.memory)))

    def answer(self, question, *, case_id=""):
        self.last_retrieved = list(self.memory)
        self.answers.append((question, list(self.memory)))
        return " ".join(self.memory)


class _FailingMemory:
    """A memory system whose ``reset`` or ``ingest`` blows up on demand."""

    def __init__(self, fail):
        self._fail = fail
        self.last_retrieved = []
        self.answered = False

    def reset(self):
        if self._fail == "reset":
            raise RuntimeError("backing store offline")

    def ingest(self, passages, *, case_id=""):
        if self._fail == "ingest":
            raise RuntimeError("write rejected")

    def answer(self, question, *, case_id=""):
        self.answered = True
        return "unreachable"


# --------------------------------------------------------------------------- #
# registry + sample dataset
# --------------------------------------------------------------------------- #
class TestRegistry:
    def test_known_datasets_are_registered(self):
        names = list_datasets()
        for name in ("sample", "hotpotqa", "musique", "locomo"):
            assert name in names

    def test_unknown_dataset_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_loader("does-not-exist")

    def test_load_dataset_dispatches_to_loader(self):
        dataset = load_dataset("sample")
        assert dataset.name == "sample"
        assert dataset.scope == PER_CASE


class TestSampleDataset:
    def test_has_cases_with_gold_answers(self):
        dataset = load_dataset("sample")
        assert len(dataset) == 6
        for case in dataset.cases:
            assert case.question
            assert case.answers
            assert case.context

    def test_limit_truncates(self):
        assert len(load_dataset("sample", limit=2)) == 2

    def test_is_per_case_scoped(self):
        assert load_dataset("sample").scope == PER_CASE


# --------------------------------------------------------------------------- #
# file-backed loaders
# --------------------------------------------------------------------------- #
class TestHotPotQALoader:
    def _write(self, tmp_path, payload):
        path = tmp_path / "hotpot.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_official_context_shape(self, tmp_path):
        payload = [
            {
                "_id": "q1",
                "question": "Which city?",
                "answer": "Paris",
                "context": [
                    ["France", ["Paris is the capital.", "It is on the Seine."]]
                ],
            }
        ]
        dataset = load_dataset("hotpotqa", path=self._write(tmp_path, payload))
        assert len(dataset) == 1
        case = dataset.cases[0]
        assert case.case_id == "q1"
        assert case.answers == ["Paris"]
        assert case.context == ["France: Paris is the capital. It is on the Seine."]

    def test_huggingface_context_shape(self, tmp_path):
        payload = [
            {
                "id": "q2",
                "question": "Which city?",
                "answer": "Paris",
                "context": {
                    "title": ["France"],
                    "sentences": [["Paris is the capital."]],
                },
            }
        ]
        dataset = load_dataset("hotpotqa", path=self._write(tmp_path, payload))
        assert dataset.cases[0].context == ["France: Paris is the capital."]

    def test_records_without_answer_are_skipped(self, tmp_path):
        payload = [
            {"_id": "ok", "question": "q", "answer": "a", "context": []},
            {"_id": "bad", "question": "q", "answer": "", "context": []},
        ]
        dataset = load_dataset("hotpotqa", path=self._write(tmp_path, payload))
        assert [c.case_id for c in dataset.cases] == ["ok"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_dataset("hotpotqa", path=str(tmp_path / "nope.json"))


class TestMuSiQueLoader:
    def _write(self, tmp_path, records):
        path = tmp_path / "musique.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
        return str(path)

    def test_parses_jsonl_and_folds_aliases(self, tmp_path):
        records = [
            {
                "id": "m1",
                "question": "Who?",
                "answer": "Bach",
                "answer_aliases": ["Johann Sebastian Bach"],
                "paragraphs": [
                    {"title": "Composer", "paragraph_text": "Bach wrote it."}
                ],
            }
        ]
        dataset = load_dataset("musique", path=self._write(tmp_path, records))
        case = dataset.cases[0]
        assert case.answers == ["Bach", "Johann Sebastian Bach"]
        assert case.context == ["Composer: Bach wrote it."]

    def test_records_without_answer_are_skipped(self, tmp_path):
        records = [
            {"id": "ok", "question": "q", "answer": "a", "paragraphs": []},
            {"id": "bad", "question": "q", "answer": "", "paragraphs": []},
        ]
        dataset = load_dataset("musique", path=self._write(tmp_path, records))
        assert [c.case_id for c in dataset.cases] == ["ok"]


class TestLoCoMoLoader:
    def _write(self, tmp_path, payload):
        path = tmp_path / "locomo.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def _payload(self):
        return [
            {
                "sample_id": "conv-1",
                "conversation": {
                    "speaker_a": "Alice",
                    "speaker_b": "Bob",
                    "session_1_date_time": "1 Jan 2024",
                    "session_1": [
                        {"speaker": "Alice", "text": "I love hiking."},
                        {"speaker": "Bob", "text": "I prefer chess."},
                    ],
                    "session_2_date_time": "2 Jan 2024",
                    "session_2": [{"speaker": "Alice", "text": "I went hiking again."}],
                },
                "qa": [
                    {
                        "question": "What does Alice love?",
                        "answer": "hiking",
                        "category": 4,
                    },
                    {"question": "Who likes chess?", "answer": "Bob", "category": 2},
                ],
            }
        ]

    def test_scope_is_corpus(self, tmp_path):
        dataset = load_dataset("locomo", path=self._write(tmp_path, self._payload()))
        assert dataset.scope == CORPUS

    def test_sessions_are_flattened_with_dates_and_speakers(self, tmp_path):
        dataset = load_dataset("locomo", path=self._write(tmp_path, self._payload()))
        context = dataset.cases[0].context
        assert "[1 Jan 2024]" in context
        assert "Alice: I love hiking." in context
        assert "[2 Jan 2024]" in context

    def test_category_filter(self, tmp_path):
        path = self._write(tmp_path, self._payload())
        dataset = load_dataset("locomo", path=path, categories=[4])
        assert len(dataset) == 1
        assert dataset.cases[0].metadata["category_name"] == "single-hop"

    def test_license_surfaced_as_non_commercial(self, tmp_path):
        dataset = load_dataset("locomo", path=self._write(tmp_path, self._payload()))
        assert "NON-COMMERCIAL" in dataset.license

    def test_group_by_is_sample_id(self, tmp_path):
        dataset = load_dataset("locomo", path=self._write(tmp_path, self._payload()))
        assert dataset.group_by == "sample_id"

    def test_adversarial_answer_is_metadata_only(self, tmp_path):
        # Category 5 ships a tempting wrong answer next to the real one; it must
        # never reach the gold list, or a system would be credited for the trap.
        payload = [
            {
                "sample_id": "conv-9",
                "conversation": {"session_1": [{"speaker": "A", "text": "hi"}]},
                "qa": [
                    {
                        "question": "Where does Alice live?",
                        "answer": "Paris",
                        "category": 5,
                        "adversarial_answer": "London",
                    }
                ],
            }
        ]
        dataset = load_dataset("locomo", path=self._write(tmp_path, payload))
        case = dataset.cases[0]
        assert case.answers == ["Paris"]
        assert "London" not in case.answers
        assert case.metadata["adversarial_answer"] == "London"

    def test_question_without_real_answer_is_skipped(self, tmp_path):
        # An adversarial question with no real gold answer must be dropped, not
        # scored against its distractor.
        payload = [
            {
                "sample_id": "conv-9",
                "conversation": {"session_1": [{"speaker": "A", "text": "hi"}]},
                "qa": [
                    {
                        "question": "Trap?",
                        "category": 5,
                        "adversarial_answer": "London",
                    },
                    {"question": "Real?", "answer": "Paris", "category": 5},
                ],
            }
        ]
        dataset = load_dataset("locomo", path=self._write(tmp_path, payload))
        assert [case.question for case in dataset.cases] == ["Real?"]


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #
class TestTextHelpers:
    def test_tokenize_lowercases_and_drops_punctuation(self):
        assert bt.tokenize("The Quick, brown FOX!") == ["the", "quick", "brown", "fox"]

    def test_split_sentences(self):
        assert bt.split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]

    def test_overlap_score_is_share_of_question_words(self):
        assert bt.overlap_score("red apple", "the apple is red") == pytest.approx(1.0)
        assert bt.overlap_score("red apple", "blue car") == 0.0

    def test_best_sentence_picks_highest_overlap(self):
        passages = ["The capital of France is Paris.", "Paris is a large city."]
        assert bt.best_sentence("What is the capital of France?", passages) == (
            "The capital of France is Paris."
        )

    def test_best_sentence_empty_input(self):
        assert bt.best_sentence("q", []) == ""

    def test_bm25_returns_source_texts_not_tokens(self):
        index = bt.BM25()
        index.add(["alpha beta gamma", "delta epsilon"])
        hits = index.search("alpha")
        assert hits == ["alpha beta gamma"]

    def test_bm25_ranks_best_match_first(self):
        index = bt.BM25()
        index.add(["unrelated text here", "alpha beta gamma alpha"])
        assert index.search("alpha beta", top_k=1) == ["alpha beta gamma alpha"]

    def test_bm25_empty_index_returns_empty(self):
        assert bt.BM25().search("anything") == []

    def test_bm25_clear_empties_index(self):
        index = bt.BM25()
        index.add(["alpha"])
        index.clear()
        assert len(index) == 0
        assert index.search("alpha") == []


# --------------------------------------------------------------------------- #
# systems
# --------------------------------------------------------------------------- #
class TestSystemRegistry:
    def test_reference_systems_are_listed(self):
        names = list_systems()
        assert "lexical" in names
        assert "semantica" in names

    def test_unknown_system_raises_unavailable(self):
        with pytest.raises(SystemUnavailable):
            get_system("no-such-system")


class TestLexicalSystem:
    def test_extracts_the_answer_sentence(self):
        system = get_system("lexical")
        system.reset()
        system.ingest(
            [
                "The telephone inventor Alexander Graham Bell was born in Scotland.",
                "The telephone was patented in the United States.",
            ],
            case_id="c1",
        )
        answer = system.answer(
            "Which country was the telephone inventor born in?", case_id="c1"
        )
        assert answer == (
            "The telephone inventor Alexander Graham Bell was born in Scotland."
        )

    def test_reset_clears_memory(self):
        system = get_system("lexical")
        system.ingest(["only passage"], case_id="c1")
        system.reset()
        assert system.answer("only passage?", case_id="c1") == ""

    def test_answer_records_retrieved_passages(self):
        system = get_system("lexical")
        system.reset()
        system.ingest(["alpha bravo", "charlie delta"], case_id="c1")
        system.answer("alpha bravo?", case_id="c1")
        assert system.last_retrieved == ["alpha bravo"]

    def test_reset_clears_retrieved_passages(self):
        system = get_system("lexical")
        system.ingest(["alpha"], case_id="c1")
        system.answer("alpha", case_id="c1")
        system.reset()
        assert system.last_retrieved == []


# --------------------------------------------------------------------------- #
# end-to-end (offline)
# --------------------------------------------------------------------------- #
class TestRunBenchmark:
    def test_sample_plus_lexical_scores_above_floor(self):
        report = run_benchmark([load_dataset("sample")], ["lexical"])
        assert isinstance(report, BenchmarkReport)
        assert report.scores["lexical/sample"] > 0.0
        result = report.results[0]
        assert result.n == 6
        assert result.errors == 0

    def test_unavailable_system_is_skipped_not_fatal(self):
        report = run_benchmark([load_dataset("sample")], ["no-such-system"])
        assert report.results == []
        assert [entry["system"] for entry in report.skipped] == ["no-such-system"]

    def test_strict_mode_raises_on_unavailable_system(self):
        with pytest.raises(SystemUnavailable):
            run_benchmark(
                [load_dataset("sample")], ["no-such-system"], on_error="raise"
            )

    def test_markdown_table_mentions_system_and_dataset(self):
        report = run_benchmark([load_dataset("sample")], ["lexical"])
        table = report.to_markdown_table()
        assert "lexical" in table
        assert "sample" in table

    def test_report_serializes(self):
        report = run_benchmark([load_dataset("sample")], ["lexical"])
        payload = report.as_dict()
        assert payload["systems"] == ["lexical"]
        assert payload["datasets"] == ["sample"]
        assert "skipped" in payload

    def test_corpus_scope_ingests_once(self):
        dataset = Dataset(
            name="mini",
            license="test",
            scope=CORPUS,
            cases=[
                BenchmarkCase(case_id="a", question="Where is Paris?",
                              answers=["France"], context=["Paris is in France."]),
                BenchmarkCase(case_id="b", question="Where is Paris?",
                              answers=["France"], context=["Paris is in France."]),
            ],
        )
        report = run_benchmark([dataset], ["lexical"])
        assert report.results[0].n == 2
        assert report.results[0].errors == 0

    def test_predictions_carry_retrieved_passages(self):
        report = run_benchmark([load_dataset("sample")], ["lexical"])
        predictions = report.results[0].predictions
        assert predictions
        # Every sample question shares content words with its evidence, so the
        # lexical floor always retrieves something; the report must show it,
        # otherwise per-case retrieval (the main debugging surface) is invisible.
        assert all(prediction.retrieved for prediction in predictions)
        by_id = {prediction.case_id: prediction for prediction in predictions}
        assert by_id["sample-000"].retrieved[0] == (
            "The novel Neuromancer was written by William Gibson and published in 1984."
        )

    def _two_conversations(self):
        return Dataset(
            name="two-conversations",
            license="test",
            scope=CORPUS,
            group_by="sample_id",
            cases=[
                BenchmarkCase(
                    case_id="a1",
                    question="qa",
                    answers=["alpha"],
                    context=["alpha evidence"],
                    metadata={"sample_id": "conv-a"},
                ),
                BenchmarkCase(
                    case_id="b1",
                    question="qb",
                    answers=["bravo"],
                    context=["bravo evidence"],
                    metadata={"sample_id": "conv-b"},
                ),
            ],
        )

    def test_group_by_gives_each_conversation_its_own_memory(self):
        probe = _RecordingMemory()
        register_system("probe-grouped-memory", lambda **options: probe)

        report = run_benchmark([self._two_conversations()], ["probe-grouped-memory"])

        assert report.results[0].errors == 0
        # One memory per conversation, each holding only its own evidence.
        assert probe.ingest_log == [
            ("conv-a", ["alpha evidence"]),
            ("conv-b", ["bravo evidence"]),
        ]
        # ...and no answer could see the other conversation's evidence.
        assert probe.answers == [
            ("qa", ["alpha evidence"]),
            ("qb", ["bravo evidence"]),
        ]

    def test_corpus_without_group_by_uses_one_shared_memory(self):
        probe = _RecordingMemory()
        register_system("probe-shared-memory", lambda **options: probe)
        dataset = self._two_conversations()
        dataset = Dataset(
            name=dataset.name,
            license=dataset.license,
            scope=CORPUS,
            cases=dataset.cases,
        )

        run_benchmark([dataset], ["probe-shared-memory"])

        # Without group_by the whole corpus is a single memory, ingested once.
        assert len(probe.ingest_log) == 1
        assert probe.ingest_log[0][1] == ["alpha evidence", "bravo evidence"]

    def test_reset_failure_is_recorded_not_fatal(self):
        probe = _FailingMemory("reset")
        register_system("probe-failing-reset", lambda **options: probe)
        dataset = Dataset(
            name="mini",
            license="test",
            scope=PER_CASE,
            cases=[
                BenchmarkCase(case_id="c1", question="q", answers=["a"], context=["x"]),
                BenchmarkCase(case_id="c2", question="q", answers=["a"], context=["x"]),
            ],
        )

        result = run_benchmark([dataset], ["probe-failing-reset"]).results[0]

        assert result.n == 2
        assert result.errors == 2
        assert all(
            "RuntimeError" in prediction.error for prediction in result.predictions
        )
        # A failed set-up must short-circuit the question, not answer on stale state.
        assert probe.answered is False

    def test_corpus_prep_failure_marks_every_case_in_the_group(self):
        probe = _FailingMemory("ingest")
        register_system("probe-failing-ingest", lambda **options: probe)
        dataset = Dataset(
            name="mini-corpus",
            license="test",
            scope=CORPUS,
            cases=[
                BenchmarkCase(case_id="c1", question="q", answers=["a"], context=["x"]),
                BenchmarkCase(case_id="c2", question="q", answers=["a"], context=["x"]),
            ],
        )

        result = run_benchmark([dataset], ["probe-failing-ingest"]).results[0]

        assert result.errors == 2
        assert all(
            "RuntimeError" in prediction.error for prediction in result.predictions
        )

    def test_unknown_primary_metric_raises_instead_of_scoring_zero(self):
        with pytest.raises(ValueError):
            run_benchmark(
                [load_dataset("sample")], ["lexical"], primary_metric="tokn_f1"
            )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
class TestCli:
    def test_list_command_exits_cleanly(self, capsys):
        from semantica.benchmarks.__main__ import main

        assert main(["list"]) == 0
        out = capsys.readouterr().out
        assert "sample" in out

    def test_run_command_offline(self, capsys):
        from semantica.benchmarks.__main__ import main

        code = main(["run", "--dataset", "sample", "--system", "lexical", "--quiet"])
        assert code == 0
        assert "lexical" in capsys.readouterr().out

    def test_unknown_metric_exits_with_error(self):
        from semantica.benchmarks.__main__ import main

        argv = [
            "run",
            "--dataset",
            "sample",
            "--system",
            "lexical",
            "--metric",
            "tpyo",
        ]
        with pytest.raises(SystemExit):
            main(argv)
