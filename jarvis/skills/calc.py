"""Engineering calculator: solve problems by writing and running Python.

Language models are unreliable at arithmetic. For any real calculation Jarvis
writes a short Python script (numpy, scipy, sympy, matplotlib), runs it in a
separate process, and reads back the printed answer, so the numbers are
computed rather than guessed. Plots are saved and opened.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from . import RunResult, Skill

PRELUDE = '''\
import math, sys
import numpy as np
try:
    import sympy as sp
except ImportError:
    sp = None
try:
    import scipy
    from scipy import optimize, integrate, linalg
except ImportError:
    scipy = optimize = integrate = linalg = None
OUT = {out!r}

def save_plot(name="plot"):
    """Save the current matplotlib figure and open it for the user."""
    import os
    import matplotlib.pyplot as plt
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name if name.endswith(".png") else name + ".png")
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close("all")
    print("Plot saved:", path)
    print("JARVIS_OPEN " + path)
    return path
'''


class CalcSkill(Skill):
    name = "calc"
    title = "the engineering calculator"
    where = ("as a standalone Python 3 script. Pre-loaded: math, np (numpy), sp (sympy), "
             "optimize/integrate/linalg (scipy), save_plot(name) for matplotlib figures")
    units = "SI units internally; convert inputs to SI first and state units in every printed result"

    def __init__(self, config) -> None:
        super().__init__(config)
        self.out = Path(config.paths.projects).expanduser() / "calculations"

    def detect(self) -> str | None:
        if importlib.util.find_spec("numpy") is None:
            return "numpy is missing"
        return None

    def run(self, code: str, timeout: float = 120) -> RunResult:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "calc.py"
            script.write_text("import matplotlib\nmatplotlib.use('Agg')\n" + PRELUDE.format(out=str(self.out))
                              + "\n" + code + "\n", encoding="utf-8")
            try:
                proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                                      timeout=timeout, cwd=tmp, stdin=subprocess.DEVNULL,
                                      encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return RunResult(False, "", f"The calculation took longer than {timeout:.0f} s.")
        if proc.returncode != 0:
            return RunResult(False, proc.stdout, proc.stderr[-3000:] or f"exit code {proc.returncode}")
        return RunResult(True, proc.stdout)

    def state(self) -> str:
        return "Each calculation runs fresh; nothing carries over between scripts."
