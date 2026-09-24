"""The conversation loop: understand, act with tools, answer."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import Callable

from .speech_text import SentenceSplitter

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are {name}, a personal AI assistant living on the user's computer ({os}), \
modelled on J.A.R.V.I.S. from Iron Man. You are calm, capable, loyal and quietly witty, \
with a touch of dry British humour. Address the user as "{title}".

Your replies are spoken aloud by a voice, so:
- Keep them short: one to three sentences unless asked for more detail.
- Never use Markdown, bullet lists, emoji, code blocks or URLs in replies.
- Write numbers, times and symbols the way they are said out loud.

You control this computer through tools. When the user asks you to do something, \
call the right tool instead of explaining how to do it; chain several tools for \
multi-step requests. After acting, confirm briefly in a few words. Never claim you \
did something unless a tool result says it worked; if a tool reports an error, say \
so plainly. For anything longer than a short paragraph (abstracts, essays, emails, \
reports, code) use write_document instead of speaking it.

You run fully offline. Your general knowledge comes from training and stops at your \
training date, so you do not know today's news, prices or weather.{knowledge_hint} \
If you don't know something, say so rather than guessing.

Current date and time: {now}.
What you remember about the user:
{memory}
"""

KNOWLEDGE_HINT = (
    " You have an offline encyclopedia (lookup_encyclopedia): use it to check facts "
    "about people, places, history and science before answering."
)

HELD_PREFIXES = ("{", "[", "`", "<tool", "<function")


class ReplyStreamer:
    """Routes streamed reply text to the screen and to the voice.

    If a reply starts like JSON, it's probably a tool call the model wrote as
    text instead of using the proper channel, so it's held back, not spoken.
    """

    def __init__(self, speak: Callable[[str], None], show: Callable[[str], None]) -> None:
        self.speak = speak
        self.show = show
        self.splitter = SentenceSplitter()
        self.held: bool | None = None
        self.pending = ""

    def feed(self, text: str) -> None:
        if self.held is None:
            self.pending += text
            start = self.pending.lstrip()
            if not start or (len(start) < 5 and any(p.startswith(start) for p in HELD_PREFIXES)):
                return  # not enough text yet to decide
            self.held = start.startswith(HELD_PREFIXES)
            text, self.pending = self.pending, ""
            if not self.held:
                text = text.lstrip()
        if self.held:
            self.pending += text
            return
        self.show(text)
        for sentence in self.splitter.feed(text):
            self.speak(sentence)

    def finish(self, release_held: bool = True) -> None:
        """Call once the reply is complete. Held text is spoken only if it
        turned out not to be a tool call (``release_held``)."""
        if self.held is False:
            rest = self.splitter.flush()
            if rest:
                self.speak(rest)
        elif release_held and self.pending.strip():
            self.show(self.pending.strip())
            self.speak(self.pending.strip())
        self.pending = ""


def parse_text_tool_calls(content: str, tool_names: list[str]) -> list[dict]:
    """Recover tool calls that a model wrote as plain text/JSON."""
    text = content.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text).strip()
    text = re.sub(r"</?(tool_call|function_call|tools?)>", "", text).strip()
    candidates = []
    try:
        candidates = [json.loads(text)]
    except ValueError:
        for m in re.finditer(r"\{.*\}", text, flags=re.S):
            try:
                candidates.append(json.loads(m.group(0)))
            except ValueError:
                continue
    calls = []
    for item in candidates:
        for obj in item if isinstance(item, list) else [item]:
            if not isinstance(obj, dict):
                continue
            fn = obj.get("function") if isinstance(obj.get("function"), dict) else obj
            name = fn.get("name")
            args = fn.get("arguments", fn.get("parameters", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if name in tool_names:
                calls.append({"function": {"name": name, "arguments": args or {}}})
    return calls


class Brain:
    def __init__(self, config, llm, tools, memory, os_name: str,
                 speak: Callable[[str], None], show: Callable[[str], None],
                 on_tool: Callable[[str, dict, str], None] | None = None) -> None:
        self.config = config
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.os_name = os_name
        self.speak = speak
        self.show = show
        self.on_tool = on_tool or (lambda name, args, result: None)
        self.history: list[dict] = []

    def reset(self) -> None:
        self.history.clear()

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(
            name=self.config.assistant_name,
            title=self.config.user_title,
            os=self.os_name,
            now=dt.datetime.now().strftime("%A %d %B %Y, %I:%M %p"),
            memory=self.memory.as_prompt(),
            knowledge_hint=KNOWLEDGE_HINT if "lookup_encyclopedia" in self.tools.names() else "",
        )

    def _context(self, turn_start: int) -> list[dict]:
        """Recent history, with bulky tool output from earlier turns shortened."""
        limit = self.config.llm.max_history_messages
        start = max(0, len(self.history) - limit)
        while start < len(self.history) and self.history[start]["role"] != "user":
            start += 1  # never begin mid-exchange
        start = min(start, turn_start)
        msgs = []
        for i, msg in enumerate(self.history[start:], start):
            if i < turn_start and msg["role"] == "tool" and len(msg["content"]) > 400:
                msg = {**msg, "content": msg["content"][:400] + " ...(shortened)"}
            msgs.append(msg)
        return [{"role": "system", "content": self.system_prompt()}] + msgs

    def handle(self, user_text: str) -> str:
        """Answer one request. Speech is streamed out while the model writes."""
        turn_start = len(self.history)
        self.history.append({"role": "user", "content": user_text})
        schemas = self.tools.schemas()
        names = self.tools.names()

        for _ in range(self.config.llm.max_tool_rounds):
            streamer = ReplyStreamer(self.speak, self.show)
            result = self.llm.chat(self._context(turn_start), tools=schemas, on_text=streamer.feed)
            calls = result.tool_calls
            from_text = False
            if not calls and streamer.held is not False:
                calls = parse_text_tool_calls(result.content, names)
                from_text = bool(calls)
            streamer.finish(release_held=not calls)

            if not calls:
                reply = result.content
                self.history.append({"role": "assistant", "content": reply})
                return reply

            self.history.append({
                "role": "assistant",
                "content": "" if from_text else result.content,
                "tool_calls": calls,
            })
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                output = self.tools.call(name, args)
                self.on_tool(name, args, output)
                self.history.append({"role": "tool", "content": output, "tool_name": name})

        reply = "I seem to be going round in circles on that one. Could you rephrase it?"
        self.speak(reply)
        self.show(reply)
        self.history.append({"role": "assistant", "content": reply})
        return reply
