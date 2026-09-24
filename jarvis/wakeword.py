"""Ways to wake Jarvis up.

Each detector has ``wait(mic) -> str`` which blocks until Jarvis is called and
returns any command spoken in the same breath ("Jarvis, open YouTube"), or ""
if only the wake word was heard.
"""

from __future__ import annotations

import logging
import os
import re

log = logging.getLogger(__name__)


class OpenWakeWordDetector:
    """Always-on "Hey Jarvis" detector. Tiny, fast and fully offline."""

    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5) -> None:
        from openwakeword.model import Model

        self.threshold = threshold
        try:
            self.model = Model(wakeword_models=[model], inference_framework="onnx")
        except (ValueError, FileNotFoundError, OSError) as exc:
            if os.path.exists(model):
                raise
            log.info("Wake word model missing (%s); downloading it once.", exc)
            download_openwakeword([model])
            self.model = Model(wakeword_models=[model], inference_framework="onnx")

    def wait(self, mic) -> str:
        self.model.reset()
        mic.clear()
        while True:
            frame = mic.read(timeout=1)
            if frame is None:
                continue
            scores = self.model.predict(frame)
            if scores and max(scores.values()) >= self.threshold:
                self.model.reset()
                return ""


def download_openwakeword(models: list[str]) -> None:
    import openwakeword.utils

    openwakeword.utils.download_models(model_names=models)


class WhisperWakeWord:
    """Transcribes everything it hears and reacts when it hears the name.

    Heavier on the CPU than openWakeWord, but works with any name you like.
    """

    def __init__(self, stt, names: list[str]) -> None:
        self.stt = stt
        self.names = names

    def wait(self, mic) -> str:
        mic.clear()
        while True:
            audio = mic.record_utterance(start_timeout=None, silence_seconds=0.6, max_seconds=12)
            command = strip_wake_word(self.stt.transcribe(audio), self.names)
            if command is not None:
                return command


def strip_wake_word(text: str, names: list[str]) -> str | None:
    """Return the text without the wake word, or None if it wasn't said."""
    if not text:
        return None
    pattern = r"\b(?:(?:hey|hi|ok|okay|yo)[\s,]+)?(?:%s)\b[\s,.!?]*" % "|".join(
        re.escape(n) for n in names
    )
    if not re.search(pattern, text, flags=re.I):
        return None
    rest = re.sub(pattern, " ", text, count=1, flags=re.I)
    return re.sub(r"\s+", " ", rest).strip(" ,.!?")


class PushToTalk:
    """Press Enter, then speak."""

    def wait(self, mic) -> str:
        input("\n[Press Enter, then speak] ")
        mic.clear()
        return ""
