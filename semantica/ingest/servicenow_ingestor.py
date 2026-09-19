"""ServiceNow Table API ingestion module.

Pulls records from a ServiceNow table (CMDB configuration items, relationships,
incidents, changes, ...) and flattens them into document dicts that the
pipeline can feed to ``GraphBuilder``.

Design notes
------------
Three classes, matching the SAP OData ingestor:
    - ``ServiceNowData``: the rows pulled from one table (``records``,
      ``count``, ``instance``, ``table``), flattened to document dicts for
      ``GraphBuilder`` via ``export_as_documents``.
    - ``ServiceNowConnector``: auth (Basic or OAuth2) + the shared,
      SSRF-guarded :mod:`requests` session. *Every* outbound request,
      including the OAuth2 token exchange, goes through
      ``request_with_ssrf_guard``.
    - ``ServiceNowIngestor``: ``ingest_table`` and ``export_as_documents``
      (plus ``close`` for symmetry with the SQL connectors).

Pagination
----------
The Table API is offset based: ``sysparm_limit`` / ``sysparm_offset``.
``ingest_table`` walks the table in ``batch_size`` pages until a short page
comes back (or ``limit`` rows have been collected).
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except (ImportError, OSError):  # pragma: no cover - old urllib3 layout
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from .ssrf import parse_bool, request_with_ssrf_guard

__all__ = [
    "ServiceNowData",
    "ServiceNowConnector",
    "ServiceNowIngestor",
]

_logger = get_logger("servicenow_ingestor")

_TABLE_API = "/api/now/table/"
_TOKEN_PATH = "/oauth_token.do"

# Record columns whose names collide with the discriminators GraphBuilder
# uses (``source``/``target`` mark a relationship; ``id``/``table`` are
# canonical provenance). A raw ServiceNow value under any of these would
# either clobber connector provenance or flip an entity row into a
# relationship, so they are relocated into ``_RAW_RECORD_KEY``.
_RESERVED_RECORD_KEYS = ("id", "source", "target", "table")
_RAW_RECORD_KEY = "servicenow_fields"


@dataclass
class ServiceNowData:
    """Records fetched from one ServiceNow table."""

    records: List[Dict[str, Any]]
    table: str
    count: int
    instance: str
    ingested_at: datetime = field(default_factory=datetime.now)

    def to_documents(self) -> List[Dict[str, Any]]:
        """Flatten each record to a document dict ``GraphBuilder`` can consume.

        GraphBuilder only treats a dict as an entity when it carries
        ``id``/``entity_id``/``name`` (or ``text``+``type``), and treats one
        carrying both ``source`` and ``target`` as a *relationship*. Every
        ServiceNow record has a ``sys_id``; that becomes ``id``, and ``name``
        is resolved from the record's own ``name``, ``number`` or
        ``short_description`` (falling back to ``table:index``).

        ServiceNow columns whose names collide with those discriminators or
        with the connector provenance keys (``id``/``source``/``target``/
        ``table``) are moved into the nested ``servicenow_fields`` mapping, so
        a row that happens to have a ``target`` column still builds as an
        entity rather than a spurious relationship, and canonical provenance
        (``source`` = instance, ``table`` = table) is never overwritten.
        """
        docs: List[Dict[str, Any]] = []
        for index, record in enumerate(self.records):
            doc: Dict[str, Any] = {}
            raw: Dict[str, Any] = {}
            for key, value in record.items():
                if key in _RESERVED_RECORD_KEYS:
                    raw[key] = value
                else:
                    doc[key] = value
            sys_id = _scalar(record.get("sys_id"))
            doc["id"] = sys_id or f"{self.table}:{index}"
            if isinstance(doc.get("name"), dict):
                doc["name"] = _scalar(doc["name"])
            doc.setdefault("name", self._name_value(record) or sys_id or self.table)
            doc["source"] = self.instance
            doc["table"] = self.table
            if raw:
                doc[_RAW_RECORD_KEY] = raw
            docs.append(doc)
        return docs

    @staticmethod
    def _name_value(record: Dict[str, Any]) -> str:
        for key in ("name", "number", "short_description"):
            value = _scalar(record.get(key))
            if value:
                return value
        return ""


def _scalar(value: Any) -> str:
    """Unwrap ``sysparm_display_value=all`` objects to their display string."""
    if isinstance(value, dict):
        value = value.get("display_value") or value.get("value")
    if value in (None, ""):
        return ""
    return str(value)


class ServiceNowConnector:
    """Connection + authentication management for a ServiceNow instance.

    - **Basic**: ``username``/``password`` attached as an
      ``Authorization: Basic`` header.
    - **OAuth2**: ``client_id``/``client_secret`` exchanged at
      ``<instance_url>/oauth_token.do``. ServiceNow's inbound OAuth issues
      tokens for the *resource owner password* grant when ``username`` and
      ``password`` are also set, otherwise ``client_credentials`` is used.

    Example usage::

        >>> connector = ServiceNowConnector(
        ...     instance_url="https://snow.example",
        ...     username="u", password="p",
        ... )
        >>> session = connector.get_session()
    """

    def __init__(
        self,
        instance_url: Optional[str] = None,
        *,
        auth: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        allow_private_ips: bool = False,
        **config: Any,
    ) -> None:
        """Initialize the ServiceNow connector.

        Args:
            instance_url: Instance root, e.g. ``https://snow.example``.
            auth: Explicit auth flow, ``"basic"`` or ``"oauth2"``. When
                omitted, ``oauth2`` is used if ``client_id`` is set.
            username: Basic-auth user (also the OAuth2 password-grant user).
            password: Basic-auth password.
            client_id: OAuth2 client id.
            client_secret: OAuth2 client secret.
            allow_private_ips: Opt into private/loopback/link-local endpoints.
                Defaults to False (SSRF-safe).
            **config: Extra options, notably ``timeout``, ``max_retries``,
                ``backoff_factor``, ``headers``.
        """
        self.logger = _logger
        self.instance_url = (
            instance_url or os.getenv("SERVICENOW_INSTANCE_URL") or ""
        ).rstrip("/")
        self.auth = (auth or os.getenv("SERVICENOW_AUTH") or "").lower()
        self.username = username or os.getenv("SERVICENOW_USERNAME")
        self.password = password or os.getenv("SERVICENOW_PASSWORD")
        self.client_id = client_id or os.getenv("SERVICENOW_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SERVICENOW_CLIENT_SECRET")
        self.allow_private_ips = parse_bool(
            config.pop("allow_private_ips", allow_private_ips), default=False
        )
        self.config = config

        if not self.instance_url:
            raise ValidationError(
                "ServiceNow instance_url is required. Provide via 'instance_url' "
                "or SERVICENOW_INSTANCE_URL environment variable."
            )
        parsed = urlparse(self.instance_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValidationError(
                f"ServiceNow instance_url must be an absolute http(s) URL, "
                f"got {self.instance_url!r}."
            )
        if parsed.query or parsed.fragment:
            raise ValidationError(
                f"ServiceNow instance_url must not carry a query or fragment "
                f"component, got {self.instance_url!r}."
            )

        if not self.auth:
            self.auth = "oauth2" if self.client_id else "basic"
        if self.auth in ("oauth2", "oauth"):
            self.auth = "oauth2"
            if not (self.client_id and self.client_secret):
                raise ValidationError(
                    "ServiceNow OAuth2 flow requires client_id and client_secret."
                )
        elif self.auth == "basic":
            if not (self.username and self.password):
                raise ValidationError(
                    "ServiceNow Basic flow requires username and password."
                )
        else:
            raise ValidationError(
                f"ServiceNow auth must be 'basic' or 'oauth2', got {self.auth!r}."
            )

        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.config.get("max_retries", 3),
            backoff_factor=self.config.get("backoff_factor", 1),
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers["Accept"] = "application/json"
        default_headers = self.config.get("headers", {})
        if default_headers:
            self.session.headers.update(default_headers)

        self._token: Optional[str] = None
        self.logger.debug(
            "ServiceNow connector initialized (instance=%s, auth=%s, "
            "allow_private_ips=%s)",
            self.instance_url,
            self.auth,
            self.allow_private_ips,
        )

    @property
    def token_url(self) -> str:
        return self.instance_url + _TOKEN_PATH

    def get_session(self) -> requests.Session:
        """Return an authenticated session for Table API requests.

        Basic credentials are attached eagerly; for OAuth2 a token is
        fetched (and cached) on first use. The token is not refreshed, so a
        job that runs past its TTL will fail with 401 -- re-create the
        connector instead.
        """
        if self.auth == "basic":
            self.session.headers["Authorization"] = "Basic " + self._basic_header()
            return self.session
        if self._token is None:
            self._token = self._fetch_token()
        self.session.headers["Authorization"] = "Bearer " + self._token
        return self.session

    def _basic_header(self) -> str:
        pair = f"{self.username}:{self.password or ''}".encode("utf-8")
        return base64.b64encode(pair).decode("ascii")

    def _fetch_token(self) -> str:
        """Perform the OAuth2 token exchange (SSRF-guarded)."""
        body: Dict[str, str] = {
            "client_id": self.client_id or "",
            "client_secret": self.client_secret or "",
        }
        if self.username and self.password:
            body["grant_type"] = "password"
            body["username"] = self.username
            body["password"] = self.password
        else:
            body["grant_type"] = "client_credentials"
        resp = request_with_ssrf_guard(
            "POST",
            self.token_url,
            session=self.session,
            allow_private_ips=self.allow_private_ips,
            allow_private_ips_on_redirect=False,
            data=body,
            timeout=self.config.get("timeout", 30),
        )
        try:
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ProcessingError(
                f"ServiceNow OAuth2 token exchange failed: {exc}"
            ) from exc
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProcessingError(
                "ServiceNow OAuth2 token endpoint did not return JSON."
            ) from exc
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise ProcessingError(
                "ServiceNow OAuth2 token response missing 'access_token'."
            )
        return str(token)

    def close(self) -> None:
        """Close the underlying :mod:`requests` session."""
        self.session.close()


class ServiceNowIngestor:
    """Ingest records from a ServiceNow table.

    Example usage::

        >>> from semantica.ingest import ServiceNowIngestor
        >>> ing = ServiceNowIngestor(
        ...     instance_url="https://snow.example",
        ...     username="u", password="p",   # or client_id/client_secret
        ... )
        >>> data = ing.ingest_table("cmdb_ci_server", query="operational_status=1")
        >>> docs = ing.export_as_documents(data)
    """

    def __init__(
        self,
        instance_url: Optional[str] = None,
        connector: Optional[ServiceNowConnector] = None,
        **config: Any,
    ) -> None:
        """Initialize the ServiceNow ingestor.

        Args:
            instance_url: Instance root URL. Ignored if ``connector`` is given.
            connector: An existing :class:`ServiceNowConnector`.
            **config: Passed to :class:`ServiceNowConnector` when one is
                created.
        """
        self.logger = _logger
        self.connector = connector or ServiceNowConnector(
            instance_url=instance_url, **config
        )

    def ingest_table(
        self,
        table: Optional[str] = None,
        *,
        query: Optional[str] = None,
        fields: Optional[Union[str, Sequence[str]]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        batch_size: int = 100,
        display_value: Union[bool, str] = False,
        exclude_reference_link: bool = True,
    ) -> ServiceNowData:
        """Fetch pages of *table* from the Table API.

        Args:
            table: Table name, e.g. ``"incident"`` or ``"cmdb_ci_server"``.
            query: Encoded query for ``sysparm_query``
                (e.g. ``"active=true^priority=1"``).
            fields: Field names for ``sysparm_fields`` (list or comma string).
            limit: Maximum number of rows to return.
            offset: Number of leading rows to skip.
            batch_size: ``sysparm_limit`` per request.
            display_value: ``sysparm_display_value`` -- ``False`` (raw
                values), ``True`` (display values) or ``"all"`` (both).
            exclude_reference_link: Drop ``link`` objects from reference
                fields (``sysparm_exclude_reference_link``).

        Returns:
            A single :class:`ServiceNowData` holding every fetched record.
        """
        if not table:
            raise ValidationError("ServiceNow 'table' is required.")
        if limit is not None and limit < 0:
            raise ValidationError("ServiceNow 'limit' must be >= 0 (got %r)" % limit)
        if offset < 0:
            raise ValidationError("ServiceNow 'offset' must be >= 0 (got %r)" % offset)
        if batch_size <= 0:
            raise ValidationError(
                "ServiceNow 'batch_size' must be > 0 (got %r)" % batch_size
            )
        instance = self.connector.instance_url
        if limit == 0:
            return ServiceNowData(records=[], table=table, count=0, instance=instance)

        url = instance + _TABLE_API + table
        session = self.connector.get_session()
        records: List[Dict[str, Any]] = []
        current_offset = offset
        base_params = self._query_params(
            query, fields, display_value, exclude_reference_link
        )

        while True:
            page_size = batch_size
            if limit is not None:
                page_size = min(batch_size, limit - len(records))
            params = dict(base_params)
            params["sysparm_limit"] = str(page_size)
            params["sysparm_offset"] = str(current_offset)

            resp = request_with_ssrf_guard(
                "GET",
                url,
                session=session,
                allow_private_ips=self.connector.allow_private_ips,
                allow_private_ips_on_redirect=False,
                params=params,
                timeout=self.connector.config.get("timeout", 30),
            )
            try:
                resp.raise_for_status()
            except requests.exceptions.RequestException as exc:
                self.logger.error("Failed to fetch ServiceNow table %s: %s", table, exc)
                raise ProcessingError(
                    f"Failed to fetch ServiceNow table {table}: {exc}"
                ) from exc

            rows = self._parse_page(resp)
            for raw_row in rows:
                records.append(
                    raw_row if isinstance(raw_row, dict) else {"value": raw_row}
                )

            self.logger.debug(
                "Fetched %d rows from %s (offset=%d)", len(rows), table, current_offset
            )
            if len(rows) < page_size:
                break
            if limit is not None and len(records) >= limit:
                break
            current_offset += len(rows)

        return ServiceNowData(
            records=records, table=table, count=len(records), instance=instance
        )

    @staticmethod
    def _query_params(
        query: Optional[str],
        fields: Optional[Union[str, Sequence[str]]],
        display_value: Union[bool, str],
        exclude_reference_link: bool,
    ) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if query:
            params["sysparm_query"] = query
        if fields:
            if not isinstance(fields, str):
                fields = ",".join(fields)
            selected = [f.strip() for f in fields.split(",") if f.strip()]
            if "sys_id" not in selected:
                selected.insert(0, "sys_id")
            params["sysparm_fields"] = ",".join(selected)
        if isinstance(display_value, str):
            params["sysparm_display_value"] = display_value
        else:
            params["sysparm_display_value"] = "true" if display_value else "false"
        if exclude_reference_link:
            params["sysparm_exclude_reference_link"] = "true"
        return params

    @staticmethod
    def _parse_page(resp: requests.Response) -> List[Any]:
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProcessingError(
                f"ServiceNow Table API response is not JSON: {exc}"
            ) from exc
        rows = payload.get("result") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ProcessingError(
                "ServiceNow Table API payload has no 'result' list (got %s)"
                % type(rows).__name__
            )
        return rows

    def export_as_documents(self, data: ServiceNowData) -> List[Dict[str, Any]]:
        """Convert ingested records to flat document dicts for ``GraphBuilder``."""
        return data.to_documents()

    def close(self) -> None:
        """Close the underlying connector's session."""
        self.connector.close()
