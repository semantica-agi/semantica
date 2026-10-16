"""``JSONExporter`` must reject a format it cannot write instead of silently
writing JSON into a file named for another format (#1968)."""

import json
import os
import tempfile

import pytest

from semantica.export import JSONExporter
from semantica.utils.exceptions import ValidationError


def _kg() -> dict:
    return {"entities": [{"id": "X1", "text": "x", "metadata": {}}], "relationships": []}


@pytest.mark.parametrize("bad", ["parquet", "zzz", "JSON", "jsonld"])
def test_export_knowledge_graph_rejects_unknown_format(bad):
    path = os.path.join(tempfile.mkdtemp(), "out." + bad)
    with pytest.raises(ValidationError):
        JSONExporter().export_knowledge_graph(_kg(), path, format=bad)
    assert not os.path.exists(path)


def test_export_rejects_unknown_format():
    path = os.path.join(tempfile.mkdtemp(), "out.parquet")
    with pytest.raises(ValidationError):
        JSONExporter().export(_kg(), path, format="parquet")
    assert not os.path.exists(path)


def test_constructor_format_is_checked_too():
    path = os.path.join(tempfile.mkdtemp(), "out.parquet")
    with pytest.raises(ValidationError):
        JSONExporter(format="parquet").export_knowledge_graph(_kg(), path)
    assert not os.path.exists(path)


@pytest.mark.parametrize("fmt", ["json", "json-ld"])
def test_supported_formats_still_write(fmt):
    path = os.path.join(tempfile.mkdtemp(), "out." + fmt)
    JSONExporter().export_knowledge_graph(_kg(), path, format=fmt)
    with open(path, encoding="utf-8") as f:
        json.load(f)


def test_rejected_format_creates_nothing_not_even_the_parent_dir(tmp_path):
    # export() is called directly so the guard's position relative to
    # ensure_directory is what is under test; export_knowledge_graph() checks
    # the format itself before delegating.
    nested = tmp_path / "nope" / "out.parquet"
    with pytest.raises(ValidationError):
        JSONExporter().export(_kg(), str(nested), format="parquet")
    assert not nested.exists()
    assert not (tmp_path / "nope").exists()


def test_constructor_format_none_falls_back_to_json():
    # An explicit None is "not provided", not an unsupported format: the
    # wrapper in export/methods.py forwards a caller's None into the
    # constructor, and that used to write JSON.
    path = os.path.join(tempfile.mkdtemp(), "out.json")
    JSONExporter(format=None).export_knowledge_graph(_kg(), path)
    with open(path, encoding="utf-8") as f:
        json.load(f)


def test_call_format_none_falls_back_to_the_instance_default():
    path = os.path.join(tempfile.mkdtemp(), "out.json")
    JSONExporter().export_knowledge_graph(_kg(), path, format=None)
    with open(path, encoding="utf-8") as f:
        json.load(f)


def test_constructor_rejects_an_unsupported_format():
    with pytest.raises(ValidationError):
        JSONExporter(format="csv")
