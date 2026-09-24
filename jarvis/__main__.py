"""Command line entry point: ``python -m jarvis``."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis", description="A local, offline voice assistant for your computer."
    )
    parser.add_argument("--text", action="store_true", help="type instead of talking")
    parser.add_argument("--mute", action="store_true", help="don't speak replies aloud")
    parser.add_argument("--push-to-talk", action="store_true", help="press Enter to talk")
    parser.add_argument("--setup", action="store_true", help="download all models (needs internet once)")
    parser.add_argument("--check", action="store_true", help="check that everything is installed")
    parser.add_argument("--list-devices", action="store_true", help="list microphones and speakers")
    parser.add_argument("--model", help="Ollama model to use, e.g. llama3.1:8b")
    parser.add_argument("--config", help="path to a config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logs")
    args = parser.parse_args(argv)

    if os.name == "nt":
        os.system("")  # turns on colour codes in the Windows console
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("urllib3", "faster_whisper", "httpx", "comtypes"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    cfg = load_config(args.config)
    if args.model:
        cfg.llm.model = args.model
    if args.push_to_talk:
        cfg.wake_word.engine = "enter"

    if args.list_devices:
        from .audio import list_devices

        print(list_devices())
        return 0
    if args.setup:
        from .setup_models import run_setup

        return run_setup(cfg)
    if args.check:
        from .setup_models import run_check

        return run_check(cfg)

    from .assistant import Assistant

    try:
        assistant = Assistant(cfg, voice_input=not args.text, voice_output=not args.mute)
        if args.text:
            assistant.run_text()
        else:
            assistant.run_voice()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
