"""5code — Claude Code uslubidagi terminal agentic CLI.

Joriy ishlab turgan papka ustida ishlaydi: fayl o'qiydi/yozadi, shell
buyruq bajaradi (`app.ai.tools` sandboxi orqali, `workspace_root` shu
jarayonda joriy papkaga o'rnatiladi). Tool-calling sikli `app.ai.client`
dagi `stream_reply` bilan bir xil — veb-chat va CLI bitta testlangan
orkestratsiyadan foydalanadi.

Ishlatish:
    5code                              interaktiv suhbat
    5code "savol"                      bir martalik savol
    cat main.py | 5code "tushuntir"    pipe orqali kod
    5code --provider gemini "savol"    boshqa provider bilan
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, TextIO

from app.ai.client import stream_reply
from app.ai.providers import ProviderError
from app.ai.tools import ToolContext
from app.config import settings

DIM = "\033[2m"
ACC = "\033[36m"
ERR = "\033[31m"
BOLD = "\033[1m"
OFF = "\033[0m"

EXIT_WORDS = frozenset({"/bye", "exit", "quit", ":q"})
TOOL_RESULT_PREVIEW_LINES = 8
TOOL_ARGS_PREVIEW_CHARS = 100


def parse_args(argv: list[str]) -> argparse.Namespace:
    """CLI argumentlarini o'qiydi."""
    parser = argparse.ArgumentParser(
        prog="5code", description="Lokal/cloud AI kod yordamchisi — terminalda."
    )
    parser.add_argument("prompt", nargs="*", help="Bir martalik savol")
    parser.add_argument(
        "--provider",
        default=None,
        help="ollama (default) | gemini | openai | anthropic",
    )
    parser.add_argument("--model", default=None, help="Model ID (ixtiyoriy)")
    return parser.parse_args(argv)


def resolve_provider(args: argparse.Namespace) -> tuple[str, str | None]:
    """Provider/model tanlaydi — standart holatda lokal Ollama."""
    provider_name = args.provider or "ollama"
    model_name = args.model
    if model_name is None and provider_name == "ollama":
        model_name = settings.ollama_model
    return provider_name, model_name


def read_piped_stdin(stream: TextIO | None = None) -> str | None:
    """Pipe orqali kelgan matnni o'qiydi (interaktiv terminalda — None)."""
    stream = stream if stream is not None else sys.stdin
    if stream.isatty():
        return None
    data = stream.read()
    return data if data.strip() else None


# Xom provider/model nomlari ("ollama", "qwen2.5-coder"...) hech qachon
# terminalga chiqarilmaydi — o'rniga brend nomi ko'rsatiladi.
_BRAND_MODEL_LABELS = {"qwen2.5-coder": "5code_pro"}


def display_model(provider: str, model: str | None) -> str:
    """Terminalda ko'rsatiladigan brend nomi (ichki provider/model emas)."""
    if provider == "ollama":
        bare = (model or "").split(":")[0]
        return _BRAND_MODEL_LABELS.get(bare, bare or "5code")
    return model or provider


def format_banner(*, cwd: Path, provider: str, model: str | None) -> str:
    """Ishga tushishda ko'rsatiladigan holat va ruxsat banneri."""
    login_url = f"http://localhost:{settings.frontend_port}/login"
    return (
        f"{ACC}{BOLD}5code{OFF} {DIM}— lokal kod yordamchisi{OFF}\n"
        f"{DIM}Papka:{OFF}  {cwd}\n"
        f"{DIM}Model:{OFF}  {display_model(provider, model)}\n"
        f"{DIM}Sayt:{OFF}   {ACC}{login_url}{OFF} "
        f"{DIM}(avval shu yerda login qiling){OFF}\n"
        f"{DIM}Bu CLI shu papkada fayl o'qiy/yoza oladi va buyruq bajara oladi.{OFF}\n"
        f"{DIM}Xavfli buyruqlar tasdiq so'raydi. Chiqish: /bye yoki Ctrl+D{OFF}\n"
    )


def format_tool_use(name: str, tool_input: dict[str, Any]) -> str:
    """Tool chaqiruvini bitta qatorli ko'rinishda formatlaydi."""
    args = ", ".join(f"{k}={v!r}" for k, v in tool_input.items())
    if len(args) > TOOL_ARGS_PREVIEW_CHARS:
        args = args[:TOOL_ARGS_PREVIEW_CHARS] + "…"
    return f"{ACC}→ {name}{OFF}({DIM}{args}{OFF})"


def format_tool_result(content: str, *, is_error: bool) -> str:
    """Tool natijasini bir necha qatorgacha qisqartirib formatlaydi."""
    lines = content.splitlines() or [""]
    preview = "\n".join(lines[:TOOL_RESULT_PREVIEW_LINES])
    if len(lines) > TOOL_RESULT_PREVIEW_LINES:
        hidden = len(lines) - TOOL_RESULT_PREVIEW_LINES
        preview += f"\n{DIM}… ({hidden} qator yashirildi){OFF}"
    color = ERR if is_error else DIM
    return f"{color}{preview}{OFF}"


