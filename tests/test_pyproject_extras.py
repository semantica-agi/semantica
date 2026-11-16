"""Guard for the aggregate ``all`` extras in pyproject.toml.

Review of #1508 caught ``parse-pdf`` missing from every ``all`` bundle:
``semantica[all]`` installed the package without pdfplumber, so the default
PDFParser raised ProcessingError on first use.
"""

import re
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _extras():
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)["project"]["optional-dependencies"]


def _extras_in_all_bundles():
    """Collect every extra name referenced by the aggregate ``all`` extra."""
    extras = _extras()
    assert "all" in extras, "pyproject.toml must define an aggregate 'all' extra"

    names = set()
    for spec in extras["all"]:
        for bundle in re.findall(r"semantica\[([^\]]+)\]", spec):
            names.update(part.strip() for part in bundle.split(","))
    assert names, "'all' bundles must reference at least one extra"
    return names


def test_all_bundles_include_parse_pdf():
    """An all-features install must include built-in PDF parsing support."""
    assert "parse-pdf" in _extras_in_all_bundles()


def test_all_bundle_extraction_finds_known_extra():
    """Control: the extraction reads the right block (parse-docling is in)."""
    assert "parse-docling" in _extras_in_all_bundles()


def test_all_bundles_include_langdetect():
    """#1807: without langdetect, LanguageDetector reports every text as the
    default language, so ``semantica[all]`` has to pull it in."""
    assert "nlp-langdetect" in _extras_in_all_bundles()
    assert any("langdetect" in spec for spec in _extras()["nlp-langdetect"])
