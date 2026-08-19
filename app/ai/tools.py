"""ai_in_pc tool'lari: shell, fayl o'qish/yozish, papka ro'yxati.

Xavfsizlik qatlamlari (uchtasi ham majburiy):

1. **Ruxsat gate'i** — tool'lar faqat `ai_in_pc=True` foydalanuvchiga beriladi.
2. **Path sandbox** — barcha fayl amallari `workspace_root` ichida qulflangan.
3. **Tasdiqlash** — xavfli shell buyruqlari `confirmed=True` bo'lmasa
   bajarilmaydi; model foydalanuvchidan og'zaki tasdiq so'rashi kerak.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings

# --- Xavfli buyruq shablonlari ---------------------------------------------
# Har biri: (regex, o'zbekcha tushuntirish)
DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\b"), "fayl/papka o'chirish (rm)"),
    (re.compile(r"\brmdir\b"), "papka o'chirish (rmdir)"),
    (re.compile(r"\bdd\b"), "disk yozish (dd)"),
    (re.compile(r"\bmkfs\b"), "diskni formatlash (mkfs)"),
    (re.compile(r"\b(shutdown|reboot|halt)\b"), "tizimni o'chirish/qayta yuklash"),
    (re.compile(r"\b(kill|killall|pkill)\b"), "jarayonni to'xtatish"),
    (re.compile(r"\bsudo\b"), "superuser huquqi bilan bajarish (sudo)"),
    (re.compile(r"\bchmod\s+-?R?\s*777\b"), "to'liq ochiq huquq berish (chmod 777)"),
    (re.compile(r"\b(diskutil|fdisk|parted)\b"), "disk boshqaruvi"),
    (re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|push\s+--force)"),
     "qaytarib bo'lmaydigan git amali"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE), "SQL DROP"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "SQL TRUNCATE"),
    (re.compile(r">\s*/dev/"), "/dev ga yozish"),
    (re.compile(r":\(\)\s*\{.*\};\s*:"), "fork bomb"),
    (re.compile(r"\bcurl\b.*\|\s*(ba)?sh"), "internetdan skript yuklab bajarish"),
    (re.compile(r"\bwget\b.*\|\s*(ba)?sh"), "internetdan skript yuklab bajarish"),
]

MAX_FILE_READ_CHARS = 200_000


class ToolError(Exception):
    """Tool bajarilishidagi kutilgan xatolik (modelga qaytariladi)."""


@dataclass(frozen=True)
class ToolResult:
    """Tool natijasi."""

    content: str
    is_error: bool = False


# --- Tool sxemalari ---------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "run_shell",
        "description": (
            "Foydalanuvchi kompyuterida shell buyrug'ini bajaradi. Buyruq "
            "workspace papkasida ishga tushadi. Xavfli buyruqlar (rm, sudo, "
            "kill, dd va h.k.) uchun avval foydalanuvchidan og'zaki tasdiq "
            "so'rang, keyin confirmed=true bilan qayta chaqiring. Buyruqni "
            "bajarishdan oldin nima qilishini foydalanuvchiga aniq ayting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Bajariladigan shell buyrug'i",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": (
                        "Foydalanuvchi xavfli amalni og'zaki tasdiqlagan bo'lsa true"
                    ),
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Workspace ichidagi faylni o'qiydi va matn sifatida qaytaradi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Workspace'ga nisbatan fayl yo'li",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Workspace ichida fayl yaratadi yoki to'liq qayta yozadi. "
            "Foydalanuvchi fayl/kod yozishni so'raganda SHU tool'dan "
            "foydalan — javobda kod blokini yozib, foydalanuvchiga o'zi "
            "saqlashni taklif qilish emas. Mavjud faylni qayta yozishdan "
            "oldin foydalanuvchini ogohlantiring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Workspace'ga nisbatan fayl yo'li",
                },
                "content": {"type": "string", "description": "Fayl mazmuni"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "Workspace ichidagi papka mazmunini ro'yxatlaydi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Papka yo'li (bo'sh bo'lsa — workspace ildizi)",
                }
            },
            "required": [],
        },
    },
]

TOOL_NAMES = frozenset(schema["name"] for schema in TOOL_SCHEMAS)


# --- Yordamchilar -----------------------------------------------------------


def check_dangerous(command: str) -> list[str]:
    """Buyruqdagi xavfli amallar ro'yxatini qaytaradi (bo'sh bo'lsa — xavfsiz)."""
    return [reason for pattern, reason in DANGEROUS_PATTERNS if pattern.search(command)]


def resolve_in_workspace(raw_path: str) -> Path:
    """Yo'lni workspace ichida xavfsiz hal qiladi.

    Raises:
        ToolError: yo'l workspace tashqarisiga chiqsa.
    """
    root = settings.workspace_root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    candidate = Path(raw_path.strip() or ".")
    target = (candidate if candidate.is_absolute() else root / candidate).resolve()

    if target != root and root not in target.parents:
        raise ToolError(
            f"Ruxsat yo'q: '{raw_path}' workspace tashqarisida. "
            f"Faqat {root} ichida ishlash mumkin."
        )
    return target


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [{len(text) - limit} belgi qisqartirildi]"


