"""Explicit argv execution with bounded capture and best-effort child cleanup."""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from .common import display
from .secrets import redact

CAPTURE_BYTES = 32 * 1024
OUTPUT_LIMIT = 8 * 1024 * 1024


def _stop(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        elif proc.poll() is None:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


def run_command(root: Path, argv: list[str], timeout: float) -> dict:
    started = time.monotonic()
    result = {"argv": [redact(display(a)) for a in argv], "exit_code": None,
              "status": "error", "duration_seconds": 0.0, "output": ""}
    executable = shutil.which(argv[0])
    if os.name == "nt" and (argv[0].lower().endswith((".cmd", ".bat"))
                            or (executable and executable.lower().endswith((".cmd", ".bat")))):
        result["output"] = "Windows batch wrappers are not supported; invoke the interpreter and script directly."
        return result
    try:
        proc = subprocess.Popen(argv, cwd=root, shell=False, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=(os.name == "posix"))
    except OSError:
        result["output"] = "Could not start this executable; verify the command and PATH."
        return result
    chunks = bytearray()
    counter = [0]
    output_hash = hashlib.sha256()
    too_much = threading.Event()

    def consume() -> None:
        assert proc.stdout is not None
        try:
            while chunk := proc.stdout.read(8192):
                counter[0] += len(chunk)
                output_hash.update(chunk)
                room = CAPTURE_BYTES - len(chunks)
                if room > 0:
                    chunks.extend(chunk[:room])
                if counter[0] > OUTPUT_LIMIT:
                    too_much.set()
                    _stop(proc)
        finally:
            proc.stdout.close()

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=timeout)
        result.update(exit_code=code, status="passed" if code == 0 else "failed")
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        _stop(proc)
        proc.wait(timeout=5)
    finally:
        _stop(proc)  # End lingering POSIX children even after the parent exited.
        proc.wait(timeout=5)
        reader.join(timeout=2)
    if reader.is_alive():
        result["status"] = "incomplete-output"
    if too_much.is_set():
        result["status"] = "output-limit"
    raw = bytes(chunks)
    if counter[0] > CAPTURE_BYTES:
        raw = raw.rsplit(b"\n", 1)[0] if b"\n" in raw else b""
    # Preserve line breaks for reading, but neutralize terminal control sequences.
    result["output"] = "\n".join(display(line) for line in redact(raw.decode("utf-8", errors="replace")).splitlines())
    result.update(duration_seconds=round(time.monotonic() - started, 3),
                  output_bytes=counter[0], output_truncated=counter[0] > CAPTURE_BYTES,
                  output_sha256=output_hash.hexdigest())
    return result
