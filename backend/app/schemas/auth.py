"""Auth request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    # Minimum password policy enforced here at the boundary.
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=255)
    role: Role = Role.citizen
    preferred_language: str = Field(default="en", max_length=16)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: Role
    preferred_language: str
    created_at: datetime
