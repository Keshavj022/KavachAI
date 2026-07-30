"""Trusted-contact schemas."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=6, max_length=20)

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        # Accept +country code and digits, spaces or dashes.
        if not re.fullmatch(r"\+?[\d\-\s]{6,20}", v):
            raise ValueError("Enter a valid phone number")
        return v.strip()


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
