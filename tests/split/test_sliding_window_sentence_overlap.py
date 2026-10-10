"""Acceptance tests for the sentence-overlap behavior for issue #1800.

Sentence grouping packs complete sentences up to chunk_size. Overlap is a
character budget for the longest contiguous suffix of complete sentences that
also leaves room for new content. Punctuation and internal separators count
toward that budget; outer whitespace may be stripped as in existing chunks.
Long sentences fall back to character windows. Stride controls character windows
only; sentence grouping takes precedence over an explicitly configured stride.
Long-sentence fallback caps stride at chunk_size to preserve content coverage.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from semantica.split.methods import split_sliding_window
from semantica.split.sliding_window_chunker import SlidingWindowChunker


def _assert_source_coverage(text, chunks, chunk_size):
    """Check actual content as well as reported offsets, allowing outer trimming."""
    assert chunks
    covered = set()
    for chunk in chunks:
        assert 0 <= chunk.start_index < chunk.end_index <= len(text)
        assert chunk.text
        assert len(chunk.text) <= chunk_size
        assert chunk.text.strip() == text[chunk.start_index : chunk.end_index].strip()
        covered.update(range(chunk.start_index, chunk.end_index))

    missing = [
        (index, char)
        for index, char in enumerate(text)
        if not char.isspace() and index not in covered
    ]
    assert not missing, f"Uncovered non-whitespace characters: {missing!r}"


def _assert_sentence_groups(text, chunk_size, overlap, expected):
    chunks = SlidingWindowChunker(chunk_size=chunk_size, overlap=overlap).chunk(
        text, preserve_boundaries=True
    )
    _assert_source_coverage(text, chunks, chunk_size)
    assert [chunk.text for chunk in chunks] == expected

    for previous, current in zip(chunks, chunks[1:]):
        assert current.start_index > previous.start_index
        assert (
            current.end_index > previous.end_index
        ), "Every group must add new content"
        shared = text[current.start_index : previous.end_index].strip()
        assert len(shared) <= overlap


@pytest.mark.parametrize(
    "overlap, expected",
    [
        pytest.param(0, ["One.Two.Six.", "Ten.End."], id="zero-budget"),
        pytest.param(3, ["One.Two.Six.", "Ten.End."], id="last-sentence-does-not-fit"),
        pytest.param(4, ["One.Two.Six.", "Six.Ten.End."], id="one-sentence-exact-fit"),
        pytest.param(
            7, ["One.Two.Six.", "Six.Ten.End."], id="no-partial-extra-sentence"
        ),
        pytest.param(
            8,
            ["One.Two.Six.", "Two.Six.Ten.", "Six.Ten.End."],
            id="two-complete-sentences",
        ),
    ],
)
def test_sentence_overlap_uses_a_whole_sentence_budget(overlap, expected):
    # Each sentence occupies four characters, including its punctuation.
    _assert_sentence_groups("One.Two.Six.Ten.End.", 12, overlap, expected)


def test_sentence_overlap_cannot_skip_the_last_sentence_to_fit_an_earlier_one():
    # "Go." fits the budget, but "Longest." does not: the overlap must be a suffix.
    _assert_sentence_groups("Go.Longest.End.", 12, 3, ["Go.Longest.", "End."])


def test_sentence_overlap_shrinks_to_leave_room_for_a_new_sentence():
    # "Run.Sit." fits budget 8, but adding "Longer." would exceed chunk_size 12.
    _assert_sentence_groups(
        "Go.Run.Sit.Longer.End.", 12, 8, ["Go.Run.Sit.", "Sit.Longer.", "Longer.End."]
    )


def test_sentence_overlap_is_zero_when_even_one_repeated_sentence_would_overflow():
    # "Sit." fits budget 4, but "Sit.Longword." would occupy 13 characters.
    _assert_sentence_groups(
        "Go.Run.Sit.Longword.End.", 12, 4, ["Go.Run.Sit.", "Longword.", "End."]
    )


@pytest.mark.parametrize(
    "overlap, expected",
    [
        pytest.param(
            8, ["One. Two. Six.", "Six. Ten. End."], id="separator-over-budget"
        ),
        pytest.param(
            9,
            ["One. Two. Six.", "Two. Six. Ten.", "Six. Ten. End."],
            id="separator-included-in-budget",
        ),
    ],
)
def test_sentence_overlap_counts_internal_whitespace(overlap, expected):
    # "Two. Six." is nine characters, not eight; leading/trailing spaces are ignored.
    _assert_sentence_groups("One. Two. Six. Ten. End.", 14, overlap, expected)


def test_sentence_overlap_handles_mixed_sentence_terminators():
    _assert_sentence_groups(
        "One!Two?Six.Ten!End?", 12, 4, ["One!Two?Six.", "Six.Ten!End?"]
    )


def test_large_sentence_overlap_budget_still_makes_progress():
    # The first group is 11 characters and the budget is also 11. A naive
    # end - overlap update can get stuck at zero. Isolate that risk so pytest
    # can kill a non-terminating implementation instead of hanging indefinitely.
    script = textwrap.dedent("""
        import json
        from semantica.split.sliding_window_chunker import SlidingWindowChunker

        chunker = SlidingWindowChunker(chunk_size=12, overlap=11)
        chunker.progress_tracker.enabled = False
        chunks = chunker.chunk("Go.Run.Sit.Longer.End.", preserve_boundaries=True)
        print(json.dumps([
            [chunk.text, chunk.start_index, chunk.end_index] for chunk in chunks
        ]))
        """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout) == [
        ["Go.Run.Sit.", 0, 11],
        ["Sit.Longer.", 7, 18],
        ["Longer.End.", 11, 22],
    ]


@pytest.mark.parametrize(
    "preserve_boundaries", [False, True], ids=["fixed", "fallback"]
)
def test_long_sentence_keeps_character_overlap(preserve_boundaries):
    text = "abcdefghijklmnopqrstuvwxy."
    chunks = SlidingWindowChunker(chunk_size=8, overlap=3).chunk(
        text, preserve_boundaries=preserve_boundaries
    )
    _assert_source_coverage(text, chunks, 8)
    assert len(chunks) >= 2
    assert [(chunk.start_index, chunk.end_index) for chunk in chunks[:2]] == [
        (0, 8),
        (5, 13),
    ]
    for previous, current in zip(chunks, chunks[1:]):
        assert current.start_index > previous.start_index
        shared = min(3, len(previous.text), len(current.text))
        assert previous.text[-shared:] == current.text[:shared]
    # Do not prescribe the existing character-fallback behavior for final tails.


def test_long_sentence_fallback_returns_to_complete_sentence_groups():
    long_sentence = "abcdefghijklmnopqrstuvwxy."
    text = "Hi." + long_sentence + "Bye.End."
    chunks = SlidingWindowChunker(chunk_size=8, overlap=3).chunk(text)

    _assert_source_coverage(text, chunks, 8)
    assert chunks[0].text == "Hi."
    assert chunks[-1].text == "Bye.End."
    assert chunks[0].metadata["boundary_preserved"] is True
    assert chunks[-1].metadata["boundary_preserved"] is True

    fragments = chunks[1:-1]
    assert len(fragments) >= 2
    assert [(chunk.start_index, chunk.end_index) for chunk in fragments[:2]] == [
        (3, 11),
        (8, 16),
    ]
    for fragment in fragments:
        assert 3 <= fragment.start_index < fragment.end_index <= 3 + len(long_sentence)
        assert fragment.metadata["boundary_preserved"] is False
    # A fragment of the long sentence must not be repeated in the next sentence group.
    assert chunks[-1].metadata["has_overlap"] is False


def test_unterminated_final_sentence_is_kept_as_a_complete_unit():
    _assert_sentence_groups("One.Two.Tail", 8, 4, ["One.Two.", "Two.Tail"])


def test_sentence_groups_preserve_punctuation_runs_and_internal_newlines():
    _assert_sentence_groups(
        "  One?!\n\nTwo.\nTail  ", 11, 4, ["One?!\n\nTwo.", "Two.\nTail"]
    )


@pytest.mark.parametrize("text", [" \t ", "\n\n \r\n"])
def test_whitespace_only_input_does_not_emit_sentence_groups(text):
    assert SlidingWindowChunker(chunk_size=8, overlap=3).chunk(text) == []


@pytest.mark.parametrize("stride", [1, 20])
def test_sentence_grouping_takes_precedence_over_custom_stride(stride):
    text = "One.Two.Six.Ten.End."
    chunker = SlidingWindowChunker(chunk_size=12, overlap=4, stride=stride)
    chunks = chunker.chunk(text)

    _assert_source_coverage(text, chunks, 12)
    assert [chunk.text for chunk in chunks] == ["One.Two.Six.", "Six.Ten.End."]
    assert chunker.stride == stride


@pytest.mark.parametrize(
    "preserve_boundaries", [False, True], ids=["fixed", "fallback"]
)
def test_character_windows_use_custom_stride(preserve_boundaries):
    text = "abcdefghijklmnopqrstuvwxy."
    chunks = SlidingWindowChunker(chunk_size=8, overlap=3, stride=2).chunk(
        text, preserve_boundaries=preserve_boundaries
    )

    _assert_source_coverage(text, chunks, 8)
    assert [(chunk.start_index, chunk.end_index) for chunk in chunks[:3]] == [
        (0, 8),
        (2, 10),
        (4, 12),
    ]
    # Explicit stride 2 determines six shared characters, overriding the default step.
    assert chunks[0].text[-6:] == chunks[1].text[:6]


@pytest.mark.parametrize("stride", [8, 20, 64])
@pytest.mark.parametrize(
    "text",
    [
        "abcdefghijklmnopqrstuvwxy.",
        "Hi.abcdefghijklmnopqrstuvwxy.Bye.End.",
        "abcdefghijklmnopqrstuvwxy",
    ],
    ids=["long-sentence", "mixed-sentences", "unterminated"],
)
def test_long_sentence_fallback_caps_stride_to_preserve_coverage(stride, text):
    chunker = SlidingWindowChunker(chunk_size=8, overlap=3, stride=stride)

    chunks = chunker.chunk(text)

    _assert_source_coverage(text, chunks, 8)
    assert "".join(chunk.text for chunk in chunks) == text
    assert all(not chunk.metadata["has_overlap"] for chunk in chunks)
    assert chunker.stride == stride


def test_fixed_windows_keep_wide_stride_after_long_sentence_fallback():
    text = "abcdefghijklmnopqrstuvwxy."
    chunker = SlidingWindowChunker(chunk_size=8, overlap=3, stride=20)
    chunker.chunk(text)

    chunks = chunker.chunk(text, preserve_boundaries=False)

    assert [(chunk.start_index, chunk.end_index) for chunk in chunks] == [
        (0, 8),
        (20, 26),
    ]
    assert [chunk.text for chunk in chunks] == [text[:8], text[20:]]
    assert chunker.stride == 20


@pytest.mark.parametrize("overlap", [0, 8], ids=["zero-overlap", "small-overlap"])
def test_many_short_sentences_do_not_retain_all_offsets(overlap):
    # Isolate tracing from pytest's own allocations and any existing tracer.
    # A single large chunk isolates auxiliary memory from output-list growth.
    script = textwrap.dedent("""
        import json
        import sys
        import tracemalloc
        from semantica.split.sliding_window_chunker import SlidingWindowChunker

        text = "a." * 50_000
        chunker = SlidingWindowChunker(chunk_size=len(text), overlap=int(sys.argv[1]))
        chunker._chunk_with_boundaries("Warmup.")
        tracemalloc.stop()
        tracemalloc.start()
        try:
            chunks = chunker._chunk_with_boundaries(text)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert (chunks[0].start_index, chunks[0].end_index) == (0, len(text))
        print(json.dumps({"peak": peak, "text_length": len(text)}))
        """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(overlap)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    measurement = json.loads(result.stdout)
    # Allow several text copies plus fixed overhead, but not one Python offset
    # per sentence. Measure peak usage since the queue is freed before return.
    assert measurement["peak"] < 4 * measurement["text_length"] + 128 * 1024


def test_sliding_window_method_covers_long_sentences_with_wide_stride():
    text = "abcdefghijklmnopqrstuvwxy."
    chunks = split_sliding_window(text, chunk_size=8, overlap=3, stride=20)

    _assert_source_coverage(text, chunks, 8)
    assert "".join(chunk.text for chunk in chunks) == text
    assert all(chunk.metadata["boundary_preserved"] is False for chunk in chunks)


@pytest.mark.parametrize("overlap, expected", [(3, [False, False]), (4, [False, True])])
def test_sentence_overlap_metadata_reports_actual_overlap(overlap, expected):
    chunks = SlidingWindowChunker(chunk_size=12, overlap=overlap).chunk(
        "One.Two.Six.Ten.End."
    )
    assert [chunk.metadata["has_overlap"] for chunk in chunks] == expected


def test_sliding_window_method_preserves_the_sentence_overlap_contract():
    chunks = split_sliding_window(
        "One.Two.Six.Ten.End.", chunk_size=12, overlap=4, preserve_boundaries=True
    )
    assert [chunk.text for chunk in chunks] == ["One.Two.Six.", "Six.Ten.End."]
    assert all(chunk.metadata["boundary_preserved"] for chunk in chunks)
