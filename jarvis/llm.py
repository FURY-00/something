"""Client for a local Ollama server (https://ollama.com).

Ollama runs the language model entirely on your machine. We talk to it over
its HTTP API on localhost, so nothing leaves your laptop.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

import requests


class LLMError(RuntimeError):
    pass


@dataclass
class ChatResult:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)


class ThinkFilter:
    """Hides ``<think>...</think>`` reasoning that some models print inline.

    Works on streamed text, where a tag can be split across chunks.
    """

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False

    def feed(self, text: str) -> str:
        self._buf += text
        out = []
        while self._buf:
            tag = self.CLOSE if self._inside else self.OPEN
            idx = self._buf.find(tag)
            if idx >= 0:
                if not self._inside:
                    out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(tag):]
                self._inside = not self._inside
                continue
            # Keep a possible partial tag at the end of the buffer for later.
            keep = 0
            for n in range(min(len(tag) - 1, len(self._buf)), 0, -1):
                if tag.startswith(self._buf[-n:]):
                    keep = n
                    break
            if not self._inside:
                out.append(self._buf[: len(self._buf) - keep])
            self._buf = self._buf[len(self._buf) - keep:] if keep else ""
            break
        return "".join(out)

    def flush(self) -> str:
        rest = "" if self._inside else self._buf
        self._buf = ""
        return rest


def strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<think>.*", "", text, flags=re.S).strip()


class OllamaClient:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        temperature: float = 0.6,
        num_ctx: int = 8192,
        keep_alive: str | int = "30m",
        think: bool | None = None,
        stream: bool = True,
        timeout: float = 300,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.think = think
        self.stream = stream
        self.timeout = timeout

    @classmethod
    def from_config(cls, llm_cfg) -> "OllamaClient":
        return cls(
            host=llm_cfg.host,
            model=llm_cfg.model,
            temperature=llm_cfg.temperature,
            num_ctx=llm_cfg.num_ctx,
            keep_alive=llm_cfg.keep_alive,
            think=llm_cfg.think,
            stream=llm_cfg.stream,
            timeout=llm_cfg.timeout,
        )

    # ------------------------------------------------------------------ status
    def list_models(self) -> list[str]:
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                f"Can't reach Ollama at {self.host}. Is it running? "
                "Start it with 'ollama serve' or open the Ollama app."
            ) from exc
        return [m.get("name", "") for m in resp.json().get("models", [])]

    def has_model(self, name: str | None = None) -> bool:
        name = name or self.model
        wanted = name if ":" in name else f"{name}:latest"
        return any(m == wanted or m == name for m in self.list_models())

    def warm_up(self) -> None:
        """Load the model into memory so the first real answer is quick."""
        requests.post(
            f"{self.host}/api/generate",
            json={"model": self.model, "keep_alive": self.keep_alive},
            timeout=self.timeout,
        )

    def pull(self, name: str, on_progress: Callable[[str], None] = print) -> None:
        with requests.post(
            f"{self.host}/api/pull", json={"model": name}, stream=True, timeout=None
        ) as resp:
            if resp.status_code != 200:
                raise LLMError(f"Pull failed: {resp.text}")
            last = ""
            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise LLMError(data["error"])
                status = data.get("status", "")
                if data.get("total"):
                    pct = 100 * data.get("completed", 0) / data["total"]
                    status = f"{status} {pct:5.1f}%"
                if status != last:
                    on_progress(status)
                    last = status

    # -------------------------------------------------------------------- chat
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_text: Callable[[str], None] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        stream: bool | None = None,
    ) -> ChatResult:
        """Send a chat request. ``on_text`` receives answer text as it streams."""
        stream = self.stream if stream is None else stream
        payload: dict = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_ctx": self.num_ctx,
            },
        }
        if tools:
            payload["tools"] = tools
        if self.think is not None and model in (None, self.model):
            payload["think"] = self.think

        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                stream=stream,
                timeout=(10, self.timeout),
            )
        except requests.RequestException as exc:
            raise LLMError(f"Can't reach Ollama at {self.host}: {exc}") from exc

        with resp:
            if resp.status_code != 200:
                raise LLMError(_error_text(resp))
            chunks = _iter_json_lines(resp.iter_lines()) if stream else [resp.json()]
            return self._collect(chunks, on_text)

    @staticmethod
    def _collect(chunks: Iterable[dict], on_text: Callable[[str], None] | None) -> ChatResult:
        result = ChatResult()
        think = ThinkFilter()
        parts: list[str] = []
        for chunk in chunks:
            if "error" in chunk:
                raise LLMError(chunk["error"])
            msg = chunk.get("message") or {}
            piece = msg.get("content") or ""
            if piece:
                visible = think.feed(piece)
                if visible:
                    parts.append(visible)
                    if on_text:
                        on_text(visible)
            for call in msg.get("tool_calls") or []:
                result.tool_calls.append(call)
            if chunk.get("done"):
                break
        tail = think.flush()
        if tail:
            parts.append(tail)
            if on_text:
                on_text(tail)
        result.content = "".join(parts).strip()
        return result


def _iter_json_lines(lines: Iterable[bytes]) -> Iterable[dict]:
    for line in lines:
        if line:
            yield json.loads(line)


def _error_text(resp: requests.Response) -> str:
    try:
        err = resp.json().get("error", resp.text)
    except ValueError:
        err = resp.text
    if "not found" in err and "model" in err:
        err += " (download it with: ollama pull <model>)"
    return f"Ollama error {resp.status_code}: {err}"
