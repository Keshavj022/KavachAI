"""FastAPI dependencies: DB session, current user, role gating."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.enums import Role
from app.models.user import User

# ``tokenUrl`` is where the interactive docs send the login form.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise _credentials_exc
    except jwt.PyJWTError:
        raise _credentials_exc

    user = db.get(User, int(user_id))
    if user is None:
        raise _credentials_exc
    return user


def require_role(role: Role | str) -> Callable[[User], User]:
    """Dependency factory gating a route to a single role.

    Usage: ``Depends(require_role("authority"))``.
    """
    role_value = role.value if isinstance(role, Role) else role

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != role_value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this resource",
            )
        return current_user

    return _checker
