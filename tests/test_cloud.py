"""The optional Claude brain, with the network replaced by a fake SDK client."""

import types

import pytest

pytest.importorskip("anthropic")

from jarvis.llm_cloud import AnthropicClient, to_anthropic_messages, to_anthropic_tools  # noqa: E402


def test_history_conversion_pairs_tool_results_with_calls():
    history = [
        {"role": "system", "content": "Be Jarvis."},
        {"role": "user", "content": "open youtube and tell me the time"},
        {"role": "assistant", "content": "On it.", "tool_calls": [
            {"function": {"name": "open_website", "arguments": {"site": "youtube"}}},
            {"id": "toolu_7", "function": {"name": "get_date_time", "arguments": "{}"}},
        ]},
        {"role": "tool", "content": "Opened", "tool_name": "open_website"},
        {"role": "tool", "content": "It is noon", "tool_name": "get_date_time", "tool_call_id": "toolu_7"},
        {"role": "assistant", "content": "Done, sir."},
        {"role": "user", "content": "thanks", "images": ["QUJD"]},
    ]
    system, msgs = to_anthropic_messages(history)
    assert system == "Be Jarvis."
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    blocks = msgs[1]["content"]
    assert blocks[0] == {"type": "text", "text": "On it."}
    first_id = blocks[1]["id"]
    assert blocks[1]["name"] == "open_website" and blocks[2]["id"] == "toolu_7"
    results = msgs[2]["content"]  # both results in ONE user message
    assert [r["tool_use_id"] for r in results] == [first_id, "toolu_7"]
    assert msgs[4]["content"][0]["type"] == "image"


def test_raw_claude_content_is_replayed_unchanged():
    raw = [types.SimpleNamespace(type="thinking", thinking=""), types.SimpleNamespace(type="tool_use", id="t1")]
    _, msgs = to_anthropic_messages([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [], "_anthropic_content": raw},
        {"role": "tool", "content": "ok", "tool_name": "x"},
    ])
    assert msgs[1]["content"] is raw
    assert msgs[2]["content"][0]["tool_use_id"] == "t1"


def test_tool_schema_conversion():
    tools = to_anthropic_tools([{"type": "function", "function": {
        "name": "scroll", "description": "Scroll",
        "parameters": {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object", "properties": {}}}}])
    assert tools == [{"name": "scroll", "description": "Scroll", "eager_input_streaming": True,
                      "input_schema": {"type": "object", "properties": {}}}]


class FakeStream:
    def __init__(self, final):
        self.final = final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield types.SimpleNamespace(type="text", text="Hello ")
        yield types.SimpleNamespace(type="text", text="sir.")

    def get_final_message(self):
        return self.final


def test_chat_streams_text_and_returns_tool_calls(monkeypatch):
    client = AnthropicClient(model="claude-opus-5", effort="medium")
    final = types.SimpleNamespace(stop_reason="tool_use", content=[
        types.SimpleNamespace(type="text", text="Hello sir."),
        types.SimpleNamespace(type="tool_use", id="toolu_1", name="scroll", input={"direction": "down"}),
    ])
    seen = {}

    def stream(**params):
        seen.update(params)
        return FakeStream(final)

    monkeypatch.setattr(client.client.beta.messages, "stream", stream)
    pieces = []
    result = client.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "scroll"}],
                         tools=[{"type": "function", "function": {"name": "scroll", "parameters": {}}}],
                         on_text=pieces.append, temperature=0.9, num_ctx=4096)
    assert "".join(pieces) == "Hello sir."
    assert result.content == "Hello sir."
    assert result.tool_calls == [{"id": "toolu_1", "function": {"name": "scroll", "arguments": {"direction": "down"}}}]
    assert result.raw is final.content
    assert seen["model"] == "claude-opus-5" and seen["system"] == "S"
    assert seen["thinking"] == {"type": "adaptive"} and seen["output_config"] == {"effort": "medium"}
    assert seen["fallbacks"] == "default" and seen["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in seen  # not accepted by current Claude models


def test_refusal_is_reported_politely(monkeypatch):
    client = AnthropicClient()
    final = types.SimpleNamespace(stop_reason="refusal", content=[])
    monkeypatch.setattr(client.client.beta.messages, "stream", lambda **p: FakeStream(final))
    assert client.chat([{"role": "user", "content": "x"}]).content == "I can't help with that one."
