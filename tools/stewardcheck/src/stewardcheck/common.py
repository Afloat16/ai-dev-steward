"""Small, deterministic primitives shared by the CLI and library."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any


class StewardError(Exception):
    """An actionable input, repository, or resource-limit error."""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def display(value: str) -> str:
    """Escape terminal controls, including Unicode directional overrides."""
    return re.sub(
        r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]",
        lambda m: f"\\u{ord(m[0]):04x}", value,
    )


def normalize_pattern(value: str) -> str:
    value = value.removeprefix("./")
    if value.endswith("/"):
        value += "**"
    parts = value.split("/")
    if (not value or len(value) > 300 or "\\" in value or ":" in value
            or value.startswith(("/", "!")) or any(p in ("", ".", "..") for p in parts)):
        raise StewardError("Patterns must be relative POSIX globs, without '..' or negation.")
    return value


def matches(path: str, pattern: str) -> bool:
    """Root-anchored glob: '*' stays in a segment; '**' spans zero or more."""
    parts, pats = tuple(PurePosixPath(path).parts), tuple(pattern.split("/"))

    @lru_cache(maxsize=None)
    def visit(i: int, j: int) -> bool:
        if j == len(pats):
            return i == len(parts)
        if pats[j] == "**":
            return visit(i, j + 1) or (i < len(parts) and visit(i + 1, j))
        return i < len(parts) and fnmatch.fnmatchcase(parts[i], pats[j]) and visit(i + 1, j + 1)

    return visit(0, 0)


def any_match(path: str, patterns: list[str]) -> bool:
    return any(matches(path, pattern) for pattern in patterns)