# --- Tool implementatsiyalari ----------------------------------------------


async def _run_shell(command: str, confirmed: bool = False) -> ToolResult:
    command = command.strip()
    if not command:
        raise ToolError("Bo'sh buyruq berildi.")

    dangers = check_dangerous(command)
    if dangers and not confirmed:
        joined = ", ".join(dangers)
        return ToolResult(
            content=(
                "TASDIQLASH_KERAK\n"
                f"Buyruq: {command}\n"
                f"Aniqlangan xavf: {joined}\n"
                "Bu amalni bajarishdan oldin foydalanuvchidan aniq tasdiq so'rang "
                "(\"Bu amalni bajarishga ishonchingiz komilmi? Bu qaytarib "
                "bo'lmaydi.\"). Tasdiq olingandan keyin confirmed=true bilan "
                "qayta chaqiring."
            ),
            is_error=True,
        )

    cwd = settings.workspace_root.resolve()
    cwd.mkdir(parents=True, exist_ok=True)

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(cwd),
            env=env,
        )
    except OSError as exc:  # pragma: no cover - OS darajasidagi nodir xato
        raise ToolError(f"Buyruqni ishga tushirib bo'lmadi: {exc}") from exc

    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(), timeout=settings.shell_timeout_seconds
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise ToolError(
            f"Buyruq {settings.shell_timeout_seconds}s ichida tugamadi va to'xtatildi."
        ) from None

    output = stdout.decode("utf-8", errors="replace")
    body = _truncate(output, settings.shell_max_output_chars) or "(chiqish bo'sh)"

    return ToolResult(
        content=f"exit_code={process.returncode}\n{body}",
        is_error=process.returncode != 0,
    )


async def _read_file(path: str) -> ToolResult:
    target = resolve_in_workspace(path)
    if not target.is_file():
        raise ToolError(f"Fayl topilmadi: {path}")
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ToolError(f"Faylni o'qib bo'lmadi: {exc}") from exc
    return ToolResult(content=_truncate(text, MAX_FILE_READ_CHARS))


async def _write_file(path: str, content: str) -> ToolResult:
    target = resolve_in_workspace(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Faylni yozib bo'lmadi: {exc}") from exc
    rel = target.relative_to(settings.workspace_root.resolve())
    return ToolResult(content=f"Yozildi: {rel} ({len(content)} belgi)")


async def _list_dir(path: str = "") -> ToolResult:
    target = resolve_in_workspace(path)
    if not target.is_dir():
        raise ToolError(f"Papka topilmadi: {path or '.'}")

    entries: list[str] = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if item.is_dir():
            entries.append(f"{item.name}/")
        else:
            entries.append(f"{item.name}  ({item.stat().st_size} bayt)")

    return ToolResult(content="\n".join(entries) or "(papka bo'sh)")


_HANDLERS = {
    "run_shell": _run_shell,
    "read_file": _read_file,
    "write_file": _write_file,
    "list_dir": _list_dir,
}


# --- Artifact tool'lari -----------------------------------------------------
# Bular kompyuterga tegmaydi, shuning uchun ai_in_pc ruxsatisiz ham ishlaydi.

ARTIFACT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "create_artifact",
        "description": (
            "To'liq, ishga tayyor bir faylli HTML sayt yoki ilova yaratadi va "
            "foydalanuvchiga jonli ko'rinishda ko'rsatadi. Foydalanuvchi sayt, "
            "landing page, dashboard, o'yin yoki interaktiv demo so'raganda "
            "SHU tool'dan foydalan — javobda kod bloki yozib qo'yish emas.\n"
            "Talablar: butun sayt bitta HTML faylda; CSS `<style>` ichida, JS "
            "`<script>` ichida; responsive; hover va focus state; kirish "
            "animatsiyalari (fadeInUp/scaleIn) va stagger delay; CSS custom "
            "properties. Generic template dizayn qabul qilinmaydi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Sayt nomi (qisqa)",
                },
                "html": {
                    "type": "string",
                    "description": "<!doctype html> bilan boshlanadigan to'liq HTML",
                },
            },
            "required": ["title", "html"],
        },
    },
    {
        "name": "update_artifact",
        "description": (
            "Mavjud artifactni yangi HTML bilan to'liq almashtiradi (yangi "
            "versiya yaratiladi). Foydalanuvchi o'zgartirish so'raganda ishlating."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "integer", "description": "Artifact ID"},
                "html": {"type": "string", "description": "Yangilangan to'liq HTML"},
                "title": {"type": "string", "description": "Yangi nom (ixtiyoriy)"},
            },
            "required": ["artifact_id", "html"],
        },
    },
]

