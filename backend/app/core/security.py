"""Password hashing and JWT creation/verification.

Passwords are hashed with bcrypt (never stored plaintext). Access tokens are
signed HS256 JWTs carrying the user id (``sub``) and ``role``.
"""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt has a 72-byte input limit; passlib handles truncation but we also
# validate max length at the schema layer.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash for a plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        # Malformed hash — treat as a failed verification rather than raising.
        return False


def create_access_token(*, subject: str, role: str) -> str:
    """Create a signed JWT for the given user id and role."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` on failure."""
    return jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
