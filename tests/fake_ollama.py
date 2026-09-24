"""A tiny stand-in for the Ollama HTTP API, for tests.

``script`` is a function that receives the chat request body and returns a
list of streamed ``message`` dicts (content pieces and/or tool_calls).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self, script, models=("qwen2.5:7b",)) -> None:
        self.script = script
        self.models = list(models)
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def _json(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/api/tags":
                    self._json(200, {"models": [{"name": m} for m in outer.models]})
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/generate":
                    self._json(200, {"done": True})
                    return
                if self.path != "/api/chat":
                    self._json(404, {"error": "not found"})
                    return
                outer.requests.append(body)
                if body.get("model") not in outer.models:
                    self._json(404, {"error": f"model '{body.get('model')}' not found"})
                    return
                messages = outer.script(body)
                if not body.get("stream", True):
                    merged = {"role": "assistant", "content": "", "tool_calls": []}
                    for m in messages:
                        merged["content"] += m.get("content", "")
                        merged["tool_calls"] += m.get("tool_calls", [])
                    self._json(200, {"message": merged, "done": True})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for m in messages:
                    chunk = {"message": {"role": "assistant", **m}, "done": False}
                    self.wfile.write((json.dumps(chunk) + "\n").encode())
                    self.wfile.flush()
                self.wfile.write((json.dumps({"message": {"role": "assistant", "content": ""},
                                              "done": True}) + "\n").encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeOllama":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()


def pieces(text: str, size: int = 7) -> list[dict]:
    """Split text into streamed content chunks."""
    return [{"content": text[i:i + size]} for i in range(0, len(text), size)]


def tool_call(name: str, **arguments) -> dict:
    return {"tool_calls": [{"function": {"name": name, "arguments": arguments}}]}
