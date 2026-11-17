"""Tests for the LDAP-backed login layer (auth.py + routes/auth.py).

Covers: signed session token issuance/verification (round trip, expiry,
tampering, secret rotation), the /api/auth routes (status discovery,
login success/failure/unavailable/not-configured, /me introspection),
require_auth's bearer-token chain including its interplay with the
shared X-API-Key scheme, the WebSocket ?token= handshake, and the
search-then-bind / direct-bind flows against a stubbed ldap3.Connection.

The directory is stubbed at the Connection level, not at the network
layer: no test here opens a socket.
"""

import sys

import pytest

from semantica.context.context_graph import ContextGraph

# fastapi ships in the optional 'explorer' extra, not in 'dev', so this
# module must skip rather than fail collection when it is absent (same
# guard as test_explorer_auth.py).
pytest.importorskip("fastapi")

from starlette.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from semantica.explorer import auth as auth_module  # noqa: E402
from semantica.explorer.app import create_app  # noqa: E402
from semantica.explorer.auth import (  # noqa: E402
    InvalidCredentials,
    LdapNotConfigured,
    LdapUnavailable,
    authenticate_ldap,
    issue_token,
    verify_token,
)
from semantica.explorer.session import GraphSession  # noqa: E402

_ACCOUNT = {
    "username": "alice",
    "dn": "uid=alice,ou=people,dc=example,dc=com",
    "display_name": "Alice Doe",
    "email": "alice@example.com",
    "groups": ["cn=kg-viewers,ou=groups,dc=example,dc=com"],
}


def _configure_ldap(monkeypatch, secret="unit-test-secret") -> None:
    """Point the login layer at a well-formed direct-bind configuration."""
    monkeypatch.delenv("SEMANTICA_ALLOW_ANONYMOUS", raising=False)
    monkeypatch.delenv("SEMANTICA_API_KEY", raising=False)
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", secret)
    monkeypatch.setenv("SEMANTICA_LDAP_URL", "ldap://directory.example.com:389")
    monkeypatch.setenv(
        "SEMANTICA_LDAP_USER_DN_TEMPLATE",
        "uid={username},ou=people,dc=example,dc=com",
    )


def _clear_auth_env(monkeypatch) -> None:
    """Remove every credential source: fail-closed territory."""
    for name in (
        "SEMANTICA_ALLOW_ANONYMOUS",
        "SEMANTICA_API_KEY",
        "SEMANTICA_AUTH_SECRET",
        "SEMANTICA_LDAP_URL",
        "SEMANTICA_LDAP_USER_DN_TEMPLATE",
        "SEMANTICA_LDAP_BIND_DN",
        "SEMANTICA_LDAP_BIND_PASSWORD",
        "SEMANTICA_LDAP_SEARCH_BASE",
    ):
        monkeypatch.delenv(name, raising=False)


def _build_sample_graph() -> ContextGraph:
    graph = ContextGraph(advanced_analytics=False)
    graph.add_node("python", node_type="language", content="Python")
    return graph


@pytest.fixture
def client(monkeypatch):
    # create_app() reads the allowed origins from the environment, so an
    # ALLOWED_ORIGINS or EXPLORER_CORS_ORIGINS exported in the developer's
    # shell would replace the defaults these tests rely on.
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("EXPLORER_CORS_ORIGINS", raising=False)
    session = GraphSession(_build_sample_graph())
    app = create_app(session=session)
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Signed session tokens
# ---------------------------------------------------------------------------


def test_token_round_trip(monkeypatch):
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")

    token, expires_at = issue_token(_ACCOUNT, ttl_seconds=120)

    claims = verify_token(token)
    assert claims is not None
    assert claims["sub"] == "alice"
    assert claims["name"] == "Alice Doe"
    assert claims["email"] == "alice@example.com"
    assert claims["groups"] == ["cn=kg-viewers,ou=groups,dc=example,dc=com"]
    assert claims["exp"] - claims["iat"] == 120
    assert expires_at.endswith("+00:00")


