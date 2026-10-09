"""Every format the ``semantica export`` command offers must produce its data.

Issue #1712: the command advertised 14 formats and six of them could not run.
Four had no branch at all in the router the command calls (``arrow``,
``shacl``, ``arangodb``, ``distance-enriched``), ``owl`` was forwarded under a
name ``OWLExporter`` rejects, and ``parquet`` aborted on the knowledge graph the
command builds.

OWL and SHACL are serialized from an ontology (``semantica ontology shacl``
generates shapes) and the distance matrix is computed from an Explorer session
graph. A graph-store dump has neither, so the command no longer offers the
three formats rather than trading a loud failure for a document with no classes
in it.

Asserting "it did not raise" would have been too weak a check even for the
formats that stayed. Every server graph backend returns relationship endpoints
as ``start_node_id``/``end_node_id`` -- Neo4j, FalkorDB and Neptune directly,
AGE after renaming its raw ``start_id``/``end_id`` fields -- while every
serializer reads ``source_id``/``target_id``. Only the local store uses those
names, so the command was broken for anyone running it against a server.
Before the fix N-Triples dropped the relationship outright, Turtle and RDF/XML
wrote an unresolved `#None` endpoint where one was expected, and Parquet
refused the records. The assertions below therefore look for both node ids and
the relationship type in what reaches disk.

The existing CLI test did not catch any of this because its fake store returned
``{"source": ..., "target": ...}``, which no backend returns.
"""

from pathlib import Path

import pytest

from semantica.cli import _EXPORT_FORMATS
from semantica.export.endpoint_names import canonical_endpoints, has_endpoints
from semantica.export.methods import MULTI_FILE_FORMATS, export_knowledge_graph
from semantica.utils.exceptions import ProcessingError

NODES = [
    {"id": "n1", "type": "Person", "properties": {"name": "Alice"}},
    {"id": "n2", "type": "Org", "properties": {"name": "Acme"}},
]

# What the server backends put in a relationship record (Neo4j, FalkorDB,
# AGE and Neptune all return this shape).
RELATIONSHIPS = [
    {
        "id": "r1",
        "type": "KNOWS",
        "start_node_id": "n1",
        "end_node_id": "n2",
        "properties": {"since": 1843},
    }
]

# The extension each advertised format is normally written to, and whether the
# file needs an Arrow reader to inspect it.
FORMAT_EXTENSIONS = {
    "turtle": ".ttl",
    "jsonld": ".jsonld",
    "ntriples": ".nt",
    "rdfxml": ".rdf",
    "parquet": ".parquet",
    "arrow": ".arrow",
    "csv": ".csv",
    "json": ".json",
    "yaml": ".yaml",
    "graphml": ".graphml",
    "arangodb": ".aql",
}


def cli_knowledge_graph(relationships=None):
    """The dictionary ``semantica export`` hands to the router.

    The command reads nodes and relationships out of the graph store and adds
    ``nodes``/``edges`` alongside ``entities``/``relationships``, because the
    graph exporters read one pair of names and the rest read the other.
    """
    rels = RELATIONSHIPS if relationships is None else relationships
    return {
        "entities": [dict(n) for n in NODES],
        "relationships": [dict(r) for r in rels],
        "nodes": [dict(n) for n in NODES],
        "edges": [dict(r) for r in rels],
    }


def _files(tmp_path, stem):
    return sorted(Path(tmp_path).glob(f"{stem}*"))


def _blob(paths):
    """Everything written as one string, so the assertions can be uniform.

    Parquet and Arrow need an Arrow reader; the rest are written as text.
    """
    chunks = []
    for path in paths:
        if path.suffix in (".parquet", ".arrow"):
            pa = pytest.importorskip("pyarrow", reason="reading the file needs pyarrow")
            if path.suffix == ".parquet":
                import pyarrow.parquet as pq

                table = pq.read_table(path)
            else:
                import pyarrow.ipc as ipc

                with pa.memory_map(str(path), "r") as source:
                    table = ipc.open_file(source).read_all()
            chunks.append(f"{path.name} rows={table.num_rows} {table.to_pydict()}")
        else:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


