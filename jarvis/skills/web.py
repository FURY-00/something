"""Writing code: interactive websites from documents, and programs in any language.

Projects live in ``Documents/Jarvis/Projects/websites/<name>`` and
``.../code/<name>``. Every edit keeps the previous version in ``.history/``.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from ..documents import extract, find_documents
from ..llm import strip_think
from .agent import check_code

SITE_SYSTEM = """\
You are an expert front-end developer and designer. You build complete, polished, \
interactive websites with HTML, CSS and JavaScript.

Output format: every file in full, each introduced by a line `### FILE: <relative path>` \
followed by one fenced code block. Nothing else. Default to a single `index.html` with \
inline <style> and <script> unless the task needs more files.

Rules:
- Plain HTML/CSS/vanilla JavaScript that works by double-clicking index.html: no build \
step, no npm, no external requests unless the user asks for online features.
- Use the source material faithfully. Don't invent facts, numbers or quotes. Organise it \
well: a header, clear navigation, sections with headings, a footer.
- Make it genuinely interactive where it helps understanding: tabs, accordions, search \
or filters, a quiz or flashcards from the content, charts drawn with SVG or <canvas>, \
an image lightbox, a light/dark toggle, smooth scrolling, progress indicators.
- Modern, clean design: good typography, spacing and colour; responsive from phone to \
desktop; accessible (semantic HTML, alt text, keyboard navigation, readable contrast).
- Use images only from the provided list, by their relative paths (assets/...).
"""

PROGRAM_SYSTEM = """\
You are an expert {language} programmer. Write complete, correct, well-structured code \
for the task, with brief comments where the code isn't obvious.

Output format: every file in full, each introduced by a line `### FILE: <relative path>` \
followed by one fenced code block. Include a short README.md saying how to run it. For \
Python, put the entry point in main.py and list third-party packages in requirements.txt.
"""

EDIT_RULES = """\
Here are the current project files. Apply the requested change. Output ONLY the files you \
changed, each in full, in the same `### FILE:` format. Keep everything else as it is."""

FILE_BLOCK = re.compile(r"^#{1,6}\s*FILE:\s*`?([^\n`]+?)`?\s*\n+```[^\n]*\n(.*?)^```", re.M | re.S)
TEXT_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".md", ".txt", ".py", ".svg", ".csv",
                 ".ts", ".java", ".c", ".cpp", ".h", ".rs", ".go", ".rb", ".php", ".sh", ".yaml", ".yml"}


def slug(name: str) -> str:
    return re.sub(r"[^\w-]+", "-", name.strip().lower()).strip("-")[:60] or "project"


def parse_files(reply: str, default_name: str) -> dict[str, str]:
    reply = strip_think(reply)
    files = {m.group(1).strip(): m.group(2) for m in FILE_BLOCK.finditer(reply)}
    if not files:
        blocks = re.findall(r"```[^\n]*\n(.*?)```", reply, flags=re.S)
        if blocks:
            files = {default_name: max(blocks, key=len)}
    clean = {}
    for name, body in files.items():
        rel = Path(name.replace("\\", "/").lstrip("/"))
        if ".." in rel.parts:
            continue  # never write outside the project folder
        clean[str(rel)] = body.rstrip() + "\n"
    return clean


def write_files(folder: Path, files: dict[str, str]) -> list[Path]:
    history = folder / ".history" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    written = []
    for rel, body in files.items():
        target = folder / rel
        if target.exists():
            (history / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, history / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        written.append(target)
    return written


def read_project(folder: Path, limit: int = 120_000) -> str:
    parts, total = [], 0
    for f in sorted(folder.rglob("*")):
        if ".history" in f.parts or not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        body = f.read_text(encoding="utf-8", errors="replace")
        total += len(body)
        if total > limit:
            parts.append(f"(more files not shown: {f.relative_to(folder)} ...)")
            break
        ext = f.suffix.lstrip(".")
        parts.append(f"### FILE: {f.relative_to(folder).as_posix()}\n```{ext}\n{body}```")
    return "\n\n".join(parts)


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.tags = 0

    def handle_starttag(self, tag, attrs):
        self.tags += 1
        for key, value in attrs:
            if key in ("src", "href") and value and not re.match(r"^(https?:|mailto:|tel:|data:|#|javascript:)", value):
                self.refs.append(value.split("#")[0].split("?")[0])


def check_site(folder: Path) -> list[str]:
    """Problems a browser would show: missing files, missing index.html."""
    index = folder / "index.html"
    if not index.exists():
        return ["There is no index.html."]
    problems = []
    for html in folder.rglob("*.htm*"):
        if ".history" in html.parts:
            continue
        parser = _Refs()
        parser.feed(html.read_text(encoding="utf-8", errors="replace"))
        if parser.tags < 3:
            problems.append(f"{html.name} has almost no HTML in it.")
        for ref in parser.refs:
            if ref and not (html.parent / ref).exists():
                problems.append(f"{html.name} links to {ref}, which doesn't exist.")
    return problems


def content_budget(cfg) -> int:
    """How many characters of source material fit in the code model's context."""
    if _provider(cfg) == "anthropic":
        return 600_000
    return max(8_000, int(cfg.skills.code_num_ctx * 2.5) - 12_000)


