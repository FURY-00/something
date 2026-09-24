"""The write -> run -> fix loop that lets Jarvis work inside an application."""

from __future__ import annotations

import ast
import datetime as dt
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ..llm import strip_think
from .guides import script_guide

log = logging.getLogger(__name__)

SYSTEM = """\
You are a senior {title} engineer working for Jarvis, an assistant on the user's \
computer. You complete tasks in {title} by writing Python scripts that run {where}.

How to answer:
- Reply with ONE complete script in a single ```python code block, followed by one \
short sentence describing what it does. Nothing else.
- Prefer the helper functions documented below; they are tested. Use the raw API \
only for things the helpers don't cover.
- The session persists: what earlier scripts created still exists (see "Current \
state"). Build on it. Don't start over unless the task says so.
- print() everything the user will want to know: names, dimensions, results, \
file paths. The printed output is all you will see.
- Units: {units}.
- If a script fails you get the error message. Find the cause, then send the whole \
corrected script, not a fragment.
- Never delete the user's files, run shell commands or use the network.

{guide}

# Current state of {title}
{state}
"""

FIX = """\
That script failed.

Error:
{error}

Output before the error:
{output}

Find the cause and send the complete corrected script."""

# Things LLM-written scripts must not do. This is a guard rail against honest
# mistakes, not a security sandbox.
BLOCKED_MODULES = {"subprocess", "socket", "requests", "urllib", "http", "ftplib",
                   "smtplib", "multiprocessing", "ctypes", "winreg", "webbrowser"}
BLOCKED_FUNCTIONS = {
    "os": {"system", "popen", "remove", "unlink", "rmdir", "removedirs", "kill", "startfile"},
    "shutil": {"rmtree", "move"},
}
BLOCKED_NAMES = {"eval", "exec", "__import__"}
BLOCKED_METHODS = {"quit_blender", "rmtree"}


def extract_code(reply: str) -> str:
    reply = strip_think(reply)
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", reply, flags=re.S)
    if blocks:
        return max(blocks, key=len).strip()
    stripped = reply.strip()
    looks_like_code = re.match(r"^(import |from |[a-zA-Z_][\w.]*\s*[=(])", stripped)
    return stripped if looks_like_code else ""


def check_code(code: str) -> str | None:
    """Return a problem description, or None if the script looks acceptable."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"SyntaxError: {exc.msg} (line {exc.lineno})"
    aliases = {}  # local name -> module, e.g. {"sh": "shutil"}
    blocked_names = {n: n for n in BLOCKED_NAMES}  # local name -> what it really is
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"Importing '{root}' isn't allowed in these scripts."
                aliases[a.asname or root] = root
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_MODULES:
                return f"Importing '{root}' isn't allowed in these scripts."
            for a in node.names:
                if a.name in BLOCKED_FUNCTIONS.get(root, ()):
                    blocked_names[a.asname or a.name] = f"{root}.{a.name}"
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in blocked_names:
            return f"Calling '{blocked_names[fn.id]}' isn't allowed in these scripts."
        if isinstance(fn, ast.Attribute):
            if fn.attr in BLOCKED_METHODS:
                return f"Calling '{fn.attr}' isn't allowed in these scripts."
            if isinstance(fn.value, ast.Name):
                module = aliases.get(fn.value.id, fn.value.id)
                if fn.attr in BLOCKED_FUNCTIONS.get(module, ()):
                    return f"Calling '{module}.{fn.attr}' isn't allowed in these scripts."
    return None


@dataclass
class TaskResult:
    ok: bool
    summary: str
    attempts: int
    script: Path | None = None


def _trim(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n...(cut)...\n" + text[-half:]


def run_task(skill, task: str, llm, cfg, say=lambda text: None) -> TaskResult:
    """Have the code model complete ``task`` in ``skill``'s application."""
    scfg = cfg.skills
    try:
        state = skill.state()
    except Exception as exc:  # noqa: BLE001 - state is only context
        state = f"(couldn't read the state: {exc})"
    system = SYSTEM.format(
        title=skill.title,
        where=skill.where,
        units=skill.units,
        guide=script_guide(skill.name, task),
        state=_trim(state, 3000),
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    script_dir = Path(cfg.paths.data) / "scripts" / skill.name
    script_dir.mkdir(parents=True, exist_ok=True)
    last_error = ""

    for attempt in range(1, scfg.max_attempts + 1):
        if attempt == 2:
            say("First try hit a snag. Fixing it.")
        reply = llm.chat(messages, temperature=0.2, num_ctx=scfg.code_num_ctx).content
        messages.append({"role": "assistant", "content": reply})
        code = extract_code(reply)
        if not code:
            last_error = "No script in the reply."
            messages.append({"role": "user", "content": "Send the script in a ```python code block."})
            continue
        problem = None if scfg.allow_unsafe_code else check_code(code)
        if problem:
            last_error = problem
            messages.append({"role": "user", "content": f"{problem} Rewrite the script without it."})
            continue

        script = script_dir / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{attempt}.py"
        script.write_text(f"# Task: {task}\n{code}\n", encoding="utf-8")
        log.info("running %s script %s", skill.name, script)
        result = skill.run(code)
        if result.ok:
            output = _trim(result.output, 2500) or "(the script printed nothing)"
            return TaskResult(True, output, attempt, script)
        last_error = _trim(result.error, 2000)
        messages.append({
            "role": "user",
            "content": FIX.format(error=last_error, output=_trim(result.output, 1000) or "(none)"),
        })

    return TaskResult(False, last_error or "unknown error", scfg.max_attempts)
