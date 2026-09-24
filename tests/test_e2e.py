"""Runs the real program in text mode against a fake Ollama server."""

import subprocess
import sys
from pathlib import Path

from .fake_ollama import FakeOllama, pieces, tool_call

ROOT = Path(__file__).resolve().parent.parent


def script(body):
    last = body["messages"][-1]
    if last["role"] == "tool":
        return pieces(f"Right away, sir. {last['content']}")
    text = last["content"].lower()
    if "time" in text:
        return [tool_call("get_date_time")]
    if "remember" in text:
        return pieces("Noted. ") + [tool_call("remember", fact="The user's favourite colour is blue.")]
    return pieces("Hello, sir. How may I help?")


def run(tmp_path, stdin):
    with FakeOllama(script) as server:
        config = tmp_path / "config.yaml"
        config.write_text(
            f"llm:\n  host: {server.url}\ntts:\n  engine: none\n"
            f"paths:\n  documents: {tmp_path / 'docs'}\n  data: {tmp_path / 'data'}\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, "-m", "jarvis", "--text", "--mute", "--config", str(config)],
            input=stdin, capture_output=True, text=True, timeout=60, cwd=ROOT,
        )
    return proc, server


def test_text_mode_conversation(tmp_path):
    proc, server = run(tmp_path, "hello\nwhat time is it\nexit\n")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "Jarvis is online" in out
    assert "Jarvis: Hello, sir. How may I help?" in out
    assert "[get_date_time()] It is " in out
    assert "Jarvis: Right away, sir. It is " in out
    assert "Goodbye, Sir." in out
    # Second request carries the first exchange as history, plus the tool list.
    second = server.requests[1]
    assert [m["role"] for m in second["messages"]] == ["system", "user", "assistant", "user"]
    assert any(t["function"]["name"] == "open_website" for t in second["tools"])


def test_memory_is_saved_and_used_next_time(tmp_path):
    proc, _ = run(tmp_path, "remember my favourite colour is blue\nexit\n")
    assert "Saved to memory" in proc.stdout
    proc, server = run(tmp_path, "hello\nexit\n")
    system_prompt = server.requests[0]["messages"][0]["content"]
    assert "- The user's favourite colour is blue." in system_prompt


def test_ollama_down_gives_clear_message(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("llm:\n  host: http://127.0.0.1:9\ntts:\n  engine: none\n")
    proc = subprocess.run(
        [sys.executable, "-m", "jarvis", "--text", "--mute", "--config", str(config)],
        input="hi\n", capture_output=True, text=True, timeout=60, cwd=ROOT,
    )
    assert proc.returncode != 0
    assert "Can't reach Ollama" in proc.stderr
