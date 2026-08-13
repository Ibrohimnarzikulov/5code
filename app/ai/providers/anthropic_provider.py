"""Anthropic Claude provideri (pullik, lekin eng kuchli)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)

from app.ai.providers.base import Provider, ProviderError, final_event

# Anthropic tool_result bloki bu maydonni qabul qilmaydi — yuborishdan
# oldin olib tashlanadi (kanonik formatda Gemini/OpenAI uchun kerak).
_INTERNAL_FIELDS = ("name",)


def _clean_blocks(content: Any) -> Any:
    """Kanonik bloklardan ichki maydonlarni olib tashlaydi."""
    if isinstance(content, str):
        return content
    cleaned: list[dict[str, Any]] = []
    for block in content:
        if block.get("type") == "tool_result":
            cleaned.append(
                {k: v for k, v in block.items() if k not in _INTERNAL_FIELDS}
            )
        else:
            cleaned.append(block)
    return cleaned


def _serialize(blocks: list[Any]) -> list[dict[str, Any]]:
    """SDK bloklarini JSON dict'larga aylantiradi."""
    out: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, dict):
            out.append(block)
        elif hasattr(block, "model_dump"):
            out.append(block.model_dump(exclude_none=True))
        else:  # pragma: no cover
            out.append({"type": "text", "text": str(block)})
    return out


class AnthropicProvider(Provider):
    """Claude Messages API (streaming + tool use)."""

    name = "anthropic"

    def __init__(
        self, api_key: str, model: str, max_tokens: int, effort: str
    ) -> None:
        if not api_key:
            raise ProviderError(
                "ANTHROPIC_API_KEY sozlanmagan. .env fayliga kalitni qo'shing."
            )
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    @property
    def model(self) -> str:
        return self._model

    async def stream_turn(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [
                {"role": m["role"], "content": _clean_blocks(m["content"])}
                for m in messages
            ],
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self._effort},
        }
        if tools:
            request["tools"] = tools

        try:
            async with self._client.messages.stream(**request) as stream:
                async for event in stream:
                    if event.type != "content_block_delta":
                        continue
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield {"type": "text", "text": delta.text}
                    elif delta.type == "thinking_delta":
                        yield {"type": "thinking", "text": delta.thinking}

                response = await stream.get_final_message()
        except AuthenticationError:
            yield final_event([], "error", "API kalit noto'g'ri yoki bekor qilingan.")
            return
        except RateLimitError:
            yield final_event([], "error", "So'rovlar limiti oshdi. Biroz kuting.")
            return
        except APIConnectionError:
            yield final_event(
                [], "error", "Tarmoq xatosi: Claude API'ga ulanib bo'lmadi."
            )
            return
        except APIStatusError as exc:
            yield final_event(
                [], "error", f"API xatosi ({exc.status_code}): {exc.message}"
            )
            return

        blocks = _serialize(response.content)

        if response.stop_reason == "refusal":
            yield final_event(
                blocks, "refusal", "So'rov xavfsizlik siyosati bo'yicha rad etildi."
            )
            return

        yield final_event(
            blocks, "tool_use" if response.stop_reason == "tool_use" else "end"
        )
