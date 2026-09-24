"""Shared state handed to every tool."""

from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger(__name__)


class ToolContext:
    def __init__(
        self,
        config,
        llm=None,
        memory=None,
        say: Callable[[str], None] | None = None,
        ask_yes_no: Callable[[str], bool] | None = None,
        announce: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        self.memory = memory
        self._say = say or (lambda text: print(f"{config.assistant_name}: {text}"))
        self._ask_yes_no = ask_yes_no or (lambda question: False)
        self._announce = announce or self._say
        # Scratch space tools can use to remember things between calls,
        # e.g. which social media feed is currently open.
        self.state: dict = {}

    def say(self, text: str) -> None:
        """Speak a short progress message right away ("Working on it, sir.")."""
        self._say(text)

    def announce(self, text: str) -> None:
        """Speak something out of the blue, e.g. when a timer goes off."""
        self._announce(text)

    def confirm(self, question: str) -> bool:
        """Ask the user a yes/no question before doing something risky."""
        if not self.config.safety.confirm_dangerous:
            return True
        answer = self._ask_yes_no(question)
        log.info("confirm %r -> %s", question, answer)
        return answer
