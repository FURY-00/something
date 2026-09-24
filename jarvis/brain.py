"""The conversation loop: understand, act with tools, answer."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import Callable

from .llm import strip_think
from .speech_text import SentenceSplitter

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are {name}, the user's personal AI assistant, living on their computer ({os}). \
Think J.A.R.V.I.S. from Iron Man: brilliant, calm, loyal and quietly witty, with dry \
British humour, and genuinely interested in whatever the user is working on.

How you talk
- This is a spoken conversation between two people. Talk the way a clever, warm friend \
would: natural, direct, sometimes playful. React to what the user says before answering, \
ask a short follow-up question when it helps, and give your honest opinion when asked. \
Remember what was said earlier and in past conversations, and bring it up when relevant.
- Keep replies short, usually one to three sentences. Go longer only to explain something \
the user asked about.
- Your words are spoken aloud: no Markdown, lists, emoji, code or URLs. Say numbers, \
units and symbols the way they are spoken.
- Call the user "{title}" now and then, not in every sentence.
- Don't lecture, don't pile on disclaimers and never say you're "just an AI".

Getting things done
- You operate this computer through tools. When asked to do something, do it with the \
right tool instead of explaining how, chaining tools for multi-step requests. Confirm \
briefly afterwards.
- Never claim something worked unless a tool said so. If a tool reports an error, say \
what went wrong in plain words and suggest what to try next.
- Longer writing (abstracts, essays, emails, reports) goes through write_document; \
programs and websites through the code tools. Don't read them out.
{skills}
Knowledge
- {knowledge}
- If you don't know or aren't sure, say so honestly instead of guessing.

Current date and time: {now}.
What you know about the user:
{memory}
Your past conversations with the user (most recent last):
{episodes}
{jobs}"""

SKILLS_PROMPT = """
Professional applications you can work in: {apps}.
- To get work done in one of them, call its tool with ONE complete, precise task: every \
dimension, unit, material, value, name and file the user mentioned, plus sensible \
defaults for anything missing (and tell the user which defaults you picked). If \
something critical is missing and has no sensible default, ask one short question first.
- Break big jobs into steps (sketch, extrude, then fillet; geometry, physics, mesh, then \
solve) and tell the user how it's going between steps.
- Use in_background for long renders, simulations and exports so you can keep talking.
- If the user wants to learn to do it by hand, use how_to and walk them through it one \
or two steps at a time, waiting for them to say they're done before continuing.
"""

KNOWLEDGE_LOCAL = ("You run offline, so your knowledge comes from training and stops at "
                   "your training date: no live news, prices or weather.")
KNOWLEDGE_CLOUD = ("Your knowledge comes from training and has a cutoff date; you have no "
                   "live news, prices or weather.")
KNOWLEDGE_HINT = (" You also have an offline encyclopedia (lookup_encyclopedia): use it to "
                  "check facts about people, places, history and science.")

SUMMARY_PROMPT = (
    "Summarise this conversation between {name} and the user in one or two sentences for "
    "{name}'s long-term memory. Focus on what the user was working on, decisions made, "
    "anything left unfinished and preferences they showed. Refer to them as \"the user\". "
    "Plain text, no preamble."
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
                 on_tool: Callable[[str, dict, str], None] | None = None,
                 jobs=None, apps: list[str] | None = None) -> None:
        self.config = config
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.os_name = os_name
        self.speak = speak
        self.show = show
        self.on_tool = on_tool or (lambda name, args, result: None)
        self.jobs = jobs
        self.apps = apps or []
        self.history: list[dict] = []

    def reset(self) -> None:
        self.history.clear()

    def system_prompt(self) -> str:
        names = self.tools.names()
        knowledge = KNOWLEDGE_CLOUD if getattr(self.llm, "append_only", False) else KNOWLEDGE_LOCAL
        if "lookup_encyclopedia" in names:
            knowledge += KNOWLEDGE_HINT
        skills = SKILLS_PROMPT.format(apps=", ".join(self.apps)) if self.apps else ""
        jobs = self.jobs.summary() if self.jobs else ""
        return SYSTEM_PROMPT.format(
            name=self.config.assistant_name,
            title=self.config.user_title,
            os=self.os_name,
            skills=skills,
            knowledge=knowledge,
            now=dt.datetime.now().strftime("%A %d %B %Y, %I:%M %p"),
            memory=self.memory.as_prompt(),
            episodes=self.memory.episodes_prompt(),
            jobs=f"Background jobs:\n{jobs}" if jobs else "",
        )

    def summarize(self) -> str:
        """One or two sentences about this conversation, for long-term memory."""
        turns = [m for m in self.history if m["role"] in ("user", "assistant") and m.get("content")]
        if sum(1 for m in turns if m["role"] == "user") < 2:
            return ""
        name = self.config.assistant_name
        transcript = "\n".join(
            f"{'User' if m['role'] == 'user' else name}: {m['content'][:600]}" for m in turns[-40:]
        )
        result = self.llm.chat(
            [{"role": "system", "content": SUMMARY_PROMPT.format(name=name)},
             {"role": "user", "content": transcript}],
            stream=False,
        )
        return strip_think(result.content)

    def _context(self, turn_start: int) -> list[dict]:
        """Recent history, with bulky tool output from earlier turns shortened.

        Cloud brains get the history untouched (they have a huge context window
        and replay earlier replies exactly), trimmed only when it gets very long.
        """
        append_only = getattr(self.llm, "append_only", False)
        limit = 400 if append_only else self.config.llm.max_history_messages
        start = max(0, len(self.history) - limit)
        while start < len(self.history) and self.history[start]["role"] != "user":
            start += 1  # never begin mid-exchange
        start = min(start, turn_start)
        msgs = []
        for i, msg in enumerate(self.history[start:], start):
            if not append_only and i < turn_start and msg["role"] == "tool" and len(msg["content"]) > 400:
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
                message = {"role": "assistant", "content": reply}
                if result.raw is not None:
                    message["_anthropic_content"] = result.raw
                self.history.append(message)
                return reply

            message = {
                "role": "assistant",
                "content": "" if from_text else result.content,
                "tool_calls": calls,
            }
            if result.raw is not None:
                message["_anthropic_content"] = result.raw
            self.history.append(message)
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
                tool_msg = {"role": "tool", "content": output, "tool_name": name}
                if call.get("id"):
                    tool_msg["tool_call_id"] = call["id"]
                self.history.append(tool_msg)

        reply = "I seem to be going round in circles on that one. Could you rephrase it?"
        self.speak(reply)
        self.show(reply)
        self.history.append({"role": "assistant", "content": reply})
        return reply
