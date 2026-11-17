"""
Semantica Explorer : LDAP-backed login and signed session tokens.

Optional user-authentication layer that complements the shared
'X-API-Key' scheme. When an LDAP directory and a token signing secret
are configured, users sign in through 'POST /api/auth/login', the
credentials are verified by binding against the directory, and the route
returns an HMAC-signed bearer token that require_auth (in
semantica.explorer.dependencies) accepts on every protected route.

Configuration is read from the environment fresh on every call, matching
the API-key behaviour so operators can rotate secrets without restarts:

Variable                       Meaning
-----------------------------  --------------------------------------------------
SEMANTICA_AUTH_SECRET          HMAC-SHA256 secret for signing tokens. Required
                               for login to be enabled.
SEMANTICA_AUTH_TOKEN_TTL       Token lifetime in seconds (default 28800, 8 h).
SEMANTICA_LDAP_URL             'ldap://host:389' or 'ldaps://host:636'.
SEMANTICA_LDAP_STARTTLS        'true' upgrades a 'ldap://' connection with
                               StartTLS.
SEMANTICA_LDAP_VERIFY_CERTS_OFF
                               Any truthy value skips server certificate
                               validation for LDAPS/StartTLS (default:
                               validate).
SEMANTICA_LDAP_TIMEOUT         Connect/search timeout in seconds (default 10).
SEMANTICA_LDAP_USER_DN_TEMPLATE
                               Direct-bind DN template containing '{username}',
                               e.g. 'uid={username},ou=people,dc=example,dc=com'.
SEMANTICA_LDAP_BIND_DN         Service-account DN for search-then-bind.
SEMANTICA_LDAP_BIND_PASSWORD   Service-account password.
SEMANTICA_LDAP_SEARCH_BASE     Search base DN for search-then-bind.
SEMANTICA_LDAP_USER_FILTER     Search-filter template containing '{username}'
                               (default '(sAMAccountName={username})').

Exactly one bind mode must be configured: the DN template (direct bind)
or the service-account pair plus a search base (search-then-bind). The
username is escaped before it is interpolated into a search filter or
DN, and passwords are never logged or embedded in issued tokens.
"""

import base64
import hashlib
import hmac
import json
import os
import ssl
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

_TOKEN_ISSUER = "semantica-explorer"
_TOKEN_ALGORITHM = "HS256"
_TOKEN_TYPE = "semantica-auth"
# Tolerated clock drift between the server that signed a token and the
# worker that verifies it when checking the 'exp' claim.
_TOKEN_CLOCK_SKEW_SECONDS = 60
_DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60
_DEFAULT_LDAP_TIMEOUT_SECONDS = 10
# Attributes copied from the directory entry into the token claims.
_LDAP_USER_ATTRIBUTES = ("cn", "mail", "displayName", "memberOf")
_DEFAULT_USER_FILTER = "(sAMAccountName={username})"


class LdapAuthError(Exception):
    """Base class for LDAP-login failures safe to surface via the API."""


class LdapNotConfigured(LdapAuthError):
    """LDAP login is not (fully) configured in this environment."""


class LdapUnavailable(LdapAuthError):
    """The directory could not be reached, or ldap3 is missing."""


class InvalidCredentials(LdapAuthError):
    """The username/password pair was rejected by the directory."""


# ---------------------------------------------------------------------------
# Environment helpers (read fresh, mirroring get_expected_api_key)
# ---------------------------------------------------------------------------


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _auth_secret() -> Optional[str]:
    secret = os.environ.get("SEMANTICA_AUTH_SECRET", "").strip()
    return secret or None


def _token_ttl_seconds() -> int:
    return max(60, _env_int("SEMANTICA_AUTH_TOKEN_TTL", _DEFAULT_TOKEN_TTL_SECONDS))


