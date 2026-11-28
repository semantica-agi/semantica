import pytest

from semantica.split import TextSplitter


@pytest.mark.parametrize("method", ["character", "recursive"])
def test_zero_overlap_keeps_chunks_disjoint(method):
    text = "".join(f"{i:04d}" for i in range(300))
    splitter = TextSplitter(method=method, chunk_size=500, chunk_overlap=0)

    chunks = splitter.split(text)

    assert splitter.chunk_overlap == 0
    assert [(c.start_index, c.end_index) for c in chunks] == [
        (0, 500),
        (500, 1000),
        (1000, 1200),
    ]
    assert "".join(c.text for c in chunks) == text


def test_zero_overlap_keeps_word_chunks_disjoint():
    text = "one two three four five six seven eight nine"
    splitter = TextSplitter(method="word", chunk_size=3, chunk_overlap=0)

    chunks = splitter.split(text)

    assert [c.text for c in chunks] == [
        "one two three",
        "four five six",
        "seven eight nine",
    ]


def test_omitted_sizes_use_split_config(monkeypatch):
    monkeypatch.setenv("SPLIT_CHUNK_SIZE", "300")
    monkeypatch.setenv("SPLIT_CHUNK_OVERLAP", "50")

    splitter = TextSplitter(method="character")

    assert (splitter.chunk_size, splitter.chunk_overlap) == (300, 50)


def test_omitted_sizes_default_without_split_config(monkeypatch):
    monkeypatch.delenv("SPLIT_CHUNK_SIZE", raising=False)
    monkeypatch.delenv("SPLIT_CHUNK_OVERLAP", raising=False)

    splitter = TextSplitter(method="character")

    assert (splitter.chunk_size, splitter.chunk_overlap) == (1000, 200)
