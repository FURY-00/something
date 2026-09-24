"""Puts the pieces together: ears, brain, voice and hands."""

from __future__ import annotations

import datetime as dt
import logging
import re
import sys
import threading
import time

from .brain import Brain
from .context import ToolContext
from .llm import LLMError, OllamaClient
from .memory import Memory
from .tools import ToolRegistry
from .tools.control import stop_auto_scroll
from .tools.system import os_description
from .tts import SilentEngine, Speaker, make_engine

log = logging.getLogger(__name__)

EXIT_WORDS = {"exit", "quit", "goodbye", "good bye", "bye", "bye jarvis", "goodbye jarvis",
              "stop listening", "that's all", "that is all", "shut down jarvis"}
HUSH_WORDS = {"stop", "stop talking", "shut up", "be quiet", "quiet", "cancel", "never mind",
              "nevermind", "nothing", "forget it"}
RESET_WORDS = {"reset", "new conversation", "start over", "clear conversation",
               "forget this conversation"}

YES = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|do it|go ahead|confirm(ed)?|affirmative|"
                 r"please do|absolutely|of course|proceed)\b", re.I)
NO = re.compile(r"\b(no|nope|don'?t|do not|stop|cancel|negative|wait)\b", re.I)

DIM, RESET_COLOR = ("\033[2m", "\033[0m") if sys.stdout.isatty() else ("", "")


def is_yes(answer: str) -> bool:
    return bool(YES.search(answer or "")) and not NO.search(answer or "")


def normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


