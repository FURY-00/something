import pytest

from jarvis.llm import LLMError, OllamaClient, ThinkFilter, strip_think

from .fake_ollama import FakeOllama, pieces, tool_call


def test_streams_text_and_collects_tool_calls():
    def script(body):
        return pieces("Opening it now. ") + [tool_call("open_website", site="youtube")]

    with FakeOllama(script) as server:
        client = OllamaClient(host=server.url)
        seen = []
        result = client.chat([{"role": "user", "content": "open youtube"}], tools=[{}],
                             on_text=seen.append)
    assert result.content == "Opening it now."
    assert "".join(seen) == "Opening it now. "
    assert result.tool_calls == [{"function": {"name": "open_website", "arguments": {"site": "youtube"}}}]
    assert server.requests[0]["tools"] == [{}]
    assert "think" not in server.requests[0]


def test_non_streaming_request():
    with FakeOllama(lambda body: pieces("Hello there.")) as server:
        result = OllamaClient(host=server.url).chat([{"role": "user", "content": "hi"}], stream=False)
    assert result.content == "Hello there."


def test_think_option_only_sent_when_configured():
    with FakeOllama(lambda body: pieces("ok")) as server:
        OllamaClient(host=server.url, think=False).chat([{"role": "user", "content": "hi"}])
    assert server.requests[0]["think"] is False


def test_missing_model_error_is_helpful():
    with FakeOllama(lambda body: [], models=["other:1b"]) as server:
        client = OllamaClient(host=server.url, model="qwen2.5:7b")
        assert not client.has_model()
        with pytest.raises(LLMError, match="ollama pull"):
            client.chat([{"role": "user", "content": "hi"}])


def test_unreachable_server():
    client = OllamaClient(host="http://127.0.0.1:9")
    with pytest.raises(LLMError, match="Can't reach Ollama"):
        client.list_models()


def test_think_filter_handles_tags_split_across_chunks():
    f = ThinkFilter()
    out = "".join(f.feed(c) for c in ["<thi", "nk>secret plan", "</th", "ink>Hello", " sir<", "b>"])
    out += f.flush()
    assert out == "Hello sir<b>"


def test_strip_think():
    assert strip_think("<think>hmm</think>\n# Title\nBody") == "# Title\nBody"
    assert strip_think("<think>never closed") == ""
