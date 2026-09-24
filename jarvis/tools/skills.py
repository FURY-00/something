"""Tools for professional applications, teaching, documents and code."""

from __future__ import annotations

import json
import logging

from . import tool
from ..skills import get_skill
from ..skills.guides import available_guides, teaching_guide

log = logging.getLogger(__name__)

TASK_PARAM = {
    "type": "string",
    "description": "One complete, precise description of the work: every dimension with units, "
    "material, value, name and file the user gave, plus the defaults you chose for anything missing",
}
BACKGROUND_PARAM = {
    "type": "boolean",
    "description": "true for long jobs (renders, simulations, big exports) so the conversation can go on",
}


def _enabled(name: str):
    def check(ctx) -> bool:
        return get_skill(ctx.config, name).enabled()
    return check


def _handle_markers(ctx, skill, output: str) -> str:
    """Act on special lines printed by helper functions, and hide them from the model."""
    kept = []
    for line in output.splitlines():
        if line.startswith("JARVIS_BACKGROUND "):
            try:
                info = json.loads(line[len("JARVIS_BACKGROUND "):])
                ctx.jobs.watch_process(info.get("name", "render"), int(info["pid"]), info.get("output", ""))
            except (ValueError, KeyError) as exc:
                log.debug("bad background marker %r: %s", line, exc)
        elif line.strip() == "JARVIS_SHOW_BLENDER" and hasattr(skill, "show"):
            kept.append(skill.show())
        else:
            kept.append(line)
    return "\n".join(kept).strip()


def run_app_task(ctx, name: str, task: str, in_background: bool = False) -> str:
    from ..skills.agent import run_task

    skill = get_skill(ctx.config, name)

    def work() -> tuple[bool, str]:
        with skill.lock:
            if name == "canva":
                result = skill.run_task(task, ctx.code_llm, ctx)
            else:
                result = run_task(skill, task, ctx.code_llm, ctx.config, say=ctx.say)
        summary = _handle_markers(ctx, skill, result.summary)
        if result.ok:
            return True, summary
        return False, f"Failed after {result.attempts} attempt(s). Last error:\n{summary}"

    if in_background:
        ctx.jobs.start(
            f"{skill.title} task", work,
            lambda job: (f"Your {skill.title} job is done." if job.status == "done"
                         else f"Your {skill.title} job ran into a problem.")
            + (" " + job.result.splitlines()[0][:150] if job.result else ""),
        )
        return f"Started in {skill.title} in the background. I'll say when it's finished."
    ctx.say(f"Working on it in {skill.title}.")
    ok, text = work()
    return ("Success. Output:\n" if ok else "") + text


@tool("Do work in Blender (3D models, scenes, materials, lighting, animation, rendering images "
      "and videos). Describe the whole task; Blender scripts it and reports back.",
      {"task": TASK_PARAM, "in_background": BACKGROUND_PARAM}, available=_enabled("blender"))
def blender(ctx, task: str, in_background: bool = False) -> str:
    return run_app_task(ctx, "blender", task, in_background)


@tool("Do work in SolidWorks: sketches (lines, circles, rectangles, arcs, polygons, slots), "
      "features (extrude, cut, revolve, fillet, chamfer, shell, planes, holes), editing dimensions, "
      "materials, mass properties, saving and exporting (STEP, STL, PDF). Lengths in mm.",
      {"task": TASK_PARAM, "in_background": BACKGROUND_PARAM}, available=_enabled("solidworks"))
def solidworks(ctx, task: str, in_background: bool = False) -> str:
    return run_app_task(ctx, "solidworks", task, in_background)


@tool("Do work in COMSOL Multiphysics: build models (1D/2D/3D geometry, materials, physics such "
      "as pipe flow, laminar flow, heat transfer, solid mechanics, electric currents), mesh, "
      "solve, evaluate results, plot and save.",
      {"task": TASK_PARAM, "in_background": BACKGROUND_PARAM}, available=_enabled("comsol"))
def comsol(ctx, task: str, in_background: bool = False) -> str:
    return run_app_task(ctx, "comsol", task, in_background)


