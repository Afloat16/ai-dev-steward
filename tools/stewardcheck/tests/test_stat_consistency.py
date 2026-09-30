"""Stat representation differences must not mask actual file changes."""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from stewardcheck.common import StewardError
from stewardcheck.files import read_bounded


FIELDS = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")


def altered(info, **changes):
    values = {name: getattr(info, name) for name in FIELDS}
    values.update(changes)
    return SimpleNamespace(**values)


class StatConsistencyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "record.json"
        self.path.write_bytes(b"abc")

    def test_stable_cross_api_ctime_difference_is_allowed(self):
        original = os.fstat
        def descriptor_stat(fd):
            info = original(fd)
            return altered(info, st_ctime_ns=info.st_ctime_ns + 123456789)
        with patch("stewardcheck.files.os.fstat", side_effect=descriptor_stat):
            self.assertEqual(read_bounded(self.path, 3), b"abc")

    def test_stable_cross_api_permission_difference_is_allowed(self):
        original = os.fstat
        def descriptor_stat(fd):
            info = original(fd)
            return altered(info, st_mode=info.st_mode ^ stat.S_IXUSR)
        with patch("stewardcheck.files.os.fstat", side_effect=descriptor_stat):
            self.assertEqual(read_bounded(self.path, 3), b"abc")

    def test_descriptor_metadata_change_is_rejected(self):
        with self.path.open("rb") as stream:
            info = os.fstat(stream.fileno())
        for field in ("st_ctime_ns", "st_mode", "st_mtime_ns"):
            with self.subTest(field=field):
                changed = altered(info, **{field: getattr(info, field) + 1})
                with patch("stewardcheck.files.os.fstat", side_effect=[info, changed]):
                    with self.assertRaises(StewardError):
                        read_bounded(self.path, 3)

    def test_path_metadata_change_is_rejected(self):
        info = self.path.lstat()
        for field in ("st_ctime_ns", "st_mode", "st_mtime_ns"):
            with self.subTest(field=field):
                changed = altered(info, **{field: getattr(info, field) + 1})
                with patch.object(Path, "lstat", side_effect=[info, changed]):
                    with self.assertRaises(StewardError):
                        read_bounded(self.path, 3)

    def test_cross_api_mtime_difference_is_rejected(self):
        original = os.fstat
        def descriptor_stat(fd):
            info = original(fd)
            return altered(info, st_mtime_ns=info.st_mtime_ns + 1)
        with patch("stewardcheck.files.os.fstat", side_effect=descriptor_stat):
            with self.assertRaises(StewardError):
                read_bounded(self.path, 3)

    def test_cross_api_size_difference_is_rejected(self):
        original = os.fstat
        def descriptor_stat(fd):
            return altered(original(fd), st_size=2)
        with patch("stewardcheck.files.os.fstat", side_effect=descriptor_stat):
            with self.assertRaises(StewardError):
                read_bounded(self.path, 3)

    def test_opened_non_regular_file_is_rejected(self):
        original = os.fstat
        def descriptor_stat(fd):
            return altered(original(fd), st_mode=stat.S_IFIFO | 0o600)
        with patch("stewardcheck.files.os.fstat", side_effect=descriptor_stat):
            with self.assertRaises(StewardError):
                read_bounded(self.path, 3)


if __name__ == "__main__":
    unittest.main()
