"""Minimal command-line workflow: start, packet, check, report, doctor."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from . import __version__
from .common import StewardError, display
from .config import load_config
from .core import EXIT_CODES, Project, contract
from .render import json_output, markdown_receipt
from .secrets import redact


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="stewardcheck", description="Task-scoped change receipts for LLM coding workflows.")
    cli.add_argument("--version", action="version", version=f"stewardcheck {__version__}")
    commands = cli.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Capture the actual working tree and a task contract.")
    start.add_argument("task")
    start.add_argument("--config", type=Path, help="Explicit TOML defaults; relative to the repository root. Never auto-loaded.")
    start.add_argument("--scope", action="append", help="Allowed relative glob; repeatable. Default: **")
    start.add_argument("--protect", action="append", help="Replace default protected globs with these explicit globs.")
    start.add_argument("--accept", action="append", help="Human acceptance criterion; repeatable.")
    start.add_argument("--check", action="append", default=[], help="Command split with POSIX-style quoting; never a shell.")
    start.add_argument("--check-json", action="append", default=[], help="Exact JSON argv array; repeatable and portable.")
    start.add_argument("--max-files", type=int, help="Changed-file limit (default: 20).")
    start.add_argument("--timeout", type=float, help="Seconds per check command (default: 120).")
    start.add_argument("--scan-mib", type=int, help="Maximum bytes hashed per snapshot, in MiB (default: 256).")
    start.add_argument("--replace", action="store_true", help="Explicitly replace the previous task and receipt.")
    packet = commands.add_parser("packet", help="Print a redacted, bounded context packet; never upload it.")
    packet.add_argument("--max-bytes", type=int, default=32_000)
    packet.add_argument("--include", action="append", help="Context-only globs; does not expand allowed edit scope.")
    check = commands.add_parser("check", help="Inspect changes; run checks only with --run.")
    check.add_argument("--run", action="store_true", help="Execute the pinned commands as your user, without a sandbox.")
    report = commands.add_parser("report", help="Print the last receipt, checking whether it is stale.")
    doctor = commands.add_parser("doctor", help="Inspect prerequisites and suggest, but never run, checks.")
    for sub in (start, packet, check, report, doctor):
        sub.add_argument("--root", type=Path, default=Path.cwd(), help="Any directory inside the target Git working tree.")
    for sub in (check, report):
        sub.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return cli


def parse_checks(text_commands: list[str], json_commands: list[str]) -> list[list[str]]:
    result = []
    try:
        for command in text_commands:
            argv = shlex.split(command, posix=True)
            if any(token in {"|", "||", "&&", ";", ">", ">>", "<"} for token in argv):
                raise StewardError("Shell operators are not supported. Declare separate check commands.")
            result.append(argv)
        result.extend(json.loads(command) for command in json_commands)
    except (ValueError, json.JSONDecodeError) as exc:
        raise StewardError("Invalid check quoting or JSON. Use an argv array such as [\"python\",\"-m\",\"unittest\"].") from exc
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        project = Project(args.root)
        if args.command == "start":
            options = load_config(project.root, args.config) if args.config else {}
            for key, value in (("scope", args.scope), ("protect", args.protect),
                               ("acceptance", args.accept), ("max_files", args.max_files),
                               ("timeout", args.timeout)):
                if value is not None:
                    options[key] = value
            if args.scan_mib is not None:
                options["scan_bytes"] = args.scan_mib * 1024 * 1024
            if args.check or args.check_json:
                options["commands"] = parse_checks(args.check, args.check_json)
            policy = contract(args.task, **options)
            result = project.start(policy, replace=args.replace)
            print(json_output(result), end="")
            print("Task captured. Next: stewardcheck packet", file=sys.stderr)
            return 0
        if args.command == "packet":
            print(project.packet(args.max_bytes, args.include), end="")
            return 0
        if args.command == "doctor":
            suggestions = []
            if (project.root / "pyproject.toml").exists() or (project.root / "tests").is_dir():
                suggestions.append(["python", "-m", "unittest", "discover", "-s", "tests"])
            if (project.root / "package.json").exists():
                suggestions.append(["npm", "test"])
            if (project.root / "Cargo.toml").exists():
                suggestions.append(["cargo", "test"])
            if (project.root / "go.mod").exists():
                suggestions.append(["go", "test", "./..."])
            print(json_output({"python": sys.version.split()[0], "git_worktree": True,
                               "active_task": project.store.path.exists(),
                               "suggestions_not_executed": suggestions,
                               "note": "Choose commands appropriate for your test framework. Nothing was executed."}), end="")
            return 0
        receipt = project.check(args.run) if args.command == "check" else project.report()
        print(json_output(receipt) if args.format == "json" else markdown_receipt(receipt), end="")
        return EXIT_CODES[receipt["verdict"]]
    except BrokenPipeError:
        return 3
    except (StewardError, OSError) as exc:
        print("stewardcheck: " + redact(display(str(exc))), file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("stewardcheck: interrupted; rerun check before relying on a receipt.", file=sys.stderr)
        return 130