class TestEveryAdvertisedFormatRuns:
    """Drive the router the way the command does, for every offered format."""

    @pytest.mark.parametrize("fmt", _EXPORT_FORMATS)
    def test_format_writes_its_graph(self, tmp_path, fmt):
        stem = f"export_{fmt}"
        target = tmp_path / f"{stem}{FORMAT_EXTENSIONS[fmt]}"

        export_knowledge_graph(cli_knowledge_graph(), str(target), format=fmt)

        files = _files(tmp_path, stem)
        assert files, f"{fmt} wrote no file"
        assert all(f.stat().st_size for f in files), f"{fmt} wrote an empty file"

        blob = _blob(files)
        assert "KNOWS" in blob, f"{fmt} lost the relationship type"
        assert "n1" in blob and "n2" in blob, f"{fmt} lost a relationship endpoint"
        # `#None` is the IRI fragment the RDF serializers fell back to when
        # they could not resolve an endpoint before the store's names were
        # understood: `<...#None>` in Turtle, `rdf:about="...#None"` in RDF/XML.
        assert "#None" not in blob, f"{fmt} wrote an unresolved endpoint"

    @pytest.mark.parametrize("fmt", _EXPORT_FORMATS)
    def test_this_module_covers_exactly_what_the_command_offers(self, fmt):
        """A format added to the command has to be covered here in the same change."""
        assert (
            fmt in FORMAT_EXTENSIONS
        ), f"{fmt} is advertised but this module does not build it"


class TestGraphStoreEndpointNames:
    """The store's endpoint names are accepted on the way in.

    The backend's spelling is not the one the serializers read, so a record
    has to keep its endpoints through the router whichever name it arrived
    under.
    """

    @pytest.mark.parametrize(
        "source_key,target_key",
        [
            ("start_node_id", "end_node_id"),  # Neo4j, FalkorDB, AGE, Neptune
            ("start_id", "end_id"),  # AGE's raw edge fields
            ("source", "target"),
            ("source_id", "target_id"),  # already canonical
        ],
    )
    def test_endpoints_survive_regardless_of_their_name(
        self, tmp_path, source_key, target_key
    ):
        relationships = [
            {
                "id": "r1",
                "type": "KNOWS",
                source_key: "n1",
                target_key: "n2",
            }
        ]
        target = tmp_path / f"{source_key}.ttl"

        export_knowledge_graph(
            cli_knowledge_graph(relationships), str(target), format="turtle"
        )

        body = target.read_text(encoding="utf-8")
        assert (
            "n1" in body and "n2" in body
        ), f"endpoints named {source_key}/{target_key} did not reach the output"
        assert "#None" not in body

    def test_relationships_reach_parquet_with_the_store_names(self, tmp_path):
        """Parquet used to refuse these records outright.

        ``export_relationships`` only recognised ``source*``/``target*``, so a
        store-shaped record produced no valid rows and raised.
        """
        pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")

        export_knowledge_graph(cli_knowledge_graph(), str(tmp_path / "o.parquet"))

        blob = _blob(_files(tmp_path, "o_relationships"))
        assert "n1" in blob and "n2" in blob


