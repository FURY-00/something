from jarvis.brain import Brain, ReplyStreamer, parse_text_tool_calls
from jarvis.config import load_config
from jarvis.context import ToolContext
from jarvis.llm import ChatResult
from jarvis.memory import Memory
from jarvis.tools import ToolRegistry, tool, _REGISTRY


class ScriptedLLM:
    """Returns canned results in order and records what it was sent."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def chat(self, messages, tools=None, on_text=None, **kwargs):
        self.calls.append(messages)
        content, tool_calls = self.results.pop(0)
        if on_text:
            for i in range(0, len(content), 5):
                on_text(content[i:i + 5])
        return ChatResult(content=content.strip(), tool_calls=tool_calls)


def make_brain(tmp_path, llm, tools):
    cfg = load_config()
    memory = Memory(tmp_path / "memory.json")
    ctx = ToolContext(cfg, llm, memory)
    registry = ToolRegistry(ctx, tools)
    spoken, shown = [], []
    brain = Brain(cfg, llm, registry, memory, "TestOS", speak=spoken.append, show=shown.append)
    return brain, spoken, shown


def _echo_tool():
    calls = []

    @tool("Echo things.", {"word": {"type": "string", "description": "w"}}, name="echo_test")
    def echo_test(ctx, word):
        calls.append(word)
        return f"echoed {word}"

    return {"echo_test": _REGISTRY.pop("echo_test")}, calls


def test_plain_answer_is_spoken_sentence_by_sentence(tmp_path):
    llm = ScriptedLLM(("Good evening, sir. All systems are running. Anything else?", []))
    brain, spoken, shown = make_brain(tmp_path, llm, {})
    reply = brain.handle("status report")
    assert reply.startswith("Good evening")
    assert spoken == ["Good evening, sir.", "All systems are running.", "Anything else?"]
    assert "".join(shown) == reply
    system = llm.calls[0][0]
    assert system["role"] == "system" and "TestOS" in system["content"]


def test_tool_call_then_answer(tmp_path):
    tools, calls = _echo_tool()
    llm = ScriptedLLM(
        ("", [{"function": {"name": "echo_test", "arguments": {"word": "hello"}}}]),
        ("I echoed it, sir.", []),
    )
    brain, spoken, _ = make_brain(tmp_path, llm, tools)
    assert brain.handle("echo hello") == "I echoed it, sir."
    assert calls == ["hello"]
    second_request = llm.calls[1]
    assert second_request[-1] == {"role": "tool", "content": "echoed hello", "tool_name": "echo_test"}
    assert spoken == ["I echoed it, sir."]


def test_tool_call_written_as_json_text_is_executed_not_spoken(tmp_path):
    tools, calls = _echo_tool()
    llm = ScriptedLLM(
        ('{"name": "echo_test", "arguments": {"word": "hi"}}', []),
        ("Done.", []),
    )
    brain, spoken, shown = make_brain(tmp_path, llm, tools)
    brain.handle("echo hi")
    assert calls == ["hi"]
    assert spoken == ["Done."]
    assert "echo_test" not in "".join(shown)


def test_json_that_is_not_a_tool_call_is_still_spoken(tmp_path):
    llm = ScriptedLLM(('{"answer": 42}', []))
    brain, spoken, _ = make_brain(tmp_path, llm, {})
    brain.handle("give me json")
    assert spoken == ['{"answer": 42}']


def test_gives_up_after_too_many_tool_rounds(tmp_path):
    tools, calls = _echo_tool()
    call = ("", [{"function": {"name": "echo_test", "arguments": {"word": "x"}}}])
    llm = ScriptedLLM(*[call] * 10)
    brain, spoken, _ = make_brain(tmp_path, llm, tools)
    reply = brain.handle("loop forever")
    assert "rephrase" in reply
    assert len(calls) == brain.config.llm.max_tool_rounds


def test_history_trims_old_tool_output_and_starts_with_user(tmp_path):
    llm = ScriptedLLM(("ok", []))
    brain, _, _ = make_brain(tmp_path, llm, {})
    brain.config.llm.max_history_messages = 4
    brain.history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "content": "x" * 1000, "tool_name": "t"},
        {"role": "assistant", "content": "done"},
        {"role": "user", "content": "two"},
        {"role": "assistant", "content": "ok"},
    ]
    brain.handle("three")
    sent = llm.calls[0]
    assert sent[0]["role"] == "system"
    assert sent[1] == {"role": "user", "content": "two"}


def test_parse_text_tool_calls_formats():
    names = ["open_website"]
    assert parse_text_tool_calls('{"name": "open_website", "arguments": {"site": "x"}}', names) == [
        {"function": {"name": "open_website", "arguments": {"site": "x"}}}
    ]
    wrapped = '<tool_call>\n{"name": "open_website", "parameters": {"site": "x"}}\n</tool_call>'
    assert parse_text_tool_calls(wrapped, names)[0]["function"]["arguments"] == {"site": "x"}
    fenced = '```json\n{"function": {"name": "open_website", "arguments": "{\\"site\\": \\"y\\"}"}}\n```'
    assert parse_text_tool_calls(fenced, names)[0]["function"]["arguments"] == {"site": "y"}
    assert parse_text_tool_calls('{"name": "rm_rf", "arguments": {}}', names) == []
    assert parse_text_tool_calls("just words", names) == []


def test_reply_streamer_waits_before_deciding():
    spoken, shown = [], []
    s = ReplyStreamer(spoken.append, shown.append)
    for chunk in ["  ", "Hel", "lo. Next"]:
        s.feed(chunk)
    s.finish()
    assert spoken == ["Hello.", "Next"]
    assert "".join(shown) == "Hello. Next"
