"""
Semantica Explorer : FastAPI Dependencies

Provides ``Depends()``-compatible callables for injecting the
current ``GraphSession`` and ``ConnectionManager`` into route handlers.
"""

from fastapi import Request, HTTPException, status

from .session import GraphSession
from .ws import ConnectionManager


def get_session(request: Request) -> GraphSession:
    """Retrieve the GraphSession stored on ``app.state``."""
    if not hasattr(request.app.state, "session") or request.app.state.session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphSession not initialized."
        )
    return request.app.state.session


def get_ws_manager(request: Request) -> ConnectionManager:
    """Retrieve the ConnectionManager stored on ``app.state``."""
    if not hasattr(request.app.state, "ws_manager") or request.app.state.ws_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket manager not initialized.",
        )
    return request.app.state.ws_manager
