from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import SecurityRegime


class FacilityBase(BaseModel):
    name: str
    code: str
    address: str | None = None
    security_regime: SecurityRegime = SecurityRegime.GENERAL


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None
    security_regime: SecurityRegime | None = None
    is_active: bool | None = None


class FacilityResponse(BaseModel):
    id: UUID
    name: str
    code: str
    address: str | None
    security_regime: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