def test_token_ttl_env_override(monkeypatch):
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    monkeypatch.setenv("SEMANTICA_AUTH_TOKEN_TTL", "600")

    token, _ = issue_token(_ACCOUNT)
    claims = verify_token(token)
    assert claims is not None
    assert claims["exp"] - claims["iat"] == 600


def test_expired_token_rejected(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    token, _ = issue_token(_ACCOUNT, ttl_seconds=100)
    # Simulate the clock having moved far past expiry (including skew).
    monkeypatch.setattr(auth_module, "time", SimpleNamespace(time=lambda: 10**12))
    assert verify_token(token) is None


def test_tampered_payload_rejected(monkeypatch):
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    token, _ = issue_token({**_ACCOUNT, "groups": ["cn=admins,ou=groups"]})
    header, payload, signature = token.split(".")
    forged = auth_module._b64encode(
        b'{"iss": "semantica-explorer", "sub": "alice", "exp": 9999999999}'
    )
    assert verify_token(f"{header}.{forged}.{signature}") is None
    assert verify_token(f"{header}.{payload}.{signature}x") is None


def test_wrong_secret_rejected(monkeypatch):
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "secret-a")
    token, _ = issue_token(_ACCOUNT)
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "secret-b")
    assert verify_token(token) is None


def test_verify_without_secret_returns_none(monkeypatch):
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    token, _ = issue_token(_ACCOUNT)
    monkeypatch.delenv("SEMANTICA_AUTH_SECRET", raising=False)
    assert verify_token(token) is None


@pytest.mark.parametrize(
    "token", ["", "not-a-token", "a.b", "x.y.z", "...", "dGVzdA.dGVzdA.dGVzdA"]
)
def test_garbage_tokens_rejected(monkeypatch, token):
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    assert verify_token(token) is None


# ---------------------------------------------------------------------------
# ldap3 flows against a stubbed Connection
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, dn, attributes):
        self.entry_dn = dn
        self.entry_attributes_as_dict = attributes


def _install_fake_ldap3(monkeypatch, entries, fail_binds=()):
    """Replace ldap3.Connection with a recording, canned-result stub."""
    import ldap3
    from ldap3.core.exceptions import LDAPBindError

    binds = []

    class FakeConnection:
        def __init__(
            self,
            server,
            user=None,
            password=None,
            authentication=None,
            auto_bind=False,
            receive_timeout=None,
            raise_exceptions=False,
        ):
            self.user = user
            binds.append((user, password))
            if (user, password) in set(fail_binds):
                raise LDAPBindError("invalid credentials")
            self.entries = list(entries.get(user, []))

        def search(self, *args, **_kwargs):
            # ldap3 passes (search_base, search_filter) positionally for the
            # BASE-scope self-search; entries are read off the connection.
            return True

        def unbind(self):
            return True

    monkeypatch.setattr(ldap3, "Connection", FakeConnection)
    return binds


def test_authenticate_requires_configuration(monkeypatch):
    _clear_auth_env(monkeypatch)
    with pytest.raises(LdapNotConfigured):
        authenticate_ldap("alice", "pw")


def test_authenticate_rejects_empty_credentials(monkeypatch):
    _configure_ldap(monkeypatch)
    with pytest.raises(InvalidCredentials):
        authenticate_ldap("", "pw")
    with pytest.raises(InvalidCredentials):
        authenticate_ldap("alice", "")


