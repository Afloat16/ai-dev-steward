"""Conservative, original heuristics; not a replacement for a secret scanner."""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

# These compact patterns are maintained here, not imported from another ruleset.
_RULES = [
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?"
                               r"(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|\Z)")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("provider-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("credential-url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.I)),
    ("literal-secret", re.compile(
        r'''(?ix)\b[a-z0-9_]*(?:api[_-]?key|secret|password|access[_-]?token)\b
        ["']?\s*[:=]\s*["'](?P<value>[^"'\r\n]{8,})["']''')),
]
_PLACEHOLDERS = ("example", "placeholder", "changeme", "your_", "your-", "dummy", "${", "<")


def findings(text: str) -> list[dict]:
    result = []
    for rule, pattern in _RULES:
        for match in pattern.finditer(text):
            value = match.groupdict().get("value") or match[0]
            if rule == "literal-secret" and value.lower().startswith(_PLACEHOLDERS):
                continue
            start, end = match.span("value") if "value" in match.groupdict() else match.span()
            result.append({
                "rule": rule,
                "line": text.count("\n", 0, start) + 1,
                "id": hashlib.sha256((rule + "\0" + value).encode()).hexdigest(),
                "start": start, "end": end,
            })
    return result


def redact(text: str) -> str:
    spans = sorted((f["start"], f["end"]) for f in findings(text))
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    for start, end in reversed(merged):
        text = text[:start] + "[REDACTED]" + text[end:]
    return text


def sensitive_path(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return (name == ".env" or name.startswith(".env.")
            or name.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
            or name in {"id_rsa", "id_ed25519", "credentials", "credentials.json", ".netrc", ".npmrc"})


def test_metrics(path: str, text: str) -> dict:
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    is_test = (any(p in {"test", "tests", "__tests__"} for p in parts)
               or name.startswith("test_") or "_test." in name
               or ".test." in name or ".spec." in name)
    if not is_test:
        return {"is_test": False, "assertions": 0, "skips": 0}
    return {
        "is_test": True,
        "assertions": len(re.findall(r"\b(?:(?:assert|Assert)(?:[A-Z][A-Za-z0-9_]*|_(?:eq|ne))?|expect)\b", text)),
        "skips": len(re.findall(
            r"(?:pytest\.mark\.(?:skip|xfail)|\bskipTest\s*\(|\.(?:skip|todo)\s*\("
            r"|#\[ignore\]|\bt\.Skip\s*\(|@(?:unittest\.)?skip\b)", text)),
    }
