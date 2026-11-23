"""Tests for the ``semantica.ingest`` public package API.

Six of the 33 ingestors were not reachable from the package. Each one's own
module docstring documents the package-level import, and each of those
imports raised ``ImportError``::

    DuckDBIngestor      duckdb_ingestor.py:21
    ElasticIngestor     elastic_ingestor.py:19
    GDriveIngestor      gdrive_ingestor.py:19
    HuggingFaceIngestor huggingface_ingestor.py:18
    MongoIngestor       mongo_ingestor.py:20
    PandasIngestor      pandas_ingestor.py:19

Same shape as #2243, in a package that has a deliberate lazy-export
mechanism those six were never added to: ``_LAZY_EXPORTS`` carried 90 entries
covering 27 of the 33 ingestor classes.

Nothing caught it because every existing test imports these classes by their
full module path, so the tests exercise the classes while never touching the
package surface that was broken. ``test_every_ingestor_class_is_reachable``
is the durable guard: it fails if a 34th backend is added without being
registered, which is how these six got in.

**On attribute access.** ``hasattr(semantica.ingest, "RepoIngestor")`` raises
``ImportError`` on a core install rather than returning ``False``: the lazy
``__getattr__`` probes the optional dependency and raises a helpful message,
and ``hasattr`` only swallows ``AttributeError``. So the sweep below reads
``_LAZY_EXPORTS`` and ``__all__`` statically and never touches an attribute
whose backend might be absent.
"""

import ast
import pathlib

import pytest

import semantica.ingest as ingest_pkg

_INGEST_DIR = pathlib.Path(ingest_pkg.__file__).parent

# Added by this change, with the module each comes from. These six guard
# their optional import with an ``X = None`` sentinel rather than an
# ``X_AVAILABLE`` flag, so no probe was added for them and the names resolve
# with the dependency absent -- see TestResolvesWithoutTheDependency.
_NEWLY_EXPORTED = {
    "DuckDBIngestor": "duckdb_ingestor",
    "DuckDBData": "duckdb_ingestor",
    "ElasticIngestor": "elastic_ingestor",
    "ElasticData": "elastic_ingestor",
    "GDriveIngestor": "gdrive_ingestor",
    "GDriveData": "gdrive_ingestor",
    "HuggingFaceIngestor": "huggingface_ingestor",
    "HFData": "huggingface_ingestor",
    "MongoIngestor": "mongo_ingestor",
    "MongoData": "mongo_ingestor",
    "MongoConnector": "mongo_ingestor",
    "PandasIngestor": "pandas_ingestor",
    "PandasData": "pandas_ingestor",
}

# The six whose documented package-level import was broken.
_DOCUMENTED_IMPORTS = [
    "DuckDBIngestor",
    "ElasticIngestor",
    "GDriveIngestor",
    "HuggingFaceIngestor",
    "MongoIngestor",
    "PandasIngestor",
]


def _really_importable(name):
    """True if ``from semantica.ingest import name`` would succeed.

    The guard this replaces compared names against
    ``set(_LAZY_EXPORTS) | set(__all__)``. Because that is a **union**, a name
    listed in ``__all__`` with no lazy mapping counted as reachable while
    importing it raised ``AttributeError`` -- so the guard written to catch
    the next unregistered ingestor would have passed it. Appending a
    ``GhostIngestor`` to ``__all__`` demonstrates it.

    The thing being guarded is a behaviour, so this asserts the behaviour.
    ``hasattr`` cannot be used: for a probe-backed backend the lazy
    ``__getattr__`` raises ``ImportError`` with an install hint on a core
    install, and ``hasattr`` only swallows ``AttributeError``. That
    ``ImportError`` means the name *is* registered and the extra is simply
    absent, which is reachable for our purposes -- so it is caught
    explicitly rather than avoided by not asking.
    """
    try:
        getattr(ingest_pkg, name)
    except AttributeError:
        return False
    except ImportError:
        # Registered, but its optional backend is not installed.
        return True
    return True


