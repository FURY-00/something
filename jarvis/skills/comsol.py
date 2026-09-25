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

    # -- shortcuts for the most common model-building steps ------------------
    MATERIAL_KEYS = {
        "density": ("def", "density"), "rho": ("def", "density"),
        "mu": ("def", "dynamicviscosity"), "viscosity": ("def", "dynamicviscosity"),
        "k": ("def", "thermalconductivity"), "cp": ("def", "heatcapacity"),
        "alpha": ("def", "thermalexpansioncoefficient"), "sigma": ("def", "electricconductivity"),
        "E": ("Enu", "E"), "nu": ("Enu", "nu"),
    }

    def component(self, tag: str = "comp1"):
        jm = self.jm
        if tag in self.tags(jm.component()):
            return jm.component(tag)
        return jm.component().create(tag, True)

    def material(self, name: str, comp: str = "comp1", tag: str | None = None, selection=None, **props):
        """Add a material with properties given as numbers/expressions with units, e.g.
        cs.material("Steel", density="7850[kg/m^3]", E="200e9[Pa]", nu=0.3, k="45[W/(m*K)]").
        Keys: density, mu, k, cp, alpha, sigma, E, nu. selection: domain numbers (default all)."""
        c = self.component(comp)
        tag = tag or f"mat{len(self.tags(c.material())) + 1}"
        mat = c.material().create(tag, "Common")
        mat.label(name)
        if {"E", "nu"} & set(props):
            mat.propertyGroup().create("Enu", "Young's modulus and Poisson's ratio")
        for key, value in props.items():
            group, prop = self.MATERIAL_KEYS[key]
            mat.propertyGroup(group).set(prop, str(value))
        if selection is None:
            mat.selection().all()
        else:
            mat.selection().set(list(selection))
        print(f"Material {name} ({tag}): {props}")
        return mat

    def box(self, name: str, dim: int, comp: str = "comp1", **limits):
        """Named Box selection of entities of dimension `dim` (0 points, 1 edges, 2 faces, 3 domains)
        lying inside xmin/xmax/ymin/ymax/zmin/zmax (numbers in model units). Use a small tolerance."""
        sel = self.component(comp).selection().create(name, "Box")
        sel.set("entitydim", str(dim))
        for key, value in limits.items():
            sel.set(key, str(value))
        sel.set("condition", "inside")
        print(f"Box selection {name!r}: dim {dim}, {limits}")
        return name

    def operator(self, kind: str, tag: str, selection=None, dim: int | None = None, comp: str = "comp1"):
        """Component coupling operator: kind 'Maximum', 'Minimum', 'Average' or 'Integration'.
        selection: a named selection or a list of entity numbers; dim: entity dimension."""
        op = self.component(comp).cpl().create(tag, kind)
        if dim is not None:
            op.selection().geom("geom1", dim)
        if isinstance(selection, str):
            op.selection().named(selection)
        elif selection is not None:
            op.selection().set(list(selection))
        else:
            op.selection().all()
        return tag

    def study(self, kind: str = "Stationary", tag: str = "std1", **settings):
        """Create a study: 'Stationary', 'Transient' (tlist="range(0,1,100)"),
        'Eigenfrequency' (neigs=6), 'Frequency' (plist="range(10,10,1000)")."""
        std = self.jm.study().create(tag)
        step = std.create({"Stationary": "stat", "Transient": "time", "Eigenfrequency": "eig",
                           "Frequency": "freq"}.get(kind, "step1"), kind)
        for key, value in settings.items():
            step.set(key, str(value))
        print(f"Study {tag}: {kind} {settings}")
        return std

    def sweep(self, study: str, parameter: str, values: str) -> None:
        """Parametric sweep, e.g. cs.sweep("std1", "L", "range(0.1,0.1,1)")."""
        p = self.jm.study(study).create("param", "Parametric")
        p.set("pname", [parameter])
        p.set("plistarr", [values])
        print(f"Sweep {parameter} over {values}")

    def plot(self, expr: str, dim: int, tag: str = "pg1", kind: str | None = None, path: str | None = None):
        """Make a plot of `expr` (dim 1: line graph, 2: surface, 3: volume) and optionally save a PNG."""
        pg = self.jm.result().create(tag, dim)
        kind = kind or {1: "LineGraph", 2: "Surface", 3: "Volume"}[dim]
        feat = pg.create(f"{kind.lower()}1", kind)
        feat.set("expr", expr)
        if kind == "LineGraph":
            feat.selection().all()
        pg.run()
        print(f"Plot {tag}: {kind} of {expr}")
        if path:
            self.export_image(tag, path)
        return tag

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
