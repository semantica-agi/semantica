"""
Tableau Ingestion Module

This module provides Tableau workbook and datasource metadata ingestion for
the Semantica framework, enabling extraction of workbooks, published data
sources, and field definitions from Tableau Server or Tableau Cloud via the
Tableau REST API.

Key Features:
    - Personal Access Token (PAT) and username/password authentication
    - Workbook and datasource metadata ingestion
    - Field-level schema discovery for published datasources
    - Progress tracking and structured error handling
    - Connection management with context-manager support

Main Classes:
    - TableauConnector: Manages the tableauserverclient authentication lifecycle
    - TableauData: Dataclass representing ingested Tableau metadata
    - TableauIngestor: Orchestrates ingestion operations

Optional Dependency:
    Install via the ``ingest-tableau`` extra::

        pip install "semantica[ingest-tableau]"

    or directly::

        pip install tableauserverclient>=0.25

Example Usage::

    >>> import os
    >>> from semantica.ingest import TableauIngestor
    >>> ingestor = TableauIngestor(
    ...     server_url=os.getenv("TABLEAU_SERVER_URL"),
    ...     token_name=os.getenv("TABLEAU_TOKEN_NAME"),
    ...     token_value=os.getenv("TABLEAU_TOKEN_VALUE"),
    ... )

Author: Semantica Contributors
License: MIT
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

# ---------------------------------------------------------------------------
# Optional-dependency guard — mirrors the pattern in salesforce_ingestor.
# The module always imports cleanly; the guard fires at instantiation time
# via the TABLEAU_AVAILABLE check in __init__.
# ---------------------------------------------------------------------------
try:
    import tableauserverclient as TSC  # type: ignore[import]

    TABLEAU_AVAILABLE = True
except (ImportError, OSError):
    TSC = None  # type: ignore[assignment]
    TABLEAU_AVAILABLE = False


logger = get_logger("tableau_ingestor")


# ---------------------------------------------------------------------------
# TableauData
# ---------------------------------------------------------------------------


@dataclass
class TableauData:
    """Metadata ingested from Tableau Server or Tableau Cloud.

    Attributes:
        workbooks: List of workbook metadata dictionaries.  Each entry
            contains at minimum ``id``, ``name``, ``project_name``,
            ``owner_id``, and ``content_url``.
        datasources: List of published datasource metadata dictionaries.
            Each entry contains at minimum ``id``, ``name``,
            ``project_name``, and ``content_url``.
        fields: List of field metadata dictionaries when a specific
            datasource was introspected (via :meth:`TableauIngestor.ingest_fields`).
            Empty list otherwise.
        server_url: Tableau Server / Cloud base URL used for the ingestion.
        site_name: Tableau site name (empty string for the default site).
        row_count: Total number of items across ``workbooks``,
            ``datasources``, and ``fields`` combined.
        metadata: Arbitrary extra metadata populated by ingestion methods.
        ingested_at: Timestamp recorded when this object was created.
    """

    workbooks: List[Dict[str, Any]] = field(default_factory=list)
    datasources: List[Dict[str, Any]] = field(default_factory=list)
    fields: List[Dict[str, Any]] = field(default_factory=list)
    server_url: Optional[str] = None
    site_name: Optional[str] = None
    row_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# TableauConnector
# ---------------------------------------------------------------------------


class TableauConnector:
    """Manages the tableauserverclient authentication lifecycle.

    Supports two authentication modes:

    **Personal Access Token (PAT)** — recommended for production::

        connector = TableauConnector(
            server_url="https://prod.tableau.example.com",
            site_name="",               # empty string = default site
            token_name="my-pat",
            token_value=os.getenv("TABLEAU_TOKEN_VALUE"),
        )

    **Username / Password**::

        connector = TableauConnector(
            server_url="https://prod.tableau.example.com",
            username=os.getenv("TABLEAU_USERNAME"),
            password=os.getenv("TABLEAU_PASSWORD"),
        )

    Environment Variables
    ----------------------
    Every constructor parameter has an environment-variable fallback:

    * ``TABLEAU_SERVER_URL``
    * ``TABLEAU_SITE_NAME``   (default: ``""``)
    * ``TABLEAU_TOKEN_NAME``
    * ``TABLEAU_TOKEN_VALUE``
    * ``TABLEAU_USERNAME``
    * ``TABLEAU_PASSWORD``

    Raises:
        ImportError: If ``tableauserverclient`` is not installed.
        ValidationError: If no usable credential set is provided.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        site_name: Optional[str] = None,
        token_name: Optional[str] = None,
        token_value: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        if not TABLEAU_AVAILABLE:
            raise ImportError(
                "tableauserverclient is required for TableauConnector. "
                'Install it with: pip install "semantica[ingest-tableau]" '
                "or: pip install tableauserverclient>=0.25"
            )

        self.logger = get_logger("tableau_connector")

        self.server_url: Optional[str] = server_url or os.getenv("TABLEAU_SERVER_URL")
        self.site_name: str = (
            site_name
            if site_name is not None
            else os.getenv("TABLEAU_SITE_NAME", "")
        )
        self._token_name: Optional[str] = token_name or os.getenv("TABLEAU_TOKEN_NAME")
        self._token_value: Optional[str] = token_value or os.getenv("TABLEAU_TOKEN_VALUE")
        self._username: Optional[str] = username or os.getenv("TABLEAU_USERNAME")
        self._password: Optional[str] = password or os.getenv("TABLEAU_PASSWORD")

        # Internal server reference — None until connect() is called.
        self._server: Optional[Any] = None

        self._validate_auth()

        self.logger.debug(
            "Tableau connector initialised: server_url=%s site_name=%s",
            self.server_url or "<unset>",
            self.site_name or "<default>",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_auth(self) -> None:
        """Raise ValidationError if no usable authentication path is present."""
        has_pat = bool(self._token_name and self._token_value)
        has_password = bool(self._username and self._password)

        if not self.server_url:
            raise ValidationError(
                "Tableau server_url is required. Pass it directly or set "
                "TABLEAU_SERVER_URL in the environment."
            )
        if not (has_pat or has_password):
            raise ValidationError(
                "Tableau authentication requires either a Personal Access Token "
                "(token_name + token_value) or username/password credentials. "
                "Pass them directly or set TABLEAU_TOKEN_NAME + TABLEAU_TOKEN_VALUE "
                "or TABLEAU_USERNAME + TABLEAU_PASSWORD in the environment."
            )

    # ------------------------------------------------------------------
    # Public lifecycle methods
    # ------------------------------------------------------------------

    def connect(self) -> Any:
        """Authenticate to Tableau and return the active server client.

        Returns the existing client immediately if already connected.

        Returns:
            An authenticated ``tableauserverclient.Server`` instance.

        Raises:
            ProcessingError: If authentication fails.
        """
        if self._server is not None:
            return self._server

        try:
            server = TSC.Server(self.server_url, use_server_version=True)

            if self._token_name and self._token_value:
                auth = TSC.PersonalAccessTokenAuth(
                    self._token_name,
                    self._token_value,
                    site_id=self.site_name,
                )
            else:
                auth = TSC.TableauAuth(
                    self._username,
                    self._password,
                    site_id=self.site_name,
                )

            server.auth.sign_in(auth)
            self._server = server
            self.logger.debug("Tableau authentication successful.")
            return self._server

        except Exception as exc:
            raise ProcessingError(
                f"Failed to authenticate to Tableau: {type(exc).__name__}"
            ) from exc

    def disconnect(self) -> None:
        """Sign out from Tableau and release the client."""
        if self._server is not None:
            try:
                self._server.auth.sign_out()
            except Exception:  # noqa: BLE001
                pass
            self._server = None
            self.logger.debug("Tableau connection closed.")

    def test_connection(self) -> bool:
        """Return True if a connection can be established, False otherwise."""
        try:
            server = self.connect()
            return server is not None
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# TableauIngestor
# ---------------------------------------------------------------------------


class TableauIngestor:
    """Ingests workbook and datasource metadata from Tableau Server or Cloud.

    Args:
        server_url: Tableau Server or Cloud base URL.
        site_name: Tableau site name (empty string for the default site).
        token_name: Personal Access Token name.
        token_value: Personal Access Token value.
        username: Tableau username (alternative to PAT).
        password: Tableau password (alternative to PAT).
        config: Optional extra configuration.
        **kwargs: Additional keyword arguments merged into ``config``.

    Example::

        import os
        from semantica.ingest import TableauIngestor

        with TableauIngestor(
            server_url=os.getenv("TABLEAU_SERVER_URL"),
            token_name=os.getenv("TABLEAU_TOKEN_NAME"),
            token_value=os.getenv("TABLEAU_TOKEN_VALUE"),
        ) as t:
            data = t.ingest_workbooks()
            docs = t.export_as_documents(data)
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        site_name: Optional[str] = None,
        token_name: Optional[str] = None,
        token_value: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.logger = get_logger("tableau_ingestor")
        self.config: Dict[str, Any] = config or {}
        self.config.update(kwargs)

        self.connector = TableauConnector(
            server_url=server_url,
            site_name=site_name,
            token_name=token_name,
            token_value=token_value,
            username=username,
            password=password,
        )

        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Tableau ingestor initialised.")

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "TableauIngestor":
        self.connector.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Sign out from Tableau and release the connection."""
        self.connector.disconnect()

    # ------------------------------------------------------------------
    # Ingestion methods
    # ------------------------------------------------------------------

    def ingest_workbooks(
        self,
        project_name: Optional[str] = None,
    ) -> TableauData:
        """Fetch metadata for all accessible workbooks.

        Args:
            project_name: Optional project filter.  When provided, only
                workbooks belonging to that project are returned.

        Returns:
            :class:`TableauData` with ``workbooks`` populated.

        Raises:
            ProcessingError: If the Tableau API call fails.
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="ingest",
            submodule="TableauIngestor",
            message="Fetching workbooks…",
        )

        try:
            already_connected = self.connector._server is not None
            server = self.connector.connect()

            try:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Listing workbooks from Tableau…"
                )

                all_workbooks, _ = server.workbooks.get()
                workbooks = []
                for wb in all_workbooks:
                    if project_name and wb.project_name != project_name:
                        continue
                    workbooks.append(
                        {
                            "id": wb.id,
                            "name": wb.name,
                            "project_name": wb.project_name,
                            "owner_id": wb.owner_id,
                            "content_url": wb.content_url,
                            "show_tabs": wb.show_tabs,
                            "size": wb.size,
                            "created_at": str(wb.created_at) if wb.created_at else None,
                            "updated_at": str(wb.updated_at) if wb.updated_at else None,
                        }
                    )

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Fetched {len(workbooks)} workbooks",
                )
                self.logger.info("Workbook ingestion completed: %d workbook(s)", len(workbooks))

                return TableauData(
                    workbooks=workbooks,
                    server_url=self.connector.server_url,
                    site_name=self.connector.site_name,
                    row_count=len(workbooks),
                    metadata={"project_filter": project_name},
                )

            finally:
                if not already_connected:
                    self.connector.disconnect()

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(tracking_id, status="failed", message="Failed")
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error("Failed to ingest workbooks: %s", type(exc).__name__)
            raise ProcessingError(
                f"Failed to ingest Tableau workbooks: {type(exc).__name__}"
            ) from exc

    def ingest_datasources(
        self,
        project_name: Optional[str] = None,
    ) -> TableauData:
        """Fetch metadata for all accessible published datasources.

        Args:
            project_name: Optional project filter.

        Returns:
            :class:`TableauData` with ``datasources`` populated.

        Raises:
            ProcessingError: If the Tableau API call fails.
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="ingest",
            submodule="TableauIngestor",
            message="Fetching datasources…",
        )

        try:
            already_connected = self.connector._server is not None
            server = self.connector.connect()

            try:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Listing datasources from Tableau…"
                )

                all_datasources, _ = server.datasources.get()
                datasources = []
                for ds in all_datasources:
                    if project_name and ds.project_name != project_name:
                        continue
                    datasources.append(
                        {
                            "id": ds.id,
                            "name": ds.name,
                            "project_name": ds.project_name,
                            "content_url": ds.content_url,
                            "type": ds.datasource_type,
                            "created_at": str(ds.created_at) if ds.created_at else None,
                            "updated_at": str(ds.updated_at) if ds.updated_at else None,
                        }
                    )

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Fetched {len(datasources)} datasources",
                )
                self.logger.info(
                    "Datasource ingestion completed: %d datasource(s)", len(datasources)
                )

                return TableauData(
                    datasources=datasources,
                    server_url=self.connector.server_url,
                    site_name=self.connector.site_name,
                    row_count=len(datasources),
                    metadata={"project_filter": project_name},
                )

            finally:
                if not already_connected:
                    self.connector.disconnect()

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(tracking_id, status="failed", message="Failed")
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error("Failed to ingest datasources: %s", type(exc).__name__)
            raise ProcessingError(
                f"Failed to ingest Tableau datasources: {type(exc).__name__}"
            ) from exc

    def ingest_fields(self, datasource_id: str) -> TableauData:
        """Fetch field-level metadata for a specific published datasource.

        Calls the Tableau REST API datasource connections/fields endpoint to
        enumerate fields, their data types, and descriptions.

        Args:
            datasource_id: The LUID of the published datasource.

        Returns:
            :class:`TableauData` with ``fields`` populated.

        Raises:
            ValidationError: If *datasource_id* is empty or not a string.
            ProcessingError: If the Tableau API call fails.
        """
        if not datasource_id or not isinstance(datasource_id, str):
            raise ValidationError("datasource_id must be a non-empty string.")

        tracking_id = self.progress_tracker.start_tracking(
            module="ingest",
            submodule="TableauIngestor",
            message=f"Fetching fields for datasource {datasource_id}…",
        )

        try:
            already_connected = self.connector._server is not None
            server = self.connector.connect()

            try:
                self.progress_tracker.update_tracking(
                    tracking_id, message="Querying datasource fields…"
                )

                ds_item = TSC.DatasourceItem(project_id="")
                ds_item._id = datasource_id

                connections, _ = server.datasources.connections(ds_item)
                fields: List[Dict[str, Any]] = []
                for conn in connections:
                    for field_item in getattr(conn, "fields", []):
                        fields.append(
                            {
                                "name": getattr(field_item, "name", None),
                                "type": getattr(field_item, "data_type", None),
                                "description": getattr(field_item, "description", None),
                                "connection_id": conn.id,
                            }
                        )

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Fetched {len(fields)} field(s)",
                )
                self.logger.info("Field ingestion completed: %d field(s)", len(fields))

                return TableauData(
                    fields=fields,
                    server_url=self.connector.server_url,
                    site_name=self.connector.site_name,
                    row_count=len(fields),
                    metadata={"datasource_id": datasource_id},
                )

            finally:
                if not already_connected:
                    self.connector.disconnect()

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(tracking_id, status="failed", message="Failed")
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error(
                "Failed to ingest fields for datasource %s: %s",
                datasource_id,
                type(exc).__name__,
            )
            raise ProcessingError(
                f"Failed to ingest Tableau datasource fields for '{datasource_id}': "
                f"{type(exc).__name__}"
            ) from exc

    def export_as_documents(
        self,
        data: TableauData,
    ) -> List[Dict[str, Any]]:
        """Convert :class:`TableauData` to the Semantica document format.

        Produces the ``{id, text, metadata}`` shape used by other ingestors,
        making :class:`TableauData` directly usable with ``GraphBuilder``.

        Workbooks and datasources are each converted to one document; fields
        are each converted individually.

        Args:
            data: A :class:`TableauData` object returned by one of the
                ingestion methods.

        Returns:
            List of document dictionaries::

                [
                    {
                        "id": str,
                        "text": str,
                        "metadata": {
                            "source": "tableau",
                            "type": "workbook" | "datasource" | "field",
                            "server_url": ...,
                            "site_name": ...,
                            "row_data": {...},
                        },
                    },
                    ...
                ]
        """
        documents: List[Dict[str, Any]] = []

        for wb in data.workbooks:
            doc_id = str(wb.get("id", ""))
            text_parts = [wb.get("name", ""), wb.get("project_name", "")]
            documents.append(
                {
                    "id": doc_id,
                    "text": " ".join(p for p in text_parts if p),
                    "metadata": {
                        "source": "tableau",
                        "type": "workbook",
                        "server_url": data.server_url,
                        "site_name": data.site_name,
                        "row_data": wb,
                    },
                }
            )

        for ds in data.datasources:
            doc_id = str(ds.get("id", ""))
            text_parts = [ds.get("name", ""), ds.get("project_name", "")]
            documents.append(
                {
                    "id": doc_id,
                    "text": " ".join(p for p in text_parts if p),
                    "metadata": {
                        "source": "tableau",
                        "type": "datasource",
                        "server_url": data.server_url,
                        "site_name": data.site_name,
                        "row_data": ds,
                    },
                }
            )

        for f in data.fields:
            doc_id = f"{f.get('connection_id', '')}_{f.get('name', '')}"
            text_parts = [f.get("name", ""), f.get("description", "")]
            documents.append(
                {
                    "id": doc_id,
                    "text": " ".join(p for p in text_parts if p),
                    "metadata": {
                        "source": "tableau",
                        "type": "field",
                        "server_url": data.server_url,
                        "site_name": data.site_name,
                        "row_data": f,
                    },
                }
            )

        self.logger.debug(
            "export_as_documents: exported %d document(s)", len(documents)
        )
        return documents
