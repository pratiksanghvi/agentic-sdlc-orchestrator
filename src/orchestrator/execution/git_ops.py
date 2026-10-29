"""Git operations on the generated product's own repository (never this orchestrator repo).

Model: `master` holds only human-accepted releases; each run works on `run/<run_id>`;
a backup tag `pre-impl/<run_id>` is always taken before implementation; failed runs are kept as
`failed/<run_id>`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

AGENT_NAME = "orchestrator-agent"
AGENT_EMAIL = "orchestrator-agent@localhost"


class GitError(Exception):
    pass


class ProductRepo:
    def __init__(self, path: Path) -> None:
        self.path = path

    def git(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-c", f"user.name={AGENT_NAME}", "-c", f"user.email={AGENT_EMAIL}",
             "-c", "commit.gpgsign=false", *args],
            cwd=self.path, capture_output=True, text=True,
        )
        if check and proc.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    def ensure(self) -> None:
        """Create the repo with an initial commit on master if it does not exist yet."""
        self.path.mkdir(parents=True, exist_ok=True)
        if (self.path / ".git").exists():
            return
        self.git("init", "-q", "-b", "master")
        (self.path / ".gitignore").write_text("target/\n*.db\n*.sqlite\n.DS_Store\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Initialize product repository")

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def backup(self, run_id: str) -> str:
        tag = f"pre-impl/{run_id}"
        self.git("tag", "-f", tag, "master")
        return tag

    def start_run_branch(self, run_id: str) -> str:
        branch = f"run/{run_id}"
        if self.git("branch", "--list", branch):
            self.git("checkout", "-q", branch)
        else:
            self.git("checkout", "-q", "-b", branch, "master")
        return branch

    def commit_all(self, message: str) -> str | None:
        self.git("add", "-A")
        if not self.git("status", "--porcelain"):
            return None
        self.git("commit", "-q", "-m", message)
        return self.head()

    def reset_to(self, rev: str) -> None:
        """Drop uncommitted and later changes (used to undo a failed task attempt)."""
        self.git("reset", "-q", "--hard", rev)
        self.git("clean", "-q", "-fd")

    def rollback(self, run_id: str) -> str:
        """Keep the failed work as failed/<run_id> and return the workspace to master."""
        failed = f"failed/{run_id}"
        self.commit_all(f"Snapshot of failed run {run_id}")
        self.git("branch", "-f", failed, f"run/{run_id}")
        self.git("checkout", "-q", "-f", "master")
        self.git("clean", "-q", "-fd")
        return failed

    def release(self, run_id: str, version: str) -> str:
        self.git("checkout", "-q", "master")
        self.git("merge", "-q", "--no-ff", f"run/{run_id}", "-m", f"Release {version} ({run_id})")
        self.git("tag", "-a", version, "-m", f"Release {version} accepted by human ({run_id})")
        return self.head()

    def tags(self, pattern: str = "v*") -> list[str]:
        out = self.git("tag", "--list", pattern)
        return [t for t in out.splitlines() if t]
