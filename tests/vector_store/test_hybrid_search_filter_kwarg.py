"""HybridSearch.search(filter=...) used to vanish into **options (#1802)."""

import unittest
import warnings

import numpy as np

from semantica.vector_store.hybrid_search import HybridSearch, MetadataFilter, pop_legacy_filter
from semantica.vector_store.methods import hybrid_search


class TestHybridSearchFilterKwarg(unittest.TestCase):

    def setUp(self):
        self.query = np.array([1.0, 0.0])
        self.vectors = [
            np.array([1.0, 0.0]),
            np.array([0.9, 0.1]),
            np.array([0.0, 1.0]),
        ]
        self.metadata = [{"source": "wiki"}, {"source": "blog"}, {"source": "wiki"}]
        self.ids = ["a", "b", "c"]
        self.wiki = MetadataFilter().eq("source", "wiki")

    def _ids(self, results):
        return sorted(r["id"] for r in results)

    def test_filter_alias_is_applied(self):
        search = HybridSearch()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            results = search.search(
                self.query, self.vectors, self.metadata, self.ids, k=3, filter=self.wiki
            )
        self.assertEqual(self._ids(results), ["a", "c"])
        self.assertTrue(any(issubclass(w.category, DeprecationWarning) for w in caught))

    def test_filter_alias_matches_metadata_filter(self):
        search = HybridSearch()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            via_alias = search.search(
                self.query, self.vectors, self.metadata, self.ids, k=3, filter=self.wiki
            )
        via_name = search.search(
            self.query,
            self.vectors,
            self.metadata,
            self.ids,
            k=3,
            metadata_filter=self.wiki,
        )
        self.assertEqual(self._ids(via_alias), self._ids(via_name))

    def test_both_names_raise(self):
        search = HybridSearch()
        with self.assertRaises(TypeError):
            search.search(
                self.query,
                self.vectors,
                self.metadata,
                self.ids,
                k=3,
                filter=self.wiki,
                metadata_filter=self.wiki,
            )

    def test_filter_none_is_ignored_without_warning(self):
        search = HybridSearch()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            results = search.search(
                self.query, self.vectors, self.metadata, self.ids, k=3, filter=None
            )
        self.assertEqual(self._ids(results), ["a", "b", "c"])
        self.assertFalse(
            any(issubclass(w.category, DeprecationWarning) for w in caught)
        )

    def test_module_level_hybrid_search_accepts_the_alias(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = hybrid_search(
                self.query, self.vectors, self.metadata, self.ids, k=3, filter=self.wiki
            )
        self.assertEqual(self._ids(results), ["a", "c"])


    def test_warning_points_at_the_callers_line(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            HybridSearch().search(self.query, self.vectors, self.metadata, self.ids, k=3, filter=self.wiki)
            hybrid_search(self.query, self.vectors, self.metadata, self.ids, k=3, filter=self.wiki)
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        # one warning per call, both naming this file rather than library code
        self.assertEqual(len(deprecations), 2)
        self.assertEqual({w.filename for w in deprecations}, {__file__})

    def test_a_dict_filter_is_left_for_the_backend(self):
        # a plain dict is a backend-native filter (e.g. Pinecone): it keeps going
        # through **options to search_vectors, as before
        options = {"filter": {"source": "wiki"}}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertIsNone(pop_legacy_filter(options, None))
        self.assertEqual(options, {"filter": {"source": "wiki"}})
        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