def _read_ldap_config() -> Dict[str, Any]:
    """Collect and validate the LDAP settings, or raise LdapNotConfigured."""
    url = os.environ.get("SEMANTICA_LDAP_URL", "").strip()
    if not url:
        raise LdapNotConfigured("SEMANTICA_LDAP_URL is not set.")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("ldap", "ldaps") or not parsed.hostname:
        raise LdapNotConfigured(
            "SEMANTICA_LDAP_URL must look like ldap://host:389 " "or ldaps://host:636."
        )

    dn_template = os.environ.get("SEMANTICA_LDAP_USER_DN_TEMPLATE", "").strip()
    bind_dn = os.environ.get("SEMANTICA_LDAP_BIND_DN", "").strip()
    # Passwords may legitimately contain leading/trailing spaces, so they are
    # read raw and only treated as unset when empty.
    bind_password = os.environ.get("SEMANTICA_LDAP_BIND_PASSWORD", "")
    search_base = os.environ.get("SEMANTICA_LDAP_SEARCH_BASE", "").strip()

    if dn_template:
        if "{username}" not in dn_template:
            raise LdapNotConfigured(
                "SEMANTICA_LDAP_USER_DN_TEMPLATE must contain '{username}'."
            )
        if bind_dn or bind_password or search_base:
            raise LdapNotConfigured(
                "Direct bind (SEMANTICA_LDAP_USER_DN_TEMPLATE) and "
                "search-then-bind (SEMANTICA_LDAP_BIND_DN/PASSWORD/SEARCH_BASE) "
                "are mutually exclusive; configure exactly one."
            )
        mode = "direct"
    else:
        if not (bind_dn and bind_password and search_base):
            raise LdapNotConfigured(
                "Set SEMANTICA_LDAP_USER_DN_TEMPLATE for direct bind, or "
                "SEMANTICA_LDAP_BIND_DN, SEMANTICA_LDAP_BIND_PASSWORD and "
                "SEMANTICA_LDAP_SEARCH_BASE for search-then-bind."
            )
        mode = "search"

    user_filter = os.environ.get("SEMANTICA_LDAP_USER_FILTER", "").strip()
    if not user_filter:
        user_filter = _DEFAULT_USER_FILTER
    if "{username}" not in user_filter:
        raise LdapNotConfigured("SEMANTICA_LDAP_USER_FILTER must contain '{username}'.")

    return {
        "url": url,
        "host": parsed.hostname,
        "port": parsed.port or (636 if scheme == "ldaps" else 389),
        "use_ssl": scheme == "ldaps",
        "starttls": _env_flag("SEMANTICA_LDAP_STARTTLS"),
        "verify_certs": not _env_flag("SEMANTICA_LDAP_VERIFY_CERTS_OFF"),
        "timeout": _env_int("SEMANTICA_LDAP_TIMEOUT", _DEFAULT_LDAP_TIMEOUT_SECONDS),
        "mode": mode,
        "dn_template": dn_template,
        "bind_dn": bind_dn,
        "bind_password": bind_password,
        "search_base": search_base,
        "user_filter": user_filter,
    }


def ldap_login_enabled() -> bool:
    """True when a directory and a token signing secret are both set."""
    if not _auth_secret():
        return False
    try:
        _read_ldap_config()
    except LdapNotConfigured:
        return False
    return True


# ---------------------------------------------------------------------------
# LDAP authentication
# ---------------------------------------------------------------------------


def _first_attribute(value: Any) -> Optional[str]:
    """Return the first usable string of an ldap3 attribute value."""
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _first_attribute(item)
            if text:
                return text
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    text = str(value).strip() if value is not None else ""
    return text or None


def authenticate_ldap(username: str, password: str) -> Dict[str, Any]:
    """Bind against the configured directory to verify the credentials.

    Returns an account dictionary (username, dn, display_name, email,
    groups) on success. Raises InvalidCredentials for rejected
    credentials, LdapUnavailable when the directory cannot be reached or
    ldap3 is not installed, and LdapNotConfigured for incomplete
    configuration.
    """
    if not username or not password:
        raise InvalidCredentials("Username and password are required.")

    config = _read_ldap_config()
    try:
        import ldap3
        from ldap3 import SIMPLE, SUBTREE
        from ldap3.core.exceptions import (
            LDAPBindError,
            LDAPException,
            LDAPSocketOpenError,
        )
        from ldap3.utils.conv import escape_filter_chars
    except ImportError as exc:
        raise LdapUnavailable(
            "The ldap3 package is not installed. Install semantica[auth-ldap]."
        ) from exc

    tls = None
    if config["use_ssl"] or config["starttls"]:
        tls = ldap3.Tls(
            validate=ssl.CERT_REQUIRED if config["verify_certs"] else ssl.CERT_NONE
        )
    server = ldap3.Server(
        config["host"],
        port=config["port"],
        use_ssl=config["use_ssl"],
        tls=tls,
        connect_timeout=config["timeout"],
        get_info=None,
    )

    def _bind(user: str, secret: str):
        return ldap3.Connection(
            server,
            user=user,
            password=secret,
            authentication=SIMPLE,
            auto_bind=True,
            receive_timeout=config["timeout"],
            raise_exceptions=True,
        )

    connection = None
    try:
        attributes: Dict[str, Any] = {}
        if config["mode"] == "search":
            try:
                service = _bind(config["bind_dn"], config["bind_password"])
            except LDAPBindError as exc:
                raise LdapUnavailable(
                    "LDAP service account bind failed; check "
                    "SEMANTICA_LDAP_BIND_DN and SEMANTICA_LDAP_BIND_PASSWORD."
                ) from exc
            try:
                service.search(
                    search_base=config["search_base"],
                    search_filter=config["user_filter"].replace(
                        "{username}", escape_filter_chars(username)
                    ),
                    search_scope=SUBTREE,
                    attributes=list(_LDAP_USER_ATTRIBUTES),
                    size_limit=5,
                )
            except LDAPException as exc:
                raise LdapUnavailable(f"LDAP user search failed: {exc}") from exc
            if not service.entries:
                # Report unknown users identically to wrong passwords so the
                # endpoint does not leak which accounts exist.
                raise InvalidCredentials("Invalid username or password.")
            user_dn = service.entries[0].entry_dn
            attributes = service.entries[0].entry_attributes_as_dict

            try:
                connection = _bind(user_dn, password)
            except LDAPBindError as exc:
                raise InvalidCredentials("Invalid username or password.") from exc
            service.unbind()
        else:
            # Direct bind: the DN template is a naming convention, so escape
            # the username the way an RDN component would be escaped.
            safe_username = username.replace("\\", "\\\\").replace(",", "\\,")
            user_dn = config["dn_template"].replace("{username}", safe_username)
            try:
                connection = _bind(user_dn, password)
            except LDAPBindError as exc:
                raise InvalidCredentials("Invalid username or password.") from exc
            # Best-effort self-search to pick up mail/displayName/memberOf.
            try:
                connection.search(
                    user_dn,
                    "(objectClass=*)",
                    search_scope="BASE",
                    attributes=list(_LDAP_USER_ATTRIBUTES),
                )
                if connection.entries:
                    attributes = connection.entries[0].entry_attributes_as_dict
            except LDAPException:
                attributes = {}

        groups = sorted(
            value
            for value in (
                _first_attribute(item) for item in attributes.get("memberOf", [])
            )
            if value
        )
        return {
            "username": username,
            "dn": user_dn,
            "display_name": _first_attribute(attributes.get("displayName"))
            or _first_attribute(attributes.get("cn"))
            or username,
            "email": _first_attribute(attributes.get("mail")),
            "groups": groups,
        }
    except LDAPSocketOpenError as exc:
        raise LdapUnavailable("Could not connect to the LDAP directory.") from exc
    except LDAPException as exc:
        raise LdapUnavailable(f"LDAP error: {exc}") from exc
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except LDAPException:
                pass


