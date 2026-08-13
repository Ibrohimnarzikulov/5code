"""Google Gemini provideri — tekin tier'dagi eng kuchli variant.

API kalit: https://aistudio.google.com/apikey (kredit karta kerak emas).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.providers.base import Provider, ProviderError, final_event, tool_result_text

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT = httpx.Timeout(300.0, connect=15.0)


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """JSON Schema'ni Gemini qabul qiladigan ko'rinishga keltiradi."""
    allowed = {
        "type",
        "description",
        "properties",
        "required",
        "items",
        "enum",
        "nullable",
    }
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in allowed:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {k: _clean_schema(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            out[key] = _clean_schema(value)
        else:
            out[key] = value
    return out


def _to_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kanonik xabarlarni Gemini `contents` formatiga o'giradi."""
    contents: list[dict[str, Any]] = []

    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        content = message["content"]

        if isinstance(content, str):
            contents.append({"role": role, "parts": [{"text": content}]})
            continue

        parts: list[dict[str, Any]] = []
        for block in content:
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                parts.append({"text": block["text"]})
            elif kind == "tool_use":
                parts.append(
                    {
                        "functionCall": {
                            "name": block["name"],
                            "args": block.get("input") or {},
                        }
                    }
                )
            elif kind == "tool_result":
                parts.append(
                    {
                        "functionResponse": {
                            "name": block.get("name", "tool"),
                            "response": {"result": tool_result_text(block)},
                        }
                    }
                )
            # `thinking` bloklari Gemini'ga uzatilmaydi — u o'z formatiga ega.

        if parts:
            contents.append({"role": role, "parts": parts})

    return contents


class GeminiProvider(Provider):
    """Gemini REST API (`streamGenerateContent`, SSE)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ProviderError(
                "GEMINI_API_KEY sozlanmagan. Tekin kalit: "
                "https://aistudio.google.com/apikey"
            )
        self._api_key = api_key
        self._model = model

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
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": _to_contents(messages),
        }
        if tools:
            payload["tools"] = [
                {
                    "function_declarations": [
                        {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": _clean_schema(tool["input_schema"]),
                        }
                        for tool in tools
                    ]
                }
            ]

        url = f"{API_ROOT}/models/{self._model}:streamGenerateContent"
        params = {"alt": "sse", "key": self._api_key}

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        finish_reason = ""

        try:
            async with (
                httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as http,
                http.stream("POST", url, params=params, json=payload) as response,
            ):
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "replace")
                    yield final_event(
                        [], "error", _explain_http(response.status_code, body)
                    )
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    for candidate in chunk.get("candidates", []):
                        finish_reason = (
                            candidate.get("finishReason") or finish_reason
                        )
                        for part in candidate.get("content", {}).get("parts", []):
                            if part.get("thought") and part.get("text"):
                                yield {"type": "thinking", "text": part["text"]}
                            elif "text" in part and part["text"]:
                                text_parts.append(part["text"])
                                yield {"type": "text", "text": part["text"]}
                            elif "functionCall" in part:
                                call = part["functionCall"]
                                tool_calls.append(
                                    {
                                        "type": "tool_use",
                                        "id": f"call_{uuid.uuid4().hex[:12]}",
                                        "name": call.get("name", ""),
                                        "input": call.get("args") or {},
                                    }
                                )
        except httpx.HTTPError as exc:
            yield final_event([], "error", f"Tarmoq xatosi: {exc}")
            return

        blocks: list[dict[str, Any]] = []
        joined = "".join(text_parts)
        if joined:
            blocks.append({"type": "text", "text": joined})
        blocks.extend(tool_calls)

        if finish_reason in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            yield final_event(
                blocks, "refusal", "So'rov Gemini xavfsizlik filtri bilan rad etildi."
            )
            return

        yield final_event(blocks, "tool_use" if tool_calls else "end")


def _explain_http(status: int, body: str) -> str:
    """HTTP xatosini o'zbekcha tushuntiradi."""
    detail = body[:300]
    if status == 400 and "API key not valid" in body:
        return "Gemini API kaliti noto'g'ri. aistudio.google.com/apikey dan oling."
    if status == 429:
        return "Gemini tekin limiti tugadi. Biroz kuting yoki modelni almashtiring."
    if status == 404:
        return f"Model topilmadi — GEMINI_MODEL ni tekshiring. ({detail})"
    return f"Gemini API xatosi ({status}): {detail}"
