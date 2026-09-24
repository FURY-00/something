"""Configuration loading.

Settings live in ``config.yaml`` at the project root. Anything missing from that
file falls back to the defaults below, so a partial config file is fine.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"

DEFAULTS: dict[str, Any] = {
    "assistant_name": "Jarvis",
    # How Jarvis addresses you ("Sir", "Boss", your first name, ...).
    "user_title": "Sir",
    "llm": {
        # "ollama" = local and offline. "anthropic" = Claude in the cloud: much
        # smarter, needs internet and an API key (ANTHROPIC_API_KEY).
        "provider": "ollama",
        "host": "http://localhost:11434",
        # Any Ollama model that supports tool calling. See README for sizes.
        "model": "qwen2.5:7b",
        "anthropic_model": "claude-opus-5",
        # How hard Claude thinks before a spoken reply: low, medium, high.
        # Lower is faster, which matters in a voice conversation.
        "anthropic_effort": "medium",
        "temperature": 0.6,
        # Context window in tokens. Tool descriptions alone take ~4k with every app on.
        "num_ctx": 12288,
        # How long Ollama keeps the model loaded in RAM between requests.
        "keep_alive": "30m",
        # Set to false for "thinking" models (qwen3, gpt-oss, deepseek-r1) to
        # make them answer faster. Leave null for regular models.
        "think": None,
        "stream": True,
        "timeout": 300,
        # Optional vision model for "what's on my screen?" (e.g. "qwen2.5vl:7b",
        # "llava:7b", "gemma3:4b"). Leave empty to disable.
        "vision_model": "",
        "max_history_messages": 24,
        "max_tool_rounds": 8,
        # Remember the gist of past conversations (summarised when you say goodbye).
        "remember_conversations": True,
    },
    "skills": {
        # The brain that writes scripts for applications (SolidWorks, COMSOL,
        # Ansys, Blender, websites...). "same" follows llm.provider.
        "code_provider": "same",
        # Local code model (when code_provider is ollama). A coder model writes
        # much better scripts: qwen2.5-coder:7b, qwen2.5-coder:14b, ...
        "code_model": "qwen2.5-coder:7b",
        "code_num_ctx": 16384,
        # Effort for the cloud code brain: high or xhigh for engineering work.
        "code_effort": "high",
        # Write -> run -> fix attempts before giving up on a task.
        "max_attempts": 4,
        # Skip the check that stops scripts deleting files or running commands.
        "allow_unsafe_code": False,
        # Each application: enabled = auto (if installed), true or false.
        "blender": {"enabled": "auto", "executable": "", "port": 9876},
        "solidworks": {"enabled": "auto"},
        "comsol": {"enabled": "auto", "version": "", "cores": 0},
        "ansys": {"enabled": "auto", "executable": ""},
        "canva": {"enabled": "auto", "url": "https://mcp.canva.com/mcp"},
        "web": {"enabled": "auto"},
    },
    "wake_word": {
        # openwakeword: always-on "Hey Jarvis" detector (recommended)
        # whisper:      transcribes everything and reacts when it hears the name
        # enter:        push-to-talk, press Enter to speak
        "engine": "openwakeword",
        "model": "hey_jarvis",
        "threshold": 0.5,
        # Extra words the whisper engine treats as the wake word.
        "names": ["jarvis", "jervis", "travis", "charvis"],
        # After Jarvis answers, keep listening this many seconds for a
        # follow-up question without needing the wake word again. 0 disables.
        "follow_up_seconds": 6,
    },
    "stt": {
        # tiny.en, base.en, small.en, medium.en, large-v3, distil-large-v3 ...
        "model": "base.en",
        # cpu is fast enough for base/small models. Use "cuda" if you have an
        # NVIDIA GPU with CUDA 12 + cuDNN installed.
        "device": "cpu",
        "compute_type": "int8",
        "language": "en",
    },
    "tts": {
        # piper (natural neural voice) or pyttsx3 (built-in system voice)
        "engine": "piper",
        "voice": "en_GB-alan-medium",
        # 1.0 is normal speed, lower is faster, higher is slower.
        "length_scale": 0.95,
        "volume": 1.0,
    },
    "audio": {
        "sample_rate": 16000,
        "input_device": None,
        "output_device": None,
        # Seconds of silence that mark the end of what you said.
        "silence_seconds": 1.0,
        "max_record_seconds": 20,
        # How long to wait for you to start talking after the wake word.
        "start_timeout": 6,
        # Minimum loudness counted as speech. Raise it in a noisy room.
        "min_speech_rms": 350,
        "chime": True,
    },
    "knowledge": {
        # Offline Wikipedia via kiwix-serve (see README). Empty disables it.
        "kiwix_url": "",
        "kiwix_book": "",
    },
    "safety": {
        # Ask before shutting down, closing apps, running commands, ...
        "confirm_dangerous": True,
        # Let Jarvis run arbitrary terminal commands (always asks first).
        "allow_shell": False,
    },
    "paths": {
        "documents": "~/Documents/Jarvis",
        "screenshots": "~/Pictures/Jarvis",
        # Where Jarvis saves CAD parts, simulations, renders and websites.
        "projects": "~/Documents/Jarvis/Projects",
        # Where Jarvis keeps its long-term memory.
        "data": str(ROOT / "data"),
    },
}


class Section(dict):
    """A dict that also allows attribute access: ``cfg.llm.model``."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _to_section(value: Any) -> Any:
    if isinstance(value, dict):
        return Section({k: _to_section(v) for k, v in value.items()})
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | os.PathLike | None = None) -> Section:
    """Load ``config.yaml`` (or ``path``) merged over the defaults."""
    config_path = Path(path) if path else ROOT / "config.yaml"
    user_cfg: dict = {}
    if config_path.exists():
        import yaml

        with open(config_path, encoding="utf-8") as fh:
            user_cfg = yaml.safe_load(fh) or {}
    elif path:
        raise FileNotFoundError(f"Config file not found: {config_path}")

    cfg = _to_section(_deep_merge(DEFAULTS, user_cfg))
    for key, value in cfg.paths.items():
        cfg.paths[key] = Path(os.path.expandvars(os.path.expanduser(value)))
    return cfg
