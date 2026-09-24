"""The knowledge Jarvis has about each application.

Guides are Markdown files in ``jarvis/skills/guides/``. Sections are split by
``## `` headings, and the heading decides how a section is used:

* ``## Recipe: ...`` worked examples, picked by relevance to the task
* ``## GUI: ...``    click-by-click steps for teaching the user by hand
* anything else      API essentials, always given to the code model

Add your own sections (or whole guides) to teach Jarvis new tricks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

GUIDES_DIR = Path(__file__).resolve().parent / "guides"

STOPWORDS = set(
    "the a an and or of to in on for with by at from into is are be it this that as "
    "how do i me my you your make create add use using can please want need jarvis".split()
)


@dataclass
class Section:
    heading: str
    body: str

    @property
    def kind(self) -> str:
        head = self.heading.lower()
        if head.startswith("recipe:"):
            return "recipe"
        if head.startswith("gui:"):
            return "gui"
        return "core"

    def text(self) -> str:
        return f"## {self.heading}\n{self.body.strip()}\n"


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1 and w not in STOPWORDS]


def load_guide(name: str) -> tuple[str, list[Section]]:
    path = GUIDES_DIR / f"{name}.md"
    if not path.exists():
        return "", []
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^## +(.+)$", text, flags=re.M)
    intro = parts[0].strip()
    sections = [Section(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    return intro, sections


def score(section: Section, query: str) -> float:
    q = set(words(query))
    if not q:
        return 0.0
    head = words(section.heading)
    body = words(section.body)
    s = 3.0 * sum(1 for w in head if w in q)
    s += sum(min(body.count(w), 3) for w in q)
    return s / (1 + len(body) / 400)  # don't let long sections win on length alone


def best_sections(sections: list[Section], query: str, kinds: set[str], limit: int) -> list[Section]:
    pool = [s for s in sections if s.kind in kinds]
    ranked = sorted(pool, key=lambda s: score(s, query), reverse=True)
    return [s for s in ranked[:limit] if score(s, query) > 0]


def script_guide(name: str, task: str, recipes: int = 2) -> str:
    """Everything the code model needs to write a script for ``task``."""
    intro, sections = load_guide(name)
    core = [s.text() for s in sections if s.kind == "core"]
    picked = [s.text() for s in best_sections(sections, task, {"recipe"}, recipes)]
    return "\n".join([intro, *core, *picked]).strip()


def teaching_guide(name: str, question: str, limit: int = 2) -> str:
    """Step-by-step sections for walking the user through something by hand."""
    _, sections = load_guide(name)
    picked = best_sections(sections, question, {"gui"}, limit)
    if not picked:
        picked = best_sections(sections, question, {"gui", "recipe"}, limit)
    return "\n".join(s.text() for s in picked)


def available_guides() -> list[str]:
    return sorted(p.stem for p in GUIDES_DIR.glob("*.md"))
