"""app.cli (5code agentic terminal) testlari — stream_reply mock qilingan."""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app import cli
from app.ai.providers import ProviderError
from app.ai.tools import ToolContext
from app.config import settings

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _restore_workspace_root():
    """`amain` workspace_root'ni cwd'ga o'zgartiradi — testdan keyin qaytaramiz."""
    original = settings.workspace_root
    yield
    settings.workspace_root = original


def _fake_stream(events: list[dict[str, Any]]):
    """`stream_reply` o'rniga qo'yiladigan soxta oqim (test_chat.py bilan bir xil)."""

    async def fake(**_: Any) -> AsyncIterator[dict[str, Any]]:
        for event in events:
            yield event

    return fake


def _raising_stream(exc: Exception):
    async def fake(**_: Any) -> AsyncIterator[dict[str, Any]]:
        raise exc
        yield {}  # pragma: no cover — hech qachon yetib bormaydi

    return fake


class _FakeTTY:
    """Interaktiv terminalni taqlid qiladi — `.read()` chaqirilmasligi kerak."""

    def isatty(self) -> bool:
        return True

    def read(self) -> str:  # pragma: no cover
        raise AssertionError("interaktiv terminalda stdin o'qilmasligi kerak")


# --- Argument parsing ---------------------------------------------------


def test_parse_args_defaults() -> None:
    args = cli.parse_args(["salom", "dunyo"])
    assert args.prompt == ["salom", "dunyo"]
    assert args.provider is None
    assert args.model is None


def test_parse_args_empty() -> None:
    args = cli.parse_args([])
    assert args.prompt == []


def test_parse_args_provider_and_model() -> None:
    args = cli.parse_args(["--provider", "gemini", "--model", "x", "savol"])
    assert args.provider == "gemini"
    assert args.model == "x"
    assert args.prompt == ["savol"]


# --- Provider resolution --------------------------------------------------


def test_resolve_provider_defaults_to_local_ollama() -> None:
    provider, model = cli.resolve_provider(cli.parse_args([]))
    assert provider == "ollama"
    assert model == settings.ollama_model


def test_resolve_provider_explicit_provider_keeps_model_none() -> None:
    provider, model = cli.resolve_provider(cli.parse_args(["--provider", "gemini"]))
    assert provider == "gemini"
    assert model is None


def test_resolve_provider_explicit_model_without_provider() -> None:
    provider, model = cli.resolve_provider(cli.parse_args(["--model", "custom"]))
    assert provider == "ollama"
    assert model == "custom"


# --- Piped stdin ------------------------------------------------------------


def test_read_piped_stdin_returns_none_for_tty() -> None:
    assert cli.read_piped_stdin(_FakeTTY()) is None


def test_read_piped_stdin_reads_content() -> None:
    stream = io.StringIO("def f(): pass\n")
    assert cli.read_piped_stdin(stream) == "def f(): pass\n"


def test_read_piped_stdin_blank_is_none() -> None:
    assert cli.read_piped_stdin(io.StringIO("   \n  ")) is None


# --- Formatting ---------------------------------------------------------


def test_format_tool_use_shows_args() -> None:
    text = cli.format_tool_use("read_file", {"path": "main.py"})
    assert "read_file" in text
    assert "path='main.py'" in text


def test_format_tool_use_truncates_long_args() -> None:
    text = cli.format_tool_use("write_file", {"content": "x" * 500})
    # ANSI kodlarisiz uzunlik cheklovdan oshmasligi kerak
    assert "…" in text


def test_format_tool_result_truncates_long_output() -> None:
    content = "\n".join(f"line{i}" for i in range(20))
    text = cli.format_tool_result(content, is_error=False)
    assert "line0" in text
    assert "qator yashirildi" in text
    assert "line19" not in text


def test_format_tool_result_short_output_not_truncated() -> None:
    text = cli.format_tool_result("exit_code=0\nsalom", is_error=False)
    assert "yashirildi" not in text


def test_format_tool_result_error_uses_error_color() -> None:
    text = cli.format_tool_result("xato", is_error=True)
    assert cli.ERR in text


# --- render_event -------------------------------------------------------


def test_render_event_text() -> None:
    out = io.StringIO()
    thinking_open = cli.render_event(
        {"type": "text", "text": "salom"}, out=out, thinking_open=False
    )
    assert out.getvalue() == "salom"
    assert thinking_open is False


def test_render_event_thinking_then_text_closes_block() -> None:
    out = io.StringIO()
    thinking_open = cli.render_event(
        {"type": "thinking", "text": "o'ylayapman"}, out=out, thinking_open=False
    )
    assert thinking_open is True
    assert cli.DIM in out.getvalue()

    thinking_open = cli.render_event(
        {"type": "text", "text": "javob"}, out=out, thinking_open=thinking_open
    )
    assert thinking_open is False
    assert out.getvalue().endswith("javob")
    assert cli.OFF in out.getvalue()


def test_render_event_tool_use_and_result() -> None:
    out = io.StringIO()
    thinking_open = cli.render_event(
        {"type": "tool_use", "id": "1", "name": "list_dir", "input": {"path": ""}},
        out=out,
        thinking_open=False,
    )
    assert "list_dir" in out.getvalue()
    assert thinking_open is False

    cli.render_event(
        {"type": "tool_result", "content": "a.py\nb.py", "is_error": False},
        out=out,
        thinking_open=False,
    )
    assert "a.py" in out.getvalue()


