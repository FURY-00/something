"""One-time downloads so Jarvis can run with the internet switched off.

    python -m jarvis --setup

Downloads the speech recognition model, the voice, the wake word model and the
language model. After this, nothing needs the internet.
"""

from __future__ import annotations

import importlib
import shutil
import sys

import requests

from .config import MODELS_DIR
from .llm import LLMError, OllamaClient
from .stt import whisper_model_dir
from .tts import piper_voice_path

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def piper_voice_urls(voice: str) -> list[str]:
    """en_GB-alan-medium -> .../en/en_GB/alan/medium/en_GB-alan-medium.onnx(.json)"""
    locale, speaker, quality = voice.split("-", 2)
    lang = locale.split("_")[0]
    base = f"{PIPER_BASE}/{lang}/{locale}/{speaker}/{quality}/{voice}.onnx"
    return [base, base + ".json"]


def _download(url: str, dest) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r    {dest.name}: {100 * done / total:5.1f}%", end="", flush=True)
    print()
    tmp.replace(dest)


def step(title: str) -> None:
    print(f"\n==> {title}")


def setup_whisper(cfg) -> bool:
    step(f"Speech recognition model (whisper '{cfg.stt.model}')")
    target = whisper_model_dir(cfg.stt.model)
    if (target / "model.bin").exists():
        print("    already downloaded")
        return True
    from faster_whisper import download_model

    download_model(cfg.stt.model, output_dir=str(target))
    print(f"    saved to {target}")
    return True


def setup_piper(cfg) -> bool:
    if cfg.tts.engine != "piper":
        return True
    step(f"Voice (piper '{cfg.tts.voice}')")
    path = piper_voice_path(cfg.tts.voice)
    if path.exists() and path.with_suffix(".onnx.json").exists():
        print("    already downloaded")
        return True
    for url, dest in zip(piper_voice_urls(cfg.tts.voice), [path, path.with_suffix(".onnx.json")]):
        _download(url, dest)
    return True


def setup_wakeword(cfg) -> bool:
    if cfg.wake_word.engine != "openwakeword":
        return True
    step(f"Wake word model (openWakeWord '{cfg.wake_word.model}')")
    from .wakeword import download_openwakeword

    download_openwakeword([cfg.wake_word.model])
    return True


def setup_ollama(cfg) -> bool:
    client = OllamaClient.from_config(cfg.llm)
    models = [cfg.llm.model] + ([cfg.llm.vision_model] if cfg.llm.vision_model else [])
    for model in models:
        step(f"Language model (ollama '{model}')")
        try:
            if client.has_model(model):
                print("    already downloaded")
                continue
            client.pull(model, on_progress=lambda s: print(f"\r    {s:<60}", end="", flush=True))
            print()
        except LLMError as exc:
            print(f"    {exc}")
            if not shutil.which("ollama"):
                print("    Install Ollama from https://ollama.com/download, then run --setup again.")
            return False
    return True


def run_setup(cfg) -> int:
    ok = True
    for fn in (setup_whisper, setup_piper, setup_wakeword, setup_ollama):
        try:
            ok = fn(cfg) and ok
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            print(f"    FAILED: {exc}")
            ok = False
    print("\nAll set! Start Jarvis with:  python -m jarvis" if ok else
          "\nSome steps failed (see above). Fix them and run --setup again.")
    return 0 if ok else 1


def run_check(cfg) -> int:
    """Print what's working and what isn't."""
    good = True

    def report(label: str, ok: bool, detail: str = "") -> None:
        nonlocal good
        good = good and ok
        print(f"  [{'OK' if ok else '!!'}] {label}{': ' + detail if detail else ''}")

    print(f"Python {sys.version.split()[0]}")
    report("Python 3.10+", sys.version_info >= (3, 10))
    client = OllamaClient.from_config(cfg.llm)
    try:
        models = client.list_models()
        report("Ollama running", True, cfg.llm.host)
        report(f"Model {cfg.llm.model}", client.has_model(), "" if client.has_model()
               else f"run: ollama pull {cfg.llm.model}")
        if cfg.llm.vision_model:
            report(f"Vision model {cfg.llm.vision_model}", client.has_model(cfg.llm.vision_model))
        print(f"       installed models: {', '.join(models) or 'none'}")
    except LLMError as exc:
        report("Ollama running", False, str(exc))

    for module, why in [
        ("faster_whisper", "speech recognition"),
        ("sounddevice", "microphone and speakers"),
        ("openwakeword", "'Hey Jarvis' wake word"),
        ("piper", "Piper voice"),
        ("pyautogui", "keyboard and mouse control"),
        ("docx", "Word documents"),
    ]:
        try:
            importlib.import_module(module)
            report(f"{module} ({why})", True)
        except Exception as exc:  # noqa: BLE001
            detail = "no graphical display" if "DISPLAY" in str(exc) else str(exc).strip()
            report(f"{module} ({why})", False, detail.splitlines()[0] if detail else type(exc).__name__)

    whisper_dir = whisper_model_dir(cfg.stt.model)
    report(f"Whisper model {cfg.stt.model} downloaded", (whisper_dir / "model.bin").exists(),
           str(whisper_dir))
    if cfg.tts.engine == "piper":
        voice = piper_voice_path(cfg.tts.voice)
        report(f"Piper voice {cfg.tts.voice} downloaded", voice.exists(), str(voice))

    try:
        import sounddevice as sd

        dev_in = sd.query_devices(kind="input")
        dev_out = sd.query_devices(kind="output")
        report("Microphone", True, dev_in["name"])
        report("Speakers", True, dev_out["name"])
    except Exception as exc:  # noqa: BLE001
        report("Audio devices", False, str(exc))

    print(f"\nModels folder: {MODELS_DIR}")
    print("Everything looks good." if good else "Fix the items marked !! (python -m jarvis --setup "
          "downloads the missing models).")
    return 0 if good else 1
