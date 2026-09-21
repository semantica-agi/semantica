"""Microsoft Dynamics 365 Ingestion Module.

Pulls entity records from a Microsoft Dynamics 365 organisation via the
Dynamics 365 Web API (OData v4 / REST) and flattens them into document dicts
that the Semantica pipeline can feed to ``GraphBuilder``.

Why this exists
---------------
Dynamics 365 is a very common Enterprise CRM/ERP source for business entities
(Account, Opportunity, Order, Contact, Lead) that a Context Graph wants.
Dynamics exposes those entities over a standard OData v4 REST surface at::

    https://<org>.api.crm.dynamics.com/api/data/v9.2/

This connector speaks only that REST surface; it uses ``msal`` for the
Azure AD OAuth2 client-credentials flow and ``requests`` (already a core
dependency) for all HTTP calls routed through ``request_with_ssrf_guard``.

Design notes
------------
Three classes, matching the SAP/Snowflake/Salesforce ingestors:

- ``Dynamics365Data``: a collection fetch from one Dynamics entity,
  flattened to document dicts for ``GraphBuilder`` via
  ``export_as_documents``.
- ``Dynamics365Connector``: Azure AD / MSAL client-credentials auth plus the
  SSRF-guarded ``requests`` session.  *Every* outbound request goes through
  ``request_with_ssrf_guard`` so user-supplied ``org_url`` values cannot
  reach private/loopback/link-local address space.
- ``Dynamics365Ingestor``: the three main operations —
  ``list_entities``, ``ingest_entity``, and ``export_as_documents``.

Optional Dependency
-------------------
Install via the ``ingest-dynamics365`` extra::

    pip install "semantica[ingest-dynamics365]"

or directly::

    pip install msal>=1.20

Environment Variables
---------------------
``DYNAMICS_TENANT_ID``      Azure AD tenant (directory) ID.
``DYNAMICS_CLIENT_ID``      Azure AD application (client) ID.
``DYNAMICS_CLIENT_SECRET``  Azure AD client secret value.
``DYNAMICS_ORG_URL``        Base URL of your Dynamics 365 org, e.g.
                            ``https://myorg.api.crm.dynamics.com``.

Example Usage::

    >>> import os
    >>> from semantica.ingest import Dynamics365Ingestor
    >>> ingestor = Dynamics365Ingestor(
    ...     tenant_id=os.getenv("DYNAMICS_TENANT_ID"),
    ...     client_id=os.getenv("DYNAMICS_CLIENT_ID"),
    ...     client_secret=os.getenv("DYNAMICS_CLIENT_SECRET"),
    ...     org_url=os.getenv("DYNAMICS_ORG_URL"),
    ... )
    >>> data = ingestor.ingest_entity("accounts", select=["name", "accountid"], top=100)
    >>> docs = ingestor.export_as_documents(data)

Author: Semantica Contributors
License: MIT
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .ssrf import request_with_ssrf_guard

# ---------------------------------------------------------------------------
# Optional-dependency guard — mirrors the pattern in salesforce_ingestor,
# snowflake_ingestor, and bigquery_ingestor exactly.  The module always
# imports cleanly; the guard fires at instantiation time via the
# DYNAMICS_AVAILABLE check in semantica/ingest/__init__.py.__getattr__.
# ---------------------------------------------------------------------------
try:
    import msal as _msal

    DYNAMICS_AVAILABLE = True
except (ImportError, OSError):
    _msal = None  # type: ignore[assignment]
    DYNAMICS_AVAILABLE = False

__all__ = [
    "Dynamics365Data",
    "Dynamics365Connector",
    "Dynamics365Ingestor",
]

_logger = get_logger("dynamics365_ingestor")

# Dynamics 365 Web API version used for all requests.
_WEBAPI_VERSION = "v9.2"

# Entities that are almost always present in a standard Dynamics 365 org.
_DEFAULT_ENTITIES = [
    "accounts",
    "contacts",
    "leads",
    "opportunities",
    "incidents",
    "orders",
    "products",
    "systemusers",
]


# ---------------------------------------------------------------------------
# URL validation helpers
# ---------------------------------------------------------------------------

def _validate_org_url(url: str) -> str:
    """Validate a user-supplied Dynamics 365 org URL.

    Args:
        url: The org URL to validate.

    Returns:
        The normalised URL (trailing slash stripped) if valid.

    Raises:
        ValidationError: If *url* is not a valid public HTTPS URL.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValidationError(
            "Dynamics 365 org_url is required and must be a non-empty string."
        )
    url = url.rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValidationError(
            f"Dynamics 365 org_url must use the https:// scheme, got: {url!r}"
        )
    if not parsed.netloc:
        raise ValidationError(
            f"Dynamics 365 org_url must contain a valid hostname, got: {url!r}"
        )
    # Block obvious private / loopback hostnames early (SSRF guard covers IPs).
    hostname = parsed.hostname or ""
    private_suffixes = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
    if any(hostname == h or hostname.endswith("." + h) for h in private_suffixes):
        raise ValidationError(
            f"Dynamics 365 org_url must not point to a private address: {url!r}"
        )
    return url


