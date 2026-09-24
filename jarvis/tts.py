"""Text to speech.

Piper (https://github.com/OHF-Voice/piper1-gpl) is a fast neural voice that
runs on the CPU. pyttsx3 uses the voice built into Windows, macOS or Linux
(espeak) and is the fallback when no Piper voice is installed.
"""

from __future__ import annotations

import io
import logging
import queue
import threading
import time
import wave
from pathlib import Path

import numpy as np

from .config import MODELS_DIR
from .speech_text import clean_for_speech

log = logging.getLogger(__name__)


def piper_voice_path(voice: str) -> Path:
    p = Path(voice).expanduser()
    if p.suffix == ".onnx":
        return p
    return MODELS_DIR / "piper" / f"{voice}.onnx"


class PiperEngine:
    def __init__(self, model_path: Path, length_scale: float = 1.0, volume: float = 1.0,
                 output_device=None) -> None:
        from piper import PiperVoice

        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper voice not found at {model_path}. Run: python -m jarvis --setup"
            )
        self.voice = PiperVoice.load(str(model_path))
        self.length_scale = length_scale
        self.volume = volume
        self.output_device = output_device

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            if hasattr(self.voice, "synthesize_wav"):  # piper-tts >= 1.3
                from piper import SynthesisConfig

                cfg = SynthesisConfig(length_scale=self.length_scale, volume=self.volume)
                self.voice.synthesize_wav(text, wav, syn_config=cfg)
            else:  # older piper-tts
                self.voice.synthesize(text, wav, length_scale=self.length_scale)
        buf.seek(0)
        with wave.open(buf, "rb") as wav:
            rate = wav.getframerate()
            audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
        return audio, rate

    def speak(self, text: str, stop: threading.Event) -> None:
        import sounddevice as sd

        audio, rate = self.synthesize(text)
        if stop.is_set() or audio.size == 0:
            return
        sd.play(audio, rate, device=self.output_device)
        while sd.get_stream().active:
            if stop.is_set():
                sd.stop()
                return
            time.sleep(0.03)

    def interrupt(self) -> None:
        pass  # speak() polls the stop event


class Pyttsx3Engine:
    def __init__(self, length_scale: float = 1.0, volume: float = 1.0) -> None:
        try:  # Windows' speech engine needs COM set up on this thread
            import comtypes

            comtypes.CoInitialize()
        except Exception:  # noqa: BLE001 - not Windows, or not needed
            pass
        import pyttsx3

        self.engine = pyttsx3.init()
        rate = self.engine.getProperty("rate") or 200
        self.engine.setProperty("rate", int(rate / max(0.5, length_scale)))
        self.engine.setProperty("volume", volume)
        for voice in self.engine.getProperty("voices") or []:
            label = f"{voice.name} {voice.id}".lower()
            if any(n in label for n in ("daniel", "george", "ryan", "en-gb", "english_rp")):
                self.engine.setProperty("voice", voice.id)  # a British voice, if present
                break

    def speak(self, text: str, stop: threading.Event) -> None:
        self.engine.say(text)
        self.engine.runAndWait()

    def interrupt(self) -> None:
        try:
            self.engine.stop()
        except Exception:  # noqa: BLE001
            pass


class SilentEngine:
    def speak(self, text: str, stop: threading.Event) -> None:
        pass

    def interrupt(self) -> None:
        pass


def make_engine(tts_cfg, output_device=None):
    """Return a factory for the configured engine (it's built on the speaker thread).

    Falls back from Piper to the system voice to text-only, so a missing voice
    never stops Jarvis from starting.
    """
    if tts_cfg.engine == "none":
        return SilentEngine

    def build():
        if tts_cfg.engine == "piper":
            try:
                return PiperEngine(piper_voice_path(tts_cfg.voice), tts_cfg.length_scale,
                                   tts_cfg.volume, output_device)
            except Exception as exc:  # noqa: BLE001
                log.warning("Piper voice unavailable (%s). Using the system voice.", exc)
        try:
            return Pyttsx3Engine(tts_cfg.length_scale, tts_cfg.volume)
        except Exception as exc:  # noqa: BLE001
            log.warning("No voice available (%s). Replies will be text only.", exc)
            return SilentEngine()

    return build


class Speaker:
    """Speaks queued sentences one after another on a background thread."""

    def __init__(self, engine_factory) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._engine = None
        self._factory = engine_factory
        threading.Thread(target=self._run, name="speaker", daemon=True).start()
        self._ready.wait()
        if self._error:
            raise self._error

    def _run(self) -> None:
        try:
            self._engine = self._factory()
        except BaseException as exc:  # noqa: BLE001 - reported to the constructor
            self._error = exc
            self._ready.set()
            return
        self._ready.set()
        while True:
            text = self._queue.get()
            try:
                if not self._stop.is_set():
                    self._engine.speak(text, self._stop)
            except Exception as exc:  # noqa: BLE001 - never let the voice thread die
                log.error("Speech failed (%s); continuing without a voice.", exc)
                self._engine = SilentEngine()
            finally:
                self._queue.task_done()

    def say(self, text: str) -> None:
        text = clean_for_speech(text)
        if text:
            self._queue.put(text)

    def wait(self) -> None:
        """Block until everything queued has been spoken."""
        self._queue.join()

    @property
    def busy(self) -> bool:
        return self._queue.unfinished_tasks > 0

    def stop(self) -> None:
        """Stop talking now and drop anything still queued."""
        self._stop.set()
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        if self._engine:
            self._engine.interrupt()
        self._queue.join()
        self._stop.clear()