# ---------------------------------------------------------------------------
# Signed session tokens (HS256, standard library only)
# ---------------------------------------------------------------------------


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _signing_key() -> bytes:
    secret = _auth_secret()
    if not secret:
        raise LdapNotConfigured(
            "SEMANTICA_AUTH_SECRET is not set; tokens cannot be issued or " "verified."
        )
    return secret.encode("utf-8")


def issue_token(
    account: Dict[str, Any], ttl_seconds: Optional[int] = None
) -> Tuple[str, str]:
    """Sign an account dictionary into a bearer token.

    Returns (token, expires_at) where expires_at is an ISO-8601 UTC
    timestamp convenient for UI display.
    """
    ttl = ttl_seconds if ttl_seconds is not None else _token_ttl_seconds()
    issued_at = int(time.time())
    expires_at = issued_at + max(1, int(ttl))
    header = {"alg": _TOKEN_ALGORITHM, "typ": _TOKEN_TYPE}
    payload = {
        "iss": _TOKEN_ISSUER,
        "sub": account.get("username"),
        "dn": account.get("dn"),
        "name": account.get("display_name"),
        "email": account.get("email"),
        "groups": account.get("groups", []),
        "iat": issued_at,
        "exp": expires_at,
    }
    signing_input = (
        _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    signature = hmac.new(
        _signing_key(), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    token = signing_input + "." + _b64encode(signature)
    expires_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
    return token, expires_iso


def verify_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the token's claims when valid and unexpired, else None.

    Never raises: every structural, cryptographic, or configuration
    problem maps to None so callers can treat tokens as untrusted input.
    """
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        header = json.loads(_b64decode(parts[0]))
        payload = json.loads(_b64decode(parts[1]))
        signature = _b64decode(parts[2])
        if not isinstance(header, dict) or not isinstance(payload, dict):
            return None
        if header.get("alg") != _TOKEN_ALGORITHM or header.get("typ") != _TOKEN_TYPE:
            return None
        signing_input = (parts[0] + "." + parts[1]).encode("ascii")
        expected = hmac.new(_signing_key(), signing_input, hashlib.sha256).digest()
    except (ValueError, TypeError):
        # Covers malformed base64/JSON and non-ASCII segments.
        return None
    except LdapAuthError:
        # The signing secret is not configured, so nothing can verify.
        return None
    if not hmac.compare_digest(expected, signature):
        return None
    if payload.get("iss") != _TOKEN_ISSUER:
        return None
    expires = payload.get("exp")
    if not isinstance(expires, (int, float)):
        return None
    if time.time() > expires + _TOKEN_CLOCK_SKEW_SECONDS:
        return None
    return payload


def is_valid_token(token: Optional[str]) -> bool:
    """Convenience wrapper used by the WebSocket handshake."""
    return verify_token(token) is not None


def public_user_claims(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Project token claims into the user object exposed by /api/auth/me."""
    expires = payload.get("exp")
    expires_iso = (
        datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
        if isinstance(expires, (int, float))
        else None
    )
    return {
        "username": payload.get("sub"),
        "display_name": payload.get("name"),
        "email": payload.get("email"),
        "groups": payload.get("groups", []),
        "dn": payload.get("dn"),
        "expires_at": expires_iso,
    }
