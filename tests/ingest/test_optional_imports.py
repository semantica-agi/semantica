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
            err = ModuleNotFoundError(f"No module named '{{root_name}}'")
            err.name = root_name
            raise err
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
        ("git", "bs4", "pyarrow"),
    )

    assert result.returncode == 0, result.stderr
    assert "FileIngestor True" in result.stdout


def test_public_api_ingestion_imports_without_web_scraping_backends() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import PublicAPIIngestor, RESTIngestor, ingest_public_api
print(PublicAPIIngestor.__name__, RESTIngestor.__name__, callable(ingest_public_api))
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "PublicAPIIngestor RESTIngestor True" in result.stdout


def test_public_api_ingestion_falls_back_without_defusedxml() -> None:
    result = _run_python_with_blocked_modules(
        """
from unittest.mock import MagicMock, patch
from semantica.ingest import PublicAPIIngestor

response = MagicMock()
response.status_code = 200
response.headers = {"Content-Type": "application/xml"}
response.text = "<items><item id='1'>Ada</item></items>"
response.raise_for_status.return_value = None
response.json.side_effect = ValueError("not json")

with patch("requests.Session") as MockSession:
    mock_session = MockSession.return_value
    mock_session.headers = {}
    mock_session.request.return_value = response

    data = PublicAPIIngestor(rate_limit_delay=0).ingest_public_api(
        "https://example.com/data.xml",
        record_path="children",
    )

print(data.data[0]["tag"], data.metadata["response_format"])
""",
        ("defusedxml",),
    )

    assert result.returncode == 0, result.stderr
    assert "item xml" in result.stdout


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


def test_parquet_ingestion_reports_missing_pyarrow_when_used() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import ingest_parquet

try:
    ingest_parquet("events.parquet")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected parquet ingestion to fail without pyarrow")
""",
        ("pyarrow",),
    )

    assert result.returncode == 0, result.stderr
    assert "ConfigurationError" in result.stdout
    assert "Parquet ingestion" in result.stdout
    assert "pyarrow" in result.stdout


def test_repo_ingestor_probe_fails_without_gitpython() -> None:
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import RepoIngestor
    has_git = True
except ImportError:
    has_git = False

assert not has_git, "Expected RepoIngestor import to fail without GitPython"
print("RepoIngestor probe passed")
""",
        ("git",),
    )

    assert result.returncode == 0, result.stderr
    assert "RepoIngestor probe passed" in result.stdout


def test_xml_ingestor_probe_fails_without_lxml() -> None:
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import XMLIngestor
    has_lxml = True
except ImportError:
    has_lxml = False

assert not has_lxml, "Expected XMLIngestor import to fail without lxml"
print("XMLIngestor probe passed")
""",
        ("lxml",),
    )

    assert result.returncode == 0, result.stderr
    assert "XMLIngestor probe passed" in result.stdout


def test_xml_ingestion_reports_missing_lxml_when_used() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import ingest_xml

try:
    ingest_xml("catalog.xml")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected XML ingestion to fail without lxml")
""",
        ("lxml",),
    )

    assert result.returncode == 0, result.stderr
    assert "ConfigurationError" in result.stdout
    assert "XML ingestion" in result.stdout
    assert "lxml" in result.stdout


def test_sibling_imports_succeed_without_optional_backends() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import (
    CodeExtractor,
    CodeFile,
    CommitInfo,
    GitAnalyzer,
    XMLIngestionData,
    SalesforceData,
)
print(
    CodeExtractor.__name__,
    CodeFile.__name__,
    CommitInfo.__name__,
    GitAnalyzer.__name__,
    XMLIngestionData.__name__,
    SalesforceData.__name__,
)
""",
        ("git", "lxml", "simple_salesforce"),
    )

    assert result.returncode == 0, result.stderr
    assert (
        "CodeExtractor CodeFile CommitInfo GitAnalyzer XMLIngestionData SalesforceData"
        in result.stdout
    )


def test_salesforce_ingestor_probe_fails_without_simple_salesforce() -> None:
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import SalesforceIngestor
    has_salesforce = True
except ImportError:
    has_salesforce = False

assert not has_salesforce, (
    "Expected SalesforceIngestor import to fail without simple-salesforce"
)
print("SalesforceIngestor probe passed")
""",
        ("simple_salesforce",),
    )

    assert result.returncode == 0, result.stderr
    assert "SalesforceIngestor probe passed" in result.stdout


def test_salesforce_ingestion_reports_missing_dep_when_used() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import ingest_salesforce

try:
    ingest_salesforce()
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected Salesforce ingestion to fail without simple-salesforce")
""",
        ("simple_salesforce",),
    )

    assert result.returncode == 0, result.stderr
    assert "ConfigurationError" in result.stdout
    assert "Salesforce ingestion" in result.stdout
    assert "simple-salesforce" in result.stdout
