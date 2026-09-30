"""Bounded regular-file reads for local configuration and state records."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .common import StewardError


def _signature(info: os.stat_result) -> tuple:
    """Full consistency signature for two results from the same stat API."""
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _file_identity(info: os.stat_result) -> tuple:
    """Fields comparable between pathname and descriptor queries."""
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode),
            info.st_size, info.st_mtime_ns)


def read_bounded(path: Path, limit: int) -> bytes:
    """Reject links/special files and changes during a bounded read.

    O_NONBLOCK prevents a POSIX FIFO substituted between lstat and open from
    hanging before fstat. This is a local race check, not a filesystem sandbox.
    """
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise StewardError("Expected a bounded regular file, not a link, directory, or special file.")
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise StewardError("File changed while opening it; stop concurrent writers and retry.")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(data) > limit:
        raise StewardError("File exceeds the read limit.")
    # Windows pathname stat and fstat can differ in ctime semantics and
    # synthesized permission bits. Compare those only within the same API;
    # retain cross-API file identity, size, type, and modification-time checks.
    if (_signature(before) != _signature(path.lstat())
            or _signature(opened) != _signature(after)
            or _file_identity(before) != _file_identity(opened)
            or len(data) != opened.st_size):
        raise StewardError("File changed while reading it; stop concurrent writers and retry.")
    return data
