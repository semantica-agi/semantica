import unittest
import os
import sys
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from semantica.semantic_extract.triplet_extractor import Triplet
from semantica.triplet_store.blazegraph_store import BlazegraphStore


class TestBlazegraphStoreSerialization(unittest.TestCase):
    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_serializes_uri_object(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:knows",
            object="urn:entity:person:2",
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "<urn:entity:person:2>",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_serializes_literal_object(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:name",
            object="Jane Doe",
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"Jane Doe\"",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_escapes_literal_object(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:note",
            object='line "one"\\line2',
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"line \\\"one\\\"\\\\line2\"",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_serializes_typed_literal(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:age",
            object="42",
            metadata={"datatype": "http://www.w3.org/2001/XMLSchema#integer"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"42\"^^<http://www.w3.org/2001/XMLSchema#integer>",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_build_insert_data_uses_formatter(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:name",
            object="Jane Doe",
        )
        with patch.object(store, "_format_object_for_sparql", return_value="\"Jane Doe\"") as mock_fmt:
            insert_data = store._build_insert_data([triplet])
            mock_fmt.assert_called_once_with(triplet)
            self.assertEqual(
                insert_data,
                "<urn:entity:person:1> <urn:property:name> \"Jane Doe\" .",
            )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_serializes_language_literal(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:label",
            object="Color",
            metadata={"lang": "en"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(obj, "\"Color\"@en")

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_does_not_treat_invalid_uri_like_text_as_uri(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:note",
            object="http not a uri",
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(obj, "\"http not a uri\"")

    # --- Bug 1: prefixed datatype expansion ---

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_expands_xsd_prefix_to_full_iri(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:age",
            object="42",
            metadata={"datatype": "xsd:integer"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"42\"^^<http://www.w3.org/2001/XMLSchema#integer>",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_expands_rdf_prefix_to_full_iri(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:value",
            object="hello",
            metadata={"datatype": "rdf:langString"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"hello\"^^<http://www.w3.org/1999/02/22-rdf-syntax-ns#langString>",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_rejects_unknown_prefix(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:value",
            object="hello",
            metadata={"datatype": "myns:customType"},
        )
        with self.assertRaises(ValueError):
            store._format_object_for_sparql(triplet)

    # --- Bug 2: metadata injection validation ---

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_rejects_injected_lang_tag(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:label",
            object="Color",
            metadata={"lang": "en . CLEAR ALL #"},
        )
        with self.assertRaises(ValueError):
            store._format_object_for_sparql(triplet)

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_rejects_datatype_with_whitespace(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:age",
            object="42",
            metadata={"datatype": "http://example.org/type CLEAR ALL"},
        )
        with self.assertRaises(ValueError):
            store._format_object_for_sparql(triplet)

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_accepts_full_iri_datatype_no_brackets(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:age",
            object="42",
            metadata={"datatype": "http://www.w3.org/2001/XMLSchema#integer"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"42\"^^<http://www.w3.org/2001/XMLSchema#integer>",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_accepts_bracketed_iri_datatype(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:age",
            object="42",
            metadata={"datatype": "<http://www.w3.org/2001/XMLSchema#integer>"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(
            obj,
            "\"42\"^^<http://www.w3.org/2001/XMLSchema#integer>",
        )

    @patch.object(BlazegraphStore, "_connect", autospec=True)
    def test_format_object_accepts_hyphenated_lang_tag(self, _mock_connect):
        store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph")
        triplet = Triplet(
            subject="urn:entity:person:1",
            predicate="urn:property:label",
            object="Colour",
            metadata={"lang": "en-GB"},
        )
        obj = store._format_object_for_sparql(triplet)
        self.assertEqual(obj, "\"Colour\"@en-GB")


if __name__ == "__main__":
    unittest.main()
