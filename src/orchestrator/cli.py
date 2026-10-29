"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from orchestrator import __version__
from orchestrator.config import ConfigError, load_config

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator",
        description="Governed agentic SDLC orchestrator. Agents execute; humans approve.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project root holding config/, policy/, catalog/",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config", help="validate all configuration files and exit")
    run = commands.add_parser("run", help="run the SDLC pipeline for a requirement")
    run.add_argument("--requirement", required=True,
                     help="path to a requirement text file, or the requirement text itself")
    verify = commands.add_parser("verify-log", help="verify a run's hash-chained audit log")
    verify.add_argument("run_id")
    return parser


def _requirement_text(value: str) -> str:
    path = Path(value)
    return path.read_text(encoding="utf-8") if path.is_file() else value


def _run(root: Path, config, requirement: str) -> int:
    from orchestrator.graph.main import build_graph
    from orchestrator.human.gate import RichIO
    from orchestrator.llm.backends import AnthropicBackend
    from orchestrator.llm.costs import BudgetStop
    from orchestrator.runtime.context import create_run
    from orchestrator.runtime.driver import run_graph

    backend = AnthropicBackend(config.app.anthropic_api_key, config.policy.llm.request_timeout_s)
    ctx = create_run(root, config, RichIO(console), backend)
    console.print(f"[bold]Run {ctx.run_id}[/]  logs: {ctx.log.path}")
    try:
        result = run_graph(ctx, build_graph(ctx), {
            "run_id": ctx.run_id, "requirement_text": _requirement_text(requirement),
            "artifacts": {}, "status": "running",
        })
    except BudgetStop as exc:
        console.print(f"[yellow]Run stopped at the cost ceiling:[/] {exc}")
        return 3
    except KeyboardInterrupt:
        console.print("\n[yellow]Paused.[/] Run state is checkpointed in the run folder.")
        return 130
    status = result.get("status", "running")
    color = {"failed": "red", "ended": "yellow"}.get(status, "green")
    console.print(f"[{color}]Run {ctx.run_id}: {status}[/] {result.get('status_reason', '')}")
    for artifact_type, ref in sorted(result.get("artifacts", {}).items()):
        console.print(f"  {artifact_type}: v{ref['version']}")
    console.print(f"  estimated cost: ${ctx.costs.total_usd:.2f}")
    return 0 if status not in ("failed",) else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.root)
    except ConfigError as exc:
        console.print(f"[bold red]Refusing to start:[/] {exc}")
        return 2

    if args.command == "check-config":
        console.print("[green]Configuration valid.[/]")
        app = config.app
        console.print(f"  models: reasoning={app.model_reasoning} coding={app.model_coding}")
        stacks = ", ".join(
            f"{sid}{'' if s.validated else ' (not validated)'}"
            for sid, s in config.stacks.stacks.items()
        )
        console.print(f"  stacks: {stacks}")
        console.print(f"  NFR catalog: {', '.join(config.nfr.entries)}")
        for name, digest in config.governance_hashes.items():
            console.print(f"  {name} sha256: {digest[:16]}…")
        return 0
    if args.command == "run":
        return _run(args.root, config, args.requirement)
    if args.command == "verify-log":
        from orchestrator.observability.eventlog import EventLog

        ok, bad = EventLog(args.root / "runs" / args.run_id / "logs" / "events.jsonl").verify()
        console.print("[green]audit chain intact[/]" if ok else f"[red]chain broken at {bad}[/]")
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
