"""Apps, files, power, timers and system information."""

from __future__ import annotations

import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import tool

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# Spoken app name -> what to launch on each OS.
WINDOWS_APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "command prompt": "cmd",
    "cmd": "cmd",
    "terminal": "wt",
    "powershell": "powershell",
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "brave": "brave",
    "word": "winword",
    "microsoft word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "task manager": "taskmgr",
    "control panel": "control",
    "settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "clock": "ms-clock:",
    "store": "ms-windows-store:",
}
MAC_APPS = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "files": "Finder",
    "file explorer": "Finder",
    "finder": "Finder",
    "settings": "System Settings",
    "terminal": "Terminal",
    "calculator": "Calculator",
    "notepad": "TextEdit",
    "notes": "Notes",
    "music": "Music",
    "camera": "Photo Booth",
}
LINUX_APPS = {
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "google chrome": ["google-chrome", "google-chrome-stable", "chromium"],
    "firefox": ["firefox"],
    "vs code": ["code", "codium"],
    "vscode": ["code", "codium"],
    "terminal": ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"],
    "files": ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"],
    "file explorer": ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"],
    "calculator": ["gnome-calculator", "kcalc", "galculator", "qalculate-gtk"],
    "notepad": ["gedit", "gnome-text-editor", "kate", "mousepad", "xed"],
    "text editor": ["gedit", "gnome-text-editor", "kate", "mousepad", "xed"],
    "settings": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"],
    "word": ["libreoffice --writer"],
    "excel": ["libreoffice --calc"],
    "powerpoint": ["libreoffice --impress"],
    "spotify": ["spotify"],
    "vlc": ["vlc"],
}


def _detached(cmd: list[str] | str, shell: bool = False) -> None:
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "shell": shell}
    if IS_WINDOWS:
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def open_with_default_app(target: str) -> None:
    """Open a file, folder or URL the same way double-clicking it would."""
    if IS_WINDOWS:
        os.startfile(target)  # type: ignore[attr-defined]
    elif IS_MAC:
        _detached(["open", target])
    else:
        _detached(["xdg-open", target])


def _windows_app_path_exists(exe: str) -> bool:
    import winreg

    key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}.exe"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            winreg.CloseKey(winreg.OpenKey(hive, key))
            return True
        except OSError:
            continue
    return False


def _windows_start_menu_search(name: str) -> None:
    import pyautogui

    pyautogui.press("win")
    time.sleep(0.8)
    pyautogui.write(name, interval=0.03)
    time.sleep(1.0)
    pyautogui.press("enter")


@tool(
    "Open (launch) an application installed on this computer, e.g. Chrome, Word, "
    "Notepad, Spotify, VS Code, calculator, settings, file explorer.",
    {"name": {"type": "string", "description": "The application's name, e.g. 'chrome'"}},
)
def open_application(ctx, name: str) -> str:
    key = name.strip().lower()
    if IS_WINDOWS:
        target = WINDOWS_APPS.get(key, key)
        if target.endswith(":"):
            os.startfile(target)  # type: ignore[attr-defined]
        elif shutil.which(target) or _windows_app_path_exists(target):
            _detached(f'start "" "{target}"', shell=True)
        else:
            # Anything else: type it into the Start menu, like a person would.
            _windows_start_menu_search(name)
        return f"Opening {name}."
    if IS_MAC:
        app = MAC_APPS.get(key, name)
        proc = subprocess.run(["open", "-a", app], capture_output=True, text=True)
        if proc.returncode != 0:
            return f"Error: couldn't find an app called {name}."
        return f"Opened {app}."
    candidates = LINUX_APPS.get(key, [key.replace(" ", "-"), key.replace(" ", "")])
    for cmd in candidates:
        parts = cmd.split()
        if shutil.which(parts[0]):
            _detached(parts)
            return f"Opened {name}."
    if shutil.which("gtk-launch"):
        proc = subprocess.run(["gtk-launch", key.replace(" ", "-")], capture_output=True)
        if proc.returncode == 0:
            return f"Opened {name}."
    return f"Error: couldn't find an app called {name}."


@tool(
    "Close (quit) a running application by name, e.g. 'chrome' or 'spotify'.",
    {"name": {"type": "string", "description": "The application's name"}},
)
def close_application(ctx, name: str) -> str:
    import psutil

    key = name.strip().lower()
    if IS_WINDOWS:
        exe = WINDOWS_APPS.get(key, key)
    elif IS_MAC:
        exe = MAC_APPS.get(key, key)
    else:
        exe = LINUX_APPS.get(key, [key])[0].split()[0]
    exe = exe.lower().rstrip(":")
    matches = []
    for proc in psutil.process_iter(["name"]):
        pname = (proc.info.get("name") or "").lower()
        if pname and proc.pid != os.getpid() and (exe in pname or key in pname):
            matches.append(proc)
    if not matches:
        return f"{name} doesn't seem to be running."
    if not ctx.confirm(f"Close {name}? Any unsaved work will be lost."):
        return "Cancelled by the user."
    for proc in matches:
        try:
            proc.terminate()
        except psutil.Error:
            pass
    return f"Closed {name}."


@tool(
    "Open a file or folder on this computer with its default app.",
    {"path": {"type": "string", "description": "Full path, or a folder name like 'Downloads'"}},
)
def open_path(ctx, path: str) -> str:
    p = Path(os.path.expanduser(path))
    if not p.exists():
        home_candidate = Path.home() / path
        if home_candidate.exists():
            p = home_candidate
        else:
            return f"Error: {path} doesn't exist. Try search_files first."
    open_with_default_app(str(p))
    return f"Opened {p}."