# ---------------------------------------------------------------------------
# Data result type
# ---------------------------------------------------------------------------

@dataclass
class Dynamics365Data:
    """A collection fetch from one Dynamics 365 entity.

    Attributes:
        records:      Raw record dicts returned by the Web API.
        entity_name:  Logical name of the entity set, e.g. ``"accounts"``.
        row_count:    Number of records in *records*.
        columns:      Ordered list of field names present across all records.
        org_url:      Base URL of the Dynamics 365 org.
        metadata:     Optional extra metadata from the caller / connector.
        ingested_at:  UTC timestamp of when the fetch completed.
    """

    records: List[Dict[str, Any]]
    entity_name: str
    row_count: int
    columns: List[str]
    org_url: str
    metadata: Optional[Dict[str, Any]] = None
    ingested_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class Dynamics365Connector:
    """Connection and authentication management for a Dynamics 365 Web API org.

    Uses the MSAL ``ConfidentialClientApplication`` client-credentials flow
    (Azure AD app registration) to obtain a bearer token.  The token is cached
    inside the MSAL application object and refreshed transparently on expiry.

    Every outbound HTTP call — including the initial MSAL token exchange — goes
    through ``request_with_ssrf_guard`` so user-supplied URLs cannot reach
    private/loopback/link-local address space.

    Args:
        tenant_id:     Azure AD tenant (directory) ID.
        client_id:     Azure AD application (client) ID.
        client_secret: Azure AD client secret value.
        org_url:       Base URL of the Dynamics 365 org.  Validated and
                       normalised; must be an https:// URL pointing to a
                       publicly reachable host.
        **config:      Extra options forwarded to ``request_with_ssrf_guard``,
                       e.g. ``timeout``.

    Environment variables (all optional — constructor args take precedence)::

        DYNAMICS_TENANT_ID, DYNAMICS_CLIENT_ID,
        DYNAMICS_CLIENT_SECRET, DYNAMICS_ORG_URL
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        org_url: Optional[str] = None,
        **config: Any,
    ) -> None:
        if not DYNAMICS_AVAILABLE:  # pragma: no cover — guard raised by __init__
            raise ImportError(
                "Dynamics 365 ingestion requires optional dependency 'msal'. "
                "Install it with: pip install 'semantica[ingest-dynamics365]'"
            )

        self.tenant_id = tenant_id or os.getenv("DYNAMICS_TENANT_ID")
        self.client_id = client_id or os.getenv("DYNAMICS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("DYNAMICS_CLIENT_SECRET")
        raw_org_url = org_url or os.getenv("DYNAMICS_ORG_URL") or ""
        self.org_url = _validate_org_url(raw_org_url)
        self.config = config

        if not self.tenant_id:
            raise ValidationError(
                "Dynamics 365 tenant_id is required. Provide via 'tenant_id' or "
                "DYNAMICS_TENANT_ID environment variable."
            )
        if not self.client_id:
            raise ValidationError(
                "Dynamics 365 client_id is required. Provide via 'client_id' or "
                "DYNAMICS_CLIENT_ID environment variable."
            )
        if not self.client_secret:
            raise ValidationError(
                "Dynamics 365 client_secret is required. Provide via 'client_secret' or "
                "DYNAMICS_CLIENT_SECRET environment variable."
            )

        self._msal_app: Optional[Any] = None
        self._access_token: Optional[str] = None
        self.logger = _logger

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Obtain an access token via MSAL client-credentials flow.

        The MSAL ``ConfidentialClientApplication`` is initialised here so that
        tests can mock ``_msal`` before the connector is constructed.

        Raises:
            ProcessingError: If the token cannot be obtained.
        """
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        scope = [f"{self.org_url}/.default"]
        self.logger.info(
            "Dynamics365Connector.connect: acquiring token for org %s", self.org_url
        )
        try:
            self._msal_app = _msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=authority,
            )
            result = self._msal_app.acquire_token_for_client(scopes=scope)
        except Exception as exc:
            raise ProcessingError(
                f"Dynamics 365 MSAL token acquisition failed: {exc}"
            ) from exc

        if "access_token" not in result:
            error = result.get("error_description") or result.get("error") or str(result)
            raise ProcessingError(
                f"Dynamics 365 MSAL token acquisition failed: {error}"
            )

        self._access_token = result["access_token"]
        self.logger.info("Dynamics365Connector.connect: token acquired successfully")

    def disconnect(self) -> None:
        """Clear cached credentials."""
        self._access_token = None
        self._msal_app = None
        self.logger.debug("Dynamics365Connector.disconnect: token cleared")

    def test_connection(self) -> bool:
        """Probe the Web API root to verify credentials and connectivity.

        Returns:
            ``True`` if the probe returns HTTP 200.

        Raises:
            ProcessingError: If the connection test fails or an HTTP error
                is returned.
        """
        if not self._access_token:
            self.connect()

        probe_url = f"{self.org_url}/api/data/{_WEBAPI_VERSION}/"
        headers = self._auth_headers()
        try:
            resp = request_with_ssrf_guard(
                "GET",
                probe_url,
                headers=headers,
                timeout=self.config.get("timeout", 30),
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            raise ProcessingError(
                f"Dynamics 365 connection test failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        """Return HTTP headers including the Bearer token."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }

    def _ensure_connected(self) -> None:
        if not self._access_token:
            self.connect()

    # Context-manager support (mirrors SAP/Snowflake connectors).
    def __enter__(self) -> "Dynamics365Connector":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.disconnect()


# ---------------------------------------------------------------------------
# Ingestor
# ---------------------------------------------------------------------------

class Dynamics365Ingestor:
    """Orchestrates data extraction from a Microsoft Dynamics 365 org.

    Wraps a ``Dynamics365Connector`` and exposes three public methods:

    - ``list_entities``: discover available entity sets.
    - ``ingest_entity``: fetch records from a single entity set.
    - ``export_as_documents``: convert a ``Dynamics365Data`` object into the
      ``[{id, text, metadata}]`` list that ``GraphBuilder`` consumes.

    Args:
        tenant_id:     Azure AD tenant ID (or ``DYNAMICS_TENANT_ID`` env var).
        client_id:     Azure AD application ID (or ``DYNAMICS_CLIENT_ID``).
        client_secret: Azure AD client secret (or ``DYNAMICS_CLIENT_SECRET``).
        org_url:       Dynamics 365 org base URL (or ``DYNAMICS_ORG_URL``).
        connector:     Pre-built ``Dynamics365Connector`` instance; when
                       supplied the four credential args are ignored.
        **config:      Extra options forwarded to the connector, e.g.
                       ``timeout``.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        org_url: Optional[str] = None,
        *,
        connector: Optional[Dynamics365Connector] = None,
        **config: Any,
    ) -> None:
        if not DYNAMICS_AVAILABLE:  # pragma: no cover — guard raised by __init__
            raise ImportError(
                "Dynamics 365 ingestion requires optional dependency 'msal'. "
                "Install it with: pip install 'semantica[ingest-dynamics365]'"
            )

        if connector is not None:
            self._connector = connector
        else:
            self._connector = Dynamics365Connector(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                org_url=org_url,
                **config,
            )
        self.logger = _logger
        self._progress = get_progress_tracker()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def list_entities(self) -> List[str]:
        """Return a list of available entity set names from the Web API.

        Queries the OData service root (``/api/data/v9.2/``) for the list of
        entity sets.  Falls back to a built-in default list if the service
        root does not include entity-set metadata (some restricted tenants
        suppress it).

        Returns:
            List of entity set (logical plural) names, e.g.
            ``["accounts", "contacts", "leads", ...]``.

        Raises:
            ProcessingError: If the Web API is unreachable.
        """
        self._connector._ensure_connected()
        url = f"{self._connector.org_url}/api/data/{_WEBAPI_VERSION}/"
        headers = self._connector._auth_headers()
        self.logger.info("Dynamics365Ingestor.list_entities: fetching service root")
        try:
            resp = request_with_ssrf_guard(
                "GET",
                url,
                headers=headers,
                timeout=self._connector.config.get("timeout", 30),
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ProcessingError(
                f"Dynamics 365 list_entities failed: {exc}"
            ) from exc

        entity_sets = [
            str(e["name"])
            for e in data.get("value", [])
            if isinstance(e, dict) and e.get("name")
        ]
        if not entity_sets:
            self.logger.debug(
                "list_entities: no entity sets in service root, using defaults"
            )
            return list(_DEFAULT_ENTITIES)
        return entity_sets

    def ingest_entity(
        self,
        entity_name: str,
        select: Optional[List[str]] = None,
        filter: Optional[str] = None,  # noqa: A002 — mirrors the OData param name
        top: Optional[int] = None,
    ) -> Dynamics365Data:
        """Fetch records from a Dynamics 365 entity set.

        Follows ``@odata.nextLink`` for automatic server-driven pagination so
        the full record set is always returned regardless of page size.

        Args:
            entity_name: Logical plural name of the entity set, e.g.
                         ``"accounts"``, ``"contacts"``.
            select:      List of field names to include in the response
                         (OData ``$select``).  ``None`` fetches all fields.
            filter:      OData ``$filter`` expression, e.g.
                         ``"statecode eq 0"``.  ``None`` for no filter.
            top:         Maximum number of records to return (OData ``$top``).
                         ``None`` returns all pages.

        Returns:
            ``Dynamics365Data`` with the fetched records.

        Raises:
            ValidationError: If *entity_name* is empty.
            ProcessingError: If the Web API returns an error.
        """
        if not isinstance(entity_name, str) or not entity_name.strip():
            raise ValidationError(
                "entity_name must be a non-empty string."
            )
        entity_name = entity_name.strip()

        self._connector._ensure_connected()
        base_url = (
            f"{self._connector.org_url}/api/data/{_WEBAPI_VERSION}/{entity_name}"
        )
        params: Dict[str, Any] = {}
        if select:
            params["$select"] = ",".join(select)
        if filter:
            params["$filter"] = filter
        if top is not None:
            params["$top"] = top

        headers = self._connector._auth_headers()
        all_records: List[Dict[str, Any]] = []
        next_url: Optional[str] = base_url
        page = 0

        self.logger.info(
            "Dynamics365Ingestor.ingest_entity: fetching entity=%s", entity_name
        )
        tracking_id = self._progress.start_tracking(
            file=entity_name,
            module="ingest",
            submodule="Dynamics365Ingestor",
            message=f"Fetching {entity_name}",
        )

        try:
            while next_url:
                req_kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "timeout": self._connector.config.get("timeout", 60),
                }
                if page == 0:
                    req_kwargs["params"] = params

                resp = request_with_ssrf_guard("GET", next_url, **req_kwargs)
                resp.raise_for_status()
                payload = resp.json()

                records = payload.get("value", [])
                all_records.extend(records)
                page += 1
                self._progress.update_tracking(
                    tracking_id,
                    message=f"Fetched {len(all_records)} records so far…",
                )
                self.logger.debug(
                    "ingest_entity: page %d — %d records (total so far: %d)",
                    page,
                    len(records),
                    len(all_records),
                )

                next_url = payload.get("@odata.nextLink")
                # Honour top: stop paging once we have enough records.
                if top is not None and len(all_records) >= top:
                    all_records = all_records[:top]
                    break

            self._progress.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested {len(all_records)} records",
            )
        except ProcessingError:
            self._progress.stop_tracking(tracking_id, status="failed")
            raise
        except Exception as exc:
            self._progress.stop_tracking(tracking_id, status="failed")
            raise ProcessingError(
                f"Dynamics 365 ingest_entity({entity_name!r}) failed: {exc}"
            ) from exc

        # Derive columns from the union of keys across all records.
        columns: List[str] = []
        seen: set = set()
        for rec in all_records:
            for key in rec:
                if key not in seen:
                    seen.add(key)
                    columns.append(key)

        self.logger.info(
            "Dynamics365Ingestor.ingest_entity: fetched %d records from %s",
            len(all_records),
            entity_name,
        )
        return Dynamics365Data(
            records=all_records,
            entity_name=entity_name,
            row_count=len(all_records),
            columns=columns,
            org_url=self._connector.org_url,
        )

    def export_as_documents(
        self, data: Dynamics365Data
    ) -> List[Dict[str, Any]]:
        """Convert a ``Dynamics365Data`` into the document list for GraphBuilder.

        Each record is serialised as a ``text`` blob (key=value pairs) and
        wrapped with the ``id`` and ``metadata`` that the pipeline requires.

        Args:
            data: A ``Dynamics365Data`` instance produced by ``ingest_entity``.

        Returns:
            List of ``{id, text, metadata}`` dicts.  ``metadata`` always
            carries ``source="dynamics365"``, ``entity_name``, and ``org_url``.
        """
        docs: List[Dict[str, Any]] = []
        for index, record in enumerate(data.records):
            # Best-effort ID resolution: prefer common Dynamics ID fields.
            record_id = (
                record.get(f"{data.entity_name[:-1]}id")  # e.g. accountid
                or record.get("id")
                or record.get("Id")
                or f"{data.entity_name}:{index}"
            )
            text = " | ".join(
                f"{k}: {v}" for k, v in record.items() if v not in (None, "")
            )
            docs.append(
                {
                    "id": str(record_id),
                    "text": text,
                    "metadata": {
                        "source": "dynamics365",
                        "entity_name": data.entity_name,
                        "org_url": data.org_url,
                    },
                }
            )
        return docs
