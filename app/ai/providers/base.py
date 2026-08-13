"""Provider abstraksiyasi — bir nechta AI xizmatini bir xil interfeys bilan ishlatish.

**Kanonik format.** Bazada va tool siklida xabarlar Anthropic uslubidagi
bloklar ko'rinishida saqlanadi — barcha providerlar shu formatga/formatdan
o'giradi:

```python
{"role": "user",      "content": "matn"}                       # oddiy xabar
{"role": "assistant", "content": [
    {"type": "thinking",  "thinking": "...", "signature": "..."},
    {"type": "text",      "text": "..."},
    {"type": "tool_use",  "id": "...", "name": "...", "input": {...}},
]}
{"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "...", "name": "...",
     "content": "...", "is_error": False},
]}
```

`name` maydoni faqat ichki ehtiyoj uchun (Gemini/OpenAI tool javobiga nom
kerak) — Anthropic provideri uni yuborishdan oldin olib tashlaydi.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal

StopReason = Literal["end", "tool_use", "refusal", "error"]


class ProviderError(RuntimeError):
    """Provider sozlanmagan yoki noto'g'ri sozlangan."""


def final_event(
    blocks: list[dict[str, Any]],
    stop_reason: StopReason,
    message: str | None = None,
) -> dict[str, Any]:
    """Bir turning yakuniy hodisasini yasaydi."""
    return {
        "type": "final",
        "blocks": blocks,
        "stop_reason": stop_reason,
        "message": message,
    }


class Provider(ABC):
    """Bitta AI xizmati (Claude, Gemini, Groq va h.k.).

    Har bir provider **bitta turni** oqim sifatida bajaradi; tool chaqiruvlari
    sikli `app.ai.client` da umumiy tarzda boshqariladi.
    """

    name: str = "provider"

    @property
    @abstractmethod
    def model(self) -> str:
        """Ishlatilayotgan model ID."""

    @abstractmethod
    async def stream_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        """Bitta turni oqim qilib qaytaradi.

        Yield qilinadigan hodisalar:
        - `{"type": "text", "text": ...}` — javob matni bo'lagi
        - `{"type": "thinking", "text": ...}` — fikrlash bo'lagi (ixtiyoriy)
        - `{"type": "final", "blocks": [...], "stop_reason": ...}` — oxirgi

        `final` hodisasi **har doim** oxirida bir marta yuborilishi shart.
        """
        raise NotImplementedError
        yield {}  # pragma: no cover — abstract generator uchun


def text_of(blocks: list[dict[str, Any]] | str) -> str:
    """Bloklardan matnni yig'adi."""
    if isinstance(blocks, str):
        return blocks
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def tool_result_text(block: dict[str, Any]) -> str:
    """tool_result blokidan matnni oladi (string yoki bloklar ro'yxati)."""
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content)
    return str(content or "")
