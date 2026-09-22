"""Tests for the ``export_knowledge_graph`` router (issue #1699).

``export_knowledge_graph`` is the documented convenience entry point for
exporting a knowledge graph, and it advertises two behaviours it did not
deliver:

* ``format`` defaults to ``"json"`` and the extension detection is guarded by
  ``if not format:``, so the branch is unreachable for any caller that omits
  the argument -- which is exactly the documented usage
  (``export_knowledge_graph(kg, "output.ttl")``). Every extension therefore
  received a JSON document, with no exception and no warning.
* ``method`` defaults to ``None`` and is forwarded unconditionally to wrappers
  that carry their own defaults, so ``format="yaml"`` overwrote
  ``export_yaml``'s ``method="semantic_network"`` with ``None`` and raised.

A third defect sits in the multi-file branches of the CSV and Parquet
exporters: an empty collection was passed to ``export_entities`` /
``export_relationships``, which reject an empty list, so a graph with entities
and no relationships aborted before anything was written. Both exporters guard
every collection that way in their own ``export_knowledge_graph`` method --
the ``export`` method simply did not, so the fix is to match the sibling.

The suite did not catch any of the three. Every existing call to this router
passes ``format`` explicitly, the YAML tests call ``export_yaml`` directly and
so keep its default, and the sample graphs carry at least one relationship.

These tests drive the real exporters and read the files that land on disk,
since routing and file format are the behaviours under test.
"""

from pathlib import Path

import csv

import pytest
import yaml

from semantica.export.methods import export_knowledge_graph
from semantica.utils.exceptions import ProcessingError, ValidationError

ENTITY_ONLY_KG = {
    "entities": [
        {"id": "e1", "text": "Alice", "type": "PERSON", "confidence": 0.9}
    ],
    "relationships": [],
}

TWO_NODE_KG = {
    "entities": [
        {"id": "e1", "text": "Alice", "type": "PERSON", "confidence": 0.9},
        {"id": "e2", "text": "Acme", "type": "ORG", "confidence": 0.8},
    ],
    "relationships": [
        {"id": "r1", "source_id": "e1", "target_id": "e2",
         "type": "WORKS_FOR", "confidence": 0.85}
    ],
}


def _written(tmp_path, stem):
    """Return the single file the router produced for ``stem``."""
    matches = sorted(Path(tmp_path).glob(f"{stem}*"))
    assert matches, f"no file was written for {stem}"
    return matches[0]


class TestExtensionDetection:
    """Omitting ``format`` routes on the file extension."""

    @pytest.mark.parametrize(
        "extension,validator",
        [
            (".ttl", lambda body: "@prefix" in body or "@base" in body),
            (".rdf", lambda body: body.lstrip().startswith("<")),
            (".graphml", lambda body: "<graphml" in body),
            (".gexf", lambda body: "<gexf" in body),
            (".dot", lambda body: body.lstrip().startswith("digraph")),
            (".owl", lambda body: body.lstrip().startswith("<")),
        ],
    )
    def test_extension_selects_the_format(self, tmp_path, extension, validator):
        """A named extension yields that format, not JSON.

        Before the fix the ``format`` default of ``"json"`` short-circuited
        detection, so each of these extensions produced a JSON document while
        the file name claimed otherwise.
        """
        stem = "router_ext"
        export_knowledge_graph(TWO_NODE_KG, str(tmp_path / f"{stem}{extension}"))

        body = _written(tmp_path, stem).read_text(encoding="utf-8")
        assert not body.lstrip().startswith("{"), (
            f"{extension} should not contain a JSON document"
        )
        assert validator(body), f"{extension} did not produce its own format"

    def test_yaml_extension_produces_yaml(self, tmp_path):
        """The extension path reaches the YAML exporter, not the JSON one."""
        export_knowledge_graph(ENTITY_ONLY_KG, str(tmp_path / "router.yaml"))

        parsed = yaml.safe_load(_written(tmp_path, "router").read_text("utf-8"))
        assert isinstance(parsed, dict)
        assert parsed["entities"][0]["id"] == "e1"

    def test_nt_extension_produces_ntriples(self, tmp_path):
        """`.nt` routes to N-Triples, which docs/reference/export.md documents
        as its extension and RDFExporter already implements.

        The extension map had no `.nt` entry, so once detection ran at all this
        suffix fell through to the JSON default. N-Triples is told apart from
        Turtle by the absence of prefix declarations: every triple carries an
        absolute IRI.
        """
        export_knowledge_graph(TWO_NODE_KG, str(tmp_path / "router.nt"))

        body = _written(tmp_path, "router").read_text(encoding="utf-8")
        assert not body.lstrip().startswith("{"), "wrote JSON for a .nt path"
        assert "@prefix" not in body, "prefix declarations mean Turtle, not N-Triples"
        lines = [ln for ln in body.splitlines() if ln.strip()]
        assert lines, "N-Triples output was empty"
        for line in lines:
            assert line.startswith("<"), f"not a triple statement: {line[:60]}"
            assert line.rstrip().endswith("."), f"triple not terminated: {line[:60]}"

    def test_explicit_format_still_wins_over_the_extension(self, tmp_path):
        """Passing ``format`` explicitly keeps overriding the extension."""
        export_knowledge_graph(
            TWO_NODE_KG, str(tmp_path / "router_explicit.graphml"), format="json"
        )

        body = _written(tmp_path, "router_explicit").read_text(encoding="utf-8")
        assert body.lstrip().startswith("{")

    def test_unknown_extension_falls_back_to_json(self, tmp_path):
        """An unrecognized suffix keeps the previous default of JSON."""
        export_knowledge_graph(TWO_NODE_KG, str(tmp_path / "router.unknownext"))

        body = _written(tmp_path, "router").read_text(encoding="utf-8")
        assert body.lstrip().startswith("{")


