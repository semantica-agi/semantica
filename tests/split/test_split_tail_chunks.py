"""The last chunk used to be followed by shrinking copies of the tail (#1813)."""

import unittest

from semantica.split.methods import (
    split_by_characters,
    split_by_tokens,
    split_by_words,
)


class TestSplitTailChunks(unittest.TestCase):

    def test_characters_short_text_is_one_chunk(self):
        chunks = split_by_characters("word " * 6, chunk_size=50, chunk_overlap=10)
        self.assertEqual([c.text for c in chunks], ["word " * 6])

    def test_characters_keeps_overlap_and_stops_at_the_end(self):
        text = "abcdefghij" * 10  # 100 chars
        chunks = split_by_characters(text, chunk_size=40, chunk_overlap=10)
        self.assertEqual(
            [(c.start_index, c.end_index) for c in chunks],
            [(0, 40), (30, 70), (60, 100)],
        )

    def test_characters_exact_fit(self):
        chunks = split_by_characters("x" * 50, chunk_size=50, chunk_overlap=10)
        self.assertEqual(len(chunks), 1)

    def test_words_short_text_is_one_chunk(self):
        chunks = split_by_words("word " * 6, chunk_size=50, chunk_overlap=10)
        self.assertEqual([c.text for c in chunks], ["word word word word word word"])

    def test_words_keeps_overlap_and_stops_at_the_end(self):
        text = " ".join(f"w{i}" for i in range(10))
        chunks = split_by_words(text, chunk_size=4, chunk_overlap=1)
        self.assertEqual(
            [c.text for c in chunks],
            ["w0 w1 w2 w3", "w3 w4 w5 w6", "w6 w7 w8 w9"],
        )

    def test_tokens_short_text_is_one_chunk(self):
        chunks = split_by_tokens("word " * 6, chunk_size=50, chunk_overlap=10)
        self.assertEqual(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
