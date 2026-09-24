"""Optional cloud brain: Claude through the Anthropic API.

Local models that fit on a laptop are good conversationalists but struggle
with expert work such as SolidWorks API code, COMSOL model setup or building
a website from a PDF. Set ``provider: anthropic`` (for conversation) and/or
``code_provider: anthropic`` (for application scripts) in config.yaml to use
Claude instead. This needs internet and an API key in ANTHROPIC_API_KEY (or
an ``ant auth login`` profile). Voice, wake word and speech recognition
still run locally.

The class has the same ``chat()`` interface as :class:`jarvis.llm.OllamaClient`
and takes/returns messages in the same (Ollama-style) format, so the rest of
Jarvis doesn't care which brain is in use.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

from .llm import ChatResult, LLMError

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def to_anthropic_tools(tools: list[dict] | None) -> list[dict]:
    out = []
    for t in tools or []:
        fn = t.get("function", t)
        schema = dict(fn.get("parameters") or {"type": "object", "properties": {}})
        schema.pop("$schema", None)  # MCP servers include it; the tool schema doesn't need it
        out.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": schema,
            # Large inputs (whole scripts, documents) stream as they're written.
            "eager_input_streaming": True,
        })
    return out


def to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Ollama-style history -> (system prompt, Anthropic messages)."""
    system_parts: list[str] = []
    out: list[dict] = []
    pending_ids: list[str] = []  # tool_use ids waiting for their results
    counter = 0
    for m in messages:
        role = m.get("role")
        if role == "system":
            system_parts.append(m.get("content", ""))
        elif role == "user":
            content = m.get("content") or "(no text)"
            if m.get("images"):
                blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                        "data": img}} for img in m["images"]]
                content = blocks + [{"type": "text", "text": content}]
            out.append({"role": "user", "content": content})
        elif role == "assistant":
            if m.get("_anthropic_content"):
                blocks = m["_anthropic_content"]  # replay exactly what Claude sent
                pending_ids = [b.id if hasattr(b, "id") else b.get("id") for b in blocks
                               if (getattr(b, "type", None) or b.get("type")) == "tool_use"]
            else:
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                pending_ids = []
                for call in m.get("tool_calls") or []:
                    fn = call.get("function", {})
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = {}
                    counter += 1
                    call_id = call.get("id") or f"toolu_jarvis_{counter}"
                    pending_ids.append(call_id)
                    blocks.append({"type": "tool_use", "id": call_id, "name": fn.get("name", ""),
                                   "input": args})
            if blocks:
                out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            call_id = m.get("tool_call_id") or (pending_ids.pop(0) if pending_ids else None)
            if call_id is None:
                out.append({"role": "user", "content": f"[tool result] {m.get('content', '')}"})
                continue
            if call_id in pending_ids:
                pending_ids.remove(call_id)
            result = {"type": "tool_result", "tool_use_id": call_id, "content": m.get("content") or "Done."}
            if m.get("content", "").startswith("Error"):
                result["is_error"] = True
            last = out[-1] if out else None
            # All results for one assistant turn go in a single user message.
            if last and last["role"] == "user" and isinstance(last["content"], list) and all(
                b.get("type") == "tool_result" for b in last["content"]
            ):
                last["content"].append(result)
            else:
                out.append({"role": "user", "content": [result]})
    return "\n\n".join(p for p in system_parts if p), out


class AnthropicClient:
    """Claude with the same interface as OllamaClient."""

    #: History sent to Claude must only ever grow at the end (thinking blocks
    #: from earlier turns are replayed as-is), so the brain skips trimming.
    append_only = True

    def __init__(self, model: str = "claude-opus-5", effort: str = "medium",
                 max_tokens: int = 64000, timeout: float = 600) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("The cloud brain needs the anthropic package: pip install anthropic") from exc
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(timeout=timeout)
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    # Status helpers mirroring OllamaClient ------------------------------
    def has_model(self, name: str | None = None) -> bool:
        return True  # the API reports a bad model name on the first request

    def list_models(self) -> list[str]:
        return [self.model]

    def warm_up(self) -> None:
        pass

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             on_text: Callable[[str], None] | None = None, model: str | None = None,
             temperature: float | None = None, stream: bool | None = None,
             num_ctx: int | None = None) -> ChatResult:
        """``temperature``/``num_ctx``/``stream`` are accepted for compatibility and ignored."""
        anthropic = self._anthropic
        system, msgs = to_anthropic_messages(messages)
        params = dict(
            model=model or self.model,
            max_tokens=self.max_tokens,
            messages=msgs,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",  # a false-positive refusal re-runs on another model
        )
        if system:
            params["system"] = system
        if tools:
            params["tools"] = to_anthropic_tools(tools)

        for attempt in range(3):
            try:
                with self.client.beta.messages.stream(**params) as stream:
                    for event in stream:
                        if event.type == "text" and on_text:
                            on_text(event.text)
                    response = stream.get_final_message()
                break
            except ValueError:
                # Tool input JSON the SDK couldn't parse at all: re-issue the turn.
                if attempt == 2:
                    raise LLMError("Claude sent a tool call that couldn't be read.") from None
            except anthropic.AuthenticationError as exc:
                raise LLMError("Claude rejected the API key. Set ANTHROPIC_API_KEY "
                               "(or run: ant auth login).") from exc
            except anthropic.NotFoundError as exc:
                raise LLMError(f"Claude model not found: {params['model']}") from exc
            except anthropic.RateLimitError as exc:
                raise LLMError("Claude is rate-limiting requests; try again in a minute.") from exc
            except anthropic.APIConnectionError as exc:
                raise LLMError("Can't reach the Anthropic API. Is the internet on?") from exc
            except anthropic.APIStatusError as exc:
                raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc

        result = ChatResult()
        if response.stop_reason == "refusal":
            result.content = "I can't help with that one."
            return result
        texts = [b.text for b in response.content if b.type == "text"]
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if tool_uses and response.stop_reason == "max_tokens":
            raise LLMError("Claude's tool call was cut off (output limit reached).")
        result.content = "".join(texts).strip()
        for block in tool_uses:
            args = block.input if isinstance(block.input, dict) else {}
            result.tool_calls.append({"id": block.id, "function": {"name": block.name, "arguments": args}})
        result.raw = response.content
        return result