class Assistant:
    def __init__(self, config, voice_input: bool = True, voice_output: bool = True) -> None:
        self.cfg = config
        self.name = config.assistant_name
        self.voice_input = voice_input
        self.llm = OllamaClient.from_config(config.llm)
        self.memory = Memory(config.paths.data / "memory.json")
        engine = make_engine(config.tts, config.audio.output_device) if voice_output else SilentEngine
        self.speaker = Speaker(engine)
        self.ctx = ToolContext(
            config, self.llm, self.memory,
            say=self._progress, ask_yes_no=self._ask_yes_no, announce=self._announce,
        )
        self.tools = ToolRegistry(self.ctx)
        self.brain = Brain(
            config, self.llm, self.tools, self.memory, os_description(),
            speak=self.speaker.say, show=self._show, on_tool=self._on_tool,
        )
        self.mic = None
        self.stt = None
        self.wake = None
        self._line_open = False
        self._print_lock = threading.RLock()

    # ------------------------------------------------------------------ output
    def _show(self, text: str) -> None:
        with self._print_lock:
            if not self._line_open:
                print(f"\n{self.name}: ", end="")
                self._line_open = True
            print(text, end="", flush=True)

    def _end_line(self) -> None:
        with self._print_lock:
            if self._line_open:
                print(flush=True)
                self._line_open = False

    def say(self, text: str) -> None:
        self._end_line()
        with self._print_lock:
            print(f"\n{self.name}: {text}", flush=True)
        self.speaker.say(text)

    def _progress(self, text: str) -> None:
        self.say(text)

    def _announce(self, text: str) -> None:
        self.say(text)

    def _on_tool(self, name: str, args: dict, result: str) -> None:
        self._end_line()
        arg_text = ", ".join(f"{k}={v!r}" for k, v in args.items())
        if len(arg_text) > 100:
            arg_text = arg_text[:100] + "..."
        first_line = result.strip().splitlines()[0] if result.strip() else ""
        with self._print_lock:
            print(f"{DIM}  [{name}({arg_text})] {first_line[:120]}{RESET_COLOR}", flush=True)

    # ------------------------------------------------------------------- input
    def _ask_yes_no(self, question: str) -> bool:
        self.say(question)
        if not self.voice_input:
            try:
                return is_yes(input("  (yes/no) > "))
            except EOFError:
                return False
        self.speaker.wait()
        self.mic.resume()
        try:
            answer = self.listen(start_timeout=8, chime=True)
        finally:
            self.mic.pause()
        return is_yes(answer)

    def listen(self, start_timeout: float | None = None, chime: bool = True) -> str:
        from .audio import chime as play_chime

        a = self.cfg.audio
        if chime and a.chime:
            play_chime(device=a.output_device)
            time.sleep(0.25)
            self.mic.clear()  # don't let Jarvis hear its own chime
        with self._print_lock:
            print(f"{DIM}  (listening...){RESET_COLOR}", flush=True)
        audio = self.mic.record_utterance(
            start_timeout=a.start_timeout if start_timeout is None else start_timeout,
            silence_seconds=a.silence_seconds,
            max_seconds=a.max_record_seconds,
        )
        if audio is None:
            return ""
        text = self.stt.transcribe(audio)
        if text:
            with self._print_lock:
                print(f"\nYou: {text}", flush=True)
        return text

    # ---------------------------------------------------------------- behaviour
    def greeting(self) -> str:
        hour = dt.datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        return f"Good {part}, {self.cfg.user_title}. {self.name} is online and at your service."

    def check_brain(self) -> None:
        """Make sure Ollama is running and has the model; exit with help if not."""
        try:
            present = self.llm.has_model()
        except LLMError as exc:
            sys.exit(f"\n{exc}\nSee README.md, section 'Install'.")
        if not present:
            sys.exit(
                f"\nThe model '{self.llm.model}' isn't downloaded yet. Run:\n"
                f"    ollama pull {self.llm.model}\n"
                "or: python -m jarvis --setup"
            )
        # Load the model into memory in the background so the first answer is quick.
        threading.Thread(target=self._warm_up, daemon=True).start()

    def _warm_up(self) -> None:
        try:
            self.llm.warm_up()
        except Exception as exc:  # noqa: BLE001 - only an optimisation
            log.debug("warm-up failed: %s", exc)

    def builtin(self, text: str) -> str | None:
        """Handle a few commands instantly without asking the model.

        Returns "exit", "handled" or None (not a built-in command).
        """
        cmd = normalize(text)
        cmd = re.sub(rf"^(hey |ok |okay )?{re.escape(self.name.lower())}\s*", "", cmd).strip()
        if cmd in EXIT_WORDS:
            self.say(f"Goodbye, {self.cfg.user_title}.")
            return "exit"
        if cmd in HUSH_WORDS:
            self.speaker.stop()
            if stop_auto_scroll(self.ctx):
                self.say("Stopped scrolling.")
            return "handled"
        if cmd in RESET_WORDS:
            self.brain.reset()
            self.say("Fresh start. What can I do for you?")
            return "handled"
        return None

    def respond(self, text: str) -> None:
        try:
            self.brain.handle(text)
            self._end_line()
            self.speaker.wait()
        except LLMError as exc:
            self._end_line()
            message = str(exc)
            print(f"  ({message})", flush=True)
            if "does not support tools" in message:
                spoken = ("The model you picked can't use tools. Please choose one that can, "
                          "such as qwen 2.5, in the config file.")
            elif "Can't reach" in message:
                spoken = "I can't reach my language model. Is Ollama running?"
            else:
                spoken = "Something went wrong with my language model. The details are on screen."
            self.say(spoken)
            self.speaker.wait()
        except KeyboardInterrupt:
            self.speaker.stop()
            self._end_line()
            print(f"{DIM}  (interrupted){RESET_COLOR}")
            self.brain.history.append({"role": "assistant", "content": "(interrupted)"})

    # ---------------------------------------------------------------- run modes
    def run_text(self) -> None:
        self.check_brain()
        self.say(self.greeting())
        print(f"{DIM}Type a request and press Enter. 'exit' to quit, Ctrl+C to interrupt."
              f"{RESET_COLOR}")
        while True:
            try:
                text = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            result = self.builtin(text)
            if result == "exit":
                break
            if result is None:
                self.respond(text)
        self.speaker.wait()

    def _init_voice(self) -> None:
        from .audio import Microphone
        from .stt import SpeechToText
        from .wakeword import OpenWakeWordDetector, PushToTalk, WhisperWakeWord

        a, s, w = self.cfg.audio, self.cfg.stt, self.cfg.wake_word
        print("Loading speech recognition...", flush=True)
        try:
            self.stt = SpeechToText(s.model, s.device, s.compute_type, s.language)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Couldn't load the speech recognition model '{s.model}' ({exc}).\n"
                "Run this once while online: python -m jarvis --setup"
            ) from exc
        try:
            self.mic = Microphone(a.sample_rate, a.input_device, a.min_speech_rms)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Couldn't open the microphone ({exc}).\n"
                "Check it's connected, or pick one: python -m jarvis --list-devices"
            ) from exc
        names = list(dict.fromkeys([self.name.lower(), *w.names]))
        if w.engine == "openwakeword":
            try:
                self.wake = OpenWakeWordDetector(w.model, w.threshold)
                self._wake_hint = "Say 'Hey Jarvis'"
                return
            except Exception as exc:  # noqa: BLE001 - fall back gracefully
                log.warning("openWakeWord unavailable (%s); listening for the name instead.", exc)
        if w.engine in ("openwakeword", "whisper"):
            self.wake = WhisperWakeWord(self.stt, names)
            self._wake_hint = f"Say '{self.name}' followed by your request"
        else:
            self.wake = PushToTalk()
            self._wake_hint = "Press Enter and speak"

    def run_voice(self) -> None:
        self.check_brain()
        try:
            self._init_voice()
        except RuntimeError as exc:
            sys.exit(f"\n{exc}\nOr type instead of talking: python -m jarvis --text")
        follow_up = self.cfg.wake_word.follow_up_seconds
        with self.mic:
            print("Calibrating microphone, stay quiet for a second...", flush=True)
            self.mic.calibrate(1.0)
            with self.mic.paused():
                self.say(self.greeting())
                self.speaker.wait()
            print(f"{DIM}{self._wake_hint}. Ctrl+C interrupts a reply; Ctrl+C while idle quits."
                  f"{RESET_COLOR}")
            while True:
                try:
                    command = self.wake.wait(self.mic)
                except (KeyboardInterrupt, EOFError):
                    print()
                    break
                try:
                    if self._conversation(command, follow_up) == "exit":
                        break
                except KeyboardInterrupt:
                    self.speaker.stop()
                    self._end_line()

    def _conversation(self, command: str, follow_up: float) -> str | None:
        """Handle a request, then keep listening briefly for follow-ups."""
        if not command:
            command = self.listen()
        while command:
            result = self.builtin(command)
            if result == "exit":
                self.speaker.wait()
                return "exit"
            if result is None:
                with self.mic.paused():
                    self.respond(command)
            if follow_up <= 0:
                break
            command = self.listen(start_timeout=follow_up, chime=False)
        return None
