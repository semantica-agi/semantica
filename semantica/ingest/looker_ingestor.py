"""
Looker Ingestion Module

This module provides Looker metadata ingestion for the Semantica
framework, enabling extraction of Looks, Dashboards, LookML models (with
their Explores), Folders, and Projects via the official ``looker-sdk``
4.0 API.

Design notes
------------
Optional dependency
    ``looker_sdk`` is imported inside a guard.  The module always imports
    cleanly; ``LookerData`` is usable without the SDK, and
    :class:`LookerConnector` raises a clear ``ImportError`` naming the
    ``ingest-looker`` extra at instantiation time.

Validate the endpoint once, then constrain the transport
    ``looker_sdk.init40`` builds ``RequestsTransport`` internally, so the
    repository's per-request ``request_with_ssrf_guard`` hook is not
    reachable.  The connector instead resolves the effective ``base_url``
    from a constructed ``ApiSettings`` object, validates it, and passes
    that *same* object to ``init40``.  The binding mechanism is the
    ``read_config`` override on that object, which the SDK consults for
    every login.  Five compensating controls are applied:

    1. ``https`` is required unless ``allow_private_ips`` is enabled;
    2. TLS verification is forced on, so ``LOOKERSDK_VERIFY_SSL`` or the
       ini file cannot downgrade the validated connection;
    3. the SDK session's redirect cap is set to zero;
    4. proxy environment trust is disabled;
    5. connections are pinned to the addresses resolved during validation,
       closing the DNS-rebinding window between validation and dial.

    A post-construction check also compares the client's resolved
    ``base_url`` with the validated one.  The current SDK returns the same
    ``ApiSettings`` object, so that check guards against future drift
    rather than being a security control.

Credentials are injected through the ``ApiSettings`` object rather than
by mutating ``os.environ``, so no secret becomes process-global.

Allowlist redaction
    Every SDK record is projected through an explicit allowlist of
    retained fields.  ``Project.git_password``, ``Project.deploy_secret``,
    ``Project.git_remote_url`` userinfo, ``Dashboard.password``,
    ``Dashboard.pdt_password``, and ``LookmlModel.device_token`` can
    therefore never reach :class:`LookerData`, an exported document, or a
    log record.

Main Classes:
    - LookerConnector: Manages the ``looker_sdk`` client lifecycle
    - LookerData: Dataclass representing ingested Looker metadata
    - LookerIngestor: Orchestrates metadata reads and document export

Optional Dependency:
    Install via the ``ingest-looker`` extra::

        pip install "semantica[ingest-looker]"

Example Usage::

    >>> import os
    >>> from semantica.ingest.looker_ingestor import LookerIngestor
    >>> with LookerIngestor(
    ...     base_url=os.getenv("LOOKERSDK_BASE_URL"),
    ...     client_id=os.getenv("LOOKERSDK_CLIENT_ID"),
    ...     client_secret=os.getenv("LOOKERSDK_CLIENT_SECRET"),
    ... ) as ingestor:
    ...     looks = ingestor.ingest_looks()
    ...     documents = ingestor.export_as_documents(looks)

Author: Semantica Contributors
License: MIT
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence
from urllib.parse import urlparse

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .ssrf import (
    _make_pinned_adapter,
    _resolve_pinned_ips,
    parse_bool,
    validate_url_for_request,
)

# ---------------------------------------------------------------------------
# Optional-dependency guard — mirrors the pattern in salesforce_ingestor.
# The module always imports cleanly; the sentinel fires at instantiation
# time inside LookerConnector.__init__ so that:
#   - ``from semantica.ingest.looker_ingestor import LookerData`` works
#     without the SDK, and
#   - ``LookerConnector(...)`` raises a clear ImportError when it is absent.
# ---------------------------------------------------------------------------
try:
    import looker_sdk
    from looker_sdk.rtl import api_settings

    LOOKER_AVAILABLE = True
except (ImportError, OSError):
    looker_sdk = None  # type: ignore[assignment]
    api_settings = None  # type: ignore[assignment]
    LOOKER_AVAILABLE = False

__all__ = [
    "LookerData",
    "LookerConnector",
    "LookerIngestor",
]

_logger = get_logger("looker_ingestor")

# Exact install hint required by R8.
_MISSING_SDK_MESSAGE = (
    "looker-sdk is required for the Looker connector. "
    'Install it with: pip install "semantica[ingest-looker]"'
)

# Environment prefix read by the SDK's own ApiSettings.
_ENV_PREFIX = "LOOKERSDK"


def _normalize_url(value: str) -> str:
    """Return *value* with a trailing slash removed for comparison.

    Args:
        value: URL to normalize.

    Returns:
        The URL without a trailing slash.
    """
    return (value or "").strip().rstrip("/")


def _scrub_url_userinfo(value: str) -> str:
    """Strip ``user:password@`` userinfo from *value*.

    ``Project.git_remote_url`` may embed credentials.  Keep the host and
    path so the metadata stays useful, but never the userinfo.

    Args:
        value: Remote URL that may contain userinfo.

    Returns:
        The URL with any userinfo removed.
    """
    if "@" not in value:
        return value
    head, _, tail = value.rpartition("@")
    # Strip only when the '@' terminates an authority userinfo section.  A
    # path separator before it means the '@' is ordinary path content, and
    # urlparse cannot be used here because it leaves userinfo outside
    # ``netloc`` for scheme-less and scp-style remotes.
    authority_start = head.find("://")
    authority_start = 0 if authority_start == -1 else authority_start + 3
    if "/" in head[authority_start:]:
        return value
    return value[:authority_start] + tail


# ---------------------------------------------------------------------------
# LookerData
# ---------------------------------------------------------------------------


@dataclass
class LookerData:
    """Metadata records returned from a Looker API collection.

    Attributes:
        data: List of normalized metadata dictionaries.
        row_count: Number of records in ``data``.
        columns: Ordered list of field names present in ``data``.
        content_type: One of ``look``, ``dashboard``, ``lookml_model``,
            ``folder``, or ``project``.
        base_url: Validated Looker endpoint the data was read from.
        metadata: Arbitrary extra metadata (e.g. the SDK endpoint used).
        ingested_at: Timestamp recorded when this object was created.
    """

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    content_type: str
    base_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Field allowlists — explicit "retained fields" contract (R11)
# ---------------------------------------------------------------------------
# Only keys listed here survive normalization.  Secret-adjacent SDK fields
# (git_password, deploy_secret, password, pdt_password, device_token) are
# deliberately absent, so they cannot reach LookerData, documents, or logs.

# Values that reach the normalizer as plain mappings never pass through a
# record allowlist, so secret-named keys are dropped explicitly as well.
# Named arguments of LookerConnector: a config dict carrying any of these
# must not be re-forwarded as a keyword or the call raises TypeError.
_CONNECTOR_ARGUMENT_NAMES = frozenset(
    {
        "allow_private_ips",
        "base_url",
        "client_id",
        "client_secret",
        "config_file",
        "section",
    }
)

_SECRET_FIELD_NAMES = frozenset(
    {
        "deploy_secret",
        "device_token",
        "git_password",
        "password",
        "pdt_password",
    }
)

_EXPLORE_FIELD_FIELDS = frozenset(
    {
        "align",
        "available_custom_timeframes",
        "can_filter",
        "can_time_filter",
        "category",
        "convert_tz",
        "datatype",
        "default_filter_value",
        "description",
        "dimension_group",
        "drill_fields",
        "dynamic",
        "enumerations",
        "error",
        "field_group_label",
        "field_group_variant",
        "fill_style",
        "filters",
        "fiscal_month_offset",
        "has_allowed_values",
        "has_drills_metadata",
        "hidden",
        "is_filter",
        "is_fiscal",
        "is_numeric",
        "is_timeframe",
        "label",
        "label_from_parameter",
        "label_short",
        "links",
        "lookml_link",
        "map_layer",
        "measure",
        "name",
        "original_view",
        "parameter",
        "period_over_period_params",
        "permanent",
        "primary_key",
        "project_name",
        "requires_refresh_on_sort",
        "scope",
        "sortable",
        "source_file",
        "source_file_path",
        "sql",
        "sql_case",
        "strict_value_format",
        "suggest_dimension",
        "suggest_explore",
        "suggestable",
        "suggestions",
        "synonyms",
        "tags",
        "time_interval",
        "timeframe_labels",
        "times_used",
        "type",
        "user_attribute_filter_types",
        "value_format",
        "value_format_name",
        "view",
        "view_label",
        "view_name",
        "week_start_day",
    }
)

_EXPLORE_JOIN_FIELDS = frozenset(
    {
        "dependent_fields",
        "fields",
        "foreign_key",
        "from",
        "from_",
        "name",
        "outer_only",
        "relationship",
        "required_joins",
        "sql_foreign_key",
        "sql_on",
        "sql_table_name",
        "type",
        "view_label",
    }
)

_NESTED_EXTRA_FIELDS = frozenset(
    {
        "certification_status",
        "joins",
        "condition",
        "dependency_status",
        "details",
        "error_pos",
        "field",
        "field_error",
        "git_branch",
        "git_head",
        "git_status",
        "label",
        "lookml_type",
        "measure_types",
        "message",
        "project_id",
        "user_attribute",
        "value",
        "workspace_id",
    }
)

_RETAINED_FIELDS: Dict[str, frozenset] = {
    "look": frozenset(
        {
            "can",
            "certification_metadata",
            "content_favorite_id",
            "content_metadata_id",
            "created_at",
            "deleted",
            "deleted_at",
            "deleter_id",
            "description",
            "embed_url",
            "excel_file_url",
            "favorite_count",
            "folder",
            "folder_id",
            "google_spreadsheet_formula",
            "id",
            "image_embed_url",
            "is_owner_disabled",
            "is_run_on_load",
            "last_accessed_at",
            "last_updater_id",
            "last_viewed_at",
            "model",
            "public",
            "public_slug",
            "public_url",
            "query_id",
            "short_url",
            "title",
            "updated_at",
            "usage_count",
            "user_id",
            "user_name",
            "view_count",
        }
    ),
    "dashboard": frozenset(
        {
            "alert_sync_with_dashboard_filter_enabled",
            "appearance",
            "background_color",
            "can",
            "certification_metadata",
            "chat_enabled",
            "content_favorite_id",
            "content_metadata_id",
            "created_at",
            "crossfilter_enabled",
            "deleted",
            "deleted_at",
            "deleter_id",
            "description",
            "download_settings",
            "edit_uri",
            "enable_viz_full_screen",
            "favorite_count",
            "filters_bar_collapsed",
            "filters_location_top",
            "folder",
            "folder_id",
            "hidden",
            "id",
            "is_owner_disabled",
            "last_accessed_at",
            "last_updater_id",
            "last_updater_name",
            "last_viewed_at",
            "load_configuration",
            "lookml_link_id",
            "model",
            "preferred_viewer",
            "preserve_desktop_layout",
            "query_timezone",
            "readonly",
            "refresh_interval",
            "refresh_interval_to_i",
            "show_filters_bar",
            "show_title",
            "slug",
            "text_tile_text_color",
            "tile_background_color",
            "tile_text_color",
            "title",
            "title_color",
            "updated_at",
            "url",
            "usage_count",
            "user_id",
            "user_name",
            "view_count",
        }
    ),
    # ``device_token`` is intentionally absent (R11).
    "lookml_model": frozenset(
        {
            "allowed_db_connection_names",
            "can",
            "explores",
            "has_content",
            "label",
            "name",
            "project_name",
            "unlimited_db_connections",
        }
    ),
    "folder": frozenset(
        {
            "can",
            "child_count",
            "content_metadata_id",
            "created_at",
            "creator_id",
            "dashboards",
            "external_id",
            "id",
            "is_embed",
            "is_embed_shared_root",
            "is_embed_users_root",
            "is_personal",
            "is_personal_descendant",
            "is_shared_root",
            "is_users_root",
            "looks",
            "name",
            "parent_id",
        }
    ),
    # ``git_password``, ``deploy_secret``, and the password user-attribute
    # fields are intentionally absent (R11).  ``git_remote_url`` is kept
    # but has its userinfo scrubbed during normalization.
    "project": frozenset(
        {
            "allow_warnings",
            "can",
            "dependency_status",
            "git_application_server_http_port",
            "git_application_server_http_scheme",
            "git_production_branch_name",
            "git_remote_url",
            "git_release_mgmt_enabled",
            "git_service_name",
            "git_username",
            "git_username_user_attribute",
            "has_production_counterpart",
            "id",
            "is_example",
            "is_git_dev_locked",
            "name",
            "pull_request_mode",
            "unset_deploy_secret",
            "use_git_cookie_auth",
            "uses_git",
            "validation_required",
        }
    ),
}

# Nested SDK models (Explores, fields, joins, folders, and so on) are
# filtered against the union of every top-level allowlist plus the
# Explore-specific field sets.
_NESTED_RETAINED_FIELDS = frozenset(
    set().union(
        *(_RETAINED_FIELDS.values()),
        _EXPLORE_FIELD_FIELDS,
        _EXPLORE_JOIN_FIELDS,
        _NESTED_EXTRA_FIELDS,
    )
)

# Human-readable field selection used to compose a document's ``text``.
_TEXT_FIELDS: Dict[str, Sequence[str]] = {
    "look": ("title", "description", "model", "user_name"),
    "dashboard": ("title", "description", "model", "user_name"),
    "lookml_model": ("label", "name", "project_name"),
    "folder": ("name",),
    "project": ("name", "git_username"),
}

# Flattened identifier exposed in document metadata, per content type.
_ID_METADATA_KEYS: Dict[str, str] = {
    "look": "look_id",
    "dashboard": "dashboard_id",
    "folder": "folder_id",
    "project": "project_id",
}


# ---------------------------------------------------------------------------
# LookerConnector
# ---------------------------------------------------------------------------


class LookerConnector:
    """Manages the ``looker_sdk`` client lifecycle.

    Responsibilities:

    * Resolves credentials from constructor arguments, falling back to
      the ``LOOKERSDK_BASE_URL``, ``LOOKERSDK_CLIENT_ID``, and
      ``LOOKERSDK_CLIENT_SECRET`` environment variables (and, via the
      SDK's own ``ApiSettings``, a ``looker.ini`` file).
    * Resolves the effective endpoint once, validates the scheme and the
      SSRF contract, and binds the client to that exact value (KTD2/KTD4).
    * Disables redirect following and proxy environment trust on the SDK
      session, and never mutates ``os.environ``.
    * Exposes :meth:`connect`, :meth:`disconnect`, and
      :meth:`test_connection`, plus the context-manager protocol.

    Args:
        base_url: Looker instance URL. Defaults to
            ``LOOKERSDK_BASE_URL``.
        client_id: Looker API client id. Defaults to
            ``LOOKERSDK_CLIENT_ID``.
        client_secret: Looker API client secret. Defaults to
            ``LOOKERSDK_CLIENT_SECRET``.
        config_file: Path to a ``looker.ini`` file. Defaults to
            ``"looker.ini"``.
        section: Section name inside *config_file*.
        allow_private_ips: Opt into private/loopback/link-local endpoints
            and non-``https`` schemes. Defaults to ``False``.
        config: Optional extra configuration dict. ``allow_private_ips``
            is read from here when present, mirroring the SAP connector.
        **kwargs: Additional keyword arguments merged into ``config``.

    Raises:
        ImportError: When ``looker-sdk`` is not installed.
        ValidationError: When credentials are missing, the endpoint fails
            validation, or the environment conflicts with the explicit
            ``base_url``.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        config_file: Optional[str] = None,
        section: Optional[str] = None,
        allow_private_ips: bool = False,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if not LOOKER_AVAILABLE:
            raise ImportError(_MISSING_SDK_MESSAGE)

        self.logger = _logger

        self.config: Dict[str, Any] = dict(config or {})
        self.config.update(kwargs)
        self.allow_private_ips = parse_bool(
            self.config.pop("allow_private_ips", allow_private_ips), default=False
        )

        # Credentials: explicit arguments win over environment variables.
        self._explicit_base_url: Optional[str] = base_url
        self.client_id: Optional[str] = client_id or os.getenv("LOOKERSDK_CLIENT_ID")
        self._client_secret: Optional[str] = client_secret or os.getenv(
            "LOOKERSDK_CLIENT_SECRET"
        )
        self.config_file: str = config_file or "looker.ini"
        self.section: Optional[str] = section

        self._client: Optional[Any] = None
        # Endpoint validated at construction time, reused so the SSRF host
        # check (which resolves DNS) runs at most once per connector.
        self._validated_base_url: Optional[str] = None

        # Fail fast on an explicit endpoint before any SDK object exists:
        # a conflicting environment value must never silently win (AE2),
        # and a bad scheme or blocked host must never reach the SDK.
        self._validate_explicit_endpoint()

        settings = self._build_settings()
        raw_config = self._raw_read_config(settings)

        # KTD4/AE2 — the SDK's ApiSettings lets the environment (and the
        # ini file) override the constructor.  Refuse to proceed rather
        # than silently connecting somewhere the caller did not validate.
        configured_base_url = str(raw_config.get("base_url") or "")
        if self._explicit_base_url and configured_base_url:
            if _normalize_url(configured_base_url) != _normalize_url(
                self._explicit_base_url
            ):
                raise ValidationError(
                    "Looker base_url from the environment or config file "
                    f"({configured_base_url!r}) conflicts with the explicit "
                    f"'base_url' ({self._explicit_base_url!r}); refusing to "
                    "connect rather than binding the client to an "
                    "unvalidated host."
                )

        effective_base_url = (
            self._explicit_base_url
            or configured_base_url
            or str(getattr(settings, "base_url", "") or "")
        )
        effective_client_id = self.client_id or str(raw_config.get("client_id") or "")
        effective_client_secret = self._client_secret or str(
            raw_config.get("client_secret") or ""
        )

        self.base_url: str = effective_base_url
        self.client_id = effective_client_id
        self._client_secret = effective_client_secret

        # ``looker_sdk`` re-reads settings for every login, so the merged
        # values must live on ``read_config`` — assigning attributes alone
        # would not reach the OAuth2 exchange.
        settings.base_url = effective_base_url
        # `verify_ssl` comes from LOOKERSDK_VERIFY_SSL / the ini file and would
        # otherwise let an environment detail silently turn the enforced https
        # requirement into an unverified connection carrying the client secret.
        if not self.allow_private_ips:
            settings.verify_ssl = True
        base_read_config = settings.read_config

        def _effective_read_config() -> Dict[str, Any]:
            data: Dict[str, Any] = dict(base_read_config())
            if effective_base_url:
                data["base_url"] = effective_base_url
            if effective_client_id:
                data["client_id"] = effective_client_id
            if effective_client_secret:
                data["client_secret"] = effective_client_secret
            if not self.allow_private_ips:
                data["verify_ssl"] = True
            return data

        settings.read_config = _effective_read_config  # type: ignore[method-assign]
        self._settings = settings

        self._validate_auth()
        # An explicit endpoint was already validated above and always wins
        # the resolution order, so it is never validated twice.
        if self._validated_base_url is None:
            self._validated_base_url = self._validate_endpoint(effective_base_url)

        self.logger.debug(
            "Looker connector initialised (base_url=%s, allow_private_ips=%s)",
            self._validated_base_url,
            self.allow_private_ips,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_explicit_endpoint(self) -> None:
        """Validate an explicitly supplied ``base_url`` before SDK use.

        Runs before any ``ApiSettings``/``init40`` work so a conflicting
        ``LOOKERSDK_BASE_URL`` (AE2) or an unsafe explicit endpoint fails
        immediately and without touching the SDK.

        Raises:
            ValidationError: When the environment conflicts with the
                explicit value, or the explicit value fails scheme/SSRF
                validation.
        """
        if not self._explicit_base_url:
            return

        env_base_url = os.getenv("LOOKERSDK_BASE_URL")
        if env_base_url and _normalize_url(env_base_url) != _normalize_url(
            self._explicit_base_url
        ):
            raise ValidationError(
                "LOOKERSDK_BASE_URL "
                f"({env_base_url!r}) conflicts with the explicit 'base_url' "
                f"({self._explicit_base_url!r}); refusing to connect rather "
                "than binding the client to an unvalidated host."
            )

        self._validated_base_url = self._validate_endpoint(self._explicit_base_url)

    def _build_settings(self) -> Any:
        """Construct the SDK ``ApiSettings`` used to bind the client.

        Returns:
            A configured ``looker_sdk.rtl.api_settings.ApiSettings``.

        Raises:
            ValidationError: If an explicitly named config file is missing.
            ProcessingError: If settings cannot be constructed.
        """
        try:
            return api_settings.ApiSettings(
                filename=self.config_file,
                section=self.section,
                env_prefix=_ENV_PREFIX,
            )
        except FileNotFoundError as exc:
            raise ValidationError(
                f"Looker config file not found: {self.config_file!r}."
            ) from exc
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - translated with type only
            self.logger.error(
                "Failed to load Looker SDK settings: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to load Looker SDK settings: {type(exc).__name__}"
            ) from None

    @staticmethod
    def _raw_read_config(settings: Any) -> Dict[str, Any]:
        """Read the SDK's resolved config without applying our overrides."""
        try:
            data = settings.read_config()
        except Exception as exc:  # noqa: BLE001 - config read is best-effort here
            # Without the config we cannot detect an endpoint conflict, so
            # surface the cause instead of failing later as "missing
            # credentials".
            _logger.debug("Could not read Looker SDK config: %s", type(exc).__name__)
            return {}
        if isinstance(data, Mapping):
            return dict(data)
        return {}

    def _validate_auth(self) -> None:
        """Raise ``ValidationError`` when required credentials are absent.

        Validates before any network call so failures are immediate and
        never leak partial state.

        Raises:
            ValidationError: When ``base_url``, ``client_id``, or
                ``client_secret`` is missing.
        """
        if not self.base_url:
            raise ValidationError(
                "Looker base_url is required. Provide via 'base_url' or the "
                "LOOKERSDK_BASE_URL environment variable."
            )
        if not self.client_id:
            raise ValidationError(
                "Looker client_id is required. Provide via 'client_id' or the "
                "LOOKERSDK_CLIENT_ID environment variable."
            )
        if not self._client_secret:
            raise ValidationError(
                "Looker client_secret is required. Provide via "
                "'client_secret' or the LOOKERSDK_CLIENT_SECRET environment "
                "variable."
            )

    def _validate_endpoint(self, base_url: str) -> str:
        """Validate scheme and SSRF constraints for *base_url*.

        Args:
            base_url: Effective endpoint resolved from kwargs, environment,
                or the ini file.

        Returns:
            The unchanged, validated endpoint.

        Raises:
            ValidationError: When the scheme is not ``https`` and
                ``allow_private_ips`` is off, or when the host is blocked.
        """
        parsed = urlparse(base_url)
        scheme = (parsed.scheme or "").lower()
        if scheme != "https" and not self.allow_private_ips:
            raise ValidationError(
                "Looker base_url must use https unless allow_private_ips is "
                f"enabled. Got scheme {parsed.scheme!r}."
            )
        if parsed.username or parsed.password:
            raise ValidationError(
                "Looker base_url must not embed userinfo credentials; pass "
                "them as client_id/client_secret instead."
            )
        validate_url_for_request(base_url, allow_private_ips=self.allow_private_ips)
        return base_url

    @staticmethod
    def _client_base_url(client: Any) -> Optional[str]:
        """Return the ``base_url`` the constructed client is bound to."""
        settings = getattr(getattr(client, "auth", None), "settings", None)
        value = getattr(settings, "base_url", None)
        return value if isinstance(value, str) else None

    def _apply_transport_controls(self, client: Any) -> None:
        """Disable redirect following and proxy trust on the SDK session.

        Args:
            client: A constructed ``Looker40SDK`` instance.

        Raises:
            ProcessingError: If the client exposes no transport session,
                because the compensating controls could not be applied.
        """
        session = self._transport_session(client)
        if session is None:
            raise ProcessingError(
                "Looker SDK client exposes no transport session; refusing to "
                "use a client without redirect and proxy controls."
            )
        session.max_redirects = 0
        session.trust_env = False
        if session.verify is False:
            raise ProcessingError(
                "Looker SDK session has TLS verification disabled; refusing to "
                "send credentials over an unverified connection."
            )
        session.verify = True
        self._pin_session(session)

    def _pin_session(self, session: Any) -> None:
        """Pin connections to the addresses resolved during validation.

        The endpoint is validated once at construction, but the SDK resolves
        the hostname again at request time, which reopens a DNS-rebinding
        window.  Mounting a pinning adapter connects only to the addresses
        validated here, while the hostname still supplies TLS identity.

        Raises:
            ValidationError: If the endpoint no longer resolves to a
                permitted address.
        """
        pinned_ips = _resolve_pinned_ips(
            self._validated_base_url, allow_private_ips=self.allow_private_ips
        )
        if not pinned_ips:
            return
        parsed = urlparse(self._validated_base_url)
        adapter = _make_pinned_adapter(pinned_ips, parsed.hostname or "")
        adapter._semantica_pinned = True
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        port = parsed.port
        default_port = 443 if parsed.scheme == "https" else 80
        session.headers["Host"] = (
            parsed.hostname or ""
            if port in (None, default_port)
            else f"{parsed.hostname}:{port}"
        )

    @staticmethod
    def _transport_session(client: Any) -> Optional[Any]:
        """Return the SDK transport's HTTP session, if it exposes one."""
        return getattr(getattr(client, "transport", None), "session", None)

    def _close_client(self, client: Any) -> None:
        """Best-effort close of a client that must not be used."""
        session = self._transport_session(client)
        if session is None:
            return
        try:
            session.close()
        except Exception:  # noqa: BLE001 - cleanup must never raise
            pass

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def client(self) -> Optional[Any]:
        """The active ``Looker40SDK`` client, or ``None``."""
        return self._client

    @property
    def connected(self) -> bool:
        """Whether a client is currently connected."""
        return self._client is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> Any:
        """Create and return a ``looker_sdk`` client.

        If a client is already connected, returns it immediately without
        constructing a new one.

        Returns:
            The ``Looker40SDK`` client bound to the validated endpoint.

        Raises:
            ValidationError: If the constructed client is bound to a
                different endpoint than the validated one.
            ProcessingError: If client construction fails for any reason.
                Credentials are never included in the raised message.
        """
        if self._client is not None:
            return self._client

        try:
            client = looker_sdk.init40(config_settings=self._settings)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 - translated with type only
            self.logger.error(
                "Failed to initialise Looker client: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to initialise Looker client: {type(exc).__name__}"
            ) from None

        resolved = self._client_base_url(client)
        if _normalize_url(resolved or "") != _normalize_url(self._validated_base_url):
            self._close_client(client)
            self.logger.error(
                "Looker client bound to an unexpected base_url; failing closed."
            )
            raise ValidationError(
                "Looker client is bound to a different base_url than the "
                "validated endpoint; refusing to use it."
            )

        try:
            self._apply_transport_controls(client)
        except Exception:
            self._close_client(client)
            raise

        self._client = client
        self.logger.info("Connected to Looker: base_url=%s", self._validated_base_url)
        return self._client

    def disconnect(self) -> None:
        """Close the client session and release the reference.

        Safe to call when already disconnected — subsequent calls are
        no-ops, and cleanup failures are swallowed.
        """
        client, self._client = self._client, None
        if client is None:
            return
        self._close_client(client)
        self.logger.debug("Disconnected from Looker.")

    def test_connection(self) -> bool:
        """Verify connectivity with a cheap authenticated read.

        Uses ``client.me()`` (a single ``GET /user``) to confirm the
        session is live.  The client is disconnected only when this call
        opened it.

        Returns:
            ``True`` if the probe succeeds, ``False`` for any failure.
        """
        opened_here = self._client is None
        try:
            client = self.connect()
            client.me()
            return True
        except Exception as exc:  # noqa: BLE001 - bool result contract
            self.logger.debug("Looker connection test failed: %s", type(exc).__name__)
            return False
        finally:
            if opened_here:
                self.disconnect()

    def __enter__(self) -> "LookerConnector":
        """Open the Looker client on context entry."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Close the Looker client on context exit."""
        self.close()

    def close(self) -> None:
        """Disconnect from Looker and release the client."""
        self.disconnect()


# ---------------------------------------------------------------------------
# LookerIngestor
# ---------------------------------------------------------------------------


class LookerIngestor:
    """Looker metadata ingestor for the Semantica framework.

    Wraps :class:`LookerConnector` and exposes the five metadata reads,
    the deep normalizer with allowlist redaction, and the document
    projection consumed by :class:`~semantica.kg.graph_builder.GraphBuilder`.

    Args:
        base_url: Looker instance URL; see :class:`LookerConnector`.
        client_id: Looker API client id.
        client_secret: Looker API client secret.
        config_file: Path to a ``looker.ini`` file.
        section: Section inside *config_file*.
        allow_private_ips: Opt into private endpoints and non-``https``
            schemes. Defaults to ``False``.
        connector: An existing :class:`LookerConnector` to reuse.
        config: Optional extra configuration dict forwarded to the
            connector.
        **kwargs: Additional keyword arguments merged into ``config``.

    Raises:
        ImportError: When ``looker-sdk`` is not installed and no connector
            is supplied.
        ValidationError: When required credentials are incomplete.

    Example::

        from semantica.ingest.looker_ingestor import LookerIngestor

        with LookerIngestor(
            base_url="https://looker.example.com",
            client_id="...",
            client_secret="...",
        ) as ingestor:
            data = ingestor.ingest_looks()
            documents = ingestor.export_as_documents(data)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        config_file: Optional[str] = None,
        section: Optional[str] = None,
        allow_private_ips: bool = False,
        connector: Optional[LookerConnector] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.logger = _logger

        self.config: Dict[str, Any] = dict(config or {})
        self.config.update(kwargs)

        self.connector: LookerConnector = connector or LookerConnector(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            config_file=config_file,
            section=section,
            allow_private_ips=allow_private_ips,
            **{
                key: value
                for key, value in self.config.items()
                if key not in _CONNECTOR_ARGUMENT_NAMES
            },
        )

        # Progress tracker — consistent with all other ingestors.
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Looker ingestor initialised.")

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "LookerIngestor":
        """Open the Looker connection on context entry."""
        self.connector.connect()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Close the Looker connection on context exit."""
        self.close()

    def close(self) -> None:
        """Disconnect from Looker and release the client."""
        self.connector.disconnect()

    # ------------------------------------------------------------------
    # Metadata reads
    # ------------------------------------------------------------------

    def ingest_looks(self, **options: Any) -> LookerData:
        """Fetch Look metadata via ``all_looks()``.

        Args:
            **options: Optional SDK ``transport_options`` / ``fields``.

        Returns:
            :class:`LookerData` with ``content_type == "look"``.

        Raises:
            ProcessingError: If the SDK read fails.
        """
        return self._ingest("all_looks", "look", **options)

    def ingest_dashboards(self, **options: Any) -> LookerData:
        """Fetch Dashboard metadata via ``all_dashboards()``.

        The SDK returns ``DashboardBase`` objects without tiles, which
        enforces the connector's metadata-only boundary.

        Args:
            **options: Optional SDK ``transport_options`` / ``fields``.

        Returns:
            :class:`LookerData` with ``content_type == "dashboard"``.

        Raises:
            ProcessingError: If the SDK read fails.
        """
        return self._ingest("all_dashboards", "dashboard", **options)

    def ingest_lookml_models(self, **options: Any) -> LookerData:
        """Fetch LookML model metadata via ``all_lookml_models()``.

        Explores are nested inside their parent model record.

        Args:
            **options: Optional SDK ``limit`` / ``offset`` /
                ``transport_options``.

        Returns:
            :class:`LookerData` with ``content_type == "lookml_model"``.

        Raises:
            ProcessingError: If the SDK read fails.
        """
        return self._ingest("all_lookml_models", "lookml_model", **options)

    def ingest_folders(self, **options: Any) -> LookerData:
        """Fetch Folder metadata via ``all_folders()``.

        Args:
            **options: Optional SDK ``transport_options`` / ``fields``.

        Returns:
            :class:`LookerData` with ``content_type == "folder"``.

        Raises:
            ProcessingError: If the SDK read fails.
        """
        return self._ingest("all_folders", "folder", **options)

    def ingest_projects(self, **options: Any) -> LookerData:
        """Fetch Project metadata via ``all_projects()``.

        Secret-adjacent project fields are removed by the normalizer and
        ``git_remote_url`` userinfo is scrubbed.

        Args:
            **options: Optional SDK ``transport_options`` / ``fields``.

        Returns:
            :class:`LookerData` with ``content_type == "project"``.

        Raises:
            ProcessingError: If the SDK read fails.
        """
        return self._ingest("all_projects", "project", **options)

    # ------------------------------------------------------------------
    # Internal read pipeline
    # ------------------------------------------------------------------

    def _ingest(self, sdk_method: str, content_type: str, **options: Any) -> LookerData:
        """Run one SDK collection read and normalize its records.

        The connection is opened transiently unless the caller already
        connected the connector (for example via the context manager).

        Args:
            sdk_method: Name of the ``looker_sdk`` collection method.
            content_type: Content type recorded on the result.
            **options: Options forwarded to the SDK method.

        Returns:
            A populated :class:`LookerData`.

        Raises:
            ProcessingError: If the SDK read fails.
        """
        already_connected = bool(getattr(self.connector, "connected", False))
        tracking_id = self.progress_tracker.start_tracking(
            file=f"looker:{content_type}",
            module="ingest",
            submodule="LookerIngestor",
            message=f"Reading Looker {content_type} metadata",
        )

        try:
            client = self.connector.connect()
            try:
                method = getattr(client, sdk_method)
                raw = method(**options) if options else method()
            except ValidationError:
                raise
            except Exception as exc:  # noqa: BLE001 - type name only
                self.logger.error(
                    "Looker %s read failed: %s", sdk_method, type(exc).__name__
                )
                raise ProcessingError(
                    f"Looker {sdk_method} failed: {type(exc).__name__}"
                ) from None

            records = self._to_records(raw or [], content_type)
            data = LookerData(
                data=records,
                row_count=len(records),
                columns=self._derive_columns(records),
                content_type=content_type,
                base_url=getattr(self.connector, "base_url", None),
                metadata={"content_type": content_type, "endpoint": sdk_method},
            )
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Read {data.row_count} {content_type} record(s)",
            )
            self.logger.debug(
                "ingest_%s: normalized %d record(s)",
                content_type,
                data.row_count,
            )
            return data
        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="failed",
                message=f"Failed to read Looker {content_type} metadata",
            )
            raise
        except Exception as exc:  # noqa: BLE001 - finalized then re-raised
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=type(exc).__name__
            )
            self.logger.error(
                "Failed to ingest Looker %s: %s", content_type, type(exc).__name__
            )
            raise
        finally:
            if not already_connected:
                self.connector.disconnect()

    @staticmethod
    def _derive_columns(records: List[Dict[str, Any]]) -> List[str]:
        """Return the ordered union of keys present across *records*."""
        return list(dict.fromkeys(key for record in records for key in record))

    # ------------------------------------------------------------------
    # Deep normalizer
    # ------------------------------------------------------------------

    def _to_records(
        self, raw: Sequence[Any], content_type: str
    ) -> List[Dict[str, Any]]:
        """Normalize SDK records into plain, JSON-serializable dicts.

        Args:
            raw: Sequence of SDK ``Model`` objects or mappings.
            content_type: One of the allowlisted content types.

        Returns:
            A list of normalized dictionaries.

        Raises:
            ValidationError: If *content_type* has no allowlist, or a
                record is not a mapping-like object.
        """
        if content_type not in _RETAINED_FIELDS:
            raise ValidationError(f"Unsupported Looker content type: {content_type!r}.")
        allowed = _RETAINED_FIELDS[content_type]
        return [self._normalize_record(record, allowed) for record in raw]

    def _normalize_record(self, record: Any, allowed: frozenset) -> Dict[str, Any]:
        """Project a single record through the retained-fields allowlist."""
        data = self._record_mapping(record)
        return {
            key: self._normalize_field(key, value)
            for key, value in data.items()
            if key in allowed
        }

    def _normalize_field(self, key: str, value: Any) -> Any:
        """Normalize one field, scrubbing any credential-bearing URL.

        ``Project.git_remote_url`` may embed ``user:password@`` userinfo;
        the field is useful metadata, the userinfo is not.
        """
        if key == "git_remote_url" and isinstance(value, str):
            value = _scrub_url_userinfo(value)
        return self._normalize_value(value)

    def _normalize_value(self, value: Any) -> Any:
        """Recursively convert *value* into JSON-serializable primitives.

        SDK ``Model`` objects become filtered dictionaries, sequences
        become lists, and dates/datetimes become ISO 8601 strings.
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Mapping):
            # Route through _normalize_field so credential-bearing URLs are
            # scrubbed, and drop secret-named keys, at every depth.
            return {
                key: self._normalize_field(key, item)
                for key, item in value.items()
                if key not in _SECRET_FIELD_NAMES
            }
        if isinstance(value, (list, tuple, set, frozenset)):
            return [self._normalize_value(item) for item in value]
        if self._is_model_like(value):
            return self._normalize_record(value, _NESTED_RETAINED_FIELDS)
        return str(value)

    @staticmethod
    def _is_model_like(value: Any) -> bool:
        """Return True for SDK ``Model``-like objects (keys/items/iter)."""
        return callable(getattr(value, "keys", None)) and callable(
            getattr(value, "items", None)
        )

    @staticmethod
    def _record_mapping(record: Any) -> Dict[str, Any]:
        """Return a mapping view of *record*.

        ``dict(record)`` is the SDK primitive, but nested values stay
        ``Model`` objects, so callers recurse through
        :meth:`_normalize_value`.

        Raises:
            ValidationError: If *record* is not mapping-like.
        """
        if isinstance(record, Mapping):
            return dict(record)
        items = getattr(record, "items", None)
        if callable(items):
            try:
                return dict(items())
            except Exception:  # noqa: BLE001 - fall through to keys()
                pass
        keys = getattr(record, "keys", None)
        if callable(keys):
            try:
                return {str(key): record[key] for key in keys()}
            except Exception:  # noqa: BLE001 - fall through to __dict__
                pass
        data = getattr(record, "__dict__", None)
        if isinstance(data, dict):
            return dict(data)
        raise ValidationError(
            f"Unsupported Looker record type: {type(record).__name__}"
        )

    # ------------------------------------------------------------------
    # Document export
    # ------------------------------------------------------------------

    def export_as_documents(self, data: LookerData) -> List[Dict[str, Any]]:
        """Convert :class:`LookerData` to Semantica documents.

        Produces the ``{"id", "text", "metadata"}`` shape consumed by
        :class:`~semantica.kg.graph_builder.GraphBuilder`.  Document ids
        are namespaced per content type so they stay unique across
        collections, and LookML Explores are nested inside their parent
        model document.

        Metadata always carries ``source`` (``"looker"``) and
        ``content_type``; it never carries ``base_url`` or credentials.

        Args:
            data: A :class:`LookerData` returned by one of the
                ``ingest_*`` methods.

        Returns:
            A list of document dictionaries.

        Raises:
            ValidationError: If ``data.content_type`` is unsupported.
        """
        if data.content_type not in _RETAINED_FIELDS:
            raise ValidationError(
                f"Unsupported Looker content type: {data.content_type!r}."
            )

        documents: List[Dict[str, Any]] = []
        for index, row in enumerate(data.data):
            document_id = self._document_id(row, data.content_type, index)
            documents.append(
                {
                    "id": document_id,
                    "text": self._document_text(row, data.content_type),
                    "metadata": self._document_metadata(
                        row, data.content_type, document_id
                    ),
                }
            )

        self.logger.debug(
            "export_as_documents: exported %d document(s)", len(documents)
        )
        return documents

    @staticmethod
    def _document_id(row: Dict[str, Any], content_type: str, index: int) -> str:
        """Compose the namespaced document id for one record."""
        if content_type == "lookml_model":
            project = row.get("project_name") or "unknown"
            name = row.get("name") or index
            return f"looker:lookml_model:{project}.{name}"
        identifier = row.get("id")
        if identifier is None or identifier == "":
            identifier = index
        return f"looker:{content_type}:{identifier}"

    def _document_metadata(
        self, row: Dict[str, Any], content_type: str, document_id: str
    ) -> Dict[str, Any]:
        """Build the metadata block for one document."""
        metadata: Dict[str, Any] = {
            "source": "looker",
            "content_type": content_type,
            "row_data": row,
        }

        identifier_key = _ID_METADATA_KEYS.get(content_type)
        if identifier_key is not None:
            metadata[identifier_key] = row.get("id")

        if content_type == "lookml_model":
            project = row.get("project_name") or "unknown"
            name = row.get("name") or "unknown"
            metadata["project_name"] = row.get("project_name")
            metadata["model_name"] = row.get("name")
            metadata["explores"] = self._nest_explores(
                row.get("explores"), project, name, document_id
            )
            metadata["explore_count"] = len(metadata["explores"])

        return metadata

    @staticmethod
    def _nest_explores(
        explores: Any,
        project: str,
        model: str,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """Nest Explore summaries inside their parent model document.

        Explores carry no parent reference of their own, so the parent
        project/model name is composed into every nested id.
        """
        nested: List[Dict[str, Any]] = []
        if not isinstance(explores, (list, tuple)):
            return nested
        for explore in explores:
            if not isinstance(explore, Mapping):
                continue
            explore_name = explore.get("name") or "unknown"
            nested.append(
                {
                    "id": f"{document_id}:explore:{explore_name}",
                    "name": explore_name,
                    "label": explore.get("label"),
                    "view_name": explore.get("view_name"),
                    "description": explore.get("description"),
                    "parent_model": f"{project}.{model}",
                }
            )
        return nested

    def _document_text(self, row: Dict[str, Any], content_type: str) -> str:
        """Compose the searchable text for one document."""
        parts: List[str] = []

        for field_name in _TEXT_FIELDS.get(content_type, ()):
            value = row.get(field_name)
            if isinstance(value, str) and value:
                parts.append(value)

        folder = row.get("folder")
        if isinstance(folder, Mapping):
            folder_name = folder.get("name")
            if isinstance(folder_name, str) and folder_name:
                parts.append(folder_name)

        if content_type == "lookml_model":
            for explore in row.get("explores") or []:
                if not isinstance(explore, Mapping):
                    continue
                for field_name in ("label", "name", "description", "view_name"):
                    value = explore.get(field_name)
                    if isinstance(value, str) and value:
                        parts.append(value)

        return " ".join(parts)
