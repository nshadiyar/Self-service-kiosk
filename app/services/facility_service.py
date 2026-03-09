from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.models.facility import Facility
from app.schemas.facility import FacilityCreate, FacilityUpdate


class FacilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, facility_id: int) -> Facility:
        result = await self.db.execute(select(Facility).where(Facility.id == facility_id))
        f = result.scalar_one_or_none()
        if not f:
            raise NotFoundError("Facility not found")
        return f

    async def list_facilities(self, skip: int = 0, limit: int = 20):
        result = await self.db.execute(
            select(Facility).where(Facility.is_active == True).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, data: FacilityCreate) -> Facility:
        result = await self.db.execute(select(Facility).where(Facility.code == data.code))
        if result.scalar_one_or_none():
            raise ConflictError("Facility with this code already exists")
        facility = Facility(
            name=data.name,
            code=data.code,
            address=data.address,
            security_regime=data.security_regime.value,
        )
        self.db.add(facility)
        await self.db.flush()
        await self.db.refresh(facility)
        return facility

    async def update(self, facility_id: int, data: FacilityUpdate) -> Facility:
        facility = await self.get_by_id(facility_id)
        if data.name is not None:
            facility.name = data.name
        if data.code is not None:
            facility.code = data.code
        if data.address is not None:
            facility.address = data.address
        if data.security_regime is not None:
            facility.security_regime = data.security_regime.value
        if data.is_active is not None:
            facility.is_active = data.is_active
        await self.db.flush()
        await self.db.refresh(facility)
        return facility