MIN_ARTIFACT_HTML = 40


@dataclass
class ToolContext:
    """Tool bajarilishi uchun kerakli kontekst."""

    ai_in_pc: bool
    user_id: int | None = None
    conversation_id: int | None = None
    db: Any = None  # AsyncSession — sirkulyar importni oldini olish uchun Any
    # Shu turda yaratilgan/yangilangan artifactlar (UI ga yuborish uchun).
    artifacts: list[dict[str, Any]] = field(default_factory=list)


def all_tools(ctx: ToolContext) -> list[dict[str, Any]]:
    """Kontekstga mos tool ro'yxati: artifact + (ruxsat bo'lsa) kompyuter."""
    tools = list(ARTIFACT_TOOL_SCHEMAS) if ctx.db is not None else []
    if ctx.ai_in_pc:
        tools.extend(TOOL_SCHEMAS)
    return tools


async def _create_artifact(ctx: ToolContext, title: str, html: str) -> ToolResult:
    from app.models import Artifact  # kechiktirilgan import — sirkulyarlikdan qochish

    if len(html.strip()) < MIN_ARTIFACT_HTML:
        raise ToolError("HTML juda qisqa — to'liq sahifa yuboring.")

    artifact = Artifact(
        token=secrets.token_urlsafe(16),
        user_id=ctx.user_id,
        conversation_id=ctx.conversation_id,
        title=title.strip()[:200] or "Sayt",
        html=html,
        version=1,
    )
    ctx.db.add(artifact)
    await ctx.db.flush()

    ctx.artifacts.append(
        {
            "id": artifact.id,
            "token": artifact.token,
            "title": artifact.title,
            "version": artifact.version,
        }
    )
    return ToolResult(
        content=(
            f"Artifact yaratildi: id={artifact.id}, nom='{artifact.title}'. "
            "Foydalanuvchi uni o'ng paneldagi jonli ko'rinishda ko'rmoqda. "
            "Endi qisqacha nima yasaganingizni tushuntiring — HTML kodini "
            "javobga qayta yozmang."
        )
    )


async def _update_artifact(
    ctx: ToolContext, artifact_id: int, html: str, title: str | None = None
) -> ToolResult:
    from app.models import Artifact

    artifact = await ctx.db.get(Artifact, artifact_id)
    if artifact is None or artifact.user_id != ctx.user_id:
        raise ToolError(f"Artifact topilmadi: id={artifact_id}")
    if len(html.strip()) < MIN_ARTIFACT_HTML:
        raise ToolError("HTML juda qisqa — to'liq sahifa yuboring.")

    artifact.html = html
    artifact.version += 1
    if title:
        artifact.title = title.strip()[:200]
    await ctx.db.flush()

    ctx.artifacts.append(
        {
            "id": artifact.id,
            "token": artifact.token,
            "title": artifact.title,
            "version": artifact.version,
        }
    )
    return ToolResult(
        content=(
            f"Artifact yangilandi: id={artifact.id}, versiya {artifact.version}. "
            "Qisqacha nima o'zgarganini ayting — HTML kodini qayta yozmang."
        )
    )


_ARTIFACT_HANDLERS = {
    "create_artifact": _create_artifact,
    "update_artifact": _update_artifact,
}


async def execute_tool(
    name: str, tool_input: dict[str, Any], ctx: ToolContext
) -> ToolResult:
    """Tool'ni bajaradi va natijani qaytaradi.

    Xatoliklar `ToolResult(is_error=True)` ko'rinishida qaytariladi — model
    ularni o'qib, boshqa yo'l tanlashi mumkin.

    Example:
        >>> ctx = ToolContext(ai_in_pc=True)
        >>> await execute_tool("list_dir", {"path": ""}, ctx)
        ToolResult(content='...', is_error=False)
    """
    try:
        if name in _ARTIFACT_HANDLERS:
            if ctx.db is None:
                return ToolResult(
                    content="Artifact tizimi mavjud emas.", is_error=True
                )
            return await _ARTIFACT_HANDLERS[name](ctx, **tool_input)

        if name in _HANDLERS:
            if not ctx.ai_in_pc:
                return ToolResult(
                    content=(
                        "Ruxsat yo'q: sizda ai_in_pc ruxsati yoqilmagan. "
                        "Kompyuter bilan ishlash uchun admindan ruxsat so'rang."
                    ),
                    is_error=True,
                )
            return await _HANDLERS[name](**tool_input)

        return ToolResult(content=f"Noma'lum tool: {name}", is_error=True)
    except ToolError as exc:
        return ToolResult(content=str(exc), is_error=True)
    except TypeError as exc:
        return ToolResult(content=f"Noto'g'ri argumentlar: {exc}", is_error=True)
    except Exception as exc:  # noqa: BLE001 — model xatoni ko'rib tuzatsin
        return ToolResult(content=f"Kutilmagan xatolik: {exc!r}", is_error=True)

