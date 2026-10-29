"""Start the generated service and detect readiness from its log (stack-agnostic contract).

The orchestrator never relies on framework health endpoints: the service must print
`SERVICE_READY port=<port>` once listening. Readiness = that line + a successful TCP connect.
A process exit before readiness, or the timeout, is a failed start.
"""

from __future__ import annotations

import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from orchestrator.execution.runner import clean_env


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class StartResult:
    ok: bool
    port: int
    reason: str
    startup_ms: int
    log_tail: str
    error_lines: list[str] = field(default_factory=list)


class ServiceProcess:
    def __init__(self, command: list[str], cwd: Path, log_path: Path, port_env: str,
                 ready_regex: str, error_regex: str, extra_env: dict[str, str]) -> None:
        self.command = command
        self.cwd = cwd
        self.log_path = log_path
        self.port_env = port_env
        self.ready = re.compile(ready_regex)
        self.error = re.compile(error_regex)
        self.extra_env = extra_env
        self.proc: subprocess.Popen | None = None
        self._lines: list[str] = []
        self._ready_port: int | None = None

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        with self.log_path.open("a", encoding="utf-8") as log:
            for line in self.proc.stdout:
                log.write(line)
                log.flush()
                self._lines.append(line.rstrip("\n"))
                match = self.ready.search(line.strip())
                if match:
                    self._ready_port = int(match.group(1))

    def start(self, timeout_s: int) -> StartResult:
        port = free_port()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        env = clean_env({self.port_env: str(port), **self.extra_env})
        started = time.monotonic()
        self.proc = subprocess.Popen(self.command, cwd=self.cwd, env=env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()
        reason = "timed out waiting for SERVICE_READY"
        ok = False
        while time.monotonic() - started < timeout_s:
            if self._ready_port is not None:
                if _connectable(self._ready_port):
                    ok, reason = True, "ready"
                    break
            elif self.proc.poll() is not None:
                time.sleep(0.3)  # let the pump drain the last lines
                reason = f"process exited with code {self.proc.returncode} before SERVICE_READY"
                break
            time.sleep(0.2)
        if ok and self._ready_port != port:
            reason = f"ready on port {self._ready_port}, expected {port} from {self.port_env}"
            ok = False
        elapsed = round((time.monotonic() - started) * 1000)
        if not ok:
            self.stop()
        return StartResult(ok, port, reason, elapsed, self.tail(),
                           [ln for ln in self._lines if self.error.search(ln)][:20])

    def tail(self, lines: int = 100) -> str:
        return "\n".join(self._lines[-lines:])

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)


def _connectable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False
