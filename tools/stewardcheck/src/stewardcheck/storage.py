"""One local task record per Git working tree; no source files are persisted."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .common import StewardError, digest

STATE_LIMIT = 64 * 1024 * 1024


class Store:
    def __init__(self, gitdir: Path, root: Path):
        self.directory = gitdir / "stewardcheck"
        self.path = self.directory / "active.json"
        self.root = root

    @contextmanager
    def locked(self) -> Iterator[None]:
        if self.directory.is_symlink():
            raise StewardError("Refusing a symlinked StewardCheck state directory.")
        self.directory.mkdir(mode=0o700, parents=False, exist_ok=True)
        lock = self.directory / "lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise StewardError("Another operation holds the task lock. After a crash, remove the lock only when no operation is running.") from exc
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(str(os.getpid()))
            yield
        finally:
            lock.unlink(missing_ok=True)

    def load(self) -> dict:
        if self.path.is_symlink():
            raise StewardError("Refusing a symlinked task record.")
        try:
            fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError as exc:
            raise StewardError('No active task. Run: stewardcheck start "Describe the change"') from exc
        try:
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > STATE_LIMIT:
                    raise StewardError("Task record is not a bounded regular file.")
                state = json.load(stream)
            if (state["schema"] != 1 or state["root"] != str(self.root)
                    or state["contract_hash"] != digest(state["contract"])
                    or state["baseline"]["fingerprint"] != digest({k: v for k, v in state["baseline"].items() if k != "fingerprint"})):
                raise StewardError("Task record is incompatible, moved, or damaged. Start a new task explicitly.")
            return state
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise StewardError("Task record is invalid. Start a new task with --replace after reviewing the workspace.") from exc

    def save(self, state: dict) -> None:
        content = (json.dumps(state, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode()
        if len(content) > STATE_LIMIT:
            raise StewardError("Task record exceeds the storage limit.")
        fd, name = tempfile.mkstemp(prefix=".write-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