def _provider(cfg) -> str:
    p = cfg.skills.code_provider
    return cfg.llm.provider if p in ("same", "", None) else p


def condense(text: str, budget: int, llm, say) -> str:
    """Summarise long material chunk by chunk until it fits, keeping the facts."""
    if len(text) <= budget:
        return text
    say("That's a lot of material, so I'm condensing it first.")
    chunk = max(4000, budget // 2)
    notes = []
    for i in range(0, len(text), chunk):
        part = text[i:i + chunk]
        reply = llm.chat([
            {"role": "system", "content": "Turn this part of a document into detailed, well-organised "
             "notes for building a website. Keep every heading, key fact, number, definition, formula, "
             "example and [image: ...] marker. Plain Markdown."},
            {"role": "user", "content": part},
        ], temperature=0.2)
        notes.append(strip_think(reply.content))
    joined = "\n\n".join(notes)
    return joined if len(joined) <= budget else condense(joined, budget, llm, say)


def gather_sources(sources: str, assets: Path) -> tuple[str, list[str]]:
    paths = [p for p in re.split(r"[;\n]", sources or "") if p.strip()]
    texts, images = [], []
    for doc in find_documents(paths):
        ex = extract(doc, assets_dir=assets)
        texts.append(f"# Source: {doc.name}\n{ex.text}")
        images += [f"assets/{img.name}" for img in ex.images]
    return "\n\n".join(texts), images


def build_site(ctx, request: str, sources: str, name: str) -> str:
    cfg = ctx.config
    folder = Path(cfg.paths.projects).expanduser() / "websites" / slug(name)
    folder.mkdir(parents=True, exist_ok=True)
    content, images = gather_sources(sources, folder / "assets") if sources else ("", [])
    content = condense(content, content_budget(cfg), ctx.code_llm, ctx.say)
    image_list = "\n".join(images) or "(none)"
    prompt = (f"Task: {request}\n\nImages you can use (relative paths):\n{image_list}\n\n"
              f"Source material:\n{content or '(none - write the content yourself from the task)'}")
    messages = [{"role": "system", "content": SITE_SYSTEM}, {"role": "user", "content": prompt}]
    return _generate(ctx, folder, messages, "index.html", site=True)


def edit_project(ctx, folder: Path, request: str, site: bool) -> str:
    if not folder.exists():
        return f"Error: there's no project at {folder}."
    system = SITE_SYSTEM if site else PROGRAM_SYSTEM.format(language="the project's")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"{EDIT_RULES}\n\n{read_project(folder)}\n\nChange: {request}"}]
    default = "index.html" if site else "main.py"
    return _generate(ctx, folder, messages, default, site=site, open_after=site)


