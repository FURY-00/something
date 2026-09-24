"""Keyboard, mouse, media keys, volume, screen and clipboard."""

from __future__ import annotations

import base64
import datetime as dt
import io
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

from . import tool

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
MOD = "command" if IS_MAC else "ctrl"


def gui():
    """Import pyautogui lazily so text-only use works without a display."""
    try:
        import pyautogui
    except Exception as exc:  # noqa: BLE001 - e.g. no display on a headless box
        raise RuntimeError(f"keyboard/mouse control is unavailable: {exc}") from exc
    pyautogui.FAILSAFE = True  # slam the mouse into a screen corner to abort
    return pyautogui


KEY_ALIASES = {
    "control": "ctrl",
    "cmd": "command",
    "windows": "win",
    "super": "win",
    "start": "win",
    "option": "alt",
    "escape": "esc",
    "return": "enter",
    "del": "delete",
    "page down": "pagedown",
    "page up": "pageup",
    "arrow down": "down",
    "arrow up": "up",
    "arrow left": "left",
    "arrow right": "right",
    "spacebar": "space",
    "caps lock": "capslock",
    "print screen": "printscreen",
}


def parse_keys(keys: str) -> list[str]:
    parts = [p.strip().lower() for p in keys.replace(" plus ", "+").split("+") if p.strip()]
    out = []
    for p in parts:
        p = KEY_ALIASES.get(p, p)
        if IS_MAC and p == "win":
            p = "command"
        out.append(p)
    return out


@tool(
    "Press a key or a keyboard shortcut in the active window, e.g. 'enter', 'space', "
    "'ctrl+c', 'ctrl+s', 'alt+tab' (switch window), 'alt+f4' (close window), 'win+d', 'f5'.",
    {
        "keys": {"type": "string", "description": "Key or shortcut, keys joined with '+'"},
        "times": {"type": "integer", "description": "How many times to press it (default 1)"},
    },
)
def press_keys(ctx, keys: str, times: int = 1) -> str:
    g = gui()
    combo = parse_keys(keys)
    if "f4" in combo and "alt" in combo and not ctx.confirm("Close the current window?"):
        return "Cancelled by the user."
    for _ in range(max(1, min(times, 50))):
        if len(combo) == 1:
            g.press(combo[0])
        else:
            g.hotkey(*combo)
        time.sleep(0.05)
    return f"Pressed {'+'.join(combo)}" + (f" {times} times." if times > 1 else ".")


def _paste(text: str) -> None:
    import pyperclip

    g = gui()
    try:
        previous = pyperclip.paste()
    except Exception:  # noqa: BLE001
        previous = None
    pyperclip.copy(text)
    time.sleep(0.05)
    g.hotkey(MOD, "v")
    time.sleep(0.3)
    if previous is not None:
        pyperclip.copy(previous)


@tool(
    "Type text into the active window at the cursor, as if typed on the keyboard "
    "(e.g. into a search box, chat or document).",
    {
        "text": {"type": "string", "description": "The exact text to type"},
        "press_enter": {"type": "boolean", "description": "Press Enter afterwards (e.g. to send)"},
    },
)
def type_text(ctx, text: str, press_enter: bool = False) -> str:
    g = gui()
    if text.isascii() and len(text) < 200:
        g.write(text, interval=0.01)
    else:
        _paste(text)  # faster, and handles non-English characters
    if press_enter:
        g.press("enter")
    return f"Typed {len(text)} characters."


@tool(
    "Scroll the page or window under the mouse up or down.",
    {
        "direction": {"type": "string", "enum": ["up", "down"], "description": "Direction"},
        "amount": {"type": "integer", "description": "How far, in mouse-wheel notches (default 5)"},
    },
)
def scroll(ctx, direction: str, amount: int = 5) -> str:
    g = gui()
    notch = 120 if IS_WINDOWS else 3 if IS_MAC else 1
    clicks = max(1, amount) * notch
    g.scroll(clicks if direction == "up" else -clicks)
    return f"Scrolled {direction}."


FEEDS = {
    "instagram": "https://www.instagram.com/reels/",
    "youtube": "https://www.youtube.com/shorts",
}


def stop_auto_scroll(ctx) -> bool:
    stop = ctx.state.pop("auto_scroll_stop", None)
    if stop:
        stop.set()
        return True
    return False


