from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.core.exceptions import AuthenticationError
from app.core.enums import UserRole
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str) -> tuple[str, str]:
        result = await self.db.execute(select(User).where(User.email == email, User.is_active == True))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        access = create_access_token(user.id)
        refresh = create_refresh_token(user.id)
        return access, refresh

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid refresh token")
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token")
        result = await self.db.execute(select(User).where(User.id == int(user_id), User.is_active == True))
        user = result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("User not found")
        return create_access_token(user.id), create_refresh_token(user.id)
