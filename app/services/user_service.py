from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.core.exceptions import NotFoundError, ConflictError
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.wallet_service import WalletService


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_iin(self, iin: str) -> User | None:
        result = await self.db.execute(select(User).where(User.iin == iin))
        return result.scalar_one_or_none()

    async def list_users(self, facility_id: UUID | None = None, skip: int = 0, limit: int = 20):
        q = select(User).where(User.is_active == True)
        if facility_id is not None:
            q = q.where(User.facility_id == facility_id)
        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def create(self, data: UserCreate) -> User:
        existing = await self.get_by_email(data.email)
        if existing:
            raise ConflictError("User with this email already exists")
        if data.iin:
            existing_iin = await self.get_by_iin(data.iin)
            if existing_iin:
                raise ConflictError("User with this IIN already exists")
        user = User(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
            role=data.role,
            facility_id=data.facility_id,
            iin=data.iin,
            photo_url=data.photo_url,
            transfer_date=data.transfer_date,
            release_date=data.release_date,
        )
        self.db.add(user)
        await self.db.flush()

        if data.role == UserRole.INMATE:
            wallet_svc = WalletService(self.db)
            await wallet_svc.create_for_user(user.id)

        await self.db.refresh(user)
        return user

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        user = await self.get_by_id(user_id)
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.role is not None:
            user.role = data.role
        if data.facility_id is not None:
            user.facility_id = data.facility_id
        if data.iin is not None:
            new_iin = data.iin.strip() if data.iin else None
            if new_iin:
                existing_iin = await self.get_by_iin(new_iin)
                if existing_iin and existing_iin.id != user_id:
                    raise ConflictError("User with this IIN already exists")
            user.iin = new_iin
        if data.photo_url is not None:
            user.photo_url = data.photo_url
        if data.transfer_date is not None:
            user.transfer_date = data.transfer_date
        if data.release_date is not None:
            user.release_date = data.release_date
        if data.is_active is not None:
            user.is_active = data.is_active
        await self.db.flush()
        await self.db.refresh(user)
        return user
