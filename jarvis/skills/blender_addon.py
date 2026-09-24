"""Jarvis Bridge: lets the Jarvis voice assistant work in your open Blender window.

Install: Blender > Edit > Preferences > Add-ons > (menu) Install from Disk...
pick this file, and tick "Jarvis Bridge". It listens on 127.0.0.1 only, so
nothing outside your computer can reach it.
"""

import contextlib
import io
import json
import queue
import socket
import threading
import traceback

import bpy

bl_info = {
    "name": "Jarvis Bridge",
    "author": "Jarvis",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Runs in the background",
    "description": "Lets the Jarvis voice assistant build scenes in this Blender window",
    "category": "System",
}

HOST, PORT = "127.0.0.1", 9876

_requests: "queue.Queue[tuple[dict, queue.Queue]]" = queue.Queue()
_namespace: dict = {"__name__": "__jarvis__"}
_loaded_setup: list[str] = []  # the helper code that's already been run
_server_thread = None
_stop = threading.Event()


def execute(request: dict) -> dict:
    """Run one request. Must be called on Blender's main thread."""
    setup = request.get("setup", "")
    buf = io.StringIO()
    try:
        if setup and (not _loaded_setup or _loaded_setup[0] != setup):
            exec(compile(setup, "blender_helpers.py", "exec"), _namespace)
            _loaded_setup[:] = [setup]
        with contextlib.redirect_stdout(buf):
            exec(compile(request.get("code", ""), "<jarvis>", "exec"), _namespace)
        return {"ok": True, "output": buf.getvalue()}
    except Exception:
        return {"ok": False, "output": buf.getvalue(), "error": traceback.format_exc(limit=6)}


def pump() -> float:
    """Timer callback: run queued requests on the main thread."""
    while True:
        try:
            request, reply = _requests.get_nowait()
        except queue.Empty:
            break
        reply.put(execute(request))
    return 0.1


def handle(conn: socket.socket) -> None:
    with conn:
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                return
            data += chunk
        try:
            request = json.loads(data.decode())
        except ValueError as exc:
            conn.sendall(json.dumps({"ok": False, "error": f"bad request: {exc}"}).encode() + b"\n")
            return
        reply: queue.Queue = queue.Queue()
        _requests.put((request, reply))
        try:
            result = reply.get(timeout=900)
        except queue.Empty:
            result = {"ok": False, "error": "Blender was busy for too long."}
        conn.sendall(json.dumps(result).encode() + b"\n")


def serve(port: int = PORT) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, port))
    srv.listen(4)
    srv.settimeout(0.5)
    while not _stop.is_set():
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        threading.Thread(target=handle, args=(conn,), daemon=True).start()
    srv.close()


def register() -> None:
    global _server_thread
    _stop.clear()
    _server_thread = threading.Thread(target=serve, daemon=True)
    _server_thread.start()
    if not bpy.app.timers.is_registered(pump):
        bpy.app.timers.register(pump, persistent=True)
    print(f"Jarvis Bridge listening on {HOST}:{PORT}")


def unregister() -> None:
    _stop.set()
    if bpy.app.timers.is_registered(pump):
        bpy.app.timers.unregister(pump)
