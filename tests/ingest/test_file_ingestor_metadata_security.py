"""
Security regression tests for Hotspot 7:
  FileObject.metadata must not retain credential-like kwargs.

These tests verify that sensitive option keys passed to ingest_file() are
stripped before being copied into FileObject.metadata, while non-sensitive
custom kwargs continue to reach metadata unchanged.

No real secret values are used.  Every credential-like value is an
obvious placeholder string that is never written to logs or serialized
output by the test runner itself.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Cloud-SDK stubs — must be in place before the ingest module is imported.
# ---------------------------------------------------------------------------
_CLOUD_STUBS = [
    "boto3",
    "google",
    "google.cloud",
    "google.cloud.storage",
    "azure",
    "azure.storage",
    "azure.storage.blob",
]
for _name in _CLOUD_STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)
sys.modules["google.cloud.storage"].Client = MagicMock()
sys.modules["azure.storage.blob"].BlobServiceClient = MagicMock()
sys.modules["boto3"].client = MagicMock()

from semantica.ingest.file_ingestor import (  # noqa: E402
    FileIngestor,
    _SENSITIVE_METADATA_KEYS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Placeholder values — obviously fake, never real credentials.
_PLACEHOLDER = "test-placeholder-value"

# Every key that must be blocked, paired with a case-variant to exercise
# case-insensitive matching.
_SENSITIVE_CASES = [
    # (kwarg_name_to_pass,  description)
    # --- LLM / generic API keys (cache.py baseline) ---
    ("api_key",           "lowercase canonical"),
    ("API_KEY",           "all-caps variant"),
    ("Api_Key",           "mixed-case variant"),
    ("apikey",            "no-underscore variant"),
    ("api_secret",        "api_secret"),
    ("token",             "token"),
    ("TOKEN",             "TOKEN uppercase"),
    ("access_token",      "access_token"),
    ("refresh_token",     "refresh_token"),
    ("session_token",     "session_token"),
    ("bearer_token",      "bearer_token"),
    ("password",          "password"),
    ("PASSWORD",          "PASSWORD uppercase"),
    ("secret",            "secret"),
    ("client_secret",     "client_secret"),
    ("private_key",       "private_key"),
    ("auth",              "auth"),
    ("Auth",              "Auth mixed-case"),
    ("authorization",     "authorization"),
    ("Authorization",     "Authorization mixed-case"),
    ("credential",        "credential"),
    ("credentials",       "credentials (plural)"),
    # --- Cloud storage credentials (Qodo finding + CloudStorageIngestor) ---
    ("secret_access_key", "S3/Redshift AWS secret key"),
    ("SECRET_ACCESS_KEY", "S3/Redshift uppercase variant"),
    ("access_key_id",     "S3/Redshift access key id"),
    ("ACCESS_KEY_ID",     "S3/Redshift uppercase variant"),
    ("connection_string", "Azure Blob connection string"),
    ("Connection_String", "Azure Blob mixed-case variant"),
    # --- Additional codebase credential patterns ---
    ("auth_token",        "generic auth token"),
    ("AUTH_TOKEN",        "auth_token uppercase variant"),
    ("x-api-key",         "hyphenated HTTP header name"),
    ("X-API-Key",         "hyphenated mixed-case variant"),
    ("security_token",    "Salesforce SOAP security token"),
    ("SECURITY_TOKEN",    "Salesforce uppercase variant"),
    ("session_id",        "Salesforce pre-existing session"),
    ("consumer_key",      "Salesforce JWT Bearer consumer key"),
    ("privatekey",        "Salesforce JWT Bearer PEM string"),
    ("privatekey_file",   "Salesforce JWT Bearer PEM file path"),
    ("deploy_secret",     "Looker deploy secret"),
    ("device_token",      "Looker device token"),
    ("git_password",      "Looker git password"),
    ("pdt_password",      "Looker PDT password"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def txt_file(tmp_path: Path) -> Path:
    """A minimal plaintext file used as an ingestion source."""
    f = tmp_path / "sample.txt"
    f.write_text("security regression fixture", encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# 1. Sensitive kwargs are absent from FileObject.metadata
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,description", _SENSITIVE_CASES)
def test_sensitive_key_absent_from_metadata(
    txt_file: Path, key: str, description: str
) -> None:
    """Each credential-like kwarg must be stripped before reaching metadata."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(txt_file, **{key: _PLACEHOLDER})

    assert key not in result.metadata, (
        f"Credential key {key!r} ({description}) must not appear in "
        "FileObject.metadata, but it was found there."
    )


