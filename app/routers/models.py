"""AI modellarni ko'rish va tanlash."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.deps import CurrentUser, DbSession
from app.schemas import ModelChoice, ModelOption, UserOut

router = APIRouter(prefix="/api/models", tags=["models"])

OLLAMA_TAGS_TIMEOUT = 2.0
PRIMARY_LOCAL_MODEL = "5code"


async def _ollama_models() -> list[str]:
    """Lokal Ollama'dagi modellar ro'yxati (xizmat yopiq bo'lsa — bo'sh)."""
    base = settings.ollama_base_url.rstrip("/").removesuffix("/v1")
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TAGS_TIMEOUT) as http:
            response = await http.get(f"{base}/api/tags")
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    return [m["name"] for m in data.get("models", []) if m.get("name")]


@router.get("", response_model=list[ModelOption])
async def list_models(_: CurrentUser) -> list[ModelOption]:
    """Mavjud modellar: lokal (Ollama) + cloud.

    `available=False` — model bor, lekin kalit/yuklash yetishmaydi.
    """
    options: list[ModelOption] = []

    # --- Lokal (Ollama) ---
    installed = await _ollama_models()
    installed_bare = {name.split(":")[0] for name in installed}

    options.append(
        ModelOption(
            provider="ollama",
            model=PRIMARY_LOCAL_MODEL,
            label="5code (lokal)",
            description=(
                "Shaxsiy kod modeli —Internetsiz "
                "ishlaydi, hech qanday ma'lumot kompyuterdan chiqmaydi."
            ),
            local=True,
            available=PRIMARY_LOCAL_MODEL in installed_bare,
            recommended=True,
        )
    )

    for name in sorted(installed):
        if name.split(":")[0] == PRIMARY_LOCAL_MODEL:
            continue
        options.append(
            ModelOption(
                provider="ollama",
                model=name,
                label=name,
                description="Lokal Ollama modeli — internetsiz ishlaydi.",
                local=True,
                available=True,
            )
        )

    # --- Cloud ---
    options.append(
        ModelOption(
            provider="gemini",
            model=settings.gemini_model,
            label=f"Gemini — {settings.gemini_model}",
            description=(
                "Tekin cloud model. Kuchliroq va tezroq, lekin so'rovlar "
                "Google serverlariga yuboriladi."
            ),
            local=False,
            available=bool(settings.gemini_api_key),
        )
    )

    if settings.anthropic_api_key:
        options.append(
            ModelOption(
                provider="anthropic",
                model=settings.claude_model,
                label=f"Claude — {settings.claude_model}",
                description="Eng kuchli model (pullik).",
                local=False,
                available=True,
            )
        )

    return options


@router.put("/selection", response_model=UserOut)
async def choose_model(
    choice: ModelChoice, db: DbSession, user: CurrentUser
) -> UserOut:
    """Foydalanuvchi uchun AI modelni tanlaydi.

    Ikkalasini ham `null` yuborsangiz — global sozlamaga qaytadi.
    """
    if bool(choice.provider) != bool(choice.model):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provider va model birgalikda berilishi kerak",
        )

    allowed = {"ollama", "gemini", "openai", "anthropic"}
    if choice.provider and choice.provider not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Noma'lum provider: {choice.provider}",
        )

    user.ai_provider = choice.provider
    user.ai_model = choice.model
    await db.flush()
    await db.refresh(user)
    return UserOut.model_validate(user)
