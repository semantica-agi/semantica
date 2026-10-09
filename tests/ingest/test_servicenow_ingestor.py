"""Tests for the ServiceNow Table API ingestor.

The connector never touches a live instance: every outbound request goes
through ``semantica.ingest.ssrf.request_with_ssrf_guard``, so these tests
patch that single entry point and drive the connector / ingestor with canned
responses.

Covered:
- Basic and OAuth2 (client-credentials and password grant) credential flows
- SSRF guard is used for data *and* token-exchange requests
- ``sysparm_limit``/``sysparm_offset`` pagination, ``limit``/``offset``
- query / fields / display_value passthrough
- error paths (HTTP error, non-JSON body, malformed payload, bad arguments)
- ``export_as_documents`` yields the flat document shape GraphBuilder expects
"""

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests

from semantica.ingest import (
    ServiceNowConnector,
    ServiceNowData,
    ServiceNowIngestor,
)
from semantica.utils.exceptions import ProcessingError, ValidationError

GUARD = "semantica.ingest.servicenow_ingestor.request_with_ssrf_guard"
INSTANCE = "https://snow.example"


def _json_resp(payload, url=INSTANCE, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": "application/json"}
    resp.text = ""
    resp.url = url
    if payload is None:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = payload
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status_code} error"
        )
    return resp


def _result(*rows):
    return {"result": list(rows)}


def _basic_ingestor(**kw):
    return ServiceNowIngestor(instance_url=INSTANCE, username="u", password="p", **kw)