def test_authenticate_without_ldap3_is_unavailable(monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setitem(sys.modules, "ldap3", None)
    with pytest.raises(LdapUnavailable):
        authenticate_ldap("alice", "pw")


def test_direct_bind_success(monkeypatch):
    _configure_ldap(monkeypatch)
    binds = _install_fake_ldap3(
        monkeypatch,
        {
            "uid=alice,ou=people,dc=example,dc=com": [
                _FakeEntry(
                    "uid=alice,ou=people,dc=example,dc=com",
                    {"displayName": ["Alice Doe"], "mail": ["alice@example.com"]},
                )
            ]
        },
    )

    account = authenticate_ldap("alice", "pw")

    assert account["username"] == "alice"
    assert account["display_name"] == "Alice Doe"
    assert account["email"] == "alice@example.com"
    assert account["groups"] == []
    assert binds == [("uid=alice,ou=people,dc=example,dc=com", "pw")]


def test_direct_bind_wrong_password(monkeypatch):
    _configure_ldap(monkeypatch)
    _install_fake_ldap3(
        monkeypatch,
        {},
        fail_binds=[("uid=alice,ou=people,dc=example,dc=com", "bad")],
    )
    with pytest.raises(InvalidCredentials):
        authenticate_ldap("alice", "bad")


def test_direct_bind_escapes_dn_specials(monkeypatch):
    _configure_ldap(monkeypatch)
    binds = _install_fake_ldap3(monkeypatch, {})

    authenticate_ldap("doe, john", "pw")

    assert binds[0][0] == "uid=doe\\, john,ou=people,dc=example,dc=com"


def test_search_then_bind_success(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    monkeypatch.setenv("SEMANTICA_LDAP_URL", "ldap://directory.example.com:389")
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_DN", "cn=svc,dc=example,dc=com")
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_PASSWORD", "svc-pw")
    monkeypatch.setenv("SEMANTICA_LDAP_SEARCH_BASE", "dc=example,dc=com")
    alice_dn = "uid=alice,ou=people,dc=example,dc=com"
    binds = _install_fake_ldap3(
        monkeypatch,
        {
            "cn=svc,dc=example,dc=com": [
                _FakeEntry(
                    alice_dn,
                    {
                        "displayName": ["Alice Doe"],
                        "mail": ["alice@example.com"],
                        "memberOf": ["cn=kg-viewers,ou=groups,dc=example,dc=com"],
                    },
                )
            ]
        },
        fail_binds=[(alice_dn, "wrong")],
    )

    account = authenticate_ldap("alice", "right")

    assert account["username"] == "alice"
    assert account["groups"] == ["cn=kg-viewers,ou=groups,dc=example,dc=com"]
    # First bind is the service account, second is the resolved user DN.
    assert binds[0] == ("cn=svc,dc=example,dc=com", "svc-pw")
    assert binds[1] == (alice_dn, "right")


def test_search_then_bind_wrong_password(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    monkeypatch.setenv("SEMANTICA_LDAP_URL", "ldap://directory.example.com:389")
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_DN", "cn=svc,dc=example,dc=com")
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_PASSWORD", "svc-pw")
    monkeypatch.setenv("SEMANTICA_LDAP_SEARCH_BASE", "dc=example,dc=com")
    alice_dn = "uid=alice,ou=people,dc=example,dc=com"
    _install_fake_ldap3(
        monkeypatch,
        {"cn=svc,dc=example,dc=com": [_FakeEntry(alice_dn, {})]},
        fail_binds=[(alice_dn, "wrong")],
    )
    with pytest.raises(InvalidCredentials):
        authenticate_ldap("alice", "wrong")


def test_search_then_bind_unknown_user(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    monkeypatch.setenv("SEMANTICA_LDAP_URL", "ldap://directory.example.com:389")
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_DN", "cn=svc,dc=example,dc=com")
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_PASSWORD", "svc-pw")
    monkeypatch.setenv("SEMANTICA_LDAP_SEARCH_BASE", "dc=example,dc=com")
    _install_fake_ldap3(monkeypatch, {})
    # Unknown users report exactly what wrong passwords report.
    with pytest.raises(InvalidCredentials):
        authenticate_ldap("nobody", "pw")


def test_mutually_exclusive_bind_modes_rejected(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv("SEMANTICA_AUTH_SECRET", "s3cret")
    monkeypatch.setenv("SEMANTICA_LDAP_URL", "ldap://directory.example.com:389")
    monkeypatch.setenv(
        "SEMANTICA_LDAP_USER_DN_TEMPLATE",
        "uid={username},ou=people,dc=example,dc=com",
    )
    monkeypatch.setenv("SEMANTICA_LDAP_BIND_DN", "cn=svc,dc=example,dc=com")
    with pytest.raises(LdapNotConfigured):
        authenticate_ldap("alice", "pw")


# ---------------------------------------------------------------------------
# /api/auth routes
# ---------------------------------------------------------------------------


def test_status_reports_enabled_ldap(client, monkeypatch):
    _configure_ldap(monkeypatch)
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"anonymous": False, "ldap": True, "api_key": False}


def test_status_reports_disabled_ldap(client, monkeypatch):
    _clear_auth_env(monkeypatch)
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"anonymous": False, "ldap": False, "api_key": False}


def test_login_success_and_protected_route(client, monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setattr(auth_module, "authenticate_ldap", lambda u, p: dict(_ACCOUNT))

    resp = client.post("/api/auth/login", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["user"]["username"] == "alice"
    assert body["expires_at"].endswith("+00:00")

    protected = client.get(
        "/api/graph/nodes", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert protected.status_code == 200


def test_login_invalid_credentials(client, monkeypatch):
    _configure_ldap(monkeypatch)

    def raise_invalid(username, password):
        raise InvalidCredentials("Invalid username or password.")

    monkeypatch.setattr(auth_module, "authenticate_ldap", raise_invalid)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "bad"})
    assert resp.status_code == 401


def test_login_directory_unavailable(client, monkeypatch):
    _configure_ldap(monkeypatch)

    def raise_unavailable(username, password):
        raise LdapUnavailable("Could not connect to the LDAP directory.")

    monkeypatch.setattr(auth_module, "authenticate_ldap", raise_unavailable)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 503


def test_login_when_not_configured(client, monkeypatch):
    _clear_auth_env(monkeypatch)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 503


def test_me_with_bearer_token(client, monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setattr(auth_module, "authenticate_ldap", lambda u, p: dict(_ACCOUNT))
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw"}
    ).json()["token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "ldap"
    assert body["user"]["username"] == "alice"


def test_me_with_api_key(client, monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setenv("SEMANTICA_API_KEY", "correct-key")

    resp = client.get("/api/auth/me", headers={"X-API-Key": "correct-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "api_key"
    assert body["user"] is None


def test_me_refused_without_credentials(client, monkeypatch):
    _clear_auth_env(monkeypatch)
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 503)


# ---------------------------------------------------------------------------
# require_auth chain
# ---------------------------------------------------------------------------


def test_expired_bearer_rejected_on_protected_route(client, monkeypatch):
    from types import SimpleNamespace

    _configure_ldap(monkeypatch)
    monkeypatch.setattr(auth_module, "authenticate_ldap", lambda u, p: dict(_ACCOUNT))
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw"}
    ).json()["token"]
    # After login, wind the clock far past expiry (including skew).
    monkeypatch.setattr(auth_module, "time", SimpleNamespace(time=lambda: 10**12))

    resp = client.get("/api/graph/nodes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_invalid_bearer_does_not_fall_back_to_api_key(client, monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setenv("SEMANTICA_API_KEY", "correct-key")
    resp = client.get(
        "/api/graph/nodes",
        headers={
            "Authorization": "Bearer bogus.token.value",
            "X-API-Key": "correct-key",
        },
    )
    assert resp.status_code == 401


def test_valid_api_key_still_accepted(client, monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setenv("SEMANTICA_API_KEY", "correct-key")
    resp = client.get("/api/graph/nodes", headers={"X-API-Key": "correct-key"})
    assert resp.status_code == 200


def test_fail_closed_when_nothing_configured(client, monkeypatch):
    _clear_auth_env(monkeypatch)
    resp = client.get("/api/graph/nodes")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# WebSocket handshake with a session token
# ---------------------------------------------------------------------------


def test_ws_accepts_valid_session_token(client, monkeypatch):
    _configure_ldap(monkeypatch)
    monkeypatch.setattr(auth_module, "authenticate_ldap", lambda u, p: dict(_ACCOUNT))
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "pw"}
    ).json()["token"]

    with client.websocket_connect(f"/ws/graph-updates?token={token}") as ws:
        message = ws.receive_json()
    assert message["event"] == "connection_ack"


def test_ws_rejects_invalid_session_token(client, monkeypatch):
    _configure_ldap(monkeypatch)
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/graph-updates?token=bogus") as ws:
            ws.receive_json()
    assert excinfo.value.code == 4401
