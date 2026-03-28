from uuid import UUID

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

    async def _find_user_by_login(self, login: str) -> User | None:
        """Find user by email or IIN."""
        login = login.strip()
        if "@" in login:
            result = await self.db.execute(select(User).where(User.email == login, User.is_active == True))
        else:
            result = await self.db.execute(select(User).where(User.iin == login, User.is_active == True))
        return result.scalar_one_or_none()

    async def login(self, login: str, password: str) -> tuple[str, str, UserRole]:
        user = await self._find_user_by_login(login)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid login or password")
        access = create_access_token(user.id)
        refresh = create_refresh_token(user.id)
        return access, refresh, user.role

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str, UserRole]:
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid refresh token")
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token")
        try:
            user_uuid = UUID(user_id)
        except (ValueError, TypeError):
            raise AuthenticationError("Invalid token")
        result = await self.db.execute(select(User).where(User.id == user_uuid, User.is_active == True))
        user = result.scalar_one_or_none()
        if not user:
            raise AuthenticationError("User not found")
        return create_access_token(user.id), create_refresh_token(user.id), user.role
