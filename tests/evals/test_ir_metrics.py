# -*- coding: utf-8 -*-
"""Page-aggregated IR metrics tests (fork primitive).

Pure-function coverage, no model/store access: page-truth derivation join,
page dedup ordering, recall/nDCG arithmetic, citation hit rate, sentinel
behavior on empty truth, and type coercion of (book, page) keys.
"""

import math
import unittest

from semantica.evals import (
    citation_hit_rate,
    derive_chunk_truth,
    mean,
    ndcg_at_k,
    pages_of_retrieved,
    recall_at_k,
)


def _r(book, page, cid):
    return {"id": cid, "book": book, "page": page}


class TestDeriveChunkTruth(unittest.TestCase):
    def test_join_hits_only_truth_pages(self):
        chunks = [_r("a", 1, "c1"), _r("a", 2, "c2"), _r("b", 1, "c3")]
        truth = derive_chunk_truth([("a", 1), ("b", 1)], chunks)
        self.assertEqual(truth, {"c1", "c3"})

    def test_type_coercion(self):
        chunks = [{"id": "c1", "book": 1, "page": "3"}]
        truth = derive_chunk_truth([(1, 3)], chunks)  # book int / page str
        self.assertEqual(truth, {"c1"})

    def test_empty(self):
        self.assertEqual(derive_chunk_truth([("a", 1)], []), set())


class TestPagesOfRetrieved(unittest.TestCase):
    def test_ordered_dedup(self):
        retrieved = [_r("a", 1, "c1"), _r("a", 1, "c2"), _r("b", 2, "c3"), _r("a", 1, "c4")]
        self.assertEqual(pages_of_retrieved(retrieved), [("a", 1), ("b", 2)])

    def test_missing_keys_default(self):
        self.assertEqual(pages_of_retrieved([{}]), [("", 0)])


class TestRecallAtK(unittest.TestCase):
    def test_full_hit(self):
        retrieved = [_r("a", 1, "c1"), _r("b", 2, "c2")]
        self.assertEqual(recall_at_k(retrieved, [("a", 1), ("b", 2)]), 1.0)

    def test_partial_hit_respects_k(self):
        retrieved = [_r("a", 1, "c1"), _r("x", 9, "c2"), _r("b", 2, "c3")]
        # k=1 cuts off the third hit; only 1 of 2 truth pages within top-1
        self.assertEqual(recall_at_k(retrieved, [("a", 1), ("b", 2)], k=1), 0.5)

    def test_same_page_chunks_count_once(self):
        retrieved = [_r("a", 1, "c1"), _r("a", 1, "c2")]
        self.assertEqual(recall_at_k(retrieved, [("a", 1)]), 1.0)

    def test_empty_truth_sentinel_zero(self):
        self.assertEqual(recall_at_k([_r("a", 1, "c1")], []), 0.0)


class TestNdcgAtK(unittest.TestCase):
    def test_perfect_ordering(self):
        retrieved = [_r("a", 1, "c1"), _r("b", 2, "c2"), _r("c", 3, "c3")]
        self.assertAlmostEqual(
            ndcg_at_k(retrieved, [("a", 1), ("b", 2), ("c", 3)]), 1.0)

    def test_discount_by_page_position(self):
        # truth page ranked 2nd (page position) -> dcg = 1/log2(3)
        retrieved = [_r("x", 9, "c1"), _r("a", 1, "c2")]
        expected = (1.0 / math.log2(3)) / 1.0  # ideal for one truth page = 1
        self.assertAlmostEqual(ndcg_at_k(retrieved, [("a", 1)]), expected)

    def test_no_hit_zero(self):
        self.assertEqual(ndcg_at_k([_r("x", 9, "c1")], [("a", 1)]), 0.0)

    def test_empty_truth_sentinel_zero(self):
        self.assertEqual(ndcg_at_k([_r("a", 1, "c1")], []), 0.0)


class TestCitationHitRate(unittest.TestCase):
    def test_partial(self):
        self.assertEqual(
            citation_hit_rate([("a", 1), ("x", 9)], [("a", 1)]), 0.5)

    def test_no_citations_zero(self):
        self.assertEqual(citation_hit_rate([], [("a", 1)]), 0.0)

    def test_all_hit(self):
        self.assertEqual(
            citation_hit_rate([("a", 1), ("a", 1)], [("a", 1)]), 1.0)


class TestMean(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(mean([1.0, 0.5, 0.5]), 2.0 / 3)

    def test_empty_zero(self):
        self.assertEqual(mean([]), 0.0)


if __name__ == "__main__":
    unittest.main()
