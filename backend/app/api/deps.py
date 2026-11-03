"""
Cedric AI - Auth Dependency
=============================

`get_current_user` is a FastAPI dependency that any protected route
can require. FastAPI's dependency injection runs it before the route
function itself, so by the time your route code executes, either:

- it has a validated, real `User` object, or
- the request was already rejected with 401 Unauthorized.

`HTTPBearer` extracts the `Authorization: Bearer <token>` header for
us (and also makes an "Authorize" button appear in the /docs Swagger
UI, so protected endpoints are testable there without writing curl
commands with raw headers).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.get(User, user_id)
    if user is None:
        # Token is validly signed but the user it points to no longer
        # exists (e.g. account was deleted after the token was issued).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    return user
