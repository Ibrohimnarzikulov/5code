"""OpenAI-mos providerlar: Groq, OpenRouter, Ollama, Together va boshqalar.

Bu adapter `/chat/completions` endpoint'iga ega har qanday xizmat bilan
ishlaydi — faqat `OPENAI_BASE_URL` va `OPENAI_MODEL` ni almashtirasiz.

| Xizmat | base_url | Tekin misol model |
| --- | --- | --- |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `deepseek/deepseek-chat:free` |
| Ollama (lokal) | `http://localhost:11434/v1` | `qwen2.5-coder` |
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.providers.base import Provider, ProviderError, final_event, tool_result_text

REQUEST_TIMEOUT = httpx.Timeout(300.0, connect=15.0)

# Ollama'ning ba'zi shablonlari (masalan, qwen2.5-coder) modeldan tool
# chaqiruvini strukturaviy `tool_calls` o'rniga shu teg ichida matn sifatida
# qaytarishni so'raydi — model tegsiz, xom JSON qaytarsa ham tez-tez uchraydi.
_TOOL_CALL_TAG = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_CODE_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_fallback_tool_call(
    text: str, tool_names: set[str]
) -> dict[str, Any] | None:
    """Matn ko'rinishida kelgan tool chaqiruvni `tool_use` blokiga o'giradi.

    Ba'zi lokal modellar (Ollama orqali) tool chaqiruvini strukturaviy
    `tool_calls` maydoni o'rniga oddiy matn/JSON sifatida qaytaradi — model
    hech qanday tool_calls bermagan va butun javob bitta tool'ga mos JSON
    bo'lgandagina ishlaydi, aks holda `None` qaytarib oddiy matn sifatida
    qoldiradi.
    """
    match = _TOOL_CALL_TAG.search(text)
    candidate = match.group(1) if match else text.strip()

    if not match:
        fenced = _CODE_FENCE.match(candidate)
        if fenced:
            candidate = fenced.group(1)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    name = data.get("name")
    if not isinstance(name, str) or name not in tool_names:
        return None

    arguments = data.get("arguments", data.get("parameters", {}))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}

    return {
        "type": "tool_use",
        "id": f"call_{secrets.token_hex(4)}",
        "name": name,
        "input": arguments if isinstance(arguments, dict) else {},
    }


def _to_messages(
    system: str, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Kanonik xabarlarni OpenAI chat formatiga o'giradi."""
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]

    for message in messages:
        content = message["content"]

        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue

        if message["role"] == "user":
            # tool_result bloklari alohida `tool` rollik xabarlarga aylanadi.
            texts: list[str] = []
            for block in content:
                if block.get("type") == "tool_result":
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": tool_result_text(block),
                        }
                    )
                elif block.get("type") == "text":
                    texts.append(block.get("text", ""))
            if texts:
                out.append({"role": "user", "content": "\n".join(texts)})
            continue

        # assistant
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        tool_calls = [
            {
                "id": b["id"],
                "type": "function",
                "function": {
                    "name": b["name"],
                    "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False),
                },
            }
            for b in content
            if b.get("type") == "tool_use"
        ]
        entry: dict[str, Any] = {
            "role": "assistant",
            "content": "\n".join(t for t in texts if t) or None,
        }
        if tool_calls:
            entry["tool_calls"] = tool_calls
        out.append(entry)

    return out


class OpenAICompatProvider(Provider):
    """`/chat/completions` (SSE streaming) orqali ishlovchi provider."""

    name = "openai"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        if not base_url:
            raise ProviderError("OPENAI_BASE_URL sozlanmagan.")
        # Ollama kabi lokal xizmatlarga kalit kerak emas.
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or "not-needed"
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
            "model": self._model,
            "messages": _to_messages(system, messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ]

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            # OpenRouter tavsiya qiladigan meta-sarlavhalar
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "CodeAssistant",
        }

        text_parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        finish_reason = ""

        try:
            async with (
                httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as http,
                http.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response,
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

                    for choice in chunk.get("choices", []):
                        finish_reason = choice.get("finish_reason") or finish_reason
                        delta = choice.get("delta") or {}

                        reasoning = delta.get("reasoning") or delta.get(
                            "reasoning_content"
                        )
                        if reasoning:
                            yield {"type": "thinking", "text": reasoning}

                        if delta.get("content"):
                            text_parts.append(delta["content"])
                            yield {"type": "text", "text": delta["content"]}

                        for call in delta.get("tool_calls") or []:
                            index = call.get("index", 0)
                            slot = calls.setdefault(
                                index, {"id": "", "name": "", "args": ""}
                            )
                            if call.get("id"):
                                slot["id"] = call["id"]
                            function = call.get("function") or {}
                            if function.get("name"):
                                slot["name"] = function["name"]
                            if function.get("arguments"):
                                slot["args"] += function["arguments"]
        except httpx.HTTPError as exc:
            yield final_event([], "error", f"Tarmoq xatosi: {exc}")
            return

        blocks: list[dict[str, Any]] = []
        joined = "".join(text_parts)

        fallback_call = None
        if not calls and joined.strip():
            tool_names = {tool["name"] for tool in tools}
            fallback_call = _parse_fallback_tool_call(joined, tool_names)

        if fallback_call:
            blocks.append(fallback_call)
        elif joined:
            blocks.append({"type": "text", "text": joined})

        for index in sorted(calls):
            slot = calls[index]
            if not slot["name"]:
                continue
            try:
                arguments = json.loads(slot["args"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            blocks.append(
                {
                    "type": "tool_use",
                    "id": slot["id"] or f"call_{index}",
                    "name": slot["name"],
                    "input": arguments,
                }
            )

        has_tools = any(b["type"] == "tool_use" for b in blocks)
        if finish_reason == "content_filter":
            yield final_event(
                blocks, "refusal", "So'rov kontent filtri bilan rad etildi."
            )
            return

        yield final_event(blocks, "tool_use" if has_tools else "end")


def _explain_http(status: int, body: str) -> str:
    detail = body[:300]
    if status in (401, 403):
        return "API kalit noto'g'ri yoki ruxsat yo'q (OPENAI_API_KEY)."
    if status == 429:
        return "Limit tugadi. Biroz kuting yoki boshqa modelga o'ting."
    if status == 404:
        return (
            "Model yoki endpoint topilmadi — OPENAI_MODEL/BASE_URL ni "
            f"tekshiring. ({detail})"
        )
    return f"API xatosi ({status}): {detail}"
