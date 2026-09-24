"""The Canva agent and MCP bridge, against a local fake 'Canva' MCP server."""

import socket
import threading
import time

import pytest

pytest.importorskip("mcp")
uvicorn = pytest.importorskip("uvicorn")

from jarvis.config import load_config  # noqa: E402
from jarvis.context import ToolContext  # noqa: E402
from jarvis.llm import ChatResult  # noqa: E402
from jarvis.mcp_bridge import MCPConnection  # noqa: E402
from jarvis.skills.canva import CanvaSkill  # noqa: E402

CALLS = []


@pytest.fixture(scope="module")
def canva_url():
    from mcp.server.mcpserver import MCPServer

    srv = MCPServer("fake-canva")

    @srv.tool(name="search-designs")
    def search_designs(query: str = "", user_intent: str = "") -> str:
        """Find designs."""
        CALLS.append(("search", query))
        return '{"items": [{"design_id": "DAF1", "title": "Birthday poster"}]}'

    @srv.tool(name="read-design")
    def read_design(design_id: str, open_transaction: bool = False, user_intent: str = "") -> str:
        """Read a design."""
        CALLS.append(("read", design_id))
        return ('{"transaction_id": "tx1", "pages": [{"index": 1, "elements": [{"locator_id": "PB1-LB2", '
                '"type": "text", "text": "Happy Birthday"}]}], "thumbnail": "https://img.example/thumbnail/1.png"}')

    @srv.tool(name="edit-design")
    def edit_design(transaction_id: str, finalize: str = "keep_open", operations: list | None = None,
                    page_index: int | None = None, user_intent: str = "") -> str:
        """Edit a design."""
        CALLS.append(("edit", finalize, operations))
        return f"finalize={finalize} ops={len(operations or [])}"

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(srv.streamable_http_app(), host="127.0.0.1", port=port,
                                           log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True


def call(name, **args):
    return {"function": {"name": name, "arguments": args}}


class ScriptedAgent:
    """Plays the part of the model driving Canva's tools."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.tool_names = None
        self.results = []

    def chat(self, messages, tools=None, **kw):
        self.tool_names = [t["function"]["name"] for t in tools]
        if messages[-1]["role"] == "tool":
            self.results.append(messages[-1]["content"])
        return self.steps.pop(0)


def make_skill(tmp_path, url):
    cfg = load_config()
    cfg.paths.data = tmp_path
    skill = CanvaSkill(cfg)
    skill.conn = MCPConnection("canva-test", url).start(timeout=20)  # no sign-in for the fake server
    return skill, cfg


EDIT_STEPS = [
    ChatResult(tool_calls=[call("search-designs", query="birthday poster", user_intent="find")]),
    ChatResult(tool_calls=[call("read-design", design_id="DAF1", open_transaction=True, user_intent="read")]),
    ChatResult(tool_calls=[call("edit-design", transaction_id="tx1", page_index=1, finalize="keep_open",
                                user_intent="bigger gold title",
                                operations=[{"type": "format_text", "locator_id": "PB1-LB2",
                                             "formatting": {"font_size": 96, "color": "#D4AF37"}}])]),
    ChatResult(tool_calls=[call("edit-design", transaction_id="tx1", finalize="commit", user_intent="save")]),
]


def test_edit_is_saved_only_after_the_user_approves(tmp_path, canva_url, monkeypatch):
    CALLS.clear()
    opened = []
    monkeypatch.setattr("jarvis.skills.canva.webbrowser.open", opened.append)
    skill, cfg = make_skill(tmp_path, canva_url)
    asked = []
    ctx = ToolContext(cfg, ask_yes_no=lambda q: asked.append(q) or True)
    llm = ScriptedAgent(EDIT_STEPS + [ChatResult(content="Done, the title is bigger and gold.")])
    result = skill.run_task("make the birthday poster title bigger and gold", llm, ctx)
    assert result.ok and result.summary == "Done, the title is bigger and gold."
    assert [c[0] for c in CALLS] == ["search", "read", "edit", "edit"]
    assert CALLS[2][2][0]["formatting"]["font_size"] == 96
    assert CALLS[3][1] == "commit"
    assert asked and "save" in asked[0]
    assert opened == ["https://img.example/thumbnail/1.png"]  # preview shown before asking
    assert "open_link" in llm.tool_names and "edit-design" in llm.tool_names
    skill.close()


def test_declined_save_is_not_committed(tmp_path, canva_url, monkeypatch):
    CALLS.clear()
    monkeypatch.setattr("jarvis.skills.canva.webbrowser.open", lambda url: None)
    skill, cfg = make_skill(tmp_path, canva_url)
    ctx = ToolContext(cfg, ask_yes_no=lambda q: False)
    ctx.config.safety.confirm_dangerous = False  # Canva saves must ask even so
    llm = ScriptedAgent(EDIT_STEPS + [
        ChatResult(tool_calls=[call("edit-design", transaction_id="tx1", finalize="cancel", user_intent="discard")]),
        ChatResult(content="Okay, I discarded the changes."),
    ])
    result = skill.run_task("make the title bigger", llm, ctx)
    finals = [c[1] for c in CALLS if c[0] == "edit"]
    assert finals == ["keep_open", "cancel"]  # the commit never reached Canva
    assert "did NOT approve" in llm.results[3]
    assert result.summary == "Okay, I discarded the changes."
    skill.close()