def test_render_event_error() -> None:
    out = io.StringIO()
    cli.render_event(
        {"type": "error", "message": "tarmoq xatosi"}, out=out, thinking_open=False
    )
    assert "tarmoq xatosi" in out.getvalue()


def test_render_event_unknown_type_is_noop() -> None:
    out = io.StringIO()
    thinking_open = cli.render_event(
        {"type": "artifact", "id": 1}, out=out, thinking_open=False
    )
    assert out.getvalue() == ""
    assert thinking_open is False


# --- run_turn (stream_reply mock qilingan) -----------------------------------


async def test_run_turn_returns_new_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    assistant_messages = [
        {"role": "assistant", "content": [{"type": "text", "text": "Salom!"}]}
    ]
    monkeypatch.setattr(
        cli,
        "stream_reply",
        _fake_stream(
            [
                {"type": "text", "text": "Salom!"},
                {"type": "assistant_message", "messages": assistant_messages},
            ]
        ),
    )
    out = io.StringIO()
    ctx = ToolContext(ai_in_pc=True, db=None)

    result = await cli.run_turn(
        history=[],
        user_text="salom",
        ctx=ctx,
        provider_name="ollama",
        model_name="5code",
        out=out,
    )

    assert result == assistant_messages
    assert "Salom!" in out.getvalue()


async def test_run_turn_renders_tool_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "stream_reply",
        _fake_stream(
            [
                {
                    "type": "tool_use",
                    "id": "1",
                    "name": "read_file",
                    "input": {"path": "x.py"},
                },
                {"type": "tool_result", "content": "print(1)", "is_error": False},
                {"type": "assistant_message", "messages": []},
            ]
        ),
    )
    out = io.StringIO()
    ctx = ToolContext(ai_in_pc=True, db=None)

    result = await cli.run_turn(
        history=[],
        user_text="x.py ni o'qi",
        ctx=ctx,
        provider_name="ollama",
        model_name="5code",
        out=out,
    )

    assert result == []
    rendered = out.getvalue()
    assert "read_file" in rendered
    assert "print(1)" in rendered


async def test_run_turn_propagates_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli, "stream_reply", _raising_stream(ProviderError("kalit yo'q"))
    )
    ctx = ToolContext(ai_in_pc=True, db=None)

    with pytest.raises(ProviderError):
        await cli.run_turn(
            history=[],
            user_text="salom",
            ctx=ctx,
            provider_name="gemini",
            model_name=None,
            out=io.StringIO(),
        )


# --- amain (to'liq oqim) -----------------------------------------------------


async def test_amain_one_shot_prompt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "read_piped_stdin", lambda: None)
    monkeypatch.setattr(
        cli,
        "stream_reply",
        _fake_stream(
            [
                {"type": "text", "text": "Salom, men 5code."},
                {"type": "assistant_message", "messages": []},
            ]
        ),
    )

    exit_code = await cli.amain(["Salom, kim sen?"])

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "Salom, men 5code." in captured
    assert "5code" in captured  # banner
    assert settings.workspace_root == cli.Path.cwd()


async def test_amain_piped_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    received: dict[str, Any] = {}

    async def fake(**kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        received.update(kwargs)
        yield {"type": "text", "text": "Bu funksiya qo'shadi."}
        yield {"type": "assistant_message", "messages": []}

    monkeypatch.setattr(cli, "stream_reply", fake)
    monkeypatch.setattr(
        cli, "read_piped_stdin", lambda: "def add(a, b): return a + b"
    )

    exit_code = await cli.amain(["shu kodni tushuntir"])

    assert exit_code == 0
    assert "def add(a, b)" in received["user_message"]
    assert "shu kodni tushuntir" in received["user_message"]


async def test_amain_interactive_loop_threads_history(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "read_piped_stdin", lambda: None)

    inputs = iter(["birinchi savol", "ikkinchi savol", "/bye"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    calls: list[list[dict[str, Any]]] = []
    turn_reply = [
        {"role": "assistant", "content": [{"type": "text", "text": "javob"}]}
    ]

    async def fake(*, history: list[dict[str, Any]], **_: Any) -> AsyncIterator[
        dict[str, Any]
    ]:
        calls.append(list(history))
        yield {"type": "text", "text": "javob"}
        yield {"type": "assistant_message", "messages": turn_reply}

    monkeypatch.setattr(cli, "stream_reply", fake)

    exit_code = await cli.amain([])

    assert exit_code == 0
    assert len(calls) == 2
    assert calls[0] == []
    assert calls[1] == [
        {"role": "user", "content": "birinchi savol"},
        *turn_reply,
    ]


async def test_amain_eof_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "read_piped_stdin", lambda: None)

    def _raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)

    exit_code = await cli.amain([])

    assert exit_code == 0


async def test_amain_provider_error_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "read_piped_stdin", lambda: None)
    monkeypatch.setattr(
        cli, "stream_reply", _raising_stream(ProviderError("GEMINI_API_KEY yo'q"))
    )

    exit_code = await cli.amain(["salom"])

    assert exit_code == 1
