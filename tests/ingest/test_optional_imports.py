import os
import subprocess
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_python_with_blocked_modules(
    code: str,
    blocked_modules: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    blocker = f"""
import importlib.abc
import sys

BLOCKED_MODULES = {blocked_modules!r}


class OptionalDependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root_name = fullname.split(".", 1)[0]
        if root_name in BLOCKED_MODULES:
            raise ModuleNotFoundError(f"No module named '{{root_name}}'")
        return None


sys.meta_path.insert(0, OptionalDependencyBlocker())
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(blocker + "\n" + code)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_file_ingestion_imports_without_optional_backends() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import FileIngestor, ingest_file
print(FileIngestor.__name__, callable(ingest_file))
""",
        ("git", "bs4"),
    )

    assert result.returncode == 0, result.stderr
    assert "FileIngestor True" in result.stdout


def test_repository_ingestion_reports_missing_gitpython_when_used() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import ingest_repository

try:
    ingest_repository("https://example.com/repo.git")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected repository ingestion to fail without GitPython")
""",
        ("git",),
    )

    assert result.returncode == 0, result.stderr
    assert "ConfigurationError" in result.stdout
    assert "Repository ingestion" in result.stdout
    assert "GitPython" in result.stdout
