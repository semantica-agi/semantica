"""
Semantica Explorer : Authentication routes.

Public endpoints for the LDAP-backed login layer:

- 'GET  /api/auth/status'  reports which authentication modes the server
  currently accepts (used by the frontend to decide whether to show the
  login screen).
- 'POST /api/auth/login'   verifies LDAP credentials and returns a
  signed bearer token.
- 'GET  /api/auth/me'      introspects the current credential (behind
  the standard require_auth dependency).

The login and status routes are mounted *without* require_auth; every
other Explorer router keeps its dependency, so adding this router never
widens access to graph data. Error responses deliberately do not
distinguish unknown users from wrong passwords, and LDAP configuration
problems surface as 503 rather than 401 so operators can tell the two
failure classes apart.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from .. import auth as auth_module
from ..auth import (
    InvalidCredentials,
    LdapNotConfigured,
    LdapUnavailable,
    ldap_login_enabled,
    public_user_claims,
    verify_token,
)
from ..dependencies import anonymous_access_allowed, get_expected_api_key, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """LDAP credentials submitted to POST /api/auth/login."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.get("/status")
async def auth_status() -> Dict[str, Any]:
    """Report which authentication modes the server currently accepts.

    The frontend calls this once at startup to decide whether a login
    screen is needed, so it must stay public.
    """
    return {
        "anonymous": anonymous_access_allowed(),
        "ldap": ldap_login_enabled(),
        "api_key": get_expected_api_key() is not None,
    }


@router.post("/login")
async def login(body: LoginRequest) -> Dict[str, Any]:
    """Verify LDAP credentials and return a signed bearer token.

    Returns the token with its expiry plus the projected user object so
    the UI can greet the user without a second round trip.
    """
    try:
        account = auth_module.authenticate_ldap(body.username, body.password)
    except LdapNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LdapUnavailable as exc:
        logger.warning("LDAP login unavailable for %r: %s", body.username, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication directory is unavailable.",
        ) from exc
    except InvalidCredentials as exc:
        logger.info("LDAP login rejected for %r", body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        ) from exc

    token, expires_at = auth_module.issue_token(account)
    logger.info("LDAP login succeeded for %r", account.get("username"))
    return {
        "token_type": "Bearer",
        "token": token,
        "expires_at": expires_at,
        "user": {
            "username": account.get("username"),
            "display_name": account.get("display_name"),
            "email": account.get("email"),
            "groups": account.get("groups", []),
        },
    }


@router.get("/me", dependencies=[Depends(require_auth)])
async def authenticated_user(request: Request) -> Dict[str, Any]:
    """Introspect the credential that authenticated this request.

    Bearer tokens resolve to the embedded user claims; the shared API
    key and anonymous mode have no user identity, so they return a mode
    marker with a null user.
    """
    authorization = request.headers.get("authorization", "")
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() == "bearer":
        claims = verify_token(credential.strip())
        if claims is not None:
            return {"mode": "ldap", "user": public_user_claims(claims)}
    if anonymous_access_allowed():
        return {"mode": "anonymous", "user": None}
    return {"mode": "api_key", "user": None}
