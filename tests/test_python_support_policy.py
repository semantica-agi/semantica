"""The supported Python range must be declared identically everywhere (#1506).

``requires-python`` in pyproject.toml is the source of truth. The classifiers,
the Install Matrix, the Docker runtime image and ``semantica doctor`` all
restate it and used to drift apart (3.8 in docs and diagnostics, 3.9 in the
matrix, 3.14 in the Docker image). These tests fail when they disagree.
"""

import re
from pathlib import Path

import pytest
import tomllib
import yaml

from semantica import cli

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pyproject():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _range(requires_python: str):
    """Parse ``>=3.11.5,<3.14`` into ``((3, 11, 5), (3, 14, 0))``."""
    floor = re.fullmatch(r".*>=\s*(\d+)\.(\d+)(?:\.(\d+))?.*", requires_python)
    ceiling = re.fullmatch(r".*<\s*(\d+)\.(\d+)(?:\.(\d+))?.*", requires_python)
    assert floor and ceiling, (
        f"requires-python must state both a floor and a ceiling, got {requires_python!r}"
    )
    return (
        (int(floor.group(1)), int(floor.group(2)), int(floor.group(3) or 0)),
        (int(ceiling.group(1)), int(ceiling.group(2)), int(ceiling.group(3) or 0)),
    )


def _declared_floor(requires_python: str) -> str:
    """Return the floor exactly as declared, e.g. ``3.11.5`` or ``3.11``."""
    match = re.fullmatch(r".*>=\s*(\d+\.\d+(?:\.\d+)?).*", requires_python)
    assert match, (
        f"requires-python must state a floor, got {requires_python!r}"
    )
    return match.group(1)


def _supported_versions(pyproject):
    floor, ceiling = _range(pyproject["project"]["requires-python"])
    assert floor[0] == ceiling[0] == 3
    return {f"3.{minor}" for minor in range(floor[1], ceiling[1])}


def test_doctor_constants_match_requires_python(pyproject):
    floor, ceiling = _range(pyproject["project"]["requires-python"])
    assert cli.MIN_PYTHON == floor
    assert cli.MAX_PYTHON_EXCLUSIVE == ceiling


def test_classifiers_list_exactly_the_supported_versions(pyproject):
    prefix = "Programming Language :: Python :: "
    declared = {
        c[len(prefix):]
        for c in pyproject["project"]["classifiers"]
        if re.fullmatch(re.escape(prefix) + r"3\.\d+", c)
    }
    assert declared == _supported_versions(pyproject)


def test_install_matrix_tests_exactly_the_supported_versions(pyproject):
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "install-matrix.yml").read_text(
            encoding="utf-8"
        )
    )
    matrix = workflow["jobs"]["verify-install"]["strategy"]["matrix"]
    versions = [str(v) for v in matrix["python-version"]]
    # The matrix carries a bare major.minor for every supported line, plus the
    # floor patch release (3.11.5), because nothing before it installs.
    pinned = {".".join(v.split(".")[:2]) for v in versions}
    assert pinned == _supported_versions(pyproject)
    # Both entries are checked against the raw list. Folding 3.11.5 down to
    # 3.11 for the set comparison above would let either one go missing and
    # still pass, so the matrix is read twice.
    declared = _declared_floor(pyproject["project"]["requires-python"])
    assert declared.count(".") == 2, (
        f"the floor must be declared with a patch release, got {declared!r}: "
        "3.11.0-3.11.4 cannot resolve soupsieve 4.x (#2251)"
    )
    assert declared in versions, (
        f"Install Matrix must test the floor pin {declared}, got {versions}"
    )
    bare = ".".join(declared.split(".")[:2])
    assert bare in versions, (
        f"Install Matrix must keep the bare {bare} line alongside {declared}, "
        f"got {versions}"
    )


def test_docker_runtime_image_is_inside_the_supported_range(pyproject):
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    images = re.findall(r"^FROM python:(\d+)\.(\d+)", dockerfile, flags=re.MULTILINE)
    assert images, "Dockerfile has no python runtime image"
    supported = _supported_versions(pyproject)
    for major, minor in images:
        assert f"{major}.{minor}" in supported


def test_dev_tooling_is_a_dependency_group_not_a_runtime_extra(pyproject):
    extras = pyproject["project"]["optional-dependencies"]
    assert "dev" not in extras
    assert "dev" in pyproject["dependency-groups"]
    assert not any("dev" in re.findall(r"[\w-]+", spec) for spec in extras["all"])


@pytest.mark.parametrize(
    "version, status",
    [
        ((3, 8, 18), "fail"),
        ((3, 9, 21), "fail"),
        # 3.10 has failed since 0.8.0, which moved the floor to 3.11 (#2067).
        ((3, 10, 18), "fail"),
        # 3.11.0 to 3.11.4 cannot install soupsieve 4.x, which the audit gate
        # requires (#2251), so the floor carries a patch version.
        ((3, 11), "fail"),
        ((3, 11, 0), "fail"),
        ((3, 11, 4), "fail"),
        ((3, 11, 5), "ok"),
        ((3, 13, 9), "ok"),
        ((3, 14, 0), "warn"),
    ],
)
def test_doctor_python_check(version, status):
    got, hint = cli._python_version_check(version)
    assert got == status
    assert (hint is None) == (status == "ok")
    if status == "fail":
        assert "3.11.5" in hint
