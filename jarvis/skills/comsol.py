"""COMSOL Multiphysics through the ``mph`` library (COMSOL must be installed).

``mph`` (https://mph.readthedocs.io) starts a local COMSOL session and gives
Python the full COMSOL Java API: the same calls the COMSOL GUI records in
"Record Method" / "Save as Java". Jarvis keeps one session open, so models
persist between requests.
"""

from __future__ import annotations

import contextlib
import io
import traceback
from pathlib import Path

from . import RunResult, Skill


class ComsolHelpers:
    """Small conveniences for common chores. `model` is an mph.Model, `jm` its Java model."""

    def __init__(self, skill: "ComsolSkill") -> None:
        self._skill = skill

    @property
    def client(self):
        return self._skill.client()

    def new_model(self, name: str = "Jarvis model"):
        model = self.client.create(name)
        self._skill.current = model
        print(f"Created model {name!r}")
        return model

    def open(self, path: str):
        model = self.client.load(path)
        self._skill.current = model
        print(f"Opened {path}")
        return model

    @property
    def model(self):
        if self._skill.current is None:
            raise RuntimeError("No model yet. Call cs.new_model() or cs.open(path) first.")
        return self._skill.current

    @property
    def jm(self):
        return self.model.java

    def props(self, node) -> dict:
        """All property names and values of a Java model node, to discover the right names."""
        out = {}
        for name in node.properties():
            name = str(name)
            try:
                out[name] = str(node.getString(name))
            except Exception:  # noqa: BLE001 - array-valued properties
                try:
                    out[name] = [str(v) for v in node.getStringArray(name)]
                except Exception:  # noqa: BLE001
                    out[name] = "?"
        return out

    def tags(self, node_list) -> list[str]:
        return [str(t) for t in node_list.tags()]

    def solve(self, study: str | None = None) -> None:
        print(f"Solving {study or 'all studies'}...")
        self.model.solve(study)
        print("Solved.")

    def evaluate(self, expression: str, unit: str | None = None, dataset: str | None = None):
        value = self.model.evaluate(expression, unit=unit, dataset=dataset)
        print(f"{expression} = {value}{' ' + unit if unit else ''}")
        return value

    def save(self, path: str | None = None) -> str:
        default = Path(self._skill.projects) / "comsol" / f"{self.model.name()}.mph"
        target = Path(path).expanduser() if path else default
        target.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(str(target))
        print(f"Saved {target}")
        return str(target)

    def export_image(self, plot_group: str, path: str, width: int = 1200, height: int = 800) -> str:
        """Save a plot group (e.g. 'pg1') as a PNG image."""
        jm = self.jm
        tag = "jarvis_img"
        exports = jm.result().export()
        if tag in [str(t) for t in exports.tags()]:
            exports.remove(tag)
        img = exports.create(tag, "Image")
        img.set("sourceobject", plot_group)
        img.set("pngfilename", str(Path(path).expanduser()))
        img.set("size", "manualweb")
        img.set("unit", "px")
        img.set("width", str(width))
        img.set("height", str(height))
        img.run()
        print(f"Plot saved to {path}")
        return path

    def summary(self) -> str:
        m = self.model
        jm = m.java
        lines = [f"Model: {m.name()}  file: {m.file() or '(unsaved)'}"]
        try:
            params = m.parameters()
            if params:
                lines.append("Parameters: " + ", ".join(f"{k}={v}" for k, v in params.items()))
        except Exception:  # noqa: BLE001
            pass
        for comp in self.tags(jm.component()):
            c = jm.component(comp)
            geoms = self.tags(c.geom())
            dims = [f"{g} ({c.geom(g).getSDim()}D)" for g in geoms]
            lines.append(f"Component {comp}: geometry {dims}")
            for g in geoms:
                lines.append(f"  geometry {g} features: {self.tags(c.geom(g).feature())}")
            for ph in self.tags(c.physics()):
                p = c.physics(ph)
                lines.append(f"  physics {ph} ({p.getType()}): features {self.tags(p.feature())}")
            lines.append(f"  materials: {self.tags(c.material())}, meshes: {self.tags(c.mesh())}")
        lines.append(f"Studies: {self.tags(jm.study())}; plots: {self.tags(jm.result())}")
        return "\n".join(lines)


class ComsolSkill(Skill):
    name = "comsol"
    title = "COMSOL Multiphysics"
    where = ("in Python connected to a local COMSOL session through the mph library. Available: "
             "`cs` (helpers), `model` (the current mph.Model, or None), `jm` (its Java API model, "
             "i.e. model.java), `client` (mph.Client), `mph`, `np` (numpy)")
    units = "SI units; COMSOL expressions may carry units in brackets, e.g. '0.5[m]', '20[degC]'"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._client = None
        self.current = None
        self.projects = Path(config.paths.projects).expanduser()
        self.helpers = ComsolHelpers(self)
        self._namespace: dict = {"__name__": "__jarvis__"}

    def detect(self) -> str | None:
        try:
            import mph
        except ImportError:
            return "the mph package is missing (pip install mph)"
        try:
            mph.discovery.backend(self.settings.get("version") or None)
        except Exception as exc:  # noqa: BLE001 - no COMSOL installation found
            return f"COMSOL not found ({exc})"
        return None

    def client(self):
        if self._client is None:
            import mph

            cores = int(self.settings.get("cores") or 0) or None
            version = self.settings.get("version") or None
            print("Starting a COMSOL session (the first time takes a minute)...")
            self._client = mph.start(cores=cores, version=version)
        return self._client

    def run(self, code: str) -> RunResult:
        buf = io.StringIO()
        try:
            import mph
            import numpy as np

            with contextlib.redirect_stdout(buf):
                client = self.client()
                ns = self._namespace
                before = self.current
                ns.update(cs=self.helpers, client=client, mph=mph, np=np, model=before,
                          jm=before.java if before is not None else None)
                exec(compile(code, "<jarvis>", "exec"), ns)
                # cs.new_model()/cs.open() update self.current themselves; a script that
                # loaded a model some other way and assigned it to `model` counts too.
                if self.current is before and ns.get("model") not in (None, before):
                    self.current = ns["model"]
            return RunResult(True, buf.getvalue())
        except Exception:
            return RunResult(False, buf.getvalue(), _java_aware_traceback())

    def state(self) -> str:
        if self._client is None or self.current is None:
            return "No COMSOL model open yet (start with cs.new_model(name) or cs.open(path))."
        try:
            return self.helpers.summary()
        except Exception as exc:  # noqa: BLE001
            return f"(couldn't read the model: {exc})"

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.clear()
            except Exception:  # noqa: BLE001
                pass


def _java_aware_traceback() -> str:
    """COMSOL errors come as Java exceptions; keep their messages, which name the problem."""
    text = traceback.format_exc(limit=6)
    lines = [ln for ln in text.splitlines() if "jpype" not in ln.lower() or "Exception" in ln]
    return "\n".join(lines[-30:])
