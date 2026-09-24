"""Skills: professional applications Jarvis can work in.

Each skill connects Jarvis to one application (Blender, SolidWorks, COMSOL,
Ansys, Canva). Instead of clicking around the screen, Jarvis drives the
application through its scripting API:

  1. The task ("model a 40 x 20 x 10 mm block with a 6 mm hole") goes to a
     code-writing model, together with a guide for that application
     (``jarvis/skills/guides/<app>.md``) and the application's current state.
  2. The model writes a script, which runs inside the application.
  3. If it fails, the error goes back to the model to fix. Repeat.

Skills keep their session open, so the next request builds on the last one,
just like working with a person sitting at the application.
"""

from __future__ import annotations

import importlib
import logging
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)

SKILL_CLASSES = {
    "blender": "jarvis.skills.blender:BlenderSkill",
    "solidworks": "jarvis.skills.solidworks:SolidWorksSkill",
    "comsol": "jarvis.skills.comsol:ComsolSkill",
    "ansys": "jarvis.skills.ansys:AnsysSkill",
    "canva": "jarvis.skills.canva:CanvaSkill",
}


@dataclass
class RunResult:
    ok: bool
    output: str = ""
    error: str = ""


class Skill:
    """Base class. Subclasses fill in the class attributes and ``run``."""

    name = ""  # config key and guide file name, e.g. "blender"
    title = ""  # human name, e.g. "Blender"
    where = ""  # where scripts run, for the code model's instructions
    units = "SI units unless the user says otherwise"

    def __init__(self, config) -> None:
        self.config = config
        self.settings = config.skills.get(self.name, {})
        self.lock = threading.Lock()  # one job at a time per application
        self._enabled: bool | None = None

    # -- detection ---------------------------------------------------------
    def detect(self) -> str | None:
        """Return None if the application looks usable, else the reason why not."""
        return None

    def enabled(self) -> bool:
        if self._enabled is None:
            choice = self.settings.get("enabled", "auto")
            if choice in (False, "false", "off"):
                self._enabled = False
            elif choice in (True, "true", "on"):
                self._enabled = True
            else:
                reason = self.detect()
                if reason:
                    log.info("%s skill off: %s", self.title, reason)
                self._enabled = reason is None
        return self._enabled

    # -- execution ---------------------------------------------------------
    def run(self, code: str) -> RunResult:
        raise NotImplementedError

    def state(self) -> str:
        """A short description of what's currently open, for the code model."""
        return "(unknown)"

    def close(self) -> None:
        """Release the application session (called on exit)."""


_instances: dict[str, Skill] = {}
_instances_lock = threading.Lock()


def get_skill(config, name: str) -> Skill:
    with _instances_lock:
        if name not in _instances:
            module_name, cls_name = SKILL_CLASSES[name].split(":")
            cls = getattr(importlib.import_module(module_name), cls_name)
            _instances[name] = cls(config)
        return _instances[name]


def close_all() -> None:
    for skill in list(_instances.values()):
        try:
            skill.close()
        except Exception as exc:  # noqa: BLE001 - shutting down anyway
            log.debug("closing %s failed: %s", skill.name, exc)
