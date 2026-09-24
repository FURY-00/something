"""Voice-mode logic with a simulated microphone (no audio hardware needed)."""

import contextlib
import sys
import types

import numpy as np
import pytest

from jarvis.assistant import Assistant
from jarvis.config import load_config
from jarvis.tools import system

from .fake_ollama import FakeOllama, pieces, tool_call


class FakeMic:
    """Each record_utterance() returns the next scripted phrase (or None = silence)."""

    def __init__(self, phrases):
        self.phrases = list(phrases)
        self.paused_now = False

    def record_utterance(self, **kwargs):
        assert not self.paused_now, "listened while the mic was paused"
        return self.phrases.pop(0) if self.phrases else None

    def pause(self):
        self.paused_now = True

    def resume(self):
        self.paused_now = False

    def clear(self):
        pass

    @contextlib.contextmanager
    def paused(self):
        was = self.paused_now
        self.pause()
        yield
        if not was:
            self.resume()


class EchoSTT:
    def transcribe(self, audio):
        return audio or ""


def script(body):
    last = body["messages"][-1]
    if last["role"] == "tool":
        return pieces(f"Done. {last['content']}")
    text = last["content"].lower()
    if "shut down" in text:
        return [tool_call("system_power", action="shutdown")]
    return pieces(f"You said {text}.")


@pytest.fixture
def assistant(tmp_path):
    with FakeOllama(script) as server:
        cfg = load_config()
        cfg.llm.host = server.url
        cfg.paths.data = tmp_path
        cfg.audio.chime = False
        a = Assistant(cfg, voice_input=True, voice_output=False)
        a.stt = EchoSTT()
        a.server = server
        yield a


def test_follow_up_questions_without_wake_word(assistant):
    assistant.mic = FakeMic(["first question", "second question", None])
    assistant._conversation("", follow_up=5)
    users = [r["messages"][-1]["content"] for r in assistant.server.requests]
    assert users == ["first question", "second question"]


def test_command_said_with_wake_word_is_used_directly(assistant):
    assistant.mic = FakeMic([None])
    assistant._conversation("open youtube", follow_up=0)
    assert assistant.server.requests[0]["messages"][-1]["content"] == "open youtube"


def test_spoken_confirmation_for_dangerous_action(assistant, monkeypatch):
    launched = []
    monkeypatch.setattr(system.subprocess, "Popen", lambda cmd: launched.append(cmd))
    assistant.mic = FakeMic(["please shut down the computer", "yes do it", None])
    assistant._conversation("", follow_up=5)
    assert len(launched) == 1
    tool_result = assistant.server.requests[1]["messages"][-1]
    assert tool_result == {"role": "tool", "content": "Okay, shutdown.", "tool_name": "system_power"}


def test_spoken_refusal_cancels(assistant, monkeypatch):
    launched = []
    monkeypatch.setattr(system.subprocess, "Popen", lambda cmd: launched.append(cmd))
    assistant.mic = FakeMic(["shut down the computer", "no wait", None])
    assistant._conversation("", follow_up=0)
    assert launched == []
    assert assistant.server.requests[1]["messages"][-1]["content"] == "Cancelled by the user."


def test_exit_phrase_ends_conversation(assistant):
    assistant.mic = FakeMic(["goodbye jarvis"])
    assert assistant._conversation("", follow_up=5) == "exit"
    assert assistant.server.requests == []


# ------------------------------------------------------------ speech detection
class _FakeStream:
    def __init__(self, **kwargs):
        pass


def _mic_with_frames(monkeypatch, frames):
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=_FakeStream))
    from jarvis.audio import FRAME_SAMPLES, Microphone

    mic = Microphone(min_speech_rms=300)
    for level in frames:
        noise = np.random.default_rng(0).normal(0, level, FRAME_SAMPLES)
        mic._queue.put(noise.clip(-32768, 32767).astype(np.int16))
    return mic, FRAME_SAMPLES


def test_record_utterance_waits_for_speech_then_stops_on_silence(monkeypatch):
    frames = [30] * 10 + [3000] * 20 + [30] * 20 + [3000] * 5
    mic, n = _mic_with_frames(monkeypatch, frames)
    audio = mic.record_utterance(start_timeout=5, silence_seconds=0.8, max_seconds=10)
    # 4 frames of pre-roll + 20 loud + 10 silent (0.8 s) ~= 34 frames
    assert audio is not None and audio.dtype == np.float32
    assert 30 * n <= audio.size <= 36 * n
    assert mic._queue.qsize() == 55 - 10 - 20 - 10  # the rest is left for next time


def test_record_utterance_times_out_in_silence(monkeypatch):
    mic, _ = _mic_with_frames(monkeypatch, [30] * 40)
    assert mic.record_utterance(start_timeout=1.0) is None


def test_single_click_is_not_speech(monkeypatch):
    mic, _ = _mic_with_frames(monkeypatch, [30] * 5 + [5000] + [30] * 30)
    assert mic.record_utterance(start_timeout=2.0) is None
