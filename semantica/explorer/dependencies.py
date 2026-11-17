"""
Semantica Explorer : FastAPI Dependencies

Provides ``Depends()``-compatible callables for injecting the
current ``GraphSession`` into route handlers, and for enforcing
authentication on protected routes: a signed bearer token issued by the
LDAP-backed login (``POST /api/auth/login``) or the shared API key.
WebSocket manager access is handled directly via ``app.state.ws_manager``.
"""

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, Request, Security, status
from fastapi.security.api_key import APIKeyHeader

from ..context.agent_memory import AgentMemory
from .auth import ldap_login_enabled, verify_token
from .markdown_resources import MarkdownResourceRegistry
from .session import GraphSession

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_expected_api_key() -> Optional[str]:
    """Read the configured API key from the environment on every call.

    Read fresh (not cached) so tests and ops tooling can rotate the key
    without restarting the process.
    """
    return os.environ.get("SEMANTICA_API_KEY") or None


def anonymous_access_allowed() -> bool:
    return os.environ.get("SEMANTICA_ALLOW_ANONYMOUS", "").strip().lower() == "true"


def is_valid_api_key(candidate: Optional[str]) -> bool:
    """Return True if *candidate* matches the configured key, or if the
    server has explicitly opted into anonymous access."""
    if anonymous_access_allowed():
        return True
    expected = get_expected_api_key()
    if not expected:
        return False
    return bool(candidate) and hmac.compare_digest(candidate, expected)


def require_auth(
    api_key: Optional[str] = Security(_api_key_header),
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Dependency enforcing credentials on protected routes.

    Every Explorer/API router (except health/info/static assets) should be
    mounted with ``dependencies=[Depends(require_auth)]``. Accepted
    credentials, in order: a signed bearer token issued by the LDAP-backed
    login (``POST /api/auth/login``), or the shared ``X-API-Key``
    header. An explicitly presented but invalid bearer token is rejected
    outright rather than falling back to the API key, so expired sessions
    surface as 401. If neither SEMANTICA_API_KEY nor the LDAP login layer
    is configured, requests are refused with 503 rather than silently
    served unauthenticated — SEMANTICA_ALLOW_ANONYMOUS=true opts into that
    explicitly for local development.
    """
    if anonymous_access_allowed():
        return
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() == "bearer":
            if verify_token(credential.strip()) is not None:
                return
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Invalid or expired bearer token. Sign in again via "
                    "POST /api/auth/login."
                ),
            )
    expected = get_expected_api_key()
    if expected:
        if not api_key or not hmac.compare_digest(api_key, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=("Invalid or missing API key. Send it as the X-API-Key header."),
            )
        return
    if ldap_login_enabled():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication required. Sign in via POST /api/auth/login "
                "and send the token as 'Authorization: Bearer <token>'."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Server is not configured for authentication. Set the "
            "SEMANTICA_API_KEY environment variable, configure LDAP login "
            "(SEMANTICA_LDAP_URL with SEMANTICA_AUTH_SECRET), or explicitly "
            "opt into unauthenticated access (development only) with "
            "SEMANTICA_ALLOW_ANONYMOUS=true."
        ),
    )


def get_session(request: Request) -> GraphSession:
    """Retrieve the GraphSession stored on ``app.state``."""
    if not hasattr(request.app.state, "session") or request.app.state.session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphSession not initialized.",
        )
    return request.app.state.session


def get_markdown_resources(request: Request) -> MarkdownResourceRegistry:
    """Retrieve the Markdown resource registry stored on ``app.state``."""
    resources = getattr(request.app.state, "markdown_resources", None)
    if resources is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Markdown resources are not initialized.",
        )
    return resources


def get_agent_memory(request: Request) -> AgentMemory:
    """Retrieve the optional AgentMemory configured for Explorer."""
    memory = getattr(request.app.state, "agent_memory", None)
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AgentMemory is not configured for this Explorer instance.",
        )
    return memory
