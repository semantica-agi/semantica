"""Unit tests for explorer provenance route helpers."""

from types import SimpleNamespace

from semantica.explorer.routes.provenance import _build_provenance, _render_markdown


def _make_session_with_chain() -> SimpleNamespace:
    """Build a minimal session-like object for Source -> Intermediate -> node_id."""
    nodes = {
        "Source": SimpleNamespace(node_type="entity", content="Source"),
        "Intermediate": SimpleNamespace(node_type="entity", content="Intermediate"),
        "node_id": SimpleNamespace(node_type="entity", content="Target"),
    }
    edges = [
        SimpleNamespace(source_id="Source", target_id="Intermediate", edge_type="related_to"),
        SimpleNamespace(source_id="Intermediate", target_id="node_id", edge_type="related_to"),
    ]
    graph = SimpleNamespace(nodes=nodes, edges=edges)
    return SimpleNamespace(graph=graph)


def test_build_provenance_direction_classification_chain():
    session = _make_session_with_chain()

    data = _build_provenance(session, "node_id")

    node_ids = {node["id"] for node in data["nodes"]}
    assert "Source" in node_ids
    assert "Intermediate" in node_ids

    edge_by_pair = {(edge["source"], edge["target"]): edge for edge in data["edges"]}

    assert edge_by_pair[("Intermediate", "node_id")]["direction"] == "upstream"
    assert edge_by_pair[("Source", "Intermediate")]["direction"] != "downstream"


def test_render_markdown_groups_edges_by_direction():
    report = {
        "node_id": "node_id",
        "label": "Target",
        "type": "entity",
        "properties": {},
        "lineage": {
            "nodes": [
                {"id": "Source", "prov_type": "Entity", "label": "Source"},
                {"id": "Intermediate", "prov_type": "Entity", "label": "Intermediate"},
                {"id": "node_id", "prov_type": "Entity", "label": "Target"},
            ],
            "edges": [
                {
                    "id": "Intermediate-node_id",
                    "source": "Intermediate",
                    "target": "node_id",
                    "label": "related_to",
                    "direction": "upstream",
                },
                {
                    "id": "Source-Intermediate",
                    "source": "Source",
                    "target": "Intermediate",
                    "label": "related_to",
                    "direction": "lateral",
                },
            ],
        },
    }

    markdown = _render_markdown(report)

    assert "## Upstream" in markdown
    assert "## Lateral" in markdown
    assert "`Intermediate` -[related_to]-> `node_id`" in markdown
    assert "`Source` -[related_to]-> `Intermediate`" in markdown