def _ingestor_classes():
    """Every ``*Ingestor`` class defined in an ``*_ingestor.py`` module."""
    found = []
    for path in sorted(_INGEST_DIR.glob("*_ingestor.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith(
                "Ingestor"
            ):
                found.append((path.stem, node.name))
    return found


class TestEveryIngestorIsReachable:
    """The guard that makes this class of defect non-recurring."""

    def test_every_ingestor_class_is_reachable(self):
        missing = sorted(
            f"{stem}.{name}"
            for stem, name in _ingestor_classes()
            if not _really_importable(name)
        )
        assert missing == []

    def test_a_name_in_all_without_a_mapping_is_not_counted_reachable(self):
        """The hole this replaces: ``__all__`` membership is not an import.

        The previous guard unioned ``_LAZY_EXPORTS`` with ``__all__``, so a
        name added to ``__all__`` alone passed while importing it failed.
        """
        ingest_pkg.__all__.append("GhostIngestor")
        try:
            assert "GhostIngestor" in set(ingest_pkg.__all__)
            assert not _really_importable("GhostIngestor")
        finally:
            ingest_pkg.__all__.remove("GhostIngestor")

    def test_a_probe_backed_backend_counts_as_reachable(self):
        """``RepoIngestor`` raises ImportError, not AttributeError, bare.

        It is registered; only GitPython may be absent. Treating that as
        unreachable would make the guard fail on a core install.
        """
        assert _really_importable("RepoIngestor")

    def test_the_sweep_actually_finds_the_modules(self):
        """Rule out a sweep that passes because it collected nothing."""
        classes = _ingestor_classes()
        assert len(classes) >= 33
        names = {name for _, name in classes}
        for expected in _DOCUMENTED_IMPORTS:
            assert expected in names


class TestDocumentedImportsWork:
    @pytest.mark.parametrize("name", _DOCUMENTED_IMPORTS)
    def test_module_docstring_import_resolves(self, name):
        assert getattr(ingest_pkg, name) is not None

    @pytest.mark.parametrize("name", _DOCUMENTED_IMPORTS)
    def test_the_docstring_really_documents_that_import(self, name):
        """Pins the claim, so this list cannot drift from the docstrings."""
        stem = _NEWLY_EXPORTED[name]
        source = (_INGEST_DIR / f"{stem}.py").read_text(encoding="utf-8")
        assert f">>> from semantica.ingest import {name}" in source


class TestRegistrationIsComplete:
    @pytest.mark.parametrize("name", sorted(_NEWLY_EXPORTED))
    def test_name_is_in_lazy_exports_and_all(self, name):
        assert name in ingest_pkg._LAZY_EXPORTS
        assert name in ingest_pkg.__all__

    @pytest.mark.parametrize("name", sorted(_NEWLY_EXPORTED))
    def test_lazy_export_points_at_the_right_module(self, name):
        module_name, attr_name = ingest_pkg._LAZY_EXPORTS[name]
        assert module_name == f".{_NEWLY_EXPORTED[name]}"
        assert attr_name == name

    def test_all_has_no_duplicates(self):
        assert len(ingest_pkg.__all__) == len(set(ingest_pkg.__all__))


class TestResolvesWithoutTheDependency:
    """These six must import lazily and fail only on use.

    Each module guards its optional import with ``X = None``, so the module
    imports with the dependency absent. No probe was added for them, so the
    name resolves and the class raises on construction instead -- with a
    message naming the exact package, which is better than a generic one and
    must not be masked by the new export.
    """

    @pytest.mark.parametrize("name", sorted(_NEWLY_EXPORTED))
    def test_name_resolves_whether_or_not_the_backend_is_installed(
        self, name
    ):
        assert getattr(ingest_pkg, name) is not None

    @pytest.mark.parametrize(
        "name,package",
        [
            ("DuckDBIngestor", "duckdb"),
            ("ElasticIngestor", "elasticsearch"),
            ("HuggingFaceIngestor", "datasets"),
            ("MongoIngestor", "pymongo"),
        ],
    )
    def test_construction_names_the_missing_package(self, name, package):
        import importlib.util

        if importlib.util.find_spec(package) is not None:
            pytest.skip(f"{package} is installed, so it constructs")
        with pytest.raises(ImportError, match=package):
            getattr(ingest_pkg, name)()
