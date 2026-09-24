"""Microphone input and simple speech detection."""

from __future__ import annotations

import collections
import contextlib
import queue
import time

import numpy as np

FRAME_SAMPLES = 1280  # 80 ms at 16 kHz: the chunk size openWakeWord expects


def rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2))) if frame.size else 0.0


class Microphone:
    """A continuously running microphone stream you can read 80 ms frames from."""

    def __init__(self, sample_rate: int = 16000, device=None, min_speech_rms: float = 350) -> None:
        import sounddevice as sd

        self.sample_rate = sample_rate
        self.min_speech_rms = min_speech_rms
        self.noise_floor = min_speech_rms / 3
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._paused = False
        self._stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            device=device,
            callback=self._callback,
        )

    def _callback(self, indata, frames, time_info, status) -> None:
        if not self._paused:
            self._queue.put(indata[:, 0].copy())

    def __enter__(self) -> "Microphone":
        self._stream.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stream.stop()
        self._stream.close()

    def read(self, timeout: float | None = None) -> np.ndarray | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def pause(self) -> None:
        """Ignore the microphone (e.g. while Jarvis is talking)."""
        self._paused = True

    def resume(self) -> None:
        self.clear()
        self._paused = False

    @contextlib.contextmanager
    def paused(self):
        was_paused = self._paused
        self.pause()
        try:
            yield
        finally:
            if not was_paused:
                self.resume()

    def calibrate(self, seconds: float = 1.0) -> float:
        """Measure background noise so speech detection adapts to the room."""
        self.clear()
        levels = []
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            frame = self.read(timeout=1)
            if frame is not None:
                levels.append(rms(frame))
        if levels:
            self.noise_floor = float(np.median(levels))
        return self.noise_floor

    @property
    def speech_threshold(self) -> float:
        return max(self.min_speech_rms, self.noise_floor * 3)

    def record_utterance(
        self,
        start_timeout: float | None = 6.0,
        silence_seconds: float = 1.0,
        max_seconds: float = 20.0,
    ) -> np.ndarray | None:
        """Record one spoken phrase: wait for speech, stop after a pause.

        Returns float32 audio in [-1, 1], or None if nobody spoke in time.
        """
        frame_sec = FRAME_SAMPLES / self.sample_rate
        silence_frames = max(1, round(silence_seconds / frame_sec))
        max_frames = max(1, round(max_seconds / frame_sec))
        timeout_frames = None if start_timeout is None else round(start_timeout / frame_sec)
        pre_roll = collections.deque(maxlen=4)  # keep ~0.3 s before speech starts
        frames: list[np.ndarray] = []
        started = False
        quiet_run = 0
        waited = 0
        loud_run = 0

        while True:
            frame = self.read(timeout=2)
            if frame is None:
                continue
            level = rms(frame)
            loud = level > self.speech_threshold
            if not started:
                pre_roll.append(frame)
                loud_run = loud_run + 1 if loud else 0
                if loud_run >= 2:  # two loud frames in a row = speech, not a click
                    started = True
                    frames.extend(pre_roll)
                    continue
                if not loud:  # slowly follow the room's noise level
                    self.noise_floor = 0.95 * self.noise_floor + 0.05 * level
                waited += 1
                if timeout_frames is not None and waited >= timeout_frames:
                    return None
                continue
            frames.append(frame)
            quiet_run = 0 if loud else quiet_run + 1
            if quiet_run >= silence_frames or len(frames) >= max_frames:
                break

        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        return audio


def chime(sample_rate: int = 22050, device=None, rising: bool = True) -> None:
    """A short two-note 'I'm listening' sound. Doesn't block."""
    import sounddevice as sd

    notes = (660, 990) if rising else (990, 660)
    parts = []
    for freq in notes:
        t = np.arange(int(sample_rate * 0.09)) / sample_rate
        tone = np.sin(2 * np.pi * freq * t) * np.hanning(t.size)
        parts.append(tone)
    sd.play((np.concatenate(parts) * 0.25).astype(np.float32), sample_rate, device=device)


def list_devices() -> str:
    import sounddevice as sd

    return str(sd.query_devices())
