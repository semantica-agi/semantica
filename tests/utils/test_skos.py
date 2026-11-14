import unittest

from semantica.utils.skos import is_skos_hierarchy_edge, validate_skos_hierarchy


class TestIsSkosHierarchyEdge(unittest.TestCase):

    def test_recognizes_broader_and_narrower(self):
        self.assertTrue(is_skos_hierarchy_edge({"source": "A", "target": "B", "type": "skos:broader"}))
        self.assertTrue(is_skos_hierarchy_edge({"source": "A", "target": "B", "type": "skos:narrower"}))

    def test_ignores_other_edge_types(self):
        self.assertFalse(is_skos_hierarchy_edge({"source": "A", "target": "B", "type": "rdfs:subClassOf"}))

    def test_ignores_non_mapping(self):
        self.assertFalse(is_skos_hierarchy_edge("not-a-dict"))


class TestValidateSkosHierarchy(unittest.TestCase):

    def test_accepts_acyclic_chain(self):
        validate_skos_hierarchy([
            {"source": "A", "target": "B", "type": "skos:broader"},
            {"source": "B", "target": "C", "type": "skos:broader"},
        ])

    def test_rejects_self_loop(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_skos_hierarchy([{"source": "A", "target": "A", "type": "skos:broader"}])

    def test_rejects_direct_two_node_cycle(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_skos_hierarchy([
                {"source": "A", "target": "B", "type": "skos:broader"},
                {"source": "B", "target": "A", "type": "skos:broader"},
            ])

    def test_rejects_cycle_spanning_existing_and_new_edges(self):
        existing = [
            {"source": "A", "target": "B", "type": "skos:broader"},
            {"source": "B", "target": "C", "type": "skos:broader"},
        ]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_skos_hierarchy([{"source": "C", "target": "A", "type": "skos:broader"}], existing)

    def test_preexisting_unrelated_cycle_does_not_block_new_write(self):
        """A cycle already persisted elsewhere in the graph (e.g. legacy data
        written before cycle detection existed) must not poison unrelated
        writes for concepts it doesn't touch."""
        existing = [
            {"source": "X", "target": "Y", "type": "skos:broader"},
            {"source": "Y", "target": "X", "type": "skos:broader"},
        ]
        validate_skos_hierarchy([{"source": "C", "target": "D", "type": "skos:broader"}], existing)

    def test_none_and_blank_endpoints_are_ignored(self):
        validate_skos_hierarchy([
            {"source": None, "target": "B", "type": "skos:broader"},
            {"source": "  ", "target": "B", "type": "skos:broader"},
        ])


if __name__ == "__main__":
    unittest.main()


def test_strict_mode_rejects_a_malformed_hierarchy_edge():
    import pytest

    with pytest.raises(ValueError):
        validate_skos_hierarchy([{"type": "skos:broader"}], strict=True)


def test_strict_mode_rejects_a_blank_endpoint():
    import pytest

    with pytest.raises(ValueError):
        validate_skos_hierarchy(
            [{"type": "skos:narrower", "source": "  ", "target": "B"}], strict=True
        )


def test_strict_mode_still_ignores_non_hierarchy_edges():
    validate_skos_hierarchy(
        [{"type": "related_to", "source": "A"}],
        strict=True,
    )


def test_strict_mode_accepts_a_well_formed_edge():
    validate_skos_hierarchy(
        [{"type": "skos:broader", "source": "B", "target": "A"}],
        strict=True,
    )


def test_strict_mode_uses_the_fallback_endpoint_field():
    """source=None with a usable source_id is not a malformed edge."""
    validate_skos_hierarchy(
        [{"type": "skos:broader", "source": None, "source_id": "B", "target": "A"}],
        strict=True,
    )


def test_strict_mode_still_rejects_an_edge_with_no_endpoint_at_all():
    import pytest

    with pytest.raises(ValueError):
        validate_skos_hierarchy(
            [{"type": "skos:broader", "source": None, "target": "  "}], strict=True
        )
