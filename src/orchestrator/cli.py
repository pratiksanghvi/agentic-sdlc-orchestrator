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
    return parser


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
    return 1


if __name__ == "__main__":
    sys.exit(main())