class TestParquetAcceptsTheCommandShape:
    """``parquet`` is given the whole knowledge graph in one dict.

    ``entities``/``relationships`` are handled by key name, and the duplicate
    ``nodes``/``edges`` keys the command adds used to reach
    ``_write_parquet(schema=None)``, which always raised
    ``Schema is required for Parquet export``. They name the same two
    collections, so the router drops them before routing instead of writing
    each collection a second time.
    """

    def test_duplicate_collection_keys_are_not_written_as_well(self, tmp_path):
        pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")

        export_knowledge_graph(cli_knowledge_graph(), str(tmp_path / "graph.parquet"))

        names = sorted(p.name for p in tmp_path.glob("graph*"))
        assert names == [
            "graph_entities.parquet",
            "graph_relationships.parquet",
        ], names

    def test_a_key_that_is_neither_entities_nor_relationships_is_routed_by_shape(
        self, tmp_path
    ):
        pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")

        kg = {
            "things": [{"id": "n1", "source_id": "a", "target_id": "b", "type": "REL"}]
        }
        export_knowledge_graph(kg, str(tmp_path / "shaped.parquet"))

        blob = _blob(_files(tmp_path, "shaped_things"))
        assert "a" in blob and "b" in blob

    def test_an_explicit_schema_still_wins_over_the_key_name(self, tmp_path):
        """The documented way to write an arbitrary key is to pass a schema.

        A dictionary is still written one file per key, so the file to read is
        the one named after the key rather than the path that was asked for.
        """
        pyarrow = pytest.importorskip(
            "pyarrow", reason="the parquet writer needs pyarrow"
        )
        import pyarrow.parquet as pq

        schema = pyarrow.schema(
            [
                pyarrow.field("id", pyarrow.string()),
                pyarrow.field("note", pyarrow.string()),
            ]
        )
        kg = {"entities": [{"id": "n1", "note": "kept"}]}

        export_knowledge_graph(kg, str(tmp_path / "with_schema.parquet"), schema=schema)

        # Had the key name won, this would carry the entity schema's columns.
        target = tmp_path / "with_schema_entities.parquet"
        assert target.exists(), sorted(p.name for p in tmp_path.glob("*"))
        table = pq.read_table(target)
        assert table.column_names == ["id", "note"]
        assert table.to_pydict()["note"] == ["kept"]


class TestOnlyRunnableFormatsAreOffered:
    """The command's list is what this module covers."""

    @pytest.mark.parametrize("fmt", ["owl", "shacl", "distance-enriched"])
    def test_ontology_and_session_formats_are_not_offered(self, fmt):
        """Three formats need an input a graph-store dump does not have.

        OWL and SHACL are serialized from an ontology (``semantica ontology
        shacl`` generates shapes; ``OWLExporter`` takes ``classes`` and
        ``properties``), and the distance matrix is computed from an Explorer
        session graph. Offering them here only advertised failures, so they
        were dropped rather than faked.
        """
        assert fmt not in _EXPORT_FORMATS

    @pytest.mark.parametrize("fmt", ["shacl", "distance-enriched"])
    def test_the_router_does_not_claim_to_build_them(self, fmt):
        with pytest.raises(ProcessingError, match="Unknown export format"):
            export_knowledge_graph(cli_knowledge_graph(), "unused.out", format=fmt)

    def test_owl_is_routed_but_produces_no_classes_for_a_graph(self, tmp_path):
        """``owl`` is still routable; the short name is normalized.

        ``OWLExporter`` accepts ``owl-xml`` or ``turtle`` and rejected the bare
        ``owl`` the router forwarded, while the extension map had always mapped
        ``.owl`` to ``owl-xml``. A knowledge graph carries no classes, so the
        document is empty of them -- which is why the command does not offer
        the format.
        """
        export_knowledge_graph(
            cli_knowledge_graph(), str(tmp_path / "o.owl"), format="owl"
        )

        body = (tmp_path / "o.owl").read_text(encoding="utf-8")
        assert body.lstrip().startswith("<")
        assert "KNOWS" not in body


