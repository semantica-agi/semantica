"""TOML config files must load on every supported Python.

GraphStoreConfig, TripletStoreConfig and VectorStoreConfig imported the
third-party ``tomli`` backport, which Semantica never declared. On Python
3.11+ it was usually absent, so a ``.toml`` config file raised ImportError
inside ``_load_from_file``, was logged and ignored, and the settings were
silently dropped. Python 3.11 is now the floor, so those four config classes
use the stdlib ``tomllib``.

The other eleven config classes loaded ``.toml`` with the third-party ``toml``
package (TOML 0.5) from a text file. They now use ``tomllib`` (TOML 1.0) from
a binary file too. ``semantic_extract.config.Config`` merges the whole
document, so its case sets a top-level key. The other classes unwrap one
section.

CI's pinned environment has both ``tomli`` (coverage pulls it in) and ``toml``
installed, which would hide a regression back to either import, so every case
blocks both.
"""

import sys

import pytest

from semantica.conflicts.config import ConflictsConfig
from semantica.deduplication.config import DeduplicationConfig
from semantica.embeddings.config import EmbeddingsConfig
from semantica.export.config import ExportConfig
from semantica.graph_store.config import GraphStoreConfig
from semantica.ingest.config import IngestConfig
from semantica.kg.config import KGConfig
from semantica.normalize.config import NormalizeConfig
from semantica.ontology.config import OntologyConfig
from semantica.parse.config import ParseConfig
from semantica.semantic_extract.config import Config as SemanticExtractConfig
from semantica.split.config import SplitConfig
from semantica.triplet_store.config import TripletStoreConfig
from semantica.vector_store.config import VectorStoreConfig
from semantica.visualization.config import VisualizationConfig


def _block_third_party_toml_parsers(monkeypatch):
    # A None entry in sys.modules makes `import tomli` and `import toml` raise
    # ImportError.
    monkeypatch.setitem(sys.modules, "tomli", None)
    monkeypatch.setitem(sys.modules, "toml", None)


@pytest.mark.parametrize(
    "config_cls, section",
    [
        (GraphStoreConfig, "graph_store"),
        (TripletStoreConfig, "triplet_store"),
        (VectorStoreConfig, "vector_store"),
        (VisualizationConfig, "visualization"),
        (ConflictsConfig, "conflicts"),
        (DeduplicationConfig, "deduplication"),
        (EmbeddingsConfig, "embeddings"),
        (ExportConfig, "export"),
        (IngestConfig, "ingest"),
        (KGConfig, "kg"),
        (NormalizeConfig, "normalize"),
        (OntologyConfig, "ontology"),
        (ParseConfig, "parse"),
        (SplitConfig, "split"),
    ],
)
def test_toml_config_file_is_applied(tmp_path, monkeypatch, config_cls, section):
    _block_third_party_toml_parsers(monkeypatch)
    config_file = tmp_path / "semantica.toml"
    config_file.write_text(f'[{section}]\ntoml_probe = "from-toml"\n', encoding="utf-8")

    config = config_cls(config_file=str(config_file))

    assert config.get("toml_probe") == "from-toml"


def test_semantic_extract_toml_config_merges_the_whole_document(tmp_path, monkeypatch):
    _block_third_party_toml_parsers(monkeypatch)
    config_file = tmp_path / "semantica.toml"
    config_file.write_text('toml_probe = "from-toml"\n', encoding="utf-8")

    config = SemanticExtractConfig(config_file=str(config_file))

    assert config.get("toml_probe") == "from-toml"
