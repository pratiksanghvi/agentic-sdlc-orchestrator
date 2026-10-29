"""Run allow-listed commands for generated code in a clean environment.

Generated code is untrusted: child processes get a minimal environment (never the API key or
other secrets), run inside the workspace, and are killed at the policy timeout. This reduces
risk but is not a sandbox (documented limitation).
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_PASS_THROUGH = ("PATH", "HOME", "JAVA_HOME", "MAVEN_HOME", "M2_HOME", "LANG", "LC_ALL", "TMPDIR",
                 "GOPATH", "GOCACHE", "GOMODCACHE")


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASS_THROUGH if k in os.environ}
    env.update(extra or {})
    return env


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    output: str
    duration_ms: int
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def tail(self, lines: int = 80) -> str:
        return "\n".join(self.output.splitlines()[-lines:])


def run(command: list[str], cwd: Path, timeout_s: int,
        env: dict[str, str] | None = None) -> CommandResult:
    started = time.monotonic()
    try:
        proc = subprocess.run(command, cwd=cwd, env=clean_env(env), capture_output=True,
                              text=True, timeout=timeout_s)
        output = (proc.stdout or "") + (proc.stderr or "")
        return CommandResult(command, proc.returncode, output,
                             round((time.monotonic() - started) * 1000))
    except subprocess.TimeoutExpired as exc:
        output = _text(exc.stdout) + _text(exc.stderr)
        return CommandResult(command, -1, output + f"\n[timed out after {timeout_s}s]",
                             round((time.monotonic() - started) * 1000), timed_out=True)
    except FileNotFoundError as exc:
        return CommandResult(command, 127, f"command not found: {exc}", 0)


def _text(value) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