def test_multiple_sensitive_keys_all_absent(txt_file: Path) -> None:
    """Passing several sensitive keys at once — all must be stripped."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(
        txt_file,
        api_key=_PLACEHOLDER,
        token=_PLACEHOLDER,
        password=_PLACEHOLDER,
        client_secret=_PLACEHOLDER,
        authorization=_PLACEHOLDER,
    )
    for key in ("api_key", "token", "password", "client_secret", "authorization"):
        assert key not in result.metadata, (
            f"{key!r} must not appear in FileObject.metadata"
        )


# ---------------------------------------------------------------------------
# 2. Nested credential value (credentials={...}) is not retained
# ---------------------------------------------------------------------------

def test_nested_credentials_dict_absent(txt_file: Path) -> None:
    """credentials= with a dict value must also be stripped."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(
        txt_file,
        credentials={"user": "svc-account", "pass": _PLACEHOLDER},
    )
    assert "credentials" not in result.metadata, (
        "credentials= (nested dict) must not appear in FileObject.metadata"
    )


# ---------------------------------------------------------------------------
# 3. Non-sensitive custom kwargs still appear in metadata
# ---------------------------------------------------------------------------

def test_non_sensitive_kwargs_reach_metadata(txt_file: Path) -> None:
    """Custom, non-credential kwargs must continue to pass through."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(
        txt_file,
        source_system="test-suite",
        batch_id="batch-001",
        priority=42,
    )
    assert result.metadata.get("source_system") == "test-suite"
    assert result.metadata.get("batch_id") == "batch-001"
    assert result.metadata.get("priority") == 42


def test_read_content_option_still_works(txt_file: Path) -> None:
    """read_content is a built-in option that must not be accidentally blocked."""
    ingestor = FileIngestor()
    result_with = ingestor.ingest_file(txt_file, read_content=True)
    result_without = ingestor.ingest_file(txt_file, read_content=False)

    assert result_with.content is not None
    assert result_without.content is None
    # read_content is captured as a named local in ingest_file, so it appears
    # in metadata via the explicit "read_content": read_content assignment.
    assert result_with.metadata["read_content"] is True
    assert result_without.metadata["read_content"] is False


def test_mixed_kwargs_only_sensitive_stripped(txt_file: Path) -> None:
    """Sensitive and non-sensitive kwargs mixed — only sensitive ones removed."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(
        txt_file,
        api_key=_PLACEHOLDER,       # sensitive — must be absent
        custom_tag="audit-run",      # safe — must be present
        token=_PLACEHOLDER,          # sensitive — must be absent
        pipeline_stage="ingest",     # safe — must be present
    )
    assert "api_key" not in result.metadata
    assert "token" not in result.metadata
    assert result.metadata.get("custom_tag") == "audit-run"
    assert result.metadata.get("pipeline_stage") == "ingest"


# ---------------------------------------------------------------------------
# 4. Top-level semantica.ingest_file() also does not leak credentials
#    (verifies the double-pass path in methods.py)
# ---------------------------------------------------------------------------

