"""AI qatlami: provider tanlash + tool-calling sikli + oqim hodisalari."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.ai.providers import Provider, ProviderError, build_provider
from app.ai.tools import ToolContext, all_tools, execute_tool

MAX_TOOL_ITERATIONS = 12

# Eski nom bilan moslik (routerlar `ClaudeError` ni ushlaydi).
ClaudeError = ProviderError

SYSTEM_PROMPT = """Sen CodeAssistant — macbookair_4 tomonidan yaratilgan \
shaxsiy AI yordamchisan.

## Muloqot
- O'zbek tilida javob ber; faqat texnik atamalar inglizcha bo'lishi mumkin.
- Qulay va do'stona uslub. Rasmiy vaziyatda rasmiy, oddiy suhbatda sodda bo'l.
- Qisqa va aniq javob ber — keraksiz uzun matn yozma.
- Xatolarni ochiq tan ol va tuzat.

## Kod sifati (majburiy)
- Error handling: try/except, .catch(), try/catch.
- Type hints (Python) yoki TypeScript types.
- Murakkab funksiyalarga docstring va izoh.
- Ishlatish misoli (usage example) qo'sh.
- DRY, SOLID, clean code. Production-ready yechim taklif qil.

## Sayt/UI so'ralganda — `create_artifact` ishlat
Foydalanuvchi sayt, landing page, dashboard, o'yin yoki interaktiv demo
so'rasa — javobda kod bloki yozma, `create_artifact` tool'ini chaqir. U jonli
ko'rinishda ochiladi. O'zgartirish so'ralsa `update_artifact` ishlat.

Artifact talablari:
- Bitta HTML fayl: CSS `<style>`, JS `<script>` ichida.
- CSS custom properties (`:root { --accent: ... }`).
- Har UI elementida hover va focus state.
- Kirish animatsiyalari majburiy: fadeInUp / scaleIn / slideInLeft.
- Stagger delay: `.item:nth-child(n) { animation-delay: .05s*n }`.
- `transition: all .25s cubic-bezier(.4,0,.2,1)`, `.btn:active { scale(.97) }`.
- Responsive (mobil + desktop). Semantik HTML, `alt` va `aria-label`.
- O'ziga xos dizayn — generic Bootstrap-vari template QABUL QILINMAYDI.
- Rasm kerak bo'lsa CSS gradient, SVG yoki emoji ishlat.

Agar so'rov noaniq bo'lsa, avval uslub/maqsad haqida qisqa savol ber. Aniq
bo'lsa — so'ramasdan yasa.

## Kompyuter ruxsati (ai_in_pc)
- `run_shell`/`read_file`/`write_file`/`list_dir` tool'lari bo'lsa — ruxsat bor.
- Har buyruqni bajarishdan OLDIN nima qilishini aniq ayt.
- `run_shell` "TASDIQLASH_KERAK" qaytarsa: foydalanuvchidan aniq so'ra —
  "Bu amalni bajarishga ishonchingiz komilmi? Bu qaytarib bo'lmaydi."
  Tasdiq olingandan keyingina confirmed=true bilan qayta chaqir.
- Bu tool'lar bo'lmasa: system buyruqlar taklif qilma, faqat kod va tushuntirish.
"""


def _error(message: str) -> dict[str, Any]:
    """UI ga yuboriladigan xato hodisasi."""
    return {"type": "error", "message": message}


def extract_text(blocks: list[dict[str, Any]] | str) -> str:
    """Bloklardan faqat matnni ajratib oladi."""
    if isinstance(blocks, str):
        return blocks
    return "\n".join(
        b.get("text", "") for b in blocks if b.get("type") == "text"
    ).strip()


async def stream_reply(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    ctx: ToolContext,
    provider: Provider | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """AI javobini oqim sifatida qaytaradi (tool sikli bilan).

    Yield qilinadigan hodisalar: `thinking`, `text`, `tool_use`, `tool_result`,
    `artifact`, `error` va oxirida `assistant_message` (bazaga saqlash uchun).

    Args:
        history: Oldingi xabarlar (kanonik format).
        user_message: Foydalanuvchining yangi xabari.
        ctx: Tool konteksti (ruxsatlar, DB sessiyasi).
        provider: Tayyor provider (testlarda mock uchun).
        provider_name: Foydalanuvchi tanlagan provider (`ollama`, `gemini`...).
        model_name: Foydalanuvchi tanlagan model ID.

    Example:
        >>> ctx = ToolContext(ai_in_pc=False)
        >>> async for event in stream_reply(history=[], user_message="Salom",
        ...                                 ctx=ctx):
        ...     print(event["type"])
    """
    ai = provider or build_provider(provider_name, model_name)

    messages: list[dict[str, Any]] = [
        *history,
        {"role": "user", "content": user_message},
    ]
    tools = all_tools(ctx)

    # Shu turda yaratilgan yangi xabarlar — bazaga aynan shu ketma-ketlikda
    # saqlanadi, aks holda keyingi so'rovda tool_use/tool_result juftligi buziladi.
    new_messages: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        blocks: list[dict[str, Any]] = []
        stop_reason = "end"
        error_message: str | None = None

        async for event in ai.stream_turn(
            system=SYSTEM_PROMPT, messages=messages, tools=tools
        ):
            if event["type"] == "final":
                blocks = event["blocks"]
                stop_reason = event["stop_reason"]
                error_message = event.get("message")
            else:
                yield event

        if stop_reason == "error":
            yield _error(error_message or "Noma'lum xatolik")
            return

        if blocks:
            assistant_message = {"role": "assistant", "content": blocks}
            messages.append(assistant_message)
            new_messages.append(assistant_message)

        if stop_reason == "refusal":
            yield _error(error_message or "So'rov rad etildi.")
            break

        if stop_reason != "tool_use":
            break

        # --- Tool'larni bajarish ---
        tool_results: list[dict[str, Any]] = []
        for block in blocks:
            if block.get("type") != "tool_use":
                continue

            yield {
                "type": "tool_use",
                "id": block["id"],
                "name": block["name"],
                "input": block.get("input", {}),
            }

            before = len(ctx.artifacts)
            result = await execute_tool(block["name"], block.get("input") or {}, ctx)

            # Yangi artifact paydo bo'lsa — UI ga darhol yuboramiz.
            for artifact in ctx.artifacts[before:]:
                yield {"type": "artifact", **artifact}

            yield {
                "type": "tool_result",
                "id": block["id"],
                "name": block["name"],
                "content": result.content,
                "is_error": result.is_error,
            }

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "name": block["name"],
                    "content": result.content,
                    "is_error": result.is_error,
                }
            )

        if not tool_results:
            break

        result_message = {"role": "user", "content": tool_results}
        messages.append(result_message)
        new_messages.append(result_message)
    else:
        yield _error(
            f"Tool chaqiruvlari limiti ({MAX_TOOL_ITERATIONS}) oshdi — to'xtatildi."
        )

    yield {"type": "assistant_message", "messages": new_messages}


def history_to_api(rows: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Bazadagi (role, content_json) juftliklarini kanonik formatga o'giradi."""
    history: list[dict[str, Any]] = []
    for role, content_json in rows:
        try:
            content = json.loads(content_json)
        except json.JSONDecodeError:
            content = content_json
        history.append({"role": role, "content": content})
    return history