class TestExtensionRoutingMatchesTheExplicitFormat:
    """Naming the format and letting the extension name it must agree.

    ``format_map`` carried ``.parquet`` but not ``.arrow``, and an extension it
    does not know falls back to ``json``. Routing the Arrow branch by hand
    therefore left callers of the documented extension-driven form with JSON
    under an ``.arrow`` name, and no error. Comparing the files each spelling
    writes catches that without depending on how a format looks inside.
    """

    @pytest.mark.parametrize("fmt", _EXPORT_FORMATS)
    def test_the_extension_alone_reaches_the_same_exporter(self, tmp_path, fmt):
        ext = FORMAT_EXTENSIONS[fmt]
        explicit_dir = tmp_path / "explicit"
        inferred_dir = tmp_path / "inferred"
        explicit_dir.mkdir()
        inferred_dir.mkdir()

        export_knowledge_graph(
            cli_knowledge_graph(), str(explicit_dir / f"graph{ext}"), format=fmt
        )
        export_knowledge_graph(cli_knowledge_graph(), str(inferred_dir / f"graph{ext}"))

        written = {
            name: sorted(p.name for p in directory.iterdir())
            for name, directory in (
                ("explicit", explicit_dir),
                ("inferred", inferred_dir),
            )
        }
        assert (
            written["inferred"] == written["explicit"]
        ), f"{ext} alone routed away from the {fmt} exporter: {written}"

        files = [inferred_dir / name for name in written["inferred"]]
        blob = _blob(files)
        assert "KNOWS" in blob, f"{ext} alone lost the relationship type"
        assert "n1" in blob and "n2" in blob, f"{ext} alone lost an endpoint"
        assert "#None" not in blob, f"{ext} alone left an endpoint unresolved"


class TestParquetRecognisesStoreShapedEdges:
    """The shape check behind Parquet's routing reads the same name table.

    It listed only the ``source*``/``target*`` spellings, so a caller passing a
    store-shaped edge collection under a key of their own choosing had it
    written with the entity schema, which succeeds while dropping both
    endpoints. ``export_knowledge_graph`` normalizes first, so only a direct
    call to the exporter could see this.
    """

    def test_a_store_shaped_edges_key_is_written_as_relationships(self, tmp_path):
        pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")
        from semantica.export import ParquetExporter

        ParquetExporter().export(
            {
                "edges": [
                    {
                        "id": "r1",
                        "type": "KNOWS",
                        "start_node_id": "n1",
                        "end_node_id": "n2",
                    }
                ]
            },
            str(tmp_path / "direct.parquet"),
        )

        blob = _blob(_files(tmp_path, "direct_edges"))
        assert "KNOWS" in blob
        # The entity writer keeps id and type and drops the endpoints, so this
        # is what tells the two writers apart.
        assert "n1" in blob and "n2" in blob, "the endpoints did not reach the file"

    def test_a_bare_list_of_store_shaped_edges_is_written_as_relationships(
        self, tmp_path
    ):
        pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")
        from semantica.export import ParquetExporter

        ParquetExporter().export(
            [
                {
                    "id": "r1",
                    "type": "KNOWS",
                    "start_node_id": "n1",
                    "end_node_id": "n2",
                }
            ],
            str(tmp_path / "bare.parquet"),
        )

        blob = _blob(_files(tmp_path, "bare.parquet"))
        assert "n1" in blob and "n2" in blob, "the endpoints did not reach the file"


class TestEntityOffsetsAreNotEndpoints:
    """``start`` and ``end`` are entity offsets, not the ends of a relationship.

    Both are columns of the entity schema that ``parquet_exporter``,
    ``arrow_exporter`` and ``csv_exporter`` write. A table of endpoint names
    that includes them adds ``source_id``/``target_id`` to every entity record,
    and the shape check behind Parquet's routing then reads that as a
    relationship and hands the entities to the relationship writer, which drops
    them and raises. The names in ``endpoint_names`` are therefore limited to
    ones an entity field cannot be.
    """

    def test_a_record_with_offsets_is_not_read_as_a_relationship(self):
        entity = {"id": "e1", "type": "Person", "start": 0, "end": 5}

        assert has_endpoints(entity) is False
        assert canonical_endpoints([entity]) == [entity]

    def test_the_router_adds_no_endpoint_keys_to_entities(self, tmp_path):
        """A writer that copies records through shows the damage directly.

        The tabular writers pick named fields, so an extra key on an entity is
        invisible there; JSON writes the record out as it stands.
        """
        kg = {"entities": [{"id": "e1", "type": "Person", "start": 0, "end": 5}]}
        target = tmp_path / "entities.json"

        export_knowledge_graph(kg, str(target), format="json")

        body = target.read_text(encoding="utf-8")
        assert "source_id" not in body and "target_id" not in body

    def test_entity_offsets_survive_the_export(self, tmp_path):
        pytest.importorskip("pyarrow", reason="the parquet writer needs pyarrow")
        import pyarrow.parquet as pq

        kg = {
            "entities": [
                {"id": "e1", "type": "Person", "start": 0, "end": 5},
                {"id": "e2", "type": "Person", "start": 6, "end": 9},
            ]
        }
        export_knowledge_graph(kg, str(tmp_path / "offsets.parquet"))

        rows = pq.read_table(tmp_path / "offsets_entities.parquet").to_pydict()
        assert rows["id"] == ["e1", "e2"]
        assert rows["start"] == [0, 6]
        assert rows["end"] == [5, 9]


