"""Tests for cross-graph linking, navigation, and save/load persistence."""

import json
import os
import tempfile

import pytest

from semantica.context.context_graph import ContextGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _two_graphs():
    """Return two graphs each with one node."""
    g1 = ContextGraph()
    g2 = ContextGraph()
    g1.add_node("src", "entity", content="source entity")
    g2.add_node("dst", "entity", content="destination entity")
    return g1, g2


# ---------------------------------------------------------------------------
# link_graph / navigate_to — basic contract
# ---------------------------------------------------------------------------


class TestLinkGraph:
    def test_returns_link_id(self):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        assert isinstance(link_id, str) and len(link_id) > 0

    def test_navigate_to_returns_correct_graph_and_node(self):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        other, entry = g1.navigate_to(link_id)
        assert other is g2
        assert entry == "dst"

    def test_navigate_to_unknown_link_raises(self):
        g1, _ = _two_graphs()
        with pytest.raises(KeyError):
            g1.navigate_to("nonexistent-link-id")

    def test_source_not_in_graph_raises(self):
        g1, g2 = _two_graphs()
        with pytest.raises(KeyError):
            g1.link_graph(g2, "missing", "dst")

    def test_target_not_in_other_graph_raises(self):
        g1, g2 = _two_graphs()
        with pytest.raises(KeyError):
            g1.link_graph(g2, "src", "missing")

    def test_marker_node_has_cross_graph_link_type(self):
        """link_graph() must NOT pollute graph with phantom 'entity' nodes."""
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        marker_id = f"__cross_graph_{link_id}"
        assert marker_id in g1.nodes
        assert g1.nodes[marker_id].node_type == "cross_graph_link"

    def test_no_phantom_entity_nodes(self):
        """Only 'src' and the typed marker should exist in g1."""
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        entity_nodes = [n for n in g1.nodes.values() if n.node_type == "entity"]
        assert len(entity_nodes) == 1  # only 'src'

    def test_multiple_links_from_same_source(self):
        g1 = ContextGraph()
        g2 = ContextGraph()
        g3 = ContextGraph()
        g1.add_node("hub", "entity")
        g2.add_node("a", "entity")
        g3.add_node("b", "entity")
        lid1 = g1.link_graph(g2, "hub", "a")
        lid2 = g1.link_graph(g3, "hub", "b")
        other1, entry1 = g1.navigate_to(lid1)
        other2, entry2 = g1.navigate_to(lid2)
        assert other1 is g2 and entry1 == "a"
        assert other2 is g3 and entry2 == "b"


# ---------------------------------------------------------------------------
# Persistence: save_to_file / load_from_file + resolve_links
# ---------------------------------------------------------------------------


class TestCrossGraphPersistence:
    def test_graph_id_preserved_after_save_load(self):
        g1, _ = _two_graphs()
        original_id = g1.graph_id
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            g1.save_to_file(path)
            g1b = ContextGraph()
            g1b.load_from_file(path)
            assert g1b.graph_id == original_id
        finally:
            os.unlink(path)

    def test_links_section_written_to_file(self):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            g1.save_to_file(path)
            with open(path) as fp:
                data = json.load(fp)
            assert "links" in data
            assert len(data["links"]) == 1
            lk = data["links"][0]
            assert lk["link_id"] == link_id
            assert lk["source_node_id"] == "src"
            assert lk["target_node_id"] == "dst"
            assert lk["other_graph_id"] == g2.graph_id
        finally:
            os.unlink(path)

    def test_navigate_to_raises_helpful_error_before_resolve(self):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            g1.save_to_file(path)
            g1b = ContextGraph()
            g1b.load_from_file(path)
            with pytest.raises(KeyError, match="resolve_links"):
                g1b.navigate_to(link_id)
        finally:
            os.unlink(path)

    def test_resolve_links_restores_navigation(self):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")

        with (
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f1,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f2,
        ):
            path1, path2 = f1.name, f2.name

        try:
            g1.save_to_file(path1)
            g2.save_to_file(path2)

            g1b = ContextGraph()
            g2b = ContextGraph()
            g1b.load_from_file(path1)
            g2b.load_from_file(path2)

            resolved = g1b.resolve_links({g2b.graph_id: g2b})
            assert resolved == 1

            other, entry = g1b.navigate_to(link_id)
            assert other is g2b
            assert entry == "dst"
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_resolve_links_returns_count(self):
        g1 = ContextGraph()
        g2 = ContextGraph()
        g3 = ContextGraph()
        g1.add_node("h", "entity")
        g2.add_node("a", "entity")
        g3.add_node("b", "entity")
        g1.link_graph(g2, "h", "a")
        g1.link_graph(g3, "h", "b")

        with (
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f1,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f2,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f3,
        ):
            p1, p2, p3 = f1.name, f2.name, f3.name
        try:
            g1.save_to_file(p1); g2.save_to_file(p2); g3.save_to_file(p3)
            g1b, g2b, g3b = ContextGraph(), ContextGraph(), ContextGraph()
            g1b.load_from_file(p1); g2b.load_from_file(p2); g3b.load_from_file(p3)
            resolved = g1b.resolve_links({g2b.graph_id: g2b, g3b.graph_id: g3b})
            assert resolved == 2
        finally:
            for p in (p1, p2, p3):
                os.unlink(p)

    def test_resolve_links_partial_registry_leaves_unresolved(self):
        """Passing only one graph to resolve_links should resolve only that link."""
        g1 = ContextGraph()
        g2 = ContextGraph()
        g3 = ContextGraph()
        g1.add_node("h", "entity")
        g2.add_node("a", "entity")
        g3.add_node("b", "entity")
        lid1 = g1.link_graph(g2, "h", "a")
        lid2 = g1.link_graph(g3, "h", "b")

        with (
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f1,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f2,
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f3,
        ):
            p1, p2, p3 = f1.name, f2.name, f3.name
        try:
            g1.save_to_file(p1); g2.save_to_file(p2); g3.save_to_file(p3)
            g1b, g2b, g3b = ContextGraph(), ContextGraph(), ContextGraph()
            g1b.load_from_file(p1); g2b.load_from_file(p2); g3b.load_from_file(p3)

            # Only resolve g2
            resolved = g1b.resolve_links({g2b.graph_id: g2b})
            assert resolved == 1

            # lid1 navigable
            other, entry = g1b.navigate_to(lid1)
            assert other is g2b and entry == "a"

            # lid2 still unresolved — must raise with hint
            with pytest.raises(KeyError, match="resolve_links"):
                g1b.navigate_to(lid2)
        finally:
            for p in (p1, p2, p3):
                os.unlink(p)