@tool(
    "Control short-video feeds in the browser (Instagram Reels, YouTube Shorts): "
    "open the feed, go to the next or previous video, like, pause/play, mute, or "
    "start/stop scrolling automatically every few seconds.",
    {
        "action": {
            "type": "string",
            "enum": ["open", "next", "previous", "like", "pause", "mute", "auto_start", "auto_stop"],
            "description": "What to do",
        },
        "platform": {
            "type": "string",
            "enum": ["instagram", "youtube"],
            "description": "Which app (default: the one opened last, else instagram)",
        },
        "seconds": {"type": "integer", "description": "For auto_start: seconds per video (default 15)"},
    },
)
def reels(ctx, action: str, platform: str = "", seconds: int = 15) -> str:
    platform = platform or ctx.state.get("feed", "instagram")
    if action == "open":
        ctx.state["feed"] = platform
        webbrowser.open(FEEDS[platform])
        note = " You need to be logged in to Instagram in your browser." if platform == "instagram" else ""
        return f"Opened {platform} short videos.{note}"
    if action == "auto_stop":
        return "Stopped auto-scrolling." if stop_auto_scroll(ctx) else "Auto-scroll wasn't running."

    g = gui()
    w, h = g.size()
    if action == "next":
        g.press("down")
    elif action == "previous":
        g.press("up")
    elif action == "like":
        if platform == "youtube":
            return "Error: YouTube Shorts has no keyboard shortcut for liking."
        g.doubleClick(w // 2, h // 2)
    elif action == "pause":
        if platform == "youtube":
            g.press("k")
        else:
            g.click(w // 2, h // 2)
    elif action == "mute":
        g.press("m")
    elif action == "auto_start":
        stop_auto_scroll(ctx)
        stop = threading.Event()
        ctx.state["auto_scroll_stop"] = stop
        delay = max(3, seconds)

        def loop() -> None:
            while not stop.wait(delay):
                try:
                    gui().press("down")
                except Exception:  # noqa: BLE001 - e.g. failsafe triggered
                    break

        threading.Thread(target=loop, daemon=True).start()
        return f"Auto-scrolling every {delay} seconds. Say 'stop scrolling' to stop."
    return f"Done: {action}."


MEDIA_KEYS = {
    "play_pause": "playpause",
    "next_track": "nexttrack",
    "previous_track": "prevtrack",
    "volume_up": "volumeup",
    "volume_down": "volumedown",
    "mute": "volumemute",
}


@tool(
    "Media keys: play/pause, next/previous track, volume up/down, mute. Works with "
    "Spotify, YouTube, VLC and most players.",
    {
        "action": {"type": "string", "enum": list(MEDIA_KEYS), "description": "Which media key"},
        "times": {"type": "integer", "description": "Times to press (for volume, default 1)"},
    },
)
def media_control(ctx, action: str, times: int = 1) -> str:
    g = gui()
    if action.startswith("volume") and times == 1:
        times = 5
    for _ in range(max(1, min(times, 50))):
        g.press(MEDIA_KEYS[action])
    return f"Done: {action.replace('_', ' ')}."


@tool(
    "Set the speaker volume to an exact percentage.",
    {"percent": {"type": "integer", "description": "Volume from 0 to 100"}},
)
def set_volume(ctx, percent: int) -> str:
    percent = max(0, min(100, percent))
    if IS_MAC:
        subprocess.run(["osascript", "-e", f"set volume output volume {percent}"], check=True)
    elif not IS_WINDOWS and shutil.which("pactl"):
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"], check=True)
    elif not IS_WINDOWS and shutil.which("amixer"):
        subprocess.run(["amixer", "-q", "set", "Master", f"{percent}%"], check=True)
    else:
        # Windows volume keys move in 2% steps: go to zero, then count up.
        g = gui()
        for _ in range(50):
            g.press("volumedown")
        for _ in range(round(percent / 2)):
            g.press("volumeup")
    return f"Volume set to {percent} percent."


def _screenshot():
    return gui().screenshot()


@tool("Take a screenshot and save it to the Pictures folder.")
def take_screenshot(ctx) -> str:
    folder = ctx.config.paths.screenshots
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"screenshot-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
    _screenshot().save(path)
    return f"Screenshot saved to {path}."


@tool(
    "Look at the screen and answer a question about what is visible "
    "(e.g. 'what's on my screen?', 'read this error', 'which video is playing?').",
    {"question": {"type": "string", "description": "What to look for or answer"}},
    available=lambda ctx: bool(ctx.config.llm.vision_model),
)
def look_at_screen(ctx, question: str) -> str:
    image = _screenshot()
    image.thumbnail((1344, 1344))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    result = ctx.llm.chat(
        [{"role": "user", "content": question, "images": [b64]}],
        model=ctx.config.llm.vision_model,
        temperature=0.2,
    )
    return result.content or "I couldn't make anything out."


@tool(
    "Get text the user has selected (highlighted) on screen, or what's on the "
    "clipboard, so you can read, summarise, translate or explain it.",
    {
        "source": {
            "type": "string",
            "enum": ["selection", "clipboard"],
            "description": "'selection' copies the highlighted text first",
        }
    },
)
def get_text(ctx, source: str = "selection") -> str:
    import pyperclip

    if source == "selection":
        gui().hotkey(MOD, "c")
        time.sleep(0.4)
    text = (pyperclip.paste() or "").strip()
    if not text:
        return "The clipboard is empty. Ask the user to select or copy some text first."
    if len(text) > 8000:
        text = text[:8000] + "\n...(truncated)"
    return text