@tool("Do work in Ansys Mechanical APDL: structural, thermal and modal analyses with beams, "
      "trusses, pipes, 1D heat conduction, 2D and 3D solids; loads, supports, meshing, solving "
      "and results (displacement, stress, temperature, frequencies).",
      {"task": TASK_PARAM, "in_background": BACKGROUND_PARAM}, available=_enabled("ansys"))
def ansys(ctx, task: str, in_background: bool = False) -> str:
    return run_app_task(ctx, "ansys", task, in_background)


@tool("Work in the user's Canva account (online): find designs; change text, font size, colour, "
      "bold/italic, alignment, backgrounds and element colours; move, resize, replace images; add "
      "text, shapes or pages; resize, copy, generate and export designs. Asks before saving.",
      {"task": TASK_PARAM}, available=_enabled("canva"))
def canva(ctx, task: str) -> str:
    return run_app_task(ctx, "canva", task)


@tool("Get step-by-step instructions to teach the user how to do something by hand in an "
      "application (which menus and buttons to click). Walk them through it one or two steps at a time.",
      {"app": {"type": "string", "enum": available_guides(), "description": "Which application"},
       "question": {"type": "string", "description": "What the user wants to learn to do"}})
def how_to(ctx, app: str, question: str) -> str:
    steps = teaching_guide(app, question)
    return steps or f"I don't have written steps for that in {app}; explain from your own knowledge."


@tool("Read a document (PDF, PowerPoint .pptx, Word .docx, text, Markdown, HTML) and return its "
      "text, e.g. to summarise it, answer questions about it or quiz the user on it.",
      {"path": {"type": "string", "description": "Full path to the file (use search_files first if unsure)"}})
def read_document(ctx, path: str) -> str:
    from ..documents import extract

    doc = extract(path)
    text = doc.text
    limit = 60_000 if getattr(ctx.llm, "append_only", False) else 12_000
    note = ""
    if len(text) > limit:
        note = f"\n\n(Only the first {limit} of {len(text)} characters are shown.)"
        text = text[:limit]
    return f"{doc.path.name}: {doc.words} words.\n\n{text}{note}"


@tool("Build an interactive website (HTML, CSS, JavaScript) and open it in the browser. It can "
      "be made from documents (PDF, PowerPoint, Word...) whose text and images it uses, or from a "
      "description alone.",
      {"request": {"type": "string", "description": "What the site should be and do: purpose, style, "
                   "sections, interactive features (quiz, search, charts...), audience"},
       "sources": {"type": "string", "description": "Full paths of source files or folders, "
                   "separated by semicolons (optional)"},
       "name": {"type": "string", "description": "Short project name, e.g. 'thermo-notes'"}})
def build_website(ctx, request: str, name: str, sources: str = "") -> str:
    from ..skills.web import build_site

    ctx.say("Building the website. This takes a minute.")
    return build_site(ctx, request, sources, name)


@tool("Change an existing website or code project Jarvis made (new section, colours, fix a bug, "
      "add a feature). Keeps a backup of the old version.",
      {"request": {"type": "string", "description": "The change to make, in detail"},
       "name": {"type": "string", "description": "The project name (empty = the most recent)"},
       "kind": {"type": "string", "enum": ["websites", "code"], "description": "Website or program"}})
def edit_project(ctx, request: str, name: str = "", kind: str = "websites") -> str:
    from ..skills.web import edit_project as edit, find_project

    folder = find_project(ctx, name, kind)
    ctx.say("Updating it now.")
    return edit(ctx, folder, request, site=kind == "websites")


@tool("Write a program or script in any language (Python, JavaScript, C, C++, Java, MATLAB...) "
      "and save it as a project. For Python it can also run it and fix errors.",
      {"request": {"type": "string", "description": "What the program must do, inputs, outputs, details"},
       "language": {"type": "string", "description": "Programming language"},
       "name": {"type": "string", "description": "Short project name"},
       "run": {"type": "boolean", "description": "Run it after writing (Python only)"}})
def write_program(ctx, request: str, language: str, name: str, run: bool = False) -> str:
    from ..skills.web import write_program as write

    ctx.say("Writing the code.")
    return write(ctx, request, language, name, run)
