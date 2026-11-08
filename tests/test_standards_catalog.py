"""The standards catalog must stay complete and machine-readable (#2024).

``standards/catalog.yaml`` is the static inventory of the standards Semantica
leans on. The rules it has to satisfy live here so an entry cannot quietly
lose a field:

- the file parses as YAML and holds a non-empty list of entries;
- every entry carries name, version, license, maintainer, cadence, source and
  consumed_by;
- entry names are unique;
- ``source`` is an http(s) URL;
- every module named in ``consumed_by`` still exists in this repository.

Source-link reachability needs the network, so it is opt-in and never part of
the default run:

    SEMANTICA_TEST_STANDARDS_NETWORK=1 pytest -q tests/test_standards_catalog.py
"""

import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "standards" / "catalog.yaml"

#: Fields every entry must carry as a non-empty string.
REQUIRED_TEXT_FIELDS = (
    "name",
    "version",
    "license",
    "maintainer",
    "cadence",
    "source",
)
#: Fields every entry must carry as a non-empty list of strings.
REQUIRED_LIST_FIELDS = ("consumed_by",)


def _load_catalog():
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8"))


def _entry_problems(entry):
    """Return the reasons ``entry`` is not a valid catalog entry.

    The same function guards the real catalog and the meta-test below, so the
    meta-test cannot pass while the real check has drifted into a no-op.
    """
    if not isinstance(entry, dict):
        return [f"entry must be a mapping, got {type(entry).__name__}"]

    problems = []
    for field in REQUIRED_TEXT_FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"missing or empty field {field!r}")

    source = entry.get("source")
    if isinstance(source, str) and source.strip():
        if not source.startswith(("http://", "https://")):
            problems.append(f"source must be an http(s) URL, got {source!r}")

    for field in REQUIRED_LIST_FIELDS:
        value = entry.get(field)
        if not isinstance(value, list) or not value:
            problems.append(f"missing or empty field {field!r}")
        elif not all(isinstance(item, str) and item.strip() for item in value):
            problems.append(f"field {field!r} must list non-empty strings")

    return problems


@pytest.fixture(scope="module")
def catalog():
    return _load_catalog()


@pytest.fixture(scope="module")
def entries(catalog):
    return catalog["standards"]


def test_catalog_file_exists():
    assert CATALOG.is_file(), f"{CATALOG} is missing"


def test_catalog_parses_into_a_list_of_entries(catalog):
    assert isinstance(catalog, dict), "the catalog must be a mapping"
    standards = catalog.get("standards")
    assert isinstance(standards, list), "'standards' must be a list"
    assert standards, "the catalog must not be empty"


def test_every_entry_carries_the_required_fields(entries):
    for entry in entries:
        problems = _entry_problems(entry)
        assert not problems, (
            f"catalog entry {entry.get('name', '<unnamed>')!r} is incomplete: "
            + "; ".join(problems)
        )


def test_a_missing_field_is_reported(entries):
    """A field that goes missing has to fail the check above, not pass it."""
    complete = entries[0]
    assert not _entry_problems(complete)

    for field in REQUIRED_TEXT_FIELDS + REQUIRED_LIST_FIELDS:
        broken = {k: v for k, v in complete.items() if k != field}
        problems = _entry_problems(broken)
        assert problems, f"dropping {field!r} went unreported"
        assert any(field in problem for problem in problems), (
            f"dropping {field!r} was reported as {problems!r}, which does not "
            f"name the missing field"
        )


def test_entry_names_are_unique(entries):
    names = [entry["name"] for entry in entries]
    duplicates = {name for name in names if names.count(name) > 1}
    assert not duplicates, f"duplicate catalog entries: {sorted(duplicates)}"


def test_source_links_are_urls(entries):
    for entry in entries:
        assert entry["source"].startswith(("http://", "https://")), (
            f"{entry['name']}: source must be an http(s) URL, "
            f"got {entry['source']!r}"
        )


def test_consumed_by_modules_exist(entries):
    for entry in entries:
        for module in entry["consumed_by"]:
            assert (ROOT / module).is_file(), (
                f"{entry['name']}: consumed_by names {module}, which is not a "
                f"file in this repository"
            )


@pytest.mark.skipif(
    not os.environ.get("SEMANTICA_TEST_STANDARDS_NETWORK"),
    reason="network check; set SEMANTICA_TEST_STANDARDS_NETWORK=1 to run it",
)
def test_source_links_are_reachable(entries):
    import requests

    for entry in entries:
        response = requests.get(
            entry["source"],
            timeout=30,
            allow_redirects=True,
            stream=True,
            headers={"User-Agent": "semantica-standards-catalog-check"},
        )
        try:
            assert response.status_code == 200, (
                f"{entry['name']}: {entry['source']} returned "
                f"HTTP {response.status_code}"
            )
        finally:
            response.close()
