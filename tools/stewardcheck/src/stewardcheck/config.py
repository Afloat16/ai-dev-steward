"""Explicit, versioned TOML task defaults; never auto-discovered or executed."""

from __future__ import annotations

import tomllib
from pathlib import Path

from .common import StewardError
from .files import read_bounded

CONFIG_LIMIT = 64 * 1024
KEYS = {"schema", "scope", "protect", "acceptance", "checks",
        "max_files", "timeout", "scan_mib"}


def load_config(root: Path, path: Path) -> dict:
    """Resolve relative paths against the project root, without following links."""
    target = path if path.is_absolute() else root / path
    if ".." in target.parts or any(parent.is_symlink() for parent in target.parents):
        raise StewardError("Config paths must not traverse parents or symbolic links.")
    try:
        data = tomllib.loads(read_bounded(target, CONFIG_LIMIT).decode("utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise StewardError("Cannot read task config; use a regular UTF-8 TOML file (at most 64 KiB).") from exc
    if type(data.get("schema")) is not int or data["schema"] != 1:
        raise StewardError("Task config requires schema = 1.")
    if data.keys() - KEYS:
        raise StewardError("Unknown task config keys; allowed: " + ", ".join(sorted(KEYS)))
    for key in ("scope", "protect", "acceptance"):
        if key in data and (not isinstance(data[key], list)
                            or any(not isinstance(value, str) for value in data[key])):
            raise StewardError(f"Config {key} must be an array of strings.")
    if "scope" in data and not data["scope"]:
        raise StewardError("Config scope cannot be empty; use ['**'] for unrestricted scope.")
    checks = data.get("checks", [])
    if (not isinstance(checks, list) or any(not isinstance(argv, list) or not argv
            or any(not isinstance(arg, str) for arg in argv) for argv in checks)):
        raise StewardError("Config checks must be an array of nonempty argv arrays.")
    for key in ("max_files", "scan_mib"):
        if key in data and type(data[key]) is not int:
            raise StewardError(f"Config {key} must be an integer.")
    if "timeout" in data and type(data["timeout"]) not in (int, float):
        raise StewardError("Config timeout must be a number.")
    result = {key: value for key, value in data.items() if key not in {"schema", "checks", "scan_mib"}}
    if "checks" in data:
        result["commands"] = checks
    if "scan_mib" in data:
        result["scan_bytes"] = data["scan_mib"] * 1024 * 1024
    # Validate values even when CLI overrides would replace them. Lazy import
    # keeps file/config helpers independent of the task workflow at import time.
    from .core import contract
    contract("Validate configuration", **result)
    return result