class TestYamlRoute:
    """``format="yaml"`` is usable without passing ``method``."""

    @pytest.mark.parametrize("fmt", ["yaml", "yml"])
    def test_yaml_formats_do_not_raise(self, tmp_path, fmt):
        """Both documented spellings work with only the format given.

        The router forwarded ``method=None``, which replaced ``export_yaml``'s
        own ``method="semantic_network"`` default and raised
        ``ProcessingError: Unknown YAML export method: None``.
        """
        export_knowledge_graph(
            ENTITY_ONLY_KG, str(tmp_path / f"route_{fmt}.yaml"), format=fmt
        )

        parsed = yaml.safe_load(
            _written(tmp_path, f"route_{fmt}").read_text(encoding="utf-8")
        )
        assert parsed["entities"][0]["id"] == "e1"

    def test_wrapper_default_survives_the_router(self, tmp_path):
        """The router does not leak a ``None`` into the wrapper's default.

        Routing through ``export_knowledge_graph`` and calling ``export_yaml``
        directly must agree, since the caller supplied no ``method`` either
        way.
        """
        export_knowledge_graph(
            ENTITY_ONLY_KG, str(tmp_path / "routed.yaml"), format="yaml"
        )
        routed = yaml.safe_load(
            _written(tmp_path, "routed").read_text(encoding="utf-8")
        )

        from semantica.export.methods import export_yaml

        export_yaml(ENTITY_ONLY_KG, str(tmp_path / "direct.yaml"))
        direct = yaml.safe_load(
            _written(tmp_path, "direct").read_text(encoding="utf-8")
        )

        assert set(routed) == set(direct)

    def test_explicit_method_is_still_forwarded(self, tmp_path):
        """A caller who asks for a specific YAML method still gets it."""
        export_knowledge_graph(
            ENTITY_ONLY_KG,
            str(tmp_path / "schema.yaml"),
            format="yaml",
            method="semantic_network",
        )

        parsed = yaml.safe_load(
            _written(tmp_path, "schema").read_text(encoding="utf-8")
        )
        assert parsed["entities"][0]["id"] == "e1"

    def test_unknown_method_is_still_refused(self, tmp_path):
        """An explicitly bad ``method`` reports that value, not ``None``."""
        with pytest.raises(ProcessingError) as excinfo:
            export_knowledge_graph(
                ENTITY_ONLY_KG,
                str(tmp_path / "bad.yaml"),
                format="yaml",
                method="definitely_not_a_method",
            )

        assert "definitely_not_a_method" in str(excinfo.value)


