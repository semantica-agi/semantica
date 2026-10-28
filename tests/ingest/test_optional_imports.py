import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

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
    # Needs the optional documents extra; skip rather than fail on a
    # core install.
    pytest.importorskip("lxml")
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
    LookerData,
)
print(
    CodeExtractor.__name__,
    CodeFile.__name__,
    CommitInfo.__name__,
    GitAnalyzer.__name__,
    XMLIngestionData.__name__,
    SalesforceData.__name__,
    LookerData.__name__,
)
""",
        ("git", "lxml", "simple_salesforce", "looker_sdk"),
    )

    assert result.returncode == 0, result.stderr
    assert (
        "CodeExtractor CodeFile CommitInfo GitAnalyzer XMLIngestionData "
        "SalesforceData LookerData" in result.stdout
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


def test_redshift_package_imports_without_sdk() -> None:
    """``import semantica.ingest`` must not eagerly pull in redshift_connector."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import FileIngestor, ingest_file
print(FileIngestor.__name__, callable(ingest_file))
""",
        ("redshift_connector",),
    )

    assert result.returncode == 0, result.stderr
    assert "FileIngestor True" in result.stdout


def test_redshift_data_importable_without_sdk() -> None:
    """``RedshiftData`` is a plain dataclass — no SDK needed to import it."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import RedshiftData
print(RedshiftData.__name__)
""",
        ("redshift_connector",),
    )

    assert result.returncode == 0, result.stderr
    assert "RedshiftData" in result.stdout


def test_redshift_ingestor_probe_fails_without_sdk() -> None:
    """``from semantica.ingest import RedshiftIngestor`` must raise ``ImportError``
    when ``redshift_connector`` is absent."""
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import RedshiftIngestor
    has_redshift = True
except ImportError:
    has_redshift = False

assert not has_redshift, (
    "Expected RedshiftIngestor import to fail without redshift-connector"
)
print("RedshiftIngestor probe passed")
""",
        ("redshift_connector",),
    )

    assert result.returncode == 0, result.stderr
    assert "RedshiftIngestor probe passed" in result.stdout


def test_redshift_connector_reports_missing_dep_with_install_hint() -> None:
    """Constructing ``RedshiftConnector`` without the SDK must raise ``ImportError``
    with a message that names the ``db-redshift`` extra."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest.redshift_ingestor import RedshiftConnector

try:
    RedshiftConnector()
except ImportError as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit(
        "expected RedshiftConnector() to fail without redshift-connector"
    )
""",
        ("redshift_connector",),
    )

    assert result.returncode == 0, result.stderr
    assert "ImportError" in result.stdout
    assert "db-redshift" in result.stdout


def test_looker_package_imports_without_sdk() -> None:
    """``import semantica.ingest`` must not eagerly pull in looker_sdk."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import FileIngestor, ingest_file
print(FileIngestor.__name__, callable(ingest_file))
""",
        ("looker_sdk",),
    )

    assert result.returncode == 0, result.stderr
    assert "FileIngestor True" in result.stdout


def test_looker_data_importable_without_sdk() -> None:
    """``LookerData`` is a plain dataclass — no SDK needed to import it."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import LookerData
print(LookerData.__name__)
""",
        ("looker_sdk",),
    )

    assert result.returncode == 0, result.stderr
    assert "LookerData" in result.stdout


def test_looker_ingestor_probe_fails_without_sdk() -> None:
    """``from semantica.ingest import LookerIngestor`` must raise
    ``ImportError`` when ``looker_sdk`` is absent."""
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import LookerIngestor
    has_looker = True
except ImportError:
    has_looker = False

assert not has_looker, (
    "Expected LookerIngestor import to fail without looker-sdk"
)
print("LookerIngestor probe passed")
""",
        ("looker_sdk",),
    )

    assert result.returncode == 0, result.stderr
    assert "LookerIngestor probe passed" in result.stdout


def test_looker_connector_reports_missing_dep_with_install_hint() -> None:
    """Constructing ``LookerConnector`` without the SDK must raise
    ``ImportError`` with a message that names the ``ingest-looker`` extra."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest.looker_ingestor import LookerConnector

try:
    LookerConnector()
except ImportError as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit(
        "expected LookerConnector() to fail without looker-sdk"
    )
