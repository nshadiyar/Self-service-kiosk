from datetime import datetime
from pydantic import BaseModel, EmailStr

from app.core.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    facility_id: int | None = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    facility_id: int | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    facility_id: int | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
