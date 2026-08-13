"""Provider registri — sozlamalarga qarab kerakli AI xizmatini tanlaydi."""

from __future__ import annotations

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import Provider, ProviderError, final_event, text_of
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.openai_compat import OpenAICompatProvider
from app.config import settings

__all__ = [
    "AnthropicProvider",
    "GeminiProvider",
    "OpenAICompatProvider",
    "Provider",
    "ProviderError",
    "build_provider",
    "final_event",
    "provider_info",
    "text_of",
]


def build_provider(name: str | None = None, model: str | None = None) -> Provider:
    """Provider yaratadi (foydalanuvchi tanlovini hisobga olib).

    Args:
        name: `ollama` | `gemini` | `openai` | `anthropic`. Berilmasa `AI_PROVIDER`.
        model: Model ID. Berilmasa provider'ning standart modeli.

    Raises:
        ProviderError: nomi noma'lum yoki kalit sozlanmagan bo'lsa.

    Example:
        >>> provider = build_provider("ollama", "5code")
        >>> provider.model
        '5code'
    """
    choice = (name or settings.ai_provider).lower().strip()

    if choice == "ollama":
        # Lokal — API kalit kerak emas.
        return OpenAICompatProvider(
            settings.ollama_base_url, "", model or settings.ollama_model
        )

    if choice == "gemini":
        return GeminiProvider(
            settings.gemini_api_key or "", model or settings.gemini_model
        )

    if choice in {"openai", "groq", "openrouter"}:
        return OpenAICompatProvider(
            settings.openai_base_url,
            settings.openai_api_key or "",
            model or settings.openai_model,
        )

    if choice in {"anthropic", "claude"}:
        return AnthropicProvider(
            settings.anthropic_api_key or "",
            model or settings.claude_model,
            settings.claude_max_tokens,
            settings.claude_effort,
        )

    raise ProviderError(
        f"Noma'lum provider: '{choice}'. Mumkin: ollama, gemini, openai, anthropic."
    )


def provider_info() -> dict[str, object]:
    """Joriy provider haqida ma'lumot (`/api/health` uchun)."""
    choice = settings.ai_provider.lower().strip()
    keys = {
        "ollama": ("local", settings.ollama_model),
        "gemini": (settings.gemini_api_key, settings.gemini_model),
        "openai": (settings.openai_api_key, settings.openai_model),
        "anthropic": (settings.anthropic_api_key, settings.claude_model),
    }
    key, model = keys.get(choice, (None, "?"))
    # Ollama kabi lokal xizmatlarga kalit shart emas.
    is_local = choice == "openai" and "localhost" in settings.openai_base_url
    configured = bool(key) or is_local
    return {"provider": choice, "model": model, "configured": configured}
