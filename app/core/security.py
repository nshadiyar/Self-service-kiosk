from datetime import datetime, timedelta
from typing import Annotated, Any

import bcrypt
from fastapi import Depends, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.enums import UserRole
from app.dependencies import get_db
from app.models.user import User

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password
    return bcrypt.checkpw(pw_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    to_encode: dict[str, Any] = {"sub": str(subject)}
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | int) -> str:
    to_encode = {"sub": str(subject), "type": "refresh"}
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise AuthenticationError("Invalid or expired token")


async def get_current_user_dep(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthenticationError("Missing or invalid authorization header")
    token = auth_header.split()[-1]
    payload = verify_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token")
    result = await db.execute(
        select(User).where(User.id == int(user_id)).where(User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User not found")
    return user


def require_roles(*roles: UserRole):
    async def _check(current_user: User = Depends(get_current_user_dep)):
        if current_user.role not in roles:
            raise AuthorizationError("Insufficient permissions")
        return current_user
    return _check


require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_admin = require_roles(UserRole.SUPER_ADMIN, UserRole.PRISON_ADMIN)
require_inmate = require_roles(UserRole.INMATE)
require_any_user = require_roles(UserRole.SUPER_ADMIN, UserRole.PRISON_ADMIN, UserRole.INMATE)