SKIP_DIRS = {"node_modules", "__pycache__", "AppData", "Library", "venv", ".venv", "site-packages"}


@tool(
    "Find files or folders on this computer whose name contains some text.",
    {
        "query": {"type": "string", "description": "Part of the file name to look for"},
        "folder": {"type": "string", "description": "Where to search (default: home folder)"},
    },
)
def search_files(ctx, query: str, folder: str = "~") -> str:
    root = Path(os.path.expanduser(folder))
    needle = query.lower()
    found: list[str] = []
    deadline = time.monotonic() + 8
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS]
        for entry in dirnames + filenames:
            if needle in entry.lower():
                found.append(os.path.join(dirpath, entry))
        if len(found) >= 10 or time.monotonic() > deadline:
            break
    if not found:
        return f"No files matching '{query}' in {root}."
    return "Found:\n" + "\n".join(found[:10])


@tool("Get the current date and time.")
def get_date_time(ctx) -> str:
    now = dt.datetime.now()
    return now.strftime("It is %A, %d %B %Y, %I:%M %p.")


@tool("Get battery level, CPU and memory usage and free disk space.")
def system_status(ctx) -> str:
    import psutil

    parts = [f"CPU {psutil.cpu_percent(interval=0.5):.0f}% busy"]
    mem = psutil.virtual_memory()
    parts.append(f"memory {mem.percent:.0f}% used")
    disk = psutil.disk_usage(str(Path.home()))
    parts.append(f"{disk.free / 1e9:.0f} GB free disk space")
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if battery:
        plug = "charging" if battery.power_plugged else "on battery"
        parts.append(f"battery {battery.percent:.0f}% and {plug}")
    return ", ".join(parts) + "."


POWER_COMMANDS = {
    "win32": {
        "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
        "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        "shutdown": ["shutdown", "/s", "/t", "5"],
        "restart": ["shutdown", "/r", "/t", "5"],
        "log out": ["shutdown", "/l"],
    },
    "darwin": {
        "lock": ["pmset", "displaysleepnow"],
        "sleep": ["pmset", "sleepnow"],
        "shutdown": ["osascript", "-e", 'tell app "System Events" to shut down'],
        "restart": ["osascript", "-e", 'tell app "System Events" to restart'],
        "log out": ["osascript", "-e", 'tell app "System Events" to log out'],
    },
    "linux": {
        "lock": ["loginctl", "lock-session"],
        "sleep": ["systemctl", "suspend"],
        "shutdown": ["systemctl", "poweroff"],
        "restart": ["systemctl", "reboot"],
        "log out": ["loginctl", "terminate-user", os.environ.get("USER", "")],
    },
}


@tool(
    "Lock the screen, put the computer to sleep, shut it down, restart it or log out.",
    {
        "action": {
            "type": "string",
            "enum": ["lock", "sleep", "shutdown", "restart", "log out"],
            "description": "What to do",
        }
    },
)
def system_power(ctx, action: str) -> str:
    key = "win32" if IS_WINDOWS else "darwin" if IS_MAC else "linux"
    cmd = POWER_COMMANDS[key][action]
    if action != "lock" and not ctx.confirm(f"Are you sure you want me to {action} the computer?"):
        return "Cancelled by the user."
    subprocess.Popen(cmd)
    return f"Okay, {action}."


@tool(
    "Set a timer or a reminder. Jarvis will speak up when the time is up.",
    {
        "minutes": {"type": "number", "description": "How many minutes from now (can be a fraction)"},
        "message": {"type": "string", "description": "What to remind the user about, e.g. 'call mom'"},
    },
)
def set_timer(ctx, minutes: float, message: str = "") -> str:
    seconds = max(1.0, float(minutes) * 60)
    title = ctx.config.user_title

    def ring() -> None:
        if message:
            ctx.announce(f"{title}, this is your reminder: {message}.")
        else:
            ctx.announce(f"{title}, your timer for {_human_duration(seconds)} is done.")

    timer = threading.Timer(seconds, ring)
    timer.daemon = True
    timer.start()
    ctx.state.setdefault("timers", []).append(timer)
    return f"Timer set for {_human_duration(seconds)}."


def _human_duration(seconds: float) -> str:
    minutes, sec = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    out = []
    for value, unit in ((hours, "hour"), (minutes, "minute"), (sec, "second")):
        if value:
            out.append(f"{value} {unit}" + ("" if value == 1 else "s"))
    return " and ".join(out)


@tool(
    "Run a command in the terminal/command prompt and return its output. "
    "Only use this when no other tool can do the job.",
    {"command": {"type": "string", "description": "The exact shell command to run"}},
    available=lambda ctx: bool(ctx.config.safety.allow_shell),
)
def run_shell_command(ctx, command: str) -> str:
    # This always asks, even when confirm_dangerous is off.
    question = f"Shall I run this command: {command}?"
    if not ctx._ask_yes_no(question):
        return "Cancelled by the user."
    proc = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=60, cwd=str(Path.home())
    )
    output = (proc.stdout + proc.stderr).strip()
    if len(output) > 2000:
        output = output[:2000] + "\n...(truncated)"
    return f"Exit code {proc.returncode}.\n{output}"


def os_description() -> str:
    if IS_WINDOWS:
        return f"Windows {platform.release()}"
    if IS_MAC:
        return f"macOS {platform.mac_ver()[0]}"
    try:
        return platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
    except (AttributeError, OSError):
        return "Linux"
