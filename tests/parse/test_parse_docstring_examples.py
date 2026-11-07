#!/usr/bin/env python3
"""Regression tests for the ``Example Usage`` blocks in ``semantica/parse``.

Nine module docstrings documented methods that do not exist, so copying any
of these examples raised ``AttributeError`` on its first parser call::

    StructuredDataParser.parse_json/_csv/_xml -> parse_data
    WebParser.parse_html                      -> parse_web_content
    CodeParser.parse_file                     -> parse_code
    EmailParser.parse/parse_headers           -> parse_email/.headers
    JSONParser.extract_paths                  -> extract_values
    MediaParser.parse/get_media_info          -> parse_media
    PDFParser.extract_pages/extract_metadata  -> parse()["pages"]/["metadata"]
    DOCXParser.extract_sections/_metadata     -> parse()["sections"]/[...]
    ExcelParser.parse_sheet                   -> extract_sheet

The sweep below reads the docstrings themselves, so it fails if a documented
call names an attribute the class does not have -- the shape of the original
bug. It is deliberately static: ``semantica.parse`` imports without any
optional extra, and running the examples for real would need pdfplumber,
python-docx, openpyxl, Pillow and lxml, which is how a guard like this turns
into a suite that fails instead of skipping on a core install.

``test_json_parser_example_runs`` executes one block end to end, so the sweep
cannot pass while the examples are broken in a way attribute names do not show.
"""

import ast
import doctest
import importlib
import json
import pathlib
import re

import pytest

import semantica.parse as parse_pkg

_PARSE_DIR = pathlib.Path(parse_pkg.__file__).parent
_EXAMPLE_BLOCK_RE = re.compile(
    r"^Example Usage:\n(.*?)(?=^\S|\Z)", re.DOTALL | re.MULTILINE
)
_ASSIGN_RE = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*\(")
_CALL_RE = re.compile(r"\b(\w+)\.(\w+)\s*\(")


def _modules():
    """Every ``semantica.parse`` submodule, by dotted name."""
    return sorted(
        f"semantica.parse.{p.stem}"
        for p in _PARSE_DIR.glob("*.py")
        if p.stem != "__init__"
    )


def _example_statements(doc):
    """The ``>>>`` statements of the docstring's Example Usage block."""
    match = _EXAMPLE_BLOCK_RE.search(doc or "")
    if not match:
        return []
    parser = doctest.DocTestParser()
    return [e.source for e in parser.get_examples(match.group(1))]


def _documented_calls(module):
    """Yield (class_name, attribute, statement) for each documented call.

    Only calls on a variable assigned from a class the module exposes are
    considered, so a placeholder name in an example is not mistaken for a
    missing attribute.
    """
    for owner_doc in _docstrings(module):
        statements = _example_statements(owner_doc)
        bound = {}
        for stmt in statements:
            m = _ASSIGN_RE.match(stmt)
            if m and isinstance(getattr(module, m.group(2), None), type):
                bound[m.group(1)] = m.group(2)
        for stmt in statements:
            for var, attr in _CALL_RE.findall(stmt):
                if var in bound:
                    yield bound[var], attr, stmt.strip()


def _docstrings(module):
    """The module docstring plus every class and function docstring in it."""
    source = pathlib.Path(module.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                yield doc


@pytest.mark.parametrize("module_name", _modules())
def test_documented_calls_name_real_attributes(module_name):
    """Every documented ``obj.method(...)`` must exist on obj's class."""
    module = importlib.import_module(module_name)
    missing = [
        (cls, attr, stmt)
        for cls, attr, stmt in _documented_calls(module)
        if not hasattr(getattr(module, cls), attr)
    ]
    assert not missing, "\n".join(
        f"{module_name}: {cls} has no attribute {attr!r}"
        f" -- documented as: {stmt}"
        for cls, attr, stmt in missing
    )


def test_sweep_sees_the_parse_examples():
    """The sweep must not be silently vacuous."""
    checked = [
        call
        for name in _modules()
        for call in _documented_calls(importlib.import_module(name))
    ]
    assert len(checked) >= 20, f"only {len(checked)} documented calls found"


def test_json_parser_example_runs(tmp_path, monkeypatch):
    """Run the JSONParser block verbatim; it needs nothing but the stdlib."""
    import semantica.parse.json_parser as json_parser_module

    statements = _example_statements(json_parser_module.__doc__)
    assert statements, "json_parser docstring lost its Example Usage block"

    (tmp_path / "data.json").write_text(
        json.dumps({"a": 1, "users": [{"name": "x"}, {"name": "y"}]})
    )
    monkeypatch.chdir(tmp_path)

    namespace = {}
    source = "".join(statements)
    exec(compile(source, "<json_parser docstring>", "exec"), namespace)

    assert namespace["data"].data["a"] == 1
    assert namespace["values"] == [[{"name": "x"}, {"name": "y"}]]
