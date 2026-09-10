"""Guard for the aggregate ``all`` extras in pyproject.toml.

Review of #1508 caught ``parse-pdf`` missing from every ``all`` bundle:
``semantica[all]`` installed the package without pdfplumber, so the default
PDFParser raised ProcessingError on first use. tomllib is stdlib only from
Python 3.11, so the bundle block is parsed textually — the repo still
supports 3.9/3.10.
"""

import re
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _extras_in_all_bundles():
    """Collect every extra name referenced inside the ``all = [...]`` block."""
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r"^all = \[\n(.*?)^\]", text, re.MULTILINE | re.DOTALL)
    assert match, "pyproject.toml must define an aggregate 'all' extra"

    names = set()
    for bundle in re.findall(r"semantica\[([^\]]+)\]", match.group(1)):
        names.update(part.strip() for part in bundle.split(","))
    assert names, "'all' bundles must reference at least one extra"
    return names


def test_all_bundles_include_parse_pdf():
    """An all-features install must include built-in PDF parsing support."""
    assert "parse-pdf" in _extras_in_all_bundles()


def test_all_bundle_extraction_finds_known_extra():
    """Control: the extraction reads the right block (parse-docling is in)."""
    assert "parse-docling" in _extras_in_all_bundles()
