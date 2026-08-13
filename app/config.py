"""Ilova sozlamalari — barcha konfiguratsiya shu yerda."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Muhit o'zgaruvchilaridan (.env) o'qiladigan sozlamalar."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Umumiy ---
    app_name: str = "CodeAssistant"
    debug: bool = False

    # --- Portlar ---
    # Backend (FastAPI) → 1221 · Frontend (React/Vite) → 1991
    backend_port: int = 1221
    frontend_port: int = 1991
    # React dev-serveri boshqa portda bo'lgani uchun CORS kerak.
    cors_origins: list[str] = [
        "http://localhost:1991",
        "http://127.0.0.1:1991",
    ]

    # --- Ro'yxatdan o'tish ---
    # Yopiq bo'lsa foydalanuvchilarni faqat admin yaratadi.
    allow_signup: bool = True

    # --- Xavfsizlik ---
    secret_key: str = "CHANGE-ME-please-generate-a-long-random-string"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 kun
    jwt_algorithm: str = "HS256"

    # --- Ma'lumotlar bazasi ---
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'codeassistant.db'}"

    # --- AI provider tanlovi ---
    # gemini   → tekin, eng kuchli bepul variant (default)
    # openai   → OpenAI-mos har qanday xizmat: Groq / OpenRouter / Ollama
    # anthropic→ Claude (pullik, eng kuchli)
    ai_provider: str = "gemini"

    # --- Google Gemini (TEKIN — aistudio.google.com/apikey) ---
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    # --- Ollama (lokal, tekin, internetsiz) ---
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "5code"

    # --- OpenAI-mos xizmatlar (Groq / OpenRouter) ---
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_api_key: str | None = None
    openai_model: str = "llama-3.3-70b-versatile"

    # --- Claude API (ixtiyoriy, pullik) ---
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5"
    claude_max_tokens: int = 32000
    claude_effort: str = "high"  # low | medium | high | xhigh | max

    # --- ai_in_pc (kompyuter ruxsati) ---
    # Fayl operatsiyalari va shell buyruqlari faqat shu papka ichida ishlaydi.
    workspace_root: Path = BASE_DIR / "workspace"
    shell_timeout_seconds: int = 60
    shell_max_output_chars: int = 20_000

    # --- Birinchi admin (start-up'da avtomatik yaratiladi) ---
    # Parol bo'sh bo'lsa — tasodifiy yaratiladi va logga bir marta chiqadi.
    admin_username: str = "macbookair_4"
    admin_password: str = ""

    @property
    def sqlite_path(self) -> Path | None:
        """SQLite fayl yo'li (agar SQLite ishlatilsa)."""
        if "sqlite" not in self.database_url:
            return None
        return Path(self.database_url.split("///", 1)[-1])


@lru_cache
def get_settings() -> Settings:
    """Sozlamalarni bir marta yuklab, keshlab qo'yadi."""
    return Settings()


settings = get_settings()