# ---------------------------------------------------------------------------
# Unresolved links survive a load followed by a save
# ---------------------------------------------------------------------------


def _saved_links(path):
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)["links"]


class TestUnresolvedLinksRoundTrip:
    def test_load_then_save_keeps_unresolved_link(self, tmp_path):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        path = tmp_path / "g1.json"
        g1.save_to_file(path)

        g1b = ContextGraph()
        g1b.load_from_file(path)
        g1b.save_to_file(path)

        assert _saved_links(path) == [
            {
                "link_id": link_id,
                "source_node_id": "src",
                "target_node_id": "dst",
                "other_graph_id": g2.graph_id,
            }
        ]

    def test_unresolved_link_still_resolves_after_resave(self, tmp_path):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        path = tmp_path / "g1.json"
        g1.save_to_file(path)

        g1b = ContextGraph()
        g1b.load_from_file(path)
        g1b.save_to_file(path)
        g1c = ContextGraph()
        g1c.load_from_file(path)

        assert g1c.resolve_links({g2.graph_id: g2}) == 1
        other, entry = g1c.navigate_to(link_id)
        assert other is g2 and entry == "dst"

    def test_relinking_after_load_keeps_old_and_new_links(self, tmp_path):
        g1, g2 = _two_graphs()
        old_link = g1.link_graph(g2, "src", "dst")
        path = tmp_path / "g1.json"
        g1.save_to_file(path)

        g1b = ContextGraph()
        g1b.load_from_file(path)
        g3 = ContextGraph()
        g3.add_node("other", "entity")
        new_link = g1b.link_graph(g3, "src", "other")

        # The new link is live; the old one still waits for resolve_links.
        other, entry = g1b.navigate_to(new_link)
        assert other is g3 and entry == "other"
        with pytest.raises(KeyError, match="resolve_links"):
            g1b.navigate_to(old_link)

        g1b.save_to_file(path)
        saved = {link["link_id"]: link for link in _saved_links(path)}
        assert set(saved) == {old_link, new_link}
        assert saved[old_link]["other_graph_id"] == g2.graph_id
        assert saved[new_link]["other_graph_id"] == g3.graph_id

        g1c = ContextGraph()
        g1c.load_from_file(path)
        assert g1c.resolve_links({g2.graph_id: g2, g3.graph_id: g3}) == 2
        assert g1c.navigate_to(old_link) == (g2, "dst")
        assert g1c.navigate_to(new_link) == (g3, "other")

    def test_link_both_resolved_and_unresolved_is_written_once(self, tmp_path):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        g1._unresolved_links[link_id] = {
            "link_id": link_id,
            "source_node_id": "stale-src",
            "target_node_id": "stale-dst",
            "other_graph_id": "stale-graph",
        }
        path = tmp_path / "g1.json"
        g1.save_to_file(path)

        links = _saved_links(path)
        assert len(links) == 1
        assert links[0]["other_graph_id"] == g2.graph_id
        assert links[0]["source_node_id"] == "src"
        assert g1.to_dict()["links"] == links

    def test_to_dict_from_dict_round_trip_keeps_links(self):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")

        restored = ContextGraph()
        restored.from_dict(g1.to_dict())
        with pytest.raises(KeyError, match="resolve_links"):
            restored.navigate_to(link_id)

        # A second round trip from the unresolved state keeps the link too.
        again = ContextGraph()
        again.from_dict(restored.to_dict())
        assert again.resolve_links({g2.graph_id: g2}) == 1
        assert again.navigate_to(link_id) == (g2, "dst")

    def test_markdown_load_then_save_keeps_unresolved_link(self, tmp_path):
        g1, g2 = _two_graphs()
        link_id = g1.link_graph(g2, "src", "dst")
        export = tmp_path / "g1-md"
        g1.save_to_file(export, format="markdown")

        g1b = ContextGraph()
        g1b.load_from_file(export, format="markdown")
        g1b.save_to_file(export, format="markdown")
        g1c = ContextGraph()
        g1c.load_from_file(export, format="markdown")

        assert g1c.resolve_links({g2.graph_id: g2}) == 1
        assert g1c.navigate_to(link_id) == (g2, "dst")
