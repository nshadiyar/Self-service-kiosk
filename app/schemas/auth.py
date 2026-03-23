from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login by email or IIN (12 digits)."""

    login: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str
