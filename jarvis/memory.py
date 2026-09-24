"""Long-term memory: facts about the user that survive restarts."""

from __future__ import annotations

import json
import threading
from pathlib import Path


class Memory:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self.facts: list[str] = []
        if self.path.exists():
            try:
                self.facts = json.loads(self.path.read_text(encoding="utf-8")).get("facts", [])
            except (OSError, ValueError):
                self.facts = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"facts": self.facts}, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, fact: str) -> None:
        fact = fact.strip()
        with self._lock:
            if fact and fact.lower() not in (f.lower() for f in self.facts):
                self.facts.append(fact)
                self._save()

    def forget(self, text: str) -> list[str]:
        needle = text.strip().lower()
        with self._lock:
            removed = [f for f in self.facts if needle in f.lower()]
            if removed:
                self.facts = [f for f in self.facts if f not in removed]
                self._save()
        return removed

    def as_prompt(self) -> str:
        return "\n".join(f"- {f}" for f in self.facts) or "- (nothing yet)"
