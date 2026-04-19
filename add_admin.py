import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models import User
from app.core.security import get_password_hash
from app.core.enums import UserRole

db_url = os.environ["DATABASE_PUBLIC_URL"].replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(db_url, connect_args={"ssl": "require"})
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(User).where(User.email == "admin1@facility.kz")
        )
        if existing.scalar_one_or_none():
            print("admin1@facility.kz уже существует")
            return
        admin = User(
            email="admin1@facility.kz",
            hashed_password=get_password_hash("Admin123!"),
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            facility_id=None,
        )
        db.add(admin)
        await db.commit()
        print("SUPER_ADMIN admin1@facility.kz добавлен!")

if __name__ == "__main__":
    asyncio.run(main())
