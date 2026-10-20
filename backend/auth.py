import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DEFAULT_USERNAME = os.environ.get("CADENCE_USERNAME", "admin")
DEFAULT_PASSWORD = os.environ.get("CADENCE_PASSWORD", "password")

_tokens: set[str] = set()
_bearer = HTTPBearer(auto_error=False)


def login(username: str, password: str) -> str:
    if username != DEFAULT_USERNAME or password != DEFAULT_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = secrets.token_urlsafe(32)
    _tokens.add(token)
    return token


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None or credentials.credentials not in _tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return credentials.credentials
