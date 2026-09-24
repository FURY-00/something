"""Tools are the things Jarvis can *do*.

Each tool is a plain Python function decorated with ``@tool``. The decorator
turns the function into a JSON schema the language model can read, and the
model decides when to call it. To teach Jarvis a new skill, write a function
in one of the modules in this package (or a new module listed in
``TOOL_MODULES``) and decorate it. See README "Adding your own abilities".
"""

from __future__ import annotations

import importlib
import inspect
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)

TOOL_MODULES = [
    "jarvis.tools.system",
    "jarvis.tools.web",
    "jarvis.tools.control",
    "jarvis.tools.writing",
    "jarvis.tools.knowledge",
    "jarvis.tools.memory",
]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    required: list[str]
    func: Callable[..., Any]
    # Optional check run at startup. Returning False hides the tool from the model.
    available: Callable[[Any], bool] | None = None

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


_REGISTRY: dict[str, Tool] = {}


def tool(
    description: str,
    params: dict[str, dict] | None = None,
    *,
    name: str | None = None,
    available: Callable[[Any], bool] | None = None,
):
    """Register a function as a tool.

    ``params`` maps argument names to JSON-schema snippets, e.g.
    ``{"url": {"type": "string", "description": "Website address"}}``.
    Arguments without a default value in the function signature are required.
    The function's first argument is always the :class:`ToolContext`.
    Tools that do something risky should call ``ctx.confirm(question)`` first.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)
        arg_names = list(sig.parameters)[1:]  # skip ctx
        properties = params or {}
        missing = [a for a in arg_names if a not in properties]
        if missing:
            raise ValueError(f"Tool {func.__name__} has undocumented params: {missing}")
        required = [
            a for a in arg_names if sig.parameters[a].default is inspect.Parameter.empty
        ]
        tool_name = name or func.__name__
        _REGISTRY[tool_name] = Tool(
            name=tool_name,
            description=description,
            parameters=properties,
            required=required,
            func=func,
            available=available,
        )
        return func

    return decorator


def _coerce(value: Any, spec: dict) -> Any:
    """Small models sometimes send "3" for 3 or "true" for True. Fix that."""
    kind = spec.get("type")
    try:
        if kind == "integer" and not isinstance(value, bool):
            return int(float(value))
        if kind == "number" and not isinstance(value, bool):
            return float(value)
        if kind == "boolean" and isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1", "y", "on")
        if kind == "string" and not isinstance(value, str):
            return str(value)
    except (TypeError, ValueError):
        pass
    return value


class ToolRegistry:
    """The set of tools enabled for this session."""

    def __init__(self, ctx, tools: dict[str, Tool] | None = None) -> None:
        self.ctx = ctx
        if tools is None:
            for module in TOOL_MODULES:
                importlib.import_module(module)
            tools = _REGISTRY
        self.tools: dict[str, Tool] = {}
        for t in tools.values():
            try:
                ok = t.available(ctx) if t.available else True
            except Exception:  # noqa: BLE001 - a broken check just hides the tool
                ok = False
            if ok:
                self.tools[t.name] = t

    def names(self) -> list[str]:
        return list(self.tools)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self.tools.values()]

    def call(self, name: str, args: dict | None) -> str:
        t = self.tools.get(name)
        if t is None:
            return f"Error: there is no tool called '{name}'."
        args = dict(args or {})
        clean = {k: _coerce(v, t.parameters[k]) for k, v in args.items() if k in t.parameters}
        missing = [r for r in t.required if r not in clean]
        if missing:
            return f"Error: missing required argument(s) {missing} for {name}."
        enum_errors = [
            f"{k} must be one of {t.parameters[k]['enum']}"
            for k, v in clean.items()
            if "enum" in t.parameters[k] and v not in t.parameters[k]["enum"]
        ]
        if enum_errors:
            return "Error: " + "; ".join(enum_errors)

        log.info("tool %s(%s)", name, clean)
        try:
            result = t.func(self.ctx, **clean)
        except Exception as exc:  # noqa: BLE001 - report failures back to the model
            log.debug(traceback.format_exc())
            return f"Error while running {name}: {exc}"
        return "Done." if result is None else str(result)
