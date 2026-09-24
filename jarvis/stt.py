"""Speech to text with faster-whisper (OpenAI's Whisper, running locally)."""

from __future__ import annotations

import os

import numpy as np

from .config import MODELS_DIR

# Whisper sometimes "hears" these in silence or noise.
HALLUCINATIONS = {
    "", "you", "thank you", "thank you.", "thanks for watching!", "thanks for watching.",
    "bye.", "bye", ".", "okay.", "so", "uh", "um",
}


def whisper_model_dir(name: str):
    return MODELS_DIR / "whisper" / name


class SpeechToText:
    def __init__(self, model: str = "base.en", device: str = "cpu",
                 compute_type: str = "int8", language: str | None = "en") -> None:
        local = whisper_model_dir(model)
        if (local / "model.bin").exists():
            os.environ.setdefault("HF_HUB_OFFLINE", "1")  # never go online for it
            source = str(local)
        else:
            source = model  # downloads on first use; run --setup to do it ahead of time
        from faster_whisper import WhisperModel

        try:
            self.model = WhisperModel(source, device=device, compute_type=compute_type)
        except (RuntimeError, ValueError):
            # e.g. a CUDA build without the right GPU libraries: use the CPU.
            self.model = WhisperModel(source, device="cpu", compute_type="int8")
        # English-only models (*.en) only do English; otherwise None = auto-detect.
        self.language = "en" if model.endswith(".en") else (language or None)

    def transcribe(self, audio: np.ndarray, prompt: str | None = None) -> str:
        if audio is None or audio.size < 16000 * 0.3:
            return ""
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=prompt,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return "" if text.lower() in HALLUCINATIONS else text
