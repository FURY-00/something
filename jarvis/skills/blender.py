"""Blender: 3D modelling, animation and rendering through Blender's Python API.

Two ways to connect:

* **Live**: install ``jarvis/skills/blender_addon.py`` in Blender (Edit >
  Preferences > Add-ons > Install from Disk). Jarvis then builds the scene in
  the Blender window you have open, so you can watch and take over.
* **Background**: with no Blender window open, Jarvis runs Blender invisibly
  and keeps the scene in ``Documents/Jarvis/Projects/blender/scene.blend``,
  so each request carries on from the last one.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from . import RunResult, Skill

HELPERS = Path(__file__).with_name("blender_helpers.py")
RESULT_MARK = "JARVIS_RESULT "

# Runs inside Blender in background mode: load the scene, run the task, save.
WRAPPER = """\
import contextlib, io, json, os, sys, traceback
import bpy
_scene = {scene!r}
if os.path.exists(_scene) and os.path.abspath(bpy.data.filepath or "") != _scene:
    bpy.ops.wm.open_mainfile(filepath=_scene)
_ns = {{"__name__": "__jarvis__"}}
exec(compile(open({helpers!r}, encoding="utf-8").read(), "blender_helpers.py", "exec"), _ns)
_buf = io.StringIO()
try:
    with contextlib.redirect_stdout(_buf):
        exec(compile(open({code!r}, encoding="utf-8").read(), "<jarvis>", "exec"), _ns)
    os.makedirs(os.path.dirname(_scene), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=_scene)
    _res = {{"ok": True}}
except Exception:
    _res = {{"ok": False, "error": traceback.format_exc(limit=6)}}
_res["output"] = _buf.getvalue()
sys.stdout.write("\\n" + {mark!r} + json.dumps(_res) + "\\n")
sys.stdout.flush()
"""


def find_blender(configured: str = "") -> str | None:
    if configured:
        return configured if Path(configured).exists() or shutil.which(configured) else None
    found = shutil.which("blender")
    if found:
        return found
    if sys.platform.startswith("win"):
        pattern = r"C:\Program Files\Blender Foundation\Blender*\blender.exe"
        matches = sorted(glob.glob(pattern))
        return matches[-1] if matches else None
    if sys.platform == "darwin":
        path = "/Applications/Blender.app/Contents/MacOS/Blender"
        return path if Path(path).exists() else None
    for path in ("/snap/bin/blender", "/usr/local/bin/blender", "/opt/blender/blender"):
        if Path(path).exists():
            return path
    return None


def send_to_addon(code: str, setup: str, port: int, timeout: float = 600) -> dict:
    """Send a script to the Jarvis add-on running inside Blender."""
    payload = json.dumps({"setup": setup, "code": code}).encode() + b"\n"
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.settimeout(timeout)
        sock.sendall(payload)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b"\n"):
                break
    return json.loads(b"".join(chunks).decode())


class BlenderSkill(Skill):
    name = "blender"
    title = "Blender"
    units = "metres and degrees (Blender's defaults); frame numbers for time"

    def __init__(self, config) -> None:
        super().__init__(config)
        self.port = int(self.settings.get("port", 9876))
        self.executable = find_blender(self.settings.get("executable", ""))
        self.scene = Path(config.paths.projects).expanduser() / "blender" / "scene.blend"
        self.where = "inside Blender with bpy imported and Jarvis's helper functions pre-loaded"

    def live(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                return True
        except OSError:
            return False

    def detect(self) -> str | None:
        if self.executable or self.live():
            return None
        return "Blender not found (set skills.blender.executable in config.yaml)"

    # -- running scripts -----------------------------------------------------
    def run(self, code: str) -> RunResult:
        helpers = HELPERS.read_text(encoding="utf-8")
        if self.live():
            try:
                reply = send_to_addon(code, helpers, self.port)
            except (OSError, ValueError) as exc:
                return RunResult(False, "", f"Lost contact with the Blender add-on: {exc}")
            return RunResult(bool(reply.get("ok")), reply.get("output", ""), reply.get("error", ""))
        if not self.executable:
            return RunResult(False, "", "Blender isn't installed or couldn't be found.")
        return self._run_background(code)

    def _run_background(self, code: str, timeout: float = 900) -> RunResult:
        with tempfile.TemporaryDirectory() as tmp:
            code_file = Path(tmp) / "task.py"
            code_file.write_text(code, encoding="utf-8")
            wrapper = Path(tmp) / "wrapper.py"
            wrapper.write_text(WRAPPER.format(scene=str(self.scene), helpers=str(HELPERS),
                                              code=str(code_file), mark=RESULT_MARK), encoding="utf-8")
            if "python" in Path(self.executable).name.lower():
                cmd = [self.executable, str(wrapper)]  # a Python with the bpy module installed
            else:
                cmd = [self.executable, "-b", "--factory-startup", "--python", str(wrapper)]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                      encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return RunResult(False, "", f"Blender took longer than {timeout:.0f} seconds.")
        for line in reversed(proc.stdout.splitlines()):
            if line.startswith(RESULT_MARK):
                data = json.loads(line[len(RESULT_MARK):])
                output = data.get("output", "")
                if data.get("ok"):
                    output += f"\n(Scene saved to {self.scene})"
                return RunResult(bool(data.get("ok")), output, data.get("error", ""))
        tail = (proc.stderr or proc.stdout)[-2000:]
        return RunResult(False, "", f"Blender exited without finishing (code {proc.returncode}).\n{tail}")

    def state(self) -> str:
        if not self.live() and not self.scene.exists():
            return "A new default scene (a cube, a camera and a light). Nothing made yet."
        result = self.run("print(scene_summary())")
        mode = "live Blender window" if self.live() else "background Blender"
        return f"[{mode}]\n" + (result.output.strip() if result.ok else f"(unreadable: {result.error})")

    def show(self) -> str:
        """Open the background scene in the Blender window."""
        if self.live():
            return "It's already open in your Blender window."
        if not (self.executable and self.scene.exists()):
            return "There's no scene to show yet."
        if "python" in Path(self.executable).name.lower():
            return f"The scene is saved at {self.scene}."
        kwargs = {"start_new_session": True} if os.name != "nt" else {}
        subprocess.Popen([self.executable, str(self.scene)], **kwargs)
        return f"Opened {self.scene} in Blender."
