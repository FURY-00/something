"""Ansys Mechanical APDL through PyMAPDL (Ansys must be installed and licensed).

PyMAPDL (https://mapdl.docs.pyansys.com) is Ansys's official Python API. It
launches the MAPDL solver in the background, and every APDL command becomes a
Python method: ``/PREP7`` is ``mapdl.prep7()``, ``ET,1,BEAM188`` is
``mapdl.et(1, "BEAM188")``. It works with the Ansys Student edition too.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import traceback
from pathlib import Path

from . import RunResult, Skill


class AnsysHelpers:
    def __init__(self, skill: "AnsysSkill") -> None:
        self._skill = skill

    @property
    def mapdl(self):
        return self._skill.session()

    def new(self, title: str = "Jarvis model") -> None:
        """Start from an empty database in /PREP7 with SI units."""
        m = self.mapdl
        m.finish()
        m.clear()
        m.title(title)
        m.units("SI")
        m.prep7()
        print(f"New MAPDL model: {title}")

    def solve(self, analysis: str = "STATIC", **settings) -> str:
        """Solve: STATIC (also steady thermal), MODAL (modes=6), TRANS, HARMIC."""
        m = self.mapdl
        m.finish()
        m.run("/SOLU")
        m.antype(analysis)
        if analysis.upper() == "MODAL":
            m.modopt("LANB", settings.get("modes", 6))
            m.mxpand(settings.get("modes", 6))
        out = m.solve()
        m.finish()
        print(f"{analysis} solution finished")
        return out

    def buckling(self, modes: int = 3) -> list[float]:
        """Eigenvalue buckling: load factors (critical load = factor x applied load)."""
        m = self.mapdl
        m.finish()
        m.run("/SOLU")
        m.antype("STATIC")
        m.pstres("ON")
        m.solve()
        m.finish()
        m.run("/SOLU")
        m.antype("BUCKLE")
        m.bucopt("LANB", modes)
        m.mxpand(modes)
        m.solve()
        m.finish()
        m.post1()
        factors = []
        for i in range(1, modes + 1):
            try:
                factors.append(float(m.get_value("MODE", i, "FREQ")))
            except Exception:  # noqa: BLE001
                break
        print("Buckling load factors: " + ", ".join(f"{f:.4g}" for f in factors))
        return factors

    def transient(self, end_time: float, step: float, initial_temperature: float | None = None) -> str:
        """Transient (thermal or structural) solution from 0 to end_time in steps of `step` s."""
        m = self.mapdl
        m.finish()
        m.run("/SOLU")
        m.antype("TRANS")
        if initial_temperature is not None:
            m.ic("ALL", "TEMP", initial_temperature)
        m.time(end_time)
        m.deltim(step, step / 10, step * 10)
        m.kbc(1)
        m.outres("ALL", "ALL")
        out = m.solve()
        m.finish()
        print(f"Transient solution to t = {end_time} s finished")
        return out

    def harmonic(self, f_min: float, f_max: float, steps: int = 50, damping_ratio: float = 0.02) -> str:
        """Harmonic response between f_min and f_max Hz (loads are sinusoidal amplitudes)."""
        m = self.mapdl
        m.finish()
        m.run("/SOLU")
        m.antype("HARMIC")
        m.harfrq(f_min, f_max)
        m.nsubst(steps)
        m.kbc(1)
        m.dmprat(damping_ratio)
        out = m.solve()
        m.finish()
        print(f"Harmonic response {f_min}-{f_max} Hz finished ({steps} steps)")
        return out

    def reactions(self) -> dict:
        """Total reaction forces (N) at the supports."""
        m = self._post()
        m.allsel()
        m.fsum()
        forces = {c: float(m.get_value("FSUM", 0, "ITEM", c)) for c in ("FX", "FY", "FZ")}
        print("Reactions: " + ", ".join(f"{k} = {v:.4g} N" for k, v in forces.items()))
        return forces

    def truss(self, nodes, members, area: float, E: float = 200e9, nu: float = 0.3,
              supports=None, loads=None) -> list[float]:
        """Build and solve a pin-jointed truss with LINK180 elements.

        nodes: [(x, y) or (x, y, z), ...] in m; members: [(i, j), ...] 0-based node indices;
        supports: {node: "xy" | "y" | "xyz" ...} fixed directions; loads: {node: (fx, fy[, fz])} N.
        Returns the axial force in each member (tension positive).
        """
        m = self.mapdl
        self.new("Truss")
        m.et(1, "LINK180")
        m.mp("EX", 1, E)
        m.mp("PRXY", 1, nu)
        m.sectype(1, "LINK")
        m.secdata(area)
        planar = all(len(n) == 2 or n[2] == 0 for n in nodes)
        for i, n in enumerate(nodes, 1):
            m.n(i, *(list(n) + [0] * (3 - len(n))))
        for i, j in members:
            m.e(i + 1, j + 1)
        for node, dirs in (supports or {}).items():
            for d in dirs.lower():
                m.d(node + 1, "U" + d.upper(), 0)
        if planar:
            m.d("ALL", "UZ", 0)  # keep a 2D truss in its plane
        for node, force in (loads or {}).items():
            for comp, value in zip(("FX", "FY", "FZ"), force):
                if value:
                    m.f(node + 1, comp, value)
        self.solve("STATIC")
        m.post1()
        m.set("LAST")
        m.etable("AXF", "SMISC", 1)
        forces = []
        for e in range(1, len(members) + 1):
            forces.append(float(m.get_value("ELEM", e, "ETAB", "AXF")))
        for (i, j), f in zip(members, forces):
            print(f"Member {i}-{j}: {f / 1e3:+.3f} kN ({'tension' if f >= 0 else 'compression'})")
        return forces

    def _post(self):
        m = self.mapdl
        m.post1()
        m.set("LAST")
        return m

    def max_displacement(self, component: str = "NORM") -> float:
        values = self._post().post_processing.nodal_displacement(component)
        value = float(abs(values).max())
        print(f"Max displacement ({component}): {value:.6g} m")
        return value

    def max_stress(self) -> float:
        values = self._post().post_processing.nodal_eqv_stress()
        value = float(values.max())
        print(f"Max von Mises stress: {value / 1e6:.4g} MPa")
        return value

    def temperatures(self):
        values = self._post().post_processing.nodal_temperature()
        print(f"Temperature range: {values.min():.4g} to {values.max():.4g}")
        return values

    def frequencies(self, modes: int = 6) -> list[float]:
        m = self.mapdl
        m.post1()
        freqs = []
        for i in range(1, modes + 1):
            try:
                freqs.append(float(m.get_value("MODE", i, "FREQ")))
            except Exception:  # noqa: BLE001 - fewer modes were extracted
                break
        print("Natural frequencies (Hz): " + ", ".join(f"{f:.4g}" for f in freqs))
        return freqs

    def plot(self, result: str = "displacement", path: str | None = None) -> str:
        """Save a contour plot image: displacement, stress or temperature."""
        m = self._post()
        target = Path(path).expanduser() if path else Path(self._skill.workdir) / f"{result}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        pp = m.post_processing
        kwargs = {"savefig": str(target), "off_screen": True}
        if result.startswith("disp"):
            pp.plot_nodal_displacement("NORM", **kwargs)
        elif result.startswith("stress"):
            pp.plot_nodal_eqv_stress(**kwargs)
        else:
            pp.plot_nodal_temperature(**kwargs)
        print(f"Plot saved to {target}")
        return str(target)

    def save(self, name: str = "jarvis_model") -> str:
        path = Path(self._skill.workdir) / f"{name}.db"
        self.mapdl.save(str(path))
        print(f"Saved database {path}")
        return str(path)

    def summary(self) -> str:
        m = self.mapdl
        try:
            routine = m.parameters.routine
        except Exception:  # noqa: BLE001
            routine = "?"
        return (f"MAPDL session in {self._skill.workdir}; routine {routine}; "
                f"{m.mesh.n_node} nodes, {m.mesh.n_elem} elements")


def find_mapdl(configured: str = "") -> str | None:
    if configured:
        return configured if Path(configured).exists() else None
    try:
        from ansys.tools.path import find_mapdl as _find

        path, _version = _find()
        if path:
            return path
    except Exception:  # noqa: BLE001 - older ansys-tools-path, or nothing installed
        pass
    return None


class AnsysSkill(Skill):
    name = "ansys"
    title = "Ansys Mechanical APDL"
    where = ("in Python with a live MAPDL session (PyMAPDL). Available: `mapdl` (every APDL command "
             "as a method), `an` (helpers), `np` (numpy)")
    units = "SI (m, N, Pa, kg, s, degC or K)"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._mapdl = None
        self.workdir = Path(config.paths.projects).expanduser() / "ansys"
        self.helpers = AnsysHelpers(self)
        self._namespace: dict = {"__name__": "__jarvis__"}

    def detect(self) -> str | None:
        try:
            found = importlib.util.find_spec("ansys.mapdl.core") is not None
        except ModuleNotFoundError:  # the "ansys" namespace package isn't there at all
            found = False
        if not found:
            return "PyMAPDL is missing (pip install ansys-mapdl-core)"
        if not (find_mapdl(self.settings.get("executable", "")) or any(k.startswith("AWP_ROOT") for k in os.environ)):
            return "Ansys MAPDL not found (set skills.ansys.executable in config.yaml)"
        return None

    def session(self):
        if self._mapdl is None:
            from ansys.mapdl.core import launch_mapdl

            self.workdir.mkdir(parents=True, exist_ok=True)
            print("Starting Ansys MAPDL (this takes a little while)...")
            self._mapdl = launch_mapdl(
                exec_file=find_mapdl(self.settings.get("executable", "")),
                run_location=str(self.workdir),
                override=True,
                loglevel="ERROR",
            )
        return self._mapdl

    def run(self, code: str) -> RunResult:
        buf = io.StringIO()
        try:
            import numpy as np

            with contextlib.redirect_stdout(buf):
                self._namespace.update(mapdl=self.session(), an=self.helpers, np=np)
                exec(compile(code, "<jarvis>", "exec"), self._namespace)
            return RunResult(True, buf.getvalue())
        except Exception:
            return RunResult(False, buf.getvalue(), traceback.format_exc(limit=6))

    def state(self) -> str:
        if self._mapdl is None:
            return "No MAPDL session yet (it starts on the first script). Begin new work with an.new()."
        try:
            return self.helpers.summary()
        except Exception as exc:  # noqa: BLE001
            return f"(couldn't read MAPDL: {exc})"

    def close(self) -> None:
        if self._mapdl is not None:
            try:
                self._mapdl.exit()
            except Exception:  # noqa: BLE001
                pass
