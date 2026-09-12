"""Power BI ingestion module.

Pulls workspace, dataset, report and dataflow metadata from the Power BI
REST API and flattens it into document dicts that feed straight into
``GraphBuilder``.

The Power BI REST API is plain OAuth2 + JSON, so this connector needs
nothing beyond ``requests`` — the same shape as the SAP connector.

Design notes
------------
Three classes, matching the Snowflake/Salesforce/Redshift ingestors:

- ``PowerBIData``: holds one ingestion run's worth of metadata
  (``workspaces``, ``datasets``, ``reports``, ``dataflows``, ``metadata``,
  ``ingested_at``).  No network dependency — always importable.

- ``PowerBIConnector``: owns the Azure AD OAuth2 client-credentials token
  lifecycle and the ``requests`` session.  Raises ``ValidationError`` when
  the credentials are incomplete.  Every outbound call goes through
  ``request_with_ssrf_guard``.

- ``PowerBIIngestor``: orchestrates ingestion and exposes
  ``export_as_documents``.

Authentication
--------------
Azure AD OAuth2 client-credentials::

    connector = PowerBIConnector(
        tenant_id="00000000-0000-0000-0000-000000000000",
        client_id="...",
        client_secret="...",
    )

Credentials may also come from the environment:

* ``POWERBI_TENANT_ID``
* ``POWERBI_CLIENT_ID``
* ``POWERBI_CLIENT_SECRET``
* ``POWERBI_WORKSPACE_ID`` (optional)

The client secret is kept in a private attribute and is never logged.

Dependencies
------------
``requests`` is a core Semantica dependency, so no extra is needed::

    pip install semantica

The module is registered as a lazy export in ``__init__.py``, so a
top-level ``import semantica.ingest`` does not import it until one of the
classes below is first accessed.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

import requests

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .ssrf import request_with_ssrf_guard

__all__ = [
    "PowerBIData",
    "PowerBIConnector",
    "PowerBIIngestor",
]

_DEFAULT_API_BASE = "https://api.powerbi.com/v1.0/myorg"
_DEFAULT_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_DEFAULT_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# Resources the ingestor can pull, in the order they are exported.
_RESOURCE_KEYS = ("workspaces", "datasets", "reports", "dataflows")

_logger = get_logger("powerbi_ingestor")


def _origin(url: str) -> tuple:
    """Return the ``(scheme, host, effective port)`` triple for *url*.

    Used to keep pagination on one origin: every hop re-sends the bearer
    token, so a next link must not be allowed to move it elsewhere.
    """
    parsed = urlparse(url or "")
    scheme = (parsed.scheme or "").lower()
    default_port = 443 if scheme == "https" else 80
    return scheme, (parsed.hostname or "").lower(), parsed.port or default_port


# ---------------------------------------------------------------------------
# PowerBIData
# ---------------------------------------------------------------------------


@dataclass
class PowerBIData:
    """Metadata returned from the Power BI REST API.

    Attributes:
        workspaces: Workspace (group) summaries, one dict per workspace.
        datasets: Dataset summaries.
        reports: Report summaries.
        dataflows: Dataflow summaries.
        metadata: Run metadata (API base, workspace, per-resource counts).
        ingested_at: Timestamp recorded when this object was created.
    """

    workspaces: List[Dict[str, Any]]
    datasets: List[Dict[str, Any]]
    reports: List[Dict[str, Any]]
    dataflows: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# PowerBIConnector
# ---------------------------------------------------------------------------


class PowerBIConnector:
    """Manages the Power BI REST client and OAuth2 token lifecycle.

    Responsibilities:

    * Resolves credentials from constructor arguments, falling back to
      ``POWERBI_*`` environment variables.
    * Validates that a usable credential set is configured *before* any
      network call is made.
    * Acquires and caches an Azure AD client-credentials token, refreshing
      it shortly before expiry.
    * Exposes :meth:`test_connection` and :meth:`close`.

    Every outbound HTTP call — including the token request — goes through
    :func:`~semantica.ingest.ssrf.request_with_ssrf_guard`, so a
    user-supplied endpoint cannot reach private/loopback/link-local space.

    Raises:
        ImportError: When ``requests`` is not installed.
        ValidationError: When required credentials are incomplete.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        workspace_id: Optional[str] = None,
        api_base: Optional[str] = None,
        token_url: Optional[str] = None,
        scope: Optional[str] = None,
        allow_private_ips: Optional[bool] = None,
        timeout: int = 30,
        **config: Any,
    ) -> None:
        """Initialise the connector and validate credentials.

        Args:
            tenant_id: Azure AD tenant ID. Defaults to ``POWERBI_TENANT_ID``.
            client_id: Registered application (client) ID. Defaults to
                ``POWERBI_CLIENT_ID``.
            client_secret: Application secret. Defaults to
                ``POWERBI_CLIENT_SECRET``. Never logged.
            workspace_id: Optional default workspace (group) ID used when a
                method is called without an explicit workspace.
            api_base: Power BI API base URL. Defaults to
                ``https://api.powerbi.com/v1.0/myorg``.
            token_url: Azure AD token endpoint template. ``{tenant_id}`` is
                substituted with the configured tenant.
            scope: OAuth2 scope. Defaults to the Power BI ``.default`` scope.
            allow_private_ips: Allow requests to private networks (for
                self-hosted gateways behind a VPN).
            timeout: Per-request timeout in seconds.
            **config: Extra configuration kept for callers.

        Raises:
            ImportError: When ``requests`` is not installed.
            ValidationError: When required credentials are incomplete.
        """
        self.logger = _logger

        self.tenant_id = tenant_id or os.getenv("POWERBI_TENANT_ID")
        self.client_id = client_id or os.getenv("POWERBI_CLIENT_ID")
        # Secrets stay private and are never included in log messages.
        self._client_secret = client_secret or os.getenv("POWERBI_CLIENT_SECRET")
        self.workspace_id = workspace_id or os.getenv("POWERBI_WORKSPACE_ID")

        self.api_base = (api_base or _DEFAULT_API_BASE).rstrip("/")
        self.token_url_template = token_url or _DEFAULT_TOKEN_URL
        self.scope = scope or _DEFAULT_SCOPE
        self.allow_private_ips = allow_private_ips
        self.timeout = timeout
        self.config: Dict[str, Any] = config

        self._session: Optional[Any] = requests.Session() if requests else None
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

        self._validate_auth()

        self.logger.debug(
            "Power BI connector initialised (tenant=%s, workspace=%s)",
            self.tenant_id,
            self.workspace_id,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_auth(self) -> None:
        """Raise when the configured credentials cannot authenticate.

        Raises:
            ValidationError: If tenant_id, client_id or client_secret is
                missing.
        """
        if not self.tenant_id:
            raise ValidationError(
                "Power BI tenant_id is required. Provide via 'tenant_id' or "
                "POWERBI_TENANT_ID environment variable."
            )
        if not self.client_id:
            raise ValidationError(
                "Power BI client_id is required. Provide via 'client_id' or "
                "POWERBI_CLIENT_ID environment variable."
            )
        if not self._client_secret:
            raise ValidationError(
                "Power BI client_secret is required. Provide via "
                "'client_secret' or POWERBI_CLIENT_SECRET environment variable."
            )

    # ------------------------------------------------------------------
    # Token handling
    # ------------------------------------------------------------------

    @property
    def token_url(self) -> str:
        """Azure AD token endpoint for the configured tenant."""
        return self.token_url_template.format(tenant_id=self.tenant_id)

    def _request_token(self) -> str:
        """Acquire an OAuth2 access token via client-credentials.

        Returns:
            The access token string.

        Raises:
            ProcessingError: If the token endpoint call fails or returns no
                token.
        """
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "scope": self.scope,
        }

        try:
            response = request_with_ssrf_guard(
                "POST",
                self.token_url,
                session=self._session,
                allow_private_ips=self.allow_private_ips,
                data=data,
                timeout=self.timeout,
            )
            body = response.json()
            if response.status_code >= 400:
                raise ProcessingError(
                    f"Power BI token endpoint returned {response.status_code}: "
                    f"{str(body)[:200]}"
                )
            token = body.get("access_token")
            if not token:
                raise ProcessingError(
                    "Power BI token endpoint returned no access_token."
                )
            expires_in = int(body.get("expires_in") or 3600)
            self._access_token = token
            # Refresh a minute early so an in-flight request cannot race
            # against expiry.
            self._token_expiry = time.monotonic() + max(expires_in - 60, 0)
            return token
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(
                f"Failed to acquire Power BI access token: {type(exc).__name__}"
            ) from exc

    def _ensure_token(self) -> str:
        """Return a valid access token, refreshing when needed."""
        if self._access_token and time.monotonic() < self._token_expiry:
            return self._access_token
        return self._request_token()

    def _auth_headers(self) -> Dict[str, str]:
        """Build the Authorization header for an API call."""
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        """Join *path* onto the configured API base."""
        return f"{self.api_base}/{path.lstrip('/')}"

    def _same_origin(self, url: str) -> bool:
        """True when *url* shares the origin of the configured API base."""
        return _origin(url) == _origin(self.api_base)

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """GET a Power BI endpoint and return the decoded JSON body.

        Follows ``@odata.nextLink`` pagination up to a bounded number of
        hops, unwrapping the ``value`` list the API returns for collections.

        Args:
            path: Path relative to the API base, e.g. ``"groups"``.
            params: Optional query parameters for the first request.

        Returns:
            The decoded JSON body. For collection responses this is the
            accumulated ``value`` list.

        Raises:
            ProcessingError: If the request or JSON decoding fails.
        """
        headers = self._auth_headers()
        url = self._url(path)
        items: List[Any] = []
        saw_value = False
        hops = 0

        while url:
            try:
                response = request_with_ssrf_guard(
                    "GET",
                    url,
                    session=self._session,
                    allow_private_ips=self.allow_private_ips,
                    headers=headers,
                    params=params if hops == 0 else None,
                    timeout=self.timeout,
                )
                body = response.json()
                if response.status_code >= 400:
                    raise ProcessingError(
                        f"Power BI API returned {response.status_code} for "
                        f"{path}: {str(body)[:200]}"
                    )
            except ProcessingError:
                raise
            except Exception as exc:
                raise ProcessingError(
                    f"Failed to call Power BI API '{path}': {type(exc).__name__}"
                ) from exc

            if isinstance(body, dict):
                if "value" in body:
                    saw_value = True
                    items.extend(body.get("value") or [])
                    next_url = body.get("@odata.nextLink") or ""
                    if next_url and not self._same_origin(next_url):
                        raise ProcessingError(
                            f"Power BI pagination for '{path}' returned a next "
                            f"link on another origin ({_origin(next_url)[1]}); "
                            "refusing to send the access token there."
                        )
                    url = next_url
                else:
                    return body
            else:
                return body

            hops += 1
            if hops >= 100:  # bounded follow — defensive against loops
                self.logger.warning(
                    "Power BI pagination for '%s' exceeded 100 hops; stopping.",
                    path,
                )
                break

        return items if saw_value else []

    # ------------------------------------------------------------------
    # Resource helpers
    # ------------------------------------------------------------------

    def _workspace_path(self, resource: str, workspace_id: Optional[str]) -> str:
        """Return the API path for *resource*, scoped to a workspace if given."""
        target = workspace_id or self.workspace_id
        if target:
            return f"groups/{target}/{resource}"
        return resource

    def get_workspaces(self) -> List[Dict[str, Any]]:
        """Return workspace (group) summaries visible to the principal."""
        return list(self.get("groups") or [])

    def get_datasets(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return dataset summaries, optionally scoped to one workspace."""
        path = self._workspace_path("datasets", workspace_id)
        return list(self.get(path) or [])

    def get_reports(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return report summaries, optionally scoped to one workspace."""
        path = self._workspace_path("reports", workspace_id)
        return list(self.get(path) or [])

    def get_dataflows(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return dataflow summaries, optionally scoped to one workspace."""
        path = self._workspace_path("dataflows", workspace_id)
        return list(self.get(path) or [])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """Verify credentials by acquiring a token and listing workspaces.

        Returns:
            ``True`` when both steps succeed, ``False`` otherwise.
        """
        try:
            self._ensure_token()
            self.get_workspaces()
            return True
        except Exception as exc:
            self.logger.debug("Power BI connection test failed: %s", type(exc).__name__)
            return False

    def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None


# ---------------------------------------------------------------------------
# PowerBIIngestor
# ---------------------------------------------------------------------------


class PowerBIIngestor:
    """Power BI metadata ingestor for the Semantica framework.

    Wraps :class:`PowerBIConnector` and exposes workspace-metadata ingestion
    plus document export.

    Args:
        tenant_id: Azure AD tenant ID.
        client_id: Registered application (client) ID.
        client_secret: Application secret.
        workspace_id: Optional default workspace (group) ID.
        api_base: Power BI API base URL.
        allow_private_ips: Allow private-network requests.
        timeout: Per-request timeout in seconds.
        connector: An existing :class:`PowerBIConnector` to reuse.
        config: Optional extra configuration forwarded to the connector.
        **kwargs: Additional keyword arguments merged into ``config``.

    Example::

        from semantica.ingest import PowerBIIngestor

        ingestor = PowerBIIngestor(
            tenant_id="...", client_id="...", client_secret="..."
        )
        data = ingestor.ingest_workspace_metadata()
        documents = ingestor.export_as_documents(data)
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        workspace_id: Optional[str] = None,
        api_base: Optional[str] = None,
        allow_private_ips: Optional[bool] = None,
        timeout: int = 30,
        connector: Optional[PowerBIConnector] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.logger = _logger

        self.config: Dict[str, Any] = config or {}
        self.config.update(kwargs)

        self.connector: PowerBIConnector = connector or PowerBIConnector(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            workspace_id=workspace_id,
            api_base=api_base,
            allow_private_ips=allow_private_ips,
            timeout=timeout,
            **self.config,
        )

        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Power BI ingestor initialised.")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "PowerBIIngestor":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying connector."""
        self.connector.close()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def _fetch_child(
        self, resource: str, workspace_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Call the connector helper matching *resource* for one workspace."""
        if resource == "datasets":
            return self.connector.get_datasets(workspace_id)
        if resource == "reports":
            return self.connector.get_reports(workspace_id)
        return self.connector.get_dataflows(workspace_id)

    def ingest_workspace_metadata(
        self,
        workspace_id: Optional[str] = None,
        include: Optional[Sequence[str]] = None,
    ) -> PowerBIData:
        """Pull workspace, dataset, report and dataflow metadata.

        Args:
            workspace_id: Workspace (group) to read. Defaults to the
                connector's configured workspace; when that is unset the
                workspaces themselves are listed and datasets, reports and
                dataflows are collected across each of them, each record
                tagged with the ``workspace_id`` it came from.
            include: Subset of ``("workspaces", "datasets", "reports",
                "dataflows")`` to pull. Defaults to all four; pass an empty
                sequence to pull nothing.

        Returns:
            :class:`PowerBIData` with the requested collections populated.

        Raises:
            ValidationError: If *include* names an unknown resource.
            ProcessingError: If any API call fails.
        """
        wanted = _RESOURCE_KEYS if include is None else tuple(include)
        unknown = [name for name in wanted if name not in _RESOURCE_KEYS]
        if unknown:
            raise ValidationError(
                f"Unknown Power BI resource(s): {', '.join(unknown)}. "
                f"Expected any of: {', '.join(_RESOURCE_KEYS)}."
            )

        tracking_id = self.progress_tracker.start_tracking(
            file=workspace_id or self.connector.workspace_id or "myorg",
            module="ingest",
            submodule="PowerBIIngestor",
            message="Pulling Power BI metadata",
        )

        collected: Dict[str, List[Dict[str, Any]]] = {key: [] for key in _RESOURCE_KEYS}

        try:
            scope = workspace_id or self.connector.workspace_id

            if "workspaces" in wanted:
                if scope:
                    # A single workspace was requested — describe just it.
                    workspace = self.connector.get(f"groups/{scope}")
                    collected["workspaces"] = [workspace] if workspace else []
                else:
                    collected["workspaces"] = self.connector.get_workspaces()

            children = [k for k in ("datasets", "reports", "dataflows") if k in wanted]
            if children:
                if scope:
                    for key in children:
                        collected[key] = self._fetch_child(key, scope)
                else:
                    # With no workspace configured the unscoped endpoints only
                    # cover "My workspace", and dataflows have no unscoped
                    # endpoint at all. Walk the visible workspaces instead and
                    # tag each record with the workspace it came from.
                    workspaces = collected["workspaces"]
                    if not workspaces and "workspaces" not in wanted:
                        workspaces = self.connector.get_workspaces()
                    for workspace in workspaces:
                        if not isinstance(workspace, dict):
                            continue
                        group_id = workspace.get("id")
                        if not group_id:
                            continue
                        for key in children:
                            for item in self._fetch_child(key, group_id):
                                if isinstance(item, dict):
                                    item.setdefault("workspace_id", group_id)
                                collected[key].append(item)

            data = PowerBIData(
                workspaces=collected["workspaces"],
                datasets=collected["datasets"],
                reports=collected["reports"],
                dataflows=collected["dataflows"],
                metadata={
                    "api_base": self.connector.api_base,
                    "workspace_id": workspace_id or self.connector.workspace_id,
                    "workspace_count": len(collected["workspaces"]),
                    "dataset_count": len(collected["datasets"]),
                    "report_count": len(collected["reports"]),
                    "dataflow_count": len(collected["dataflows"]),
                },
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=(
                    f"Pulled {len(data.workspaces)} workspace(s), "
                    f"{len(data.datasets)} dataset(s), "
                    f"{len(data.reports)} report(s), "
                    f"{len(data.dataflows)} dataflow(s)"
                ),
            )
            self.logger.info(
                "Power BI ingestion completed: %d workspace(s), %d dataset(s), "
                "%d report(s), %d dataflow(s)",
                len(data.workspaces),
                len(data.datasets),
                len(data.reports),
                len(data.dataflows),
            )
            return data

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="Power BI ingestion failed"
            )
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error(
                "Failed to ingest Power BI metadata: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to ingest Power BI metadata: {type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Document export
    # ------------------------------------------------------------------

    def export_as_documents(
        self,
        data: PowerBIData,
    ) -> List[Dict[str, Any]]:
        """Convert :class:`PowerBIData` to the Semantica document format.

        Produces the same ``{"id", "text", "metadata"}`` shape used by the
        Snowflake and Redshift ingestors, so the result is directly usable
        with ``GraphBuilder``.

        Args:
            data: A :class:`PowerBIData` returned by
                :meth:`ingest_workspace_metadata`.

        Returns:
            List of document dictionaries::

                [
                    {
                        "id": str,
                        "text": str,
                        "metadata": {
                            "source": "powerbi",
                            "resource_type": "dataset" | "report" | ...,
                            ...original fields...
                        },
                    },
                    ...
                ]
        """
        documents: List[Dict[str, Any]] = []

        for resource_type in _RESOURCE_KEYS:
            singular = resource_type[:-1]  # datasets -> dataset
            for index, item in enumerate(getattr(data, resource_type) or []):
                if not isinstance(item, dict):
                    continue
                text = self._describe(item, singular)
                metadata: Dict[str, Any] = {
                    "source": "powerbi",
                    "resource_type": singular,
                }
                metadata.update(item)
                documents.append(
                    {
                        "id": str(item.get("id") or f"{singular}-{index}"),
                        "text": text,
                        "metadata": metadata,
                    }
                )

        self.logger.debug(
            "export_as_documents: exported %d document(s)", len(documents)
        )
        return documents

    @staticmethod
    def _describe(item: Dict[str, Any], resource_type: str) -> str:
        """Build a one-paragraph text description of a Power BI object."""
        name = item.get("name") or item.get("displayName") or item.get("id")
        parts = [f"{name} (Power BI {resource_type})"]

        description = item.get("description")
        if description:
            parts.append(str(description))

        for key in ("workspaceId", "datasetId", "reportType", "configuredBy"):
            if item.get(key) is not None:
                parts.append(f"{key}: {item[key]}")

        return "\n".join(parts)
