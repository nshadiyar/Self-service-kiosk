import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator

from app.core.enums import SecurityRegime, UserRole

IIN_PATTERN = re.compile(r"^\d{12}$")


def validate_iin(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not IIN_PATTERN.match(v):
        raise ValueError("ИИН должен состоять ровно из 12 цифр")
    return v


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    facility_id: UUID | None = None
    security_regime: SecurityRegime = SecurityRegime.GENERAL
    iin: str | None = None
    photo_url: str | None = None
    photo_object_key: str | None = None
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
    photo_object_key: str | None = None
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
    facility_name: str | None = None
    security_regime: SecurityRegime
    iin: str | None
    photo_url: str | None
    photo_object_key: str | None
    transfer_date: date | None
    release_date: date | None
    monthly_limit: Decimal | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("monthly_limit")
    def serialize_monthly_limit(self, v: Decimal | None) -> float | None:
        return float(v) if v is not None else None


class InmateCreateWithPhotoResponse(UserResponse):
    biometric_enrolled: bool
    biometric_provider: str


class InmateSettingsUpdate(BaseModel):
    security_regime: SecurityRegime | None = None
    monthly_limit: Decimal | None = Field(default=None, ge=0)
