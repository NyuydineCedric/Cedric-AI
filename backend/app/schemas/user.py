"""
Cedric AI - User Schemas
==========================

Pydantic schemas define the *shape* of data crossing the API
boundary - separate from `models/user.py`, which defines the
*database table* shape. Keeping these separate matters: it lets us
validate/shape API input and output independently of storage (e.g.
`UserOut` deliberately omits `hashed_password` - it is never allowed
to leave the backend, even by accident).
"""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """What a client must send to POST /api/auth/register."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    # A minimum length is a baseline sanity check, not a full password
    # policy - that's a UX/security discussion for a later phase.
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """What a client must send to POST /api/auth/login."""

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """What the backend returns about a user - never the password hash."""

    id: int
    email: EmailStr
    full_name: str

    # Lets Pydantic build this schema directly from a SQLAlchemy User
    # object's attributes (user.id, user.email, ...) instead of a dict.
    model_config = {"from_attributes": True}


class Token(BaseModel):
    """What POST /api/auth/login returns."""

    access_token: str
    token_type: str = "bearer"
