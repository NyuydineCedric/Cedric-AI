"""
Cedric AI - Password Hashing & JWT
====================================

Two separate concerns live here:

1. PASSWORD HASHING (bcrypt)
   We never store a user's actual password - only a one-way hash of
   it. bcrypt is a deliberately slow hashing algorithm (it includes a
   random "salt" and a tunable work factor), which makes brute-forcing
   stolen password hashes impractical. Even if the database leaked,
   an attacker can't recover the original passwords from it.

2. JSON WEB TOKENS (JWT)
   After a successful login, we don't keep server-side "session"
   state. Instead we hand the client a signed token containing the
   user's ID and an expiry timestamp. On every later request, the
   server re-verifies the signature using JWT_SECRET_KEY - if the
   signature checks out, the server trusts the payload (because only
   the server could have produced a validly-signed token). This is
   what "stateless auth" means: no session store, no database lookup
   needed just to check "is this token real".
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage. Called once, at registration."""
    # bcrypt operates on bytes and has a hard 72-byte input limit (a
    # quirk of the algorithm) - irrelevant for normal human passwords,
    # but worth knowing if you ever accept very long passphrases.
    hashed_bytes = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a login attempt's password against the stored hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: int) -> str:
    """Issue a signed JWT for a successfully authenticated user."""
    expire_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    # "sub" (subject) is the JWT-standard claim name for "who is this
    # token about". We store the user's DB id as a string, per spec.
    payload = {"sub": str(user_id), "exp": expire_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    """
    Verify a token's signature and expiry, and return the user id it
    belongs to - or None if the token is invalid/expired/tampered with.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None
