"""Canva, through Canva's official MCP connector (needs internet and a Canva account).

Canva is a cloud app, so this is the one skill that can't work offline.
Instead of writing scripts, a small agent uses Canva's own tools (search,
read, edit, export...) step by step. Edits are made in a draft; Jarvis shows
you a preview and saves them only after you say yes.
"""

from __future__ import annotations

import importlib.util
import json
import re
import webbrowser
from pathlib import Path

from . import RunResult, Skill
from .agent import TaskResult
from .guides import load_guide

DEFAULT_TOOLS = [
    "search-designs", "read-design", "edit-design", "export-design", "get-export-formats",
    "resize-design", "copy-design", "generate-design", "create-design-from-candidate",
    "get-create-design-async-job", "upload-asset-from-url", "get-assets", "list-brand-kits",
    "generate-image", "get-generate-image-job", "remove-background", "search-folders",
    "list-folder-items", "create-folder", "move-item-to-folder", "comment-on-design",
]

OPEN_LINK_TOOL = {"type": "function", "function": {
    "name": "open_link",
    "description": "Open a URL in the user's web browser (a design's edit/view link, an export download).",
    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
}}

SYSTEM = """\
You are working in the user's Canva account on behalf of Jarvis, their voice assistant, \
using Canva's official tools. Complete the task. When done, reply with one or two plain \
sentences saying what you did (they will be spoken aloud, so no lists, links or Markdown).
Always fill in user_intent on Canva tools. Don't invent IDs: get them from tool results.

{guide}
"""

URL = re.compile(r"https?://[^\s\"'<>)]+")


class CanvaSkill(Skill):
    name = "canva"
    title = "Canva"

    def __init__(self, config) -> None:
        super().__init__(config)
        self.url = self.settings.get("url") or "https://mcp.canva.com/mcp"
        self.token_file = Path(config.paths.data) / "mcp" / "canva.json"
        self.conn = None

    def detect(self) -> str | None:
        if importlib.util.find_spec("mcp") is None:
            return "the mcp package is missing (pip install mcp)"
        return None

    def connection(self):
        if self.conn is None:
            from ..mcp_bridge import MCPConnection

            print("Connecting to Canva (the first time, your browser opens to sign in)...")
            self.conn = MCPConnection("canva", self.url, token_file=self.token_file).start()
        return self.conn

    def run(self, code: str) -> RunResult:  # not a scripting skill
        return RunResult(False, "", "Canva is used through its tools, not scripts.")

    def run_task(self, task: str, llm, ctx, max_steps: int = 20) -> TaskResult:
        try:
            conn = self.connection()
        except Exception as exc:  # noqa: BLE001 - offline, sign-in cancelled...
            return TaskResult(False, f"Couldn't connect to Canva: {exc}", 0)
        allow = self.settings.get("tools") or DEFAULT_TOOLS
        tools = conn.tool_schemas(allow) + [OPEN_LINK_TOOL]
        intro, sections = load_guide("canva")
        guide = "\n".join([intro] + [s.text() for s in sections if s.kind == "core"])
        messages = [{"role": "system", "content": SYSTEM.format(guide=guide)},
                    {"role": "user", "content": task}]
        preview_url = None

        for step in range(1, max_steps + 1):
            result = llm.chat(messages, tools=tools, num_ctx=ctx.config.skills.code_num_ctx)
            if not result.tool_calls:
                return TaskResult(True, result.content or "Done.", step)
            message = {"role": "assistant", "content": result.content, "tool_calls": result.tool_calls}
            if result.raw is not None:
                message["_anthropic_content"] = result.raw
            messages.append(message)
            for call in result.tool_calls:
                fn = call.get("function", {})
                name, args = fn.get("name", ""), fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                output = self._call(conn, ctx, name, args, preview_url)
                preview_url = _find_preview(output) or preview_url
                tool_msg = {"role": "tool", "content": output[:12000], "tool_name": name}
                if call.get("id"):
                    tool_msg["tool_call_id"] = call["id"]
                messages.append(tool_msg)
        return TaskResult(False, "The Canva task took too many steps; it may be half done.", max_steps)

    def _call(self, conn, ctx, name: str, args: dict, preview_url: str | None) -> str:
        if name == "open_link":
            webbrowser.open(args.get("url", ""))
            return "Opened in the browser."
        if name == "edit-design" and args.get("finalize") == "commit":
            if preview_url:
                webbrowser.open(preview_url)
            question = ("I've made the changes in Canva" + (" and opened a preview" if preview_url else "")
                        + ". Shall I save them?")
            if not ctx._ask_yes_no(question):  # Canva requires explicit approval, always ask
                return ("The user did NOT approve saving. Don't commit. Ask what to change, or send "
                        "finalize 'cancel' to discard the draft.")
        try:
            return conn.call(name, args)
        except Exception as exc:  # noqa: BLE001 - report to the model so it can adapt
            return f"Error calling {name}: {exc}"

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()


def _find_preview(output: str) -> str | None:
    """A thumbnail/preview image URL in a tool result, if any."""
    for url in URL.findall(output or ""):
        if "thumbnail" in url.lower() or re.search(r"\.(png|jpe?g|webp)(\?|$)", url, re.I):
            return url
    return None
