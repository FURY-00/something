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
        # Short summaries of past conversations: [{"date": "...", "summary": "..."}]
        self.episodes: list[dict] = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.facts = data.get("facts", [])
                self.episodes = data.get("episodes", [])
            except (OSError, ValueError):
                pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"facts": self.facts, "episodes": self.episodes}, indent=2),
                       encoding="utf-8")
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

    def add_episode(self, date: str, summary: str, keep: int = 30) -> None:
        summary = summary.strip()
        if not summary:
            return
        with self._lock:
            self.episodes.append({"date": date, "summary": summary})
            self.episodes = self.episodes[-keep:]
            self._save()

    def as_prompt(self) -> str:
        return "\n".join(f"- {f}" for f in self.facts) or "- (nothing yet)"

    def episodes_prompt(self, count: int = 6) -> str:
        recent = self.episodes[-count:]
        return "\n".join(f"- {e['date']}: {e['summary']}" for e in recent) or "- (this is your first chat)"
