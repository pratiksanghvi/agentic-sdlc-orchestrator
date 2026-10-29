"""HumanGate: the only way the orchestrator asks the human anything.

Every prompt renders the same way (header with the exact version, summary, single-key options),
hides options that do not apply (callers pass only applicable ones), requires a reason where the
option demands it, confirms destructive choices with a default of No, and logs the full
interaction (what was shown, the verbatim answer, how long the human took).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from rich.console import Console
from rich.panel import Panel

from orchestrator.observability.eventlog import EventLog


class GateIO(Protocol):
    def show(self, title: str, body: str) -> None: ...
    def ask(self, prompt: str) -> str: ...


class RichIO:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def show(self, title: str, body: str) -> None:
        self.console.print(Panel(body, title=title, title_align="left", expand=True))

    def ask(self, prompt: str) -> str:
        return self.console.input(f"[bold cyan]{prompt}[/] ")


@dataclass
class ScriptedIO:
    """Test double: replays answers in order and records everything shown."""

    answers: list[str]
    shown: list[tuple[str, str]] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    def show(self, title: str, body: str) -> None:
        self.shown.append((title, body))

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError("ScriptedIO ran out of answers")
        return self.answers.pop(0)


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    needs_reason: bool = False
    confirm: str | None = None  # confirmation question for destructive choices


@dataclass(frozen=True)
class Decision:
    key: str
    reason: str = ""


class HumanGate:
    def __init__(self, io: GateIO, log: EventLog, approver: str, min_reason_chars: int) -> None:
        self.io = io
        self.log = log
        self.approver = approver
        self.min_reason_chars = min_reason_chars

    def choose(
        self,
        gate: str,
        title: str,
        summary: str,
        options: list[Option],
        artifact: dict | None = None,
    ) -> Decision:
        if not options:
            raise ValueError("a gate needs at least one applicable option")
        by_key = {o.key: o for o in options}
        menu = "   ".join(f"[{o.key}] {o.label}" for o in options)
        self.io.show(title, f"{summary}\n\n{menu}")
        started = time.monotonic()
        while True:
            answer = self.io.ask(">").strip().lower()
            option = by_key.get(answer)
            if option is None:
                self.io.show("Invalid choice", f"Choose one of: {', '.join(by_key)}")
                continue
            if option.confirm and not self._yes_no(option.confirm):
                self.io.show(title, menu)
                continue
            reason = self._reason() if option.needs_reason else ""
            break
        self._log(gate, title, summary, options, artifact, option.key, reason, started)
        return Decision(option.key, reason)

    def confirm(self, gate: str, question: str) -> bool:
        started = time.monotonic()
        result = self._yes_no(question)
        self._log(gate, question, "", [], None, "y" if result else "n", "", started)
        return result

    def text(self, gate: str, question: str, default: str | None = None) -> str:
        started = time.monotonic()
        hint = f" [default: {default}]" if default else ""
        self.io.show(gate, question + hint)
        answer = self.io.ask(">").strip() or (default or "")
        self._log(gate, question, hint, [], None, answer, "", started)
        return answer

    def _yes_no(self, question: str) -> bool:
        while True:
            answer = self.io.ask(f"{question} [y/N]").strip().lower()
            if answer in ("", "n", "no"):
                return False
            if answer in ("y", "yes"):
                return True

    def _reason(self) -> str:
        while True:
            reason = self.io.ask(f"Reason (min {self.min_reason_chars} chars):").strip()
            if len(reason) >= self.min_reason_chars:
                return reason
            self.io.show("Reason required", "Please give a short reason for the audit trail.")

    def _log(self, gate, title, summary, options, artifact, answer, reason, started) -> None:
        self.log.append(
            "human_interaction",
            gate,
            title=title,
            shown=summary,
            options=[{"key": o.key, "label": o.label} for o in options],
            artifact=artifact,
            answer=answer,
            reason=reason,
            wait_ms=round((time.monotonic() - started) * 1000),
            approver=self.approver,
        )