class TestConnectorAuth:
    def test_requires_instance_url(self, monkeypatch):
        monkeypatch.delenv("SERVICENOW_INSTANCE_URL", raising=False)
        with pytest.raises(ValidationError):
            ServiceNowConnector(username="u", password="p")

    def test_rejects_non_http_instance_url(self):
        with pytest.raises(ValidationError):
            ServiceNowConnector(instance_url="snow.example", username="u", password="p")

    def test_requires_credentials(self, monkeypatch):
        for var in (
            "SERVICENOW_USERNAME",
            "SERVICENOW_PASSWORD",
            "SERVICENOW_CLIENT_ID",
            "SERVICENOW_CLIENT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ValidationError):
            ServiceNowConnector(instance_url=INSTANCE)

    def test_oauth2_requires_client_secret(self):
        with pytest.raises(ValidationError):
            ServiceNowConnector(instance_url=INSTANCE, client_id="cid")

    def test_unknown_auth_rejected(self):
        with pytest.raises(ValidationError):
            ServiceNowConnector(
                instance_url=INSTANCE, auth="token", username="u", password="p"
            )

    def test_trailing_slash_stripped(self):
        conn = ServiceNowConnector(
            instance_url=INSTANCE + "/", username="u", password="p"
        )
        assert conn.instance_url == INSTANCE
        assert conn.token_url == INSTANCE + "/oauth_token.do"

    def test_rejects_instance_url_with_query(self):
        with pytest.raises(ValidationError):
            ServiceNowConnector(
                instance_url=INSTANCE + "/?x=1", username="u", password="p"
            )

    def test_rejects_instance_url_with_fragment(self):
        with pytest.raises(ValidationError):
            ServiceNowConnector(
                instance_url=INSTANCE + "/#x", username="u", password="p"
            )

    def test_env_configuration(self, monkeypatch):
        monkeypatch.setenv("SERVICENOW_INSTANCE_URL", INSTANCE)
        monkeypatch.setenv("SERVICENOW_USERNAME", "eu")
        monkeypatch.setenv("SERVICENOW_PASSWORD", "ep")
        conn = ServiceNowConnector()
        assert conn.auth == "basic"
        assert conn.username == "eu"

    def test_basic_auth_header_attached(self):
        conn = ServiceNowConnector(instance_url=INSTANCE, username="u", password="p")
        session = conn.get_session()
        expected = base64.b64encode(b"u:p").decode("ascii")
        assert session.headers["Authorization"] == "Basic " + expected
        assert session.headers["Accept"] == "application/json"

    def test_allow_private_ips_string_false_is_false(self):
        conn = ServiceNowConnector(
            instance_url=INSTANCE,
            username="u",
            password="p",
            allow_private_ips="false",
        )
        assert conn.allow_private_ips is False

    def test_oauth_client_credentials_exchange_goes_through_ssrf(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp({"access_token": "tok-123"})
            conn = ServiceNowConnector(
                instance_url=INSTANCE, client_id="cid", client_secret="sec"
            )
            session = conn.get_session()
            session = conn.get_session()

        assert guard.call_count == 1
        method, url = guard.call_args[0]
        assert method == "POST"
        assert url == INSTANCE + "/oauth_token.do"
        body = guard.call_args[1]["data"]
        assert body["grant_type"] == "client_credentials"
        assert body["client_id"] == "cid"
        assert session.headers["Authorization"] == "Bearer tok-123"

    def test_token_exchange_pins_private_ip_trust_to_original_host(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp({"access_token": "tok-123"})
            conn = ServiceNowConnector(
                instance_url=INSTANCE, client_id="cid", client_secret="sec"
            )
            conn.get_session()
        assert guard.call_args[1]["allow_private_ips_on_redirect"] is False

    def test_oauth_password_grant_when_user_credentials_present(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp({"access_token": "tok"})
            conn = ServiceNowConnector(
                instance_url=INSTANCE,
                client_id="cid",
                client_secret="sec",
                username="u",
                password="p",
            )
            conn.get_session()

        body = guard.call_args[1]["data"]
        assert body["grant_type"] == "password"
        assert body["username"] == "u"
        assert body["password"] == "p"

    def test_oauth_token_http_error_raises_processing_error(self):
        with patch(GUARD, return_value=_json_resp({}, status_code=401)):
            conn = ServiceNowConnector(
                instance_url=INSTANCE, client_id="cid", client_secret="sec"
            )
            with pytest.raises(ProcessingError):
                conn.get_session()

    def test_oauth_token_missing_access_token(self):
        with patch(GUARD, return_value=_json_resp({"error": "invalid"})):
            conn = ServiceNowConnector(
                instance_url=INSTANCE, client_id="cid", client_secret="sec"
            )
            with pytest.raises(ProcessingError):
                conn.get_session()

    def test_oauth_token_non_json(self):
        with patch(GUARD, return_value=_json_resp(None)):
            conn = ServiceNowConnector(
                instance_url=INSTANCE, client_id="cid", client_secret="sec"
            )
            with pytest.raises(ProcessingError):
                conn.get_session()


class TestIngestTable:
    def test_single_page_routes_via_ssrf(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result({"sys_id": "1", "number": "INC1"}))
            data = _basic_ingestor().ingest_table("incident")

        assert guard.call_count == 1
        method, url = guard.call_args[0]
        assert method == "GET"
        assert url == INSTANCE + "/api/now/table/incident"
        kwargs = guard.call_args[1]
        assert kwargs["allow_private_ips"] is False
        assert kwargs["params"]["sysparm_limit"] == "100"
        assert kwargs["params"]["sysparm_offset"] == "0"
        assert data.count == 1
        assert data.table == "incident"
        assert data.instance == INSTANCE
        assert data.records == [{"sys_id": "1", "number": "INC1"}]

    def test_offset_pagination_walks_until_short_page(self):
        pages = [
            _result({"sys_id": "1"}, {"sys_id": "2"}),
            _result({"sys_id": "3"}, {"sys_id": "4"}),
            _result({"sys_id": "5"}),
        ]
        offsets = []

        def fake_guard(method, url, **kw):
            offsets.append(kw["params"]["sysparm_offset"])
            return _json_resp(pages[len(offsets) - 1], url)

        with patch(GUARD, side_effect=fake_guard):
            data = _basic_ingestor().ingest_table("cmdb_ci", batch_size=2)

        assert offsets == ["0", "2", "4"]
        assert [r["sys_id"] for r in data.records] == ["1", "2", "3", "4", "5"]
        assert data.count == 5

    def test_exact_multiple_stops_on_empty_page(self):
        pages = [_result({"sys_id": "1"}, {"sys_id": "2"}), _result()]
        calls = []

        def fake_guard(method, url, **kw):
            calls.append(url)
            return _json_resp(pages[len(calls) - 1], url)

        with patch(GUARD, side_effect=fake_guard):
            data = _basic_ingestor().ingest_table("cmdb_ci", batch_size=2)

        assert len(calls) == 2
        assert data.count == 2

    def test_limit_caps_rows_and_page_size(self):
        sizes = []

        def fake_guard(method, url, **kw):
            sizes.append(kw["params"]["sysparm_limit"])
            n = int(kw["params"]["sysparm_limit"])
            return _json_resp(_result(*({"sys_id": str(i)} for i in range(n))), url)

        with patch(GUARD, side_effect=fake_guard):
            data = _basic_ingestor().ingest_table("incident", limit=5, batch_size=2)

        assert sizes == ["2", "2", "1"]
        assert data.count == 5

    def test_offset_passthrough(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result({"sys_id": "9"}))
            _basic_ingestor().ingest_table("incident", offset=40)
        assert guard.call_args[1]["params"]["sysparm_offset"] == "40"

    def test_limit_zero_returns_no_rows_and_makes_no_request(self):
        with patch(GUARD) as guard:
            data = _basic_ingestor().ingest_table("incident", limit=0)
        assert guard.call_count == 0
        assert data.count == 0
        assert data.records == []

    def test_query_fields_display_value_passthrough(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result())
            _basic_ingestor().ingest_table(
                "incident",
                query="active=true^priority=1",
                fields=["sys_id", "number"],
                display_value="all",
                exclude_reference_link=False,
            )
        params = guard.call_args[1]["params"]
        assert params["sysparm_query"] == "active=true^priority=1"
        assert params["sysparm_fields"] == "sys_id,number"
        assert params["sysparm_display_value"] == "all"
        assert "sysparm_exclude_reference_link" not in params

    def test_default_params(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result())
            _basic_ingestor().ingest_table("incident", fields="sys_id,name")
        params = guard.call_args[1]["params"]
        assert params["sysparm_display_value"] == "false"
        assert params["sysparm_exclude_reference_link"] == "true"
        assert params["sysparm_fields"] == "sys_id,name"
        assert "sysparm_query" not in params

    def test_field_selection_always_includes_sys_id(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result())
            _basic_ingestor().ingest_table("incident", fields=["number", "priority"])
        selected = guard.call_args[1]["params"]["sysparm_fields"].split(",")
        assert "sys_id" in selected
        assert selected == ["sys_id", "number", "priority"]

    def test_field_selection_keeps_sys_id_once_when_already_requested(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result())
            _basic_ingestor().ingest_table("incident", fields="number,sys_id")
        selected = guard.call_args[1]["params"]["sysparm_fields"].split(",")
        assert selected.count("sys_id") == 1
        assert selected == ["number", "sys_id"]

    def test_data_request_pins_private_ip_trust_to_original_host(self):
        with patch(GUARD) as guard:
            guard.return_value = _json_resp(_result())
            _basic_ingestor().ingest_table("incident")
        assert guard.call_args[1]["allow_private_ips_on_redirect"] is False

    def test_requires_table(self):
        with pytest.raises(ValidationError):
            _basic_ingestor().ingest_table()

    def test_negative_limit_rejected(self):
        with pytest.raises(ValidationError):
            _basic_ingestor().ingest_table("incident", limit=-1)

    def test_negative_offset_rejected(self):
        with pytest.raises(ValidationError):
            _basic_ingestor().ingest_table("incident", offset=-1)

    def test_zero_batch_size_rejected(self):
        with pytest.raises(ValidationError):
            _basic_ingestor().ingest_table("incident", batch_size=0)

    def test_http_error_raises_processing_error(self):
        with patch(GUARD, return_value=_json_resp({}, status_code=403)):
            with pytest.raises(ProcessingError):
                _basic_ingestor().ingest_table("incident")

    def test_non_json_response_raises_processing_error(self):
        with patch(GUARD, return_value=_json_resp(None)):
            with pytest.raises(ProcessingError):
                _basic_ingestor().ingest_table("incident")

    def test_malformed_result_rejected(self):
        with patch(GUARD, return_value=_json_resp({"result": {"sys_id": "1"}})):
            with pytest.raises(ProcessingError):
                _basic_ingestor().ingest_table("incident")

    def test_close_closes_session(self):
        ing = _basic_ingestor()
        with patch.object(ing.connector.session, "close") as close:
            ing.close()
        close.assert_called_once()


class TestExportAsDocuments:
    def test_export_flattens_to_graph_builder_shape(self):
        data = ServiceNowData(
            records=[
                {"sys_id": "abc", "number": "INC0001", "short_description": "Down"},
                {"sys_id": "def", "name": "web-01", "sys_class_name": "cmdb_ci_server"},
            ],
            table="incident",
            count=2,
            instance=INSTANCE,
        )
        docs = ServiceNowIngestor(
            connector=MagicMock(instance_url=INSTANCE)
        ).export_as_documents(data)

        assert docs[0]["id"] == "abc"
        assert docs[0]["name"] == "INC0001"
        assert docs[0]["source"] == INSTANCE
        assert docs[0]["table"] == "incident"
        assert docs[0]["short_description"] == "Down"
        assert docs[1]["id"] == "def"
        assert docs[1]["name"] == "web-01"

    def test_export_unwraps_display_value_objects(self):
        data = ServiceNowData(
            records=[
                {
                    "sys_id": {"value": "abc", "display_value": "abc"},
                    "name": {"value": "srv", "display_value": "Server 1"},
                }
            ],
            table="cmdb_ci",
            count=1,
            instance=INSTANCE,
        )
        docs = data.to_documents()
        assert docs[0]["id"] == "abc"
        assert docs[0]["name"] == "Server 1"

    def test_export_falls_back_to_table_index(self):
        data = ServiceNowData(
            records=[{"foo": "bar"}], table="incident", count=1, instance=INSTANCE
        )
        docs = data.to_documents()
        assert docs[0]["id"] == "incident:0"
        assert docs[0]["name"] == "incident"

    def test_export_does_not_mutate_records(self):
        record = {"sys_id": "abc"}
        data = ServiceNowData(records=[record], table="t", count=1, instance=INSTANCE)
        data.to_documents()
        assert record == {"sys_id": "abc"}

    def test_record_target_column_stays_an_entity(self):
        data = ServiceNowData(
            records=[{"sys_id": "abc", "name": "rel-row", "target": "cmdb_ci:xyz"}],
            table="cmdb_rel_ci",
            count=1,
            instance=INSTANCE,
        )
        doc = data.to_documents()[0]
        assert "target" not in doc
        assert doc["servicenow_fields"]["target"] == "cmdb_ci:xyz"
        assert doc["id"] == "abc"
        assert doc["name"] == "rel-row"
        assert "source" in doc and "target" not in doc

    def test_record_source_and_table_columns_do_not_override_provenance(self):
        data = ServiceNowData(
            records=[
                {"sys_id": "abc", "source": "email", "table": "sn_customerservice"}
            ],
            table="incident",
            count=1,
            instance=INSTANCE,
        )
        doc = data.to_documents()[0]
        assert doc["source"] == INSTANCE
        assert doc["table"] == "incident"
        assert doc["servicenow_fields"]["source"] == "email"
        assert doc["servicenow_fields"]["table"] == "sn_customerservice"

    def test_record_own_id_column_does_not_override_sys_id(self):
        data = ServiceNowData(
            records=[{"sys_id": "abc", "id": "wrong-id"}],
            table="incident",
            count=1,
            instance=INSTANCE,
        )
        doc = data.to_documents()[0]
        assert doc["id"] == "abc"
        assert doc["servicenow_fields"]["id"] == "wrong-id"

    def test_export_builds_graph_entity_for_row_with_target(self):
        from semantica.kg.graph_builder import GraphBuilder

        data = ServiceNowData(
            records=[{"sys_id": "abc", "name": "srv", "target": "other"}],
            table="cmdb_ci",
            count=1,
            instance=INSTANCE,
        )
        docs = data.to_documents()
        entities: list = []
        relationships: list = []
        GraphBuilder()._process_item(docs[0], entities, relationships)
        assert len(entities) == 1
        assert relationships == []
        assert entities[0]["id"] == "abc"


class TestLazyExport:
    def test_public_import_through_lazy_export(self):
        import semantica.ingest as ingest

        assert ingest.ServiceNowIngestor is ServiceNowIngestor
        assert ingest.ServiceNowConnector is ServiceNowConnector
        assert ingest.ServiceNowData is ServiceNowData
        assert "ServiceNowIngestor" in ingest.__all__