def test_top_level_ingest_file_no_credential_leak(txt_file: Path) -> None:
    """
    The public-API ingest_file() in semantica.ingest.methods passes **kwargs
    to both FileIngestor(**config) and ingestor.ingest_file(**kwargs).
    The filter must prevent leakage regardless of which layer the call enters.
    """
    from semantica.ingest.methods import ingest_file as top_level_ingest_file

    result = top_level_ingest_file(
        str(txt_file),
        method="file",
        api_key=_PLACEHOLDER,
        token=_PLACEHOLDER,
        password=_PLACEHOLDER,
        custom_label="top-level-test",
    )
    assert "api_key" not in result.metadata
    assert "token" not in result.metadata
    assert "password" not in result.metadata
    # Non-sensitive kwarg must survive the top-level path as well.
    assert result.metadata.get("custom_label") == "top-level-test"


# ---------------------------------------------------------------------------
# 5. Constant integrity — _SENSITIVE_METADATA_KEYS contains the required keys
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [
    # LLM / generic API keys (cache.py baseline)
    "api_key", "apikey", "api_secret",
    "token", "access_token", "refresh_token", "session_token", "bearer_token",
    "password", "secret", "client_secret", "private_key",
    "auth", "authorization", "credential", "credentials",
    # Cloud storage credentials
    "secret_access_key", "access_key_id", "connection_string",
    # Additional codebase credential patterns
    "auth_token", "x-api-key", "security_token", "session_id",
    "consumer_key", "privatekey", "privatekey_file",
    "deploy_secret", "device_token", "git_password", "pdt_password",
])
def test_sensitive_metadata_keys_constant_completeness(key: str) -> None:
    """_SENSITIVE_METADATA_KEYS must contain every audited key."""
    assert key in _SENSITIVE_METADATA_KEYS, (
        f"Audited sensitive key {key!r} is missing from _SENSITIVE_METADATA_KEYS"
    )


def test_sensitive_metadata_keys_is_frozenset() -> None:
    """The constant must be immutable so callers cannot accidentally mutate it."""
    assert isinstance(_SENSITIVE_METADATA_KEYS, frozenset)


# ---------------------------------------------------------------------------
# 6. Qodo HIGH-severity finding — specific regression for the four keys
#    that were absent from the initial implementation.
# ---------------------------------------------------------------------------

def test_qodo_finding_secret_access_key_absent(txt_file: Path) -> None:
    """secret_access_key (S3/Redshift AWS credential) must not reach metadata."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(txt_file, secret_access_key=_PLACEHOLDER)
    assert "secret_access_key" not in result.metadata


def test_qodo_finding_connection_string_absent(txt_file: Path) -> None:
    """connection_string (Azure Blob) must not reach metadata."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(txt_file, connection_string=_PLACEHOLDER)
    assert "connection_string" not in result.metadata


def test_qodo_finding_auth_token_absent(txt_file: Path) -> None:
    """auth_token must not reach metadata."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(txt_file, auth_token=_PLACEHOLDER)
    assert "auth_token" not in result.metadata


def test_qodo_finding_x_api_key_absent(txt_file: Path) -> None:
    """x-api-key (hyphenated HTTP header name) must not reach metadata."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(txt_file, **{"x-api-key": _PLACEHOLDER})
    assert "x-api-key" not in result.metadata


def test_qodo_finding_all_four_plus_existing_absent(txt_file: Path) -> None:
    """All four Qodo-flagged keys together with pre-existing keys — all absent."""
    ingestor = FileIngestor()
    result = ingestor.ingest_file(
        txt_file,
        # Qodo-flagged keys
        secret_access_key=_PLACEHOLDER,
        connection_string=_PLACEHOLDER,
        auth_token=_PLACEHOLDER,
        **{"x-api-key": _PLACEHOLDER},
        # Pre-existing keys — must also still be absent
        api_key=_PLACEHOLDER,
        token=_PLACEHOLDER,
        password=_PLACEHOLDER,
        # Safe keys — must still be present
        custom_tag="qodo-regression",
    )
    for key in (
        "secret_access_key", "connection_string", "auth_token", "x-api-key",
        "api_key", "token", "password",
    ):
        assert key not in result.metadata, (
            f"{key!r} must not appear in FileObject.metadata"
        )
    assert result.metadata.get("custom_tag") == "qodo-regression"