""",
        ("looker_sdk",),
    )

    assert result.returncode == 0, result.stderr
    assert "ImportError" in result.stdout
    assert "ingest-looker" in result.stdout


def test_web_ingestion_reports_missing_beautifulsoup_at_import() -> None:
    """The probe import must fail fast, not defer to call time.

    `semantica.ingest.__getattr__` raises for a backend whose module imported
    with its dependency set to None, so `try: from semantica.ingest import X`
    stays a usable availability check.
    """
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import WebIngestor
except ImportError as exc:
    print("ImportError", exc)
else:
    raise SystemExit("expected WebIngestor to fail without beautifulsoup4")
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "ImportError" in result.stdout
    assert "Web ingestion" in result.stdout
    assert "beautifulsoup4" in result.stdout


def test_feed_ingestion_reports_missing_beautifulsoup_at_import() -> None:
    result = _run_python_with_blocked_modules(
        """
try:
    from semantica.ingest import FeedIngestor
except ImportError as exc:
    print("ImportError", exc)
else:
    raise SystemExit("expected FeedIngestor to fail without beautifulsoup4")
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "ImportError" in result.stdout
    assert "Feed ingestion" in result.stdout


def test_web_ingestor_module_imports_without_beautifulsoup() -> None:
    """Importing the module must not require the extra.

    Six test modules import `semantica.ingest.web_ingestor` directly; a bare
    `from bs4 import BeautifulSoup` there aborted collection for all of them.
    """
    result = _run_python_with_blocked_modules(
        """
import semantica.ingest.web_ingestor as web

print("imported", web.BeautifulSoup is None)
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "imported True" in result.stdout


def test_html_parsing_reports_missing_beautifulsoup_when_used() -> None:
    """The guarded branch raises with the install hint rather than crashing."""
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest.web_ingestor import _parse_html

try:
    _parse_html("<p>hi</p>")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected HTML parsing to fail without beautifulsoup4")
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "ProcessingError" in result.stdout
    assert "beautifulsoup4" in result.stdout


def test_feed_discovery_does_not_report_no_feeds_without_beautifulsoup() -> None:
    """discover_feeds must raise, not return [].

    Its `except Exception` returns an empty list, so a dependency checked
    inside the try would read as "this site publishes no feeds".
    """
    result = _run_python_with_blocked_modules(
        """
import logging
from semantica.ingest.feed_ingestor import FeedIngestor

ingestor = FeedIngestor.__new__(FeedIngestor)
ingestor.allow_private_ips = False
ingestor.logger = logging.getLogger("probe")

try:
    result = ingestor.discover_feeds("https://example.com")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit(f"expected discover_feeds to raise, got {result!r}")
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "ProcessingError" in result.stdout
    assert "beautifulsoup4" in result.stdout


def test_ingest_web_reports_configuration_error_without_beautifulsoup() -> None:
    """The public entry point keeps its ConfigurationError contract.

    `ingest_web` translated an import-time ModuleNotFoundError into
    ConfigurationError. Guarding the module import made that translation stop
    firing, so the call reached validation and fetching and then failed with a
    ProcessingError from the parser — a different type, later.
    """
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import ingest_web

try:
    ingest_web("https://example.com")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected ingest_web to fail without beautifulsoup4")
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "ConfigurationError" in result.stdout
    assert "Web ingestion" in result.stdout
    assert "beautifulsoup4" in result.stdout


def test_ingest_feed_reports_configuration_error_without_beautifulsoup() -> None:
    result = _run_python_with_blocked_modules(
        """
from semantica.ingest import ingest_feed

try:
    ingest_feed("https://example.com/feed.xml")
except Exception as exc:
    print(type(exc).__name__, exc)
else:
    raise SystemExit("expected ingest_feed to fail without beautifulsoup4")
""",
        ("bs4",),
    )

    assert result.returncode == 0, result.stderr
    assert "ConfigurationError" in result.stdout
    assert "Feed ingestion" in result.stdout


def test_email_link_extraction_does_not_silently_degrade(monkeypatch) -> None:
    """extract_links must not swallow the missing dependency.

    Its `except Exception: pass` would drop the error and fall back to a regex
    scan that misses relative URLs and href-only links, leaving the caller with
    quietly worse results and no install hint.

    Tested in-process rather than through _run_python_with_blocked_modules:
    importing `semantica.ingest.email_ingestor` directly raises
    `AttributeError: module 'email' has no attribute 'message'` on main as well,
    independently of beautifulsoup4, so the subprocess form cannot reach the
    class. Patching the guarded name reproduces the same branch.
    """
    pytest.importorskip("bs4")
    from semantica.ingest import email_ingestor
    from semantica.utils.exceptions import ProcessingError

    monkeypatch.setattr(email_ingestor, "BeautifulSoup", None)
    parser = email_ingestor.EmailParser.__new__(email_ingestor.EmailParser)

    with pytest.raises(ProcessingError, match="beautifulsoup4"):
        parser.extract_links("<html><body><a href='/a'>x</a></body></html>")
