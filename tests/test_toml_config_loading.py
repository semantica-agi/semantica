"""TOML config files must load on every supported Python.

GraphStoreConfig, TripletStoreConfig and VectorStoreConfig imported the
third-party ``tomli`` backport, which Semantica never declared. On Python
3.11+ it was usually absent, so a ``.toml`` config file raised ImportError
inside ``_load_from_file``, was logged and ignored, and the settings were
silently dropped. Python 3.11 is now the floor, so all four config classes
use the stdlib ``tomllib``.

CI's pinned environment has ``tomli`` installed (coverage pulls it in), which
would hide a regression back to ``import tomli``, so the test blocks that
import for every case.
"""

import sys

import pytest

from semantica.graph_store.config import GraphStoreConfig
from semantica.triplet_store.config import TripletStoreConfig
from semantica.vector_store.config import VectorStoreConfig
from semantica.visualization.config import VisualizationConfig


@pytest.mark.parametrize(
    "config_cls, section",
    [
        (GraphStoreConfig, "graph_store"),
        (TripletStoreConfig, "triplet_store"),
        (VectorStoreConfig, "vector_store"),
        (VisualizationConfig, "visualization"),
    ],
)
def test_toml_config_file_is_applied(tmp_path, monkeypatch, config_cls, section):
    # A None entry in sys.modules makes `import tomli` raise ImportError.
    monkeypatch.setitem(sys.modules, "tomli", None)
    config_file = tmp_path / "semantica.toml"
    config_file.write_text(f'[{section}]\ntoml_probe = "from-toml"\n', encoding="utf-8")

    config = config_cls(config_file=str(config_file))

    assert config.get("toml_probe") == "from-toml"