class TestMultiFileFormats:
    """The formats that write one file per collection.

    ``arrow``, ``csv`` and ``parquet`` treat the path they are handed as a base
    name: ``graph.arrow`` becomes ``graph_entities.arrow`` and
    ``graph_relationships.arrow``, and ``graph.arrow`` itself is never created.
    A caller therefore has to be told what was written rather than what it
    asked for, and cannot send one of these formats to a single destination.
    """

    @pytest.mark.parametrize("fmt", MULTI_FILE_FORMATS)
    def test_writes_one_file_per_collection(self, tmp_path, fmt):
        stem = f"base_{fmt}"
        ext = FORMAT_EXTENSIONS[fmt]
        target = tmp_path / f"{stem}{ext}"

        export_knowledge_graph(cli_knowledge_graph(), str(target), format=fmt)

        names = sorted(p.name for p in tmp_path.glob(f"{stem}*"))
        assert names == [f"{stem}_entities{ext}", f"{stem}_relationships{ext}"], names
        assert (
            not target.exists()
        ), "the path passed in is a base name, not the artifact"

    @pytest.mark.parametrize("fmt", _EXPORT_FORMATS)
    def test_returns_the_paths_it_wrote(self, tmp_path, fmt):
        target = tmp_path / f"ret{FORMAT_EXTENSIONS[fmt]}"

        written = export_knowledge_graph(cli_knowledge_graph(), str(target), format=fmt)

        if fmt in MULTI_FILE_FORMATS:
            assert written, f"{fmt} wrote files but reported none"
            assert sorted(Path(p).name for p in written) == sorted(
                p.name for p in tmp_path.glob("ret*")
            )
        else:
            assert written is None, f"{fmt} writes the path it was given"

    @pytest.mark.parametrize("fmt", _EXPORT_FORMATS)
    def test_several_files_exactly_when_it_is_listed(self, tmp_path, fmt):
        """``MULTI_FILE_FORMATS`` makes the command refuse a single destination,
        so it has to agree with what the routes actually do."""
        target = tmp_path / f"multi{FORMAT_EXTENSIONS[fmt]}"

        export_knowledge_graph(cli_knowledge_graph(), str(target), format=fmt)

        several = len(list(tmp_path.glob("multi*"))) > 1
        assert several == (
            fmt in MULTI_FILE_FORMATS
        ), f"{fmt} wrote {several} files, listed={fmt in MULTI_FILE_FORMATS}"

    @pytest.mark.parametrize("fmt", _EXPORT_FORMATS)
    def test_a_graph_without_relationships_still_exports(self, tmp_path, fmt):
        """Nothing to relate is not a failure (#1712).

        Arrow refused an empty collection outright, so a graph whose nodes had
        no edges between them could not be exported at all.
        """
        target = tmp_path / f"lonely{FORMAT_EXTENSIONS[fmt]}"

        export_knowledge_graph(
            cli_knowledge_graph(relationships=[]), str(target), format=fmt
        )

        files = _files(tmp_path, "lonely")
        assert files, f"{fmt} wrote no file"
        assert all(f.stat().st_size for f in files), f"{fmt} wrote an empty file"
        # The entity ids, since the entity name lives in a nested property that
        # the serializers do not all flatten.
        blob = _blob(files)
        assert "n1" in blob and "n2" in blob, f"{fmt} lost the entities"