class TestMultiFileRoutes:
    """CSV and Parquet write one file per collection, empty ones included.

    Both exporters share the same defect and the same fix, so the cases are
    parameterized rather than duplicated. ``format`` is passed explicitly so
    these exercise the multi-file branches rather than extension detection.
    """

    @pytest.mark.parametrize(
        "fmt,extension",
        [("csv", ".csv"), ("parquet", ".parquet")],
    )
    def test_empty_relationships_still_writes_entities(self, tmp_path, fmt, extension):
        """The entity collection reaches disk when there are no edges.

        ``export`` looped over the dict's list-valued keys and passed the empty
        list to ``export_relationships``, which rejects it, so the call aborted
        before the entity file was written.
        """
        export_knowledge_graph(
            ENTITY_ONLY_KG,
            str(tmp_path / f"empty_rel{extension}"),
            format=fmt,
        )

        names = sorted(p.name for p in Path(tmp_path).glob("empty_rel*"))
        assert any("entit" in n for n in names), f"no entity file among {names}"

    @pytest.mark.parametrize(
        "fmt,extension",
        [("csv", ".csv"), ("parquet", ".parquet")],
    )
    def test_empty_entities_still_writes_relationships(self, tmp_path, fmt, extension):
        """The mirror case: relationships survive an entity-less graph."""
        kg = {
            "entities": [],
            "relationships": [
                {"id": "r1", "source_id": "a", "target_id": "b", "type": "REL"}
            ],
        }
        export_knowledge_graph(
            kg, str(tmp_path / f"empty_ent{extension}"), format=fmt
        )

        names = sorted(p.name for p in Path(tmp_path).glob("empty_ent*"))
        assert any("relationship" in n for n in names), (
            f"no relationship file among {names}"
        )

    @pytest.mark.parametrize(
        "fmt,extension",
        [("csv", ".csv"), ("parquet", ".parquet")],
    )
    def test_empty_collection_does_not_create_a_file(self, tmp_path, fmt, extension):
        """An empty collection produces no file at all, and no exception.

        This matches what each exporter's own ``export_knowledge_graph`` method
        already does, which guards every collection the same way.
        """
        export_knowledge_graph(
            ENTITY_ONLY_KG, str(tmp_path / f"no_rel{extension}"), format=fmt
        )

        names = sorted(p.name for p in Path(tmp_path).glob("no_rel*"))
        assert not any("relationship" in n for n in names), (
            f"an empty collection produced a file: {names}"
        )

    @pytest.mark.parametrize(
        "fmt,extension",
        [("csv", ".csv"), ("parquet", ".parquet")],
    )
    def test_empty_graph_writes_nothing_and_does_not_raise(self, tmp_path, fmt, extension):
        """A wholly empty graph is accepted and produces no files."""
        export_knowledge_graph(
            {"entities": [], "relationships": []},
            str(tmp_path / f"empty_graph{extension}"),
            format=fmt,
        )

        assert not list(Path(tmp_path).glob("empty_graph*"))

    @pytest.mark.parametrize(
        "fmt,extension",
        [("csv", ".csv"), ("parquet", ".parquet")],
    )
    def test_both_files_written_when_both_collections_are_present(
        self, tmp_path, fmt, extension
    ):
        """The normal case keeps producing an entity and a relationship file."""
        export_knowledge_graph(
            TWO_NODE_KG, str(tmp_path / f"both{extension}"), format=fmt
        )

        names = sorted(p.name for p in Path(tmp_path).glob("both*"))
        assert any("entit" in n for n in names), f"no entity file among {names}"
        assert any("relationship" in n for n in names), (
            f"no relationship file among {names}"
        )

    def test_csv_entity_rows_are_readable(self, tmp_path):
        """The surviving entity file holds the record, not just a header."""
        export_knowledge_graph(
            ENTITY_ONLY_KG, str(tmp_path / "rows.csv"), format="csv"
        )

        entity_file = next(p for p in Path(tmp_path).glob("*entit*"))
        rows = list(csv.DictReader(entity_file.read_text("utf-8").splitlines()))
        assert [r["id"] for r in rows] == ["e1"]
        assert rows[0]["text"] == "Alice"


class TestEmptyListContractUnchanged:
    """Calling a dedicated exporter with an empty list still raises.

    The fix is scoped to the ``export`` dispatch: the contract of
    ``export_entities([])`` / ``export_relationships([])`` is untouched.
    """

    @pytest.mark.parametrize("fmt", ["csv", "parquet"])
    def test_export_entities_still_rejects_an_empty_list(self, tmp_path, fmt):
        from semantica.export.csv_exporter import CSVExporter
        from semantica.export.parquet_exporter import ParquetExporter

        exporter = CSVExporter() if fmt == "csv" else ParquetExporter()
        with pytest.raises(ValidationError):
            exporter.export_entities([], str(tmp_path / f"e.{fmt}"))

    @pytest.mark.parametrize("fmt", ["csv", "parquet"])
    def test_export_relationships_still_rejects_an_empty_list(self, tmp_path, fmt):
        from semantica.export.csv_exporter import CSVExporter
        from semantica.export.parquet_exporter import ParquetExporter

        exporter = CSVExporter() if fmt == "csv" else ParquetExporter()
        with pytest.raises(ValidationError):
            exporter.export_relationships([], str(tmp_path / f"r.{fmt}"))
