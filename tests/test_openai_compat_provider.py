"""`_parse_fallback_tool_call` testlari.

Ba'zi lokal modellar (Ollama orqali, masalan qwen2.5-coder) tool chaqiruvini
strukturaviy `tool_calls` maydoni o'rniga oddiy matn/JSON sifatida qaytaradi.
Bu funksiya shu holatni aniqlab, to'g'ri `tool_use` blokiga o'giradi.
"""

from __future__ import annotations

from app.ai.providers.openai_compat import _parse_fallback_tool_call

TOOLS = {"list_dir", "create_artifact"}


def test_bare_json_is_parsed_as_tool_call() -> None:
    result = _parse_fallback_tool_call(
        '{"name": "list_dir", "arguments": {"path": "."}}', TOOLS
    )
    assert result == {
        "type": "tool_use",
        "id": result["id"],
        "name": "list_dir",
        "input": {"path": "."},
    }


def test_tool_call_tag_wrapper_is_parsed() -> None:
    text = '<tool_call>\n{"name": "list_dir", "arguments": {"path": ""}}\n</tool_call>'
    result = _parse_fallback_tool_call(text, TOOLS)
    assert result is not None
    assert result["name"] == "list_dir"
    assert result["input"] == {"path": ""}


def test_code_fence_wrapper_is_parsed() -> None:
    text = '```json\n{"name": "list_dir", "arguments": {}}\n```'
    result = _parse_fallback_tool_call(text, TOOLS)
    assert result is not None
    assert result["name"] == "list_dir"
    assert result["input"] == {}


def test_string_encoded_arguments_are_parsed() -> None:
    text = '{"name": "list_dir", "arguments": "{\\"path\\": \\"workspace\\"}"}'
    result = _parse_fallback_tool_call(text, TOOLS)
    assert result["input"] == {"path": "workspace"}


def test_missing_arguments_defaults_to_empty_dict() -> None:
    result = _parse_fallback_tool_call('{"name": "list_dir"}', TOOLS)
    assert result["input"] == {}


def test_plain_prose_is_not_a_tool_call() -> None:
    assert _parse_fallback_tool_call("Salom! Qandaysiz?", TOOLS) is None


def test_unknown_tool_name_is_rejected() -> None:
    text = '{"name": "delete_everything", "arguments": {}}'
    assert _parse_fallback_tool_call(text, TOOLS) is None


def test_mixed_prose_and_json_is_not_a_tool_call() -> None:
    text = 'Mana natija: {"name": "list_dir", "arguments": {}}'
    assert _parse_fallback_tool_call(text, TOOLS) is None


def test_each_call_gets_a_unique_id() -> None:
    text = '{"name": "list_dir", "arguments": {}}'
    first = _parse_fallback_tool_call(text, TOOLS)
    second = _parse_fallback_tool_call(text, TOOLS)
    assert first["id"] != second["id"]
