"""Turning model output into things that sound right when spoken."""

from __future__ import annotations

import re

ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e"}

_SENTENCE_END = re.compile(r"[.!?]+[\"')\]]*(?=\s|$)|\n+")
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F2FF\u2600-\u26FF\uFE0F]+"
)


class SentenceSplitter:
    """Collects streamed text and hands back whole sentences as they complete.

    Speaking sentence by sentence means Jarvis starts talking while the model
    is still writing the rest of the answer.
    """

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, text: str) -> list[str]:
        self._buf += text
        out = []
        start = 0
        for m in _SENTENCE_END.finditer(self._buf):
            newline = m.group(0).startswith("\n")
            if not newline and m.end() == len(self._buf):
                break  # might be "3." of "3.5" still streaming in
            if not newline:
                words = self._buf[start:m.start()].split()
                if words and words[-1].lower() in ABBREVIATIONS:
                    continue  # "Dr. Smith", "e.g. this"
            candidate = self._buf[start:m.end()].strip()
            if candidate:
                out.append(candidate)
            start = m.end()
        self._buf = self._buf[start:]
        return out

    def flush(self) -> str:
        rest, self._buf = self._buf.strip(), ""
        return rest


def clean_for_speech(text: str) -> str:
    """Remove Markdown, links and emoji that a voice shouldn't read out."""
    text = re.sub(r"```.*?(```|$)", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "the link", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*([-*+•]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"(\*\*|__|\*|_{1,2}(?=\w)|~~)", "", text)
    text = _EMOJI.sub("", text)
    text = text.replace("&", " and ").replace("%", " percent")
    return re.sub(r"\s+", " ", text).strip()