def write_program(ctx, request: str, language: str, name: str, run: bool) -> str:
    cfg = ctx.config
    folder = Path(cfg.paths.projects).expanduser() / "code" / slug(name)
    folder.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "system", "content": PROGRAM_SYSTEM.format(language=language)},
                {"role": "user", "content": request}]
    default = {"python": "main.py", "javascript": "main.js", "html": "index.html"}.get(language.lower(), "main.txt")
    result = _generate(ctx, folder, messages, default, site=language.lower() == "html",
                       open_after=language.lower() == "html")
    if not run or language.lower() != "python" or result.startswith("Error"):
        return result
    return _run_and_fix(ctx, folder, messages)


def _generate(ctx, folder: Path, messages: list[dict], default: str, site: bool,
              open_after: bool = True) -> str:
    from ..tools.system import open_with_default_app

    llm = ctx.code_llm
    attempts = ctx.config.skills.max_attempts
    written: list[Path] = []
    problems: list[str] = []
    for _attempt in range(attempts):
        reply = llm.chat(messages, temperature=0.3, num_ctx=ctx.config.skills.code_num_ctx).content
        files = parse_files(reply, default)
        messages.append({"role": "assistant", "content": reply})
        if not files:
            messages.append({"role": "user", "content": "Send the files in the `### FILE:` format."})
            continue
        written += write_files(folder, files)
        problems = check_site(folder) if site else []
        if not problems:
            break
        messages.append({"role": "user", "content": "Problems found:\n- " + "\n- ".join(problems)
                         + "\nFix them. Send only the changed files, in full."})
    if not written:
        return "Error: the code model didn't produce any files."
    names = sorted({p.relative_to(folder).as_posix() for p in written})
    if open_after and (folder / "index.html").exists():
        open_with_default_app(str(folder / "index.html"))
    opened = " and opened it in the browser" if open_after and site else ""
    leftover = f" Remaining problems: {'; '.join(problems)}" if problems else ""
    return f"Wrote {', '.join(names)} in {folder}{opened}.{leftover}"


def _run_and_fix(ctx, folder: Path, messages: list[dict]) -> str:
    main = folder / "main.py"
    if not main.exists():
        candidates = sorted(folder.glob("*.py"))
        if not candidates:
            return "Error: no Python file to run."
        main = candidates[0]
    code = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("*.py"))
    problem = check_code(code)
    if problem and not ctx.confirm(f"The program does something sensitive ({problem.rstrip('.')}). Run it anyway?"):
        return f"Wrote the program in {folder} but didn't run it."
    for attempt in range(ctx.config.skills.max_attempts):
        try:
            proc = subprocess.run([sys.executable, main.name], cwd=folder, capture_output=True,
                                  text=True, timeout=120, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return f"The program in {folder} was still running after 2 minutes, so I stopped it."
        output = (proc.stdout + proc.stderr).strip()
        if proc.returncode == 0:
            return f"Ran {main.name} in {folder}. Output:\n{output[-2500:] or '(nothing printed)'}"
        if attempt == ctx.config.skills.max_attempts - 1:
            break
        if attempt == 0:
            ctx.say("It crashed. Fixing it.")
        messages.append({"role": "user", "content": f"Running {main.name} failed:\n{output[-3000:]}\n"
                         "Fix it. Send only the changed files, in full."})
        reply = ctx.code_llm.chat(messages, temperature=0.2, num_ctx=ctx.config.skills.code_num_ctx).content
        messages.append({"role": "assistant", "content": reply})
        write_files(folder, parse_files(reply, main.name))
    return f"The program in {folder} still fails:\n{output[-2000:]}"


def find_project(ctx, name: str, kind: str) -> Path:
    base = Path(ctx.config.paths.projects).expanduser() / kind
    if name and (base / slug(name)).exists():
        return base / slug(name)
    projects = sorted((p for p in base.glob("*") if p.is_dir()), key=lambda p: p.stat().st_mtime)
    if name:
        for p in reversed(projects):
            if slug(name) in p.name:
                return p
        return base / slug(name)  # doesn't exist: the caller reports that
    return projects[-1] if projects else base / "project"  # the most recent one
