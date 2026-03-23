import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.core.enums import UserRole

IIN_PATTERN = re.compile(r"^\d{12}$")


def validate_iin(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not IIN_PATTERN.match(v):
        raise ValueError("IIN must be exactly 12 digits")
    return v


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    facility_id: UUID | None = None
    iin: str | None = None
    photo_url: str | None = None
    transfer_date: date | None = None
    release_date: date | None = None

    @field_validator("iin")
    @classmethod
    def validate_iin_field(cls, v: str | None) -> str | None:
        return validate_iin(v)


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    facility_id: UUID | None = None
    iin: str | None = None
    photo_url: str | None = None
    transfer_date: date | None = None
    release_date: date | None = None
    is_active: bool | None = None

    @field_validator("iin")
    @classmethod
    def validate_iin_field(cls, v: str | None) -> str | None:
        return validate_iin(v)


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    facility_id: UUID | None
    iin: str | None
    photo_url: str | None
    transfer_date: date | None
    release_date: date | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
