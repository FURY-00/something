"""Connect to MCP servers ("connectors") such as Canva's official one.

The Model Context Protocol is the standard way AI assistants reach outside
services. Jarvis keeps one connection per server on a background event-loop
thread, and exposes a blocking ``call(tool, args)`` to the rest of the code.

Servers that need a login (like Canva) use OAuth: the first time, your
browser opens the service's sign-in page; the token is then saved in
``data/mcp/<name>.json`` so you stay signed in.
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import contextlib
import json
import logging
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

log = logging.getLogger(__name__)

CALLBACK_PORT = 33418


class FileTokenStorage:
    """Keeps OAuth tokens and the registered client in a small JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _store(self, key: str, value) -> None:
        data = self._load()
        data[key] = json.loads(value.model_dump_json(exclude_none=True))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken

        data = self._load().get("tokens")
        return OAuthToken.model_validate(data) if data else None

    async def set_tokens(self, tokens) -> None:
        self._store("tokens", tokens)

    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull

        data = self._load().get("client")
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def set_client_info(self, client_info) -> None:
        self._store("client", client_info)


def _wait_for_oauth_callback(port: int, timeout: float = 300) -> dict:
    """Serve one request on localhost:port/callback and return its query parameters."""
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            result.update({k: v[0] for k, v in query.items()})
            body = (b"<html><body style='font-family:sans-serif;text-align:center;margin-top:20%'>"
                    b"<h2>Signed in. You can close this tab and go back to Jarvis.</h2></body></html>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = timeout
    try:
        server.handle_request()
    finally:
        server.server_close()
    if "code" not in result:
        raise RuntimeError(f"Sign-in didn't complete: {result.get('error', 'no code received')}")
    return result


def _oauth_provider(url: str, storage: FileTokenStorage, port: int):
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

    try:
        from mcp.shared.auth import AuthorizationCodeResult  # MCP SDK 2.x
    except ImportError:
        AuthorizationCodeResult = None

    async def redirect_handler(auth_url: str) -> None:
        print(f"\nOpening your browser to sign in... If it doesn't open, visit:\n{auth_url}\n")
        webbrowser.open(auth_url)

    async def callback_handler():
        params = await asyncio.get_running_loop().run_in_executor(None, _wait_for_oauth_callback, port)
        if AuthorizationCodeResult is not None:
            return AuthorizationCodeResult(code=params["code"], state=params.get("state"),
                                           iss=params.get("iss"))
        return params["code"], params.get("state")

    metadata = OAuthClientMetadata(
        client_name="Jarvis voice assistant",
        redirect_uris=[f"http://localhost:{port}/callback"],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )
    return OAuthClientProvider(server_url=url, client_metadata=metadata, storage=storage,
                               redirect_handler=redirect_handler, callback_handler=callback_handler)


def _attr(obj, *names, default=None):
    """MCP SDK 2.x uses snake_case field names where 1.x used camelCase."""
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def format_result(result) -> str:
    """Turn an MCP CallToolResult into text for the language model."""
    parts = []
    for item in getattr(result, "content", None) or []:
        kind = getattr(item, "type", "")
        if kind == "text":
            parts.append(item.text)
        elif kind == "image":
            suffix = "." + (_attr(item, "mime_type", "mimeType", default="image/png").split("/")[-1] or "png")
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="jarvis_mcp_") as fh:
                fh.write(base64.b64decode(item.data))
            parts.append(f"[image saved to {fh.name}]")
        elif kind == "resource_link":
            parts.append(f"[resource {getattr(item, 'name', '')}: {getattr(item, 'uri', '')}]")
        elif kind == "resource":
            res = item.resource
            parts.append(getattr(res, "text", None) or f"[resource {getattr(res, 'uri', '')}]")
    structured = _attr(result, "structured_content", "structuredContent")
    if structured and not parts:
        parts.append(json.dumps(structured, ensure_ascii=False))
    text = "\n".join(parts) or "(no output)"
    return ("Error: " + text) if _attr(result, "is_error", "isError", default=False) else text


class MCPConnection:
    """A live connection to one MCP server, usable from ordinary threads."""

    def __init__(self, name: str, url: str, token_file: Path | None = None,
                 headers: dict | None = None, callback_port: int = CALLBACK_PORT) -> None:
        self.name = name
        self.url = url
        self.token_file = token_file
        self.headers = headers or {}
        self.callback_port = callback_port
        self.tools: list = []
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name=f"mcp:{name}", daemon=True)
        self._thread.start()
        self._queue: asyncio.Queue | None = None
        self._ready: concurrent.futures.Future = concurrent.futures.Future()
        self._started = False
        self._lock = threading.Lock()

    def start(self, timeout: float = 300) -> "MCPConnection":
        with self._lock:
            if not self._started:
                self._started = True
                asyncio.run_coroutine_threadsafe(self._main(), self._loop)
        self._ready.result(timeout=timeout)
        return self

    @contextlib.asynccontextmanager
    async def _open(self):
        from mcp import ClientSession

        storage = FileTokenStorage(self.token_file) if self.token_file else None
        auth = _oauth_provider(self.url, storage, self.callback_port) if storage else None
        async with contextlib.AsyncExitStack() as stack:
            try:  # MCP SDK 2.x
                from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

                http = create_mcp_http_client(headers=self.headers or None, auth=auth)
                await stack.enter_async_context(http)
                streams = await stack.enter_async_context(streamable_http_client(self.url, http_client=http))
            except ImportError:  # MCP SDK 1.x
                from mcp.client.streamable_http import streamablehttp_client

                streams = await stack.enter_async_context(
                    streamablehttp_client(self.url, headers=self.headers or None, auth=auth))
            session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await session.initialize()
            yield session

    async def _main(self) -> None:
        self._queue = asyncio.Queue()
        try:
            async with self._open() as session:
                self.tools = list((await session.list_tools()).tools)
                self._ready.set_result(True)
                while True:
                    name, args, future = await self._queue.get()
                    if name is None:
                        break
                    try:
                        future.set_result(await session.call_tool(name, args))
                    except Exception as exc:  # noqa: BLE001 - hand errors to the caller
                        future.set_exception(exc)
        except Exception as exc:  # noqa: BLE001
            log.debug("MCP %s failed", self.name, exc_info=True)
            if not self._ready.done():
                self._ready.set_exception(exc)

    def tool_schemas(self, allow: list[str] | None = None) -> list[dict]:
        """Tools in the format the language models expect."""
        chosen = [t for t in self.tools if not allow or t.name in allow] or self.tools
        return [{"type": "function", "function": {
            "name": t.name, "description": t.description or "",
            "parameters": _attr(t, "input_schema", "inputSchema") or {"type": "object", "properties": {}},
        }} for t in chosen]

    def call(self, tool: str, arguments: dict | None = None, timeout: float = 300) -> str:
        self.start()
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (tool, arguments or {}, future))
        return format_result(future.result(timeout=timeout))

    def close(self) -> None:
        if self._queue is not None:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, (None, None, None))
