"""The supported Python range must be declared identically everywhere (#1506).

``requires-python`` in pyproject.toml is the source of truth. The classifiers,
the Install Matrix, the Docker runtime image and ``semantica doctor`` all
restate it and used to drift apart (3.8 in docs and diagnostics, 3.9 in the
matrix, 3.14 in the Docker image). These tests fail when they disagree.
"""

import re
from pathlib import Path

import pytest
import toml
import yaml

from semantica import cli

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pyproject():
    return toml.load(ROOT / "pyproject.toml")


def _range(requires_python: str):
    """Parse ``>=3.10,<3.14`` into ``((3, 10), (3, 14))``."""
    floor = re.fullmatch(r".*>=\s*(\d+)\.(\d+)(?:\.\d+)?.*", requires_python)
    ceiling = re.fullmatch(r".*<\s*(\d+)\.(\d+)(?:\.\d+)?.*", requires_python)
    assert floor and ceiling, (
        f"requires-python must state both a floor and a ceiling, got {requires_python!r}"
    )
    return (
        (int(floor.group(1)), int(floor.group(2))),
        (int(ceiling.group(1)), int(ceiling.group(2))),
    )


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
    assert {str(v) for v in matrix["python-version"]} == _supported_versions(pyproject)


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
        ((3, 10, 0), "ok"),
        ((3, 13, 9), "ok"),
        ((3, 14, 0), "warn"),
    ],
)
def test_doctor_python_check(version, status):
    got, hint = cli._python_version_check(version)
    assert got == status
    assert (hint is None) == (status == "ok")
    if status == "fail":
        assert "3.10" in hint