def render_event(event: dict[str, Any], *, out: TextIO, thinking_open: bool) -> bool:
    """Bitta oqim hodisasini terminalga yozadi.

    Returns:
        Yangilangan `thinking_open` holati — keyingi chaqiruvga uzatiladi.
    """
    kind = event["type"]

    if kind == "thinking":
        if not thinking_open:
            out.write(DIM)
        out.write(event["text"])
        out.flush()
        return True

    if thinking_open:
        out.write(f"{OFF}\n")
        thinking_open = False

    if kind == "text":
        out.write(event["text"])
        out.flush()
    elif kind == "tool_use":
        out.write(f"\n{format_tool_use(event['name'], event.get('input') or {})}\n")
    elif kind == "tool_result":
        result = format_tool_result(
            event.get("content", ""), is_error=event.get("is_error", False)
        )
        out.write(f"{result}\n")
    elif kind == "error":
        out.write(f"\n{ERR}Xatolik: {event['message']}{OFF}\n")
    # "artifact" hodisasi CLI rejimida kelmaydi (ToolContext.db=None).

    return thinking_open


async def run_turn(
    *,
    history: list[dict[str, Any]],
    user_text: str,
    ctx: ToolContext,
    provider_name: str,
    model_name: str | None,
    out: TextIO | None = None,
) -> list[dict[str, Any]]:
    """Bitta AI turnini oqim qilib bajaradi va terminalga chiqaradi.

    Returns:
        `history` ga qo'shiladigan yangi xabarlar (foydalanuvchi xabarisiz —
        uni chaqiruvchi o'zi qo'shadi, xuddi `app/routers/chat.py` dagidek).
    """
    # `out` chaqiruv vaqtida aniqlanadi — `sys.stdout` ni default qiymat
    # sifatida bersak, u import vaqtida "muzlab qolardi" (capsys kabi
    # sys.stdout'ni almashtiradigan testlarda yozuvlar ko'rinmay qolardi).
    out = out if out is not None else sys.stdout
    thinking_open = False
    new_messages: list[dict[str, Any]] = []

    async for event in stream_reply(
        history=history,
        user_message=user_text,
        ctx=ctx,
        provider_name=provider_name,
        model_name=model_name,
    ):
        if event["type"] == "assistant_message":
            new_messages = event["messages"]
            continue
        thinking_open = render_event(event, out=out, thinking_open=thinking_open)

    if thinking_open:
        out.write(f"{OFF}\n")
    out.write("\n")
    out.flush()
    return new_messages


async def amain(argv: list[str]) -> int:
    """Asosiy async kirish nuqtasi."""
    args = parse_args(argv)
    provider_name, model_name = resolve_provider(args)

    # Claude Code kabi: joriy ishlab turgan papka ustida ishlaydi (fixed
    # WORKSPACE_ROOT emas) — sandbox tekshiruvlari shu papka bilan ishlaydi.
    settings.workspace_root = Path.cwd()

    ctx = ToolContext(ai_in_pc=True, db=None)
    history: list[dict[str, Any]] = []

    piped = read_piped_stdin()
    one_shot = " ".join(args.prompt).strip()

    sys.stdout.write(
        format_banner(cwd=Path.cwd(), provider=provider_name, model=model_name)
    )

    try:
        if piped or one_shot:
            prompt = one_shot or "Shu kodni tahlil qil"
            if piped:
                prompt = f"{prompt}\n\n{piped}"
            sys.stdout.write(
                f"\n{BOLD}siz>{OFF} {one_shot or '(pipe orqali kod uzatildi)'}\n\n"
            )
            tail = await run_turn(
                history=history,
                user_text=prompt,
                ctx=ctx,
                provider_name=provider_name,
                model_name=model_name,
            )
            history.append({"role": "user", "content": prompt})
            history.extend(tail)
            return 0

        while True:
            try:
                user_text = input(f"\n{BOLD}siz>{OFF} ").strip()
            except EOFError:
                sys.stdout.write("\n")
                return 0

            if not user_text:
                continue
            if user_text in EXIT_WORDS:
                return 0

            tail = await run_turn(
                history=history,
                user_text=user_text,
                ctx=ctx,
                provider_name=provider_name,
                model_name=model_name,
            )
            history.append({"role": "user", "content": user_text})
            history.extend(tail)
    except ProviderError as exc:
        sys.stdout.write(f"{ERR}Provider xatosi: {exc}{OFF}\n")
        return 1
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return 130


def main() -> None:
    """`python -m app.cli` kirish nuqtasi."""
    raise SystemExit(asyncio.run(amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
