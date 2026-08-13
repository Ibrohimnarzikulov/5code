"""Pydantic sxemalari — so'rov va javob modellari."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Role

# --- Auth ---


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=4, max_length=128)


class SignupRequest(BaseModel):
    """Ochiq ro'yxatdan o'tish — har doim oddiy `user` roli bilan."""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[\w.-]+$")
    password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# --- Foydalanuvchi ---


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    role: Role = Role.USER
    ai_in_pc: bool = False


class UserUpdate(BaseModel):
    """Admin tomonidan o'zgartiriladigan maydonlar (barchasi ixtiyoriy)."""

    password: str | None = Field(default=None, min_length=4, max_length=128)
    role: Role | None = None
    ai_in_pc: bool | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    ai_in_pc: bool
    is_active: bool
    ai_provider: str | None = None
    ai_model: str | None = None
    created_at: datetime


# --- Suhbat ---


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationCreate(BaseModel):
    title: str = Field(default="Yangi suhbat", max_length=200)


class MessageOut(BaseModel):
    id: int
    role: str
    content: list[dict] | str
    created_at: datetime


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=200_000)


# --- Modellar ---


class ModelOption(BaseModel):
    """Tanlash mumkin bo'lgan bitta AI model."""

    provider: str
    model: str
    label: str
    description: str
    local: bool
    available: bool
    recommended: bool = False


class ModelChoice(BaseModel):
    """Foydalanuvchi tanlovi. `None` — global sozlamaga qaytish."""

    provider: str | None = None
    model: str | None = None


# --- Artifact ---


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    title: str
    html: str
    version: int
    conversation_id: int | None
    created_at: datetime
    updated_at: datetime


TokenResponse.model_rebuild()
