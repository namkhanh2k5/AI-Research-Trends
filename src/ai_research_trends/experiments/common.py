"""Small shared primitives for the venue pilot and the RQ7 dual-source ETL."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ISSN = re.compile(r"^\d{4}-\d{3}[\dX]$", re.I)


def normalize_issn(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("ISSN must be text")
    cleaned = value.strip().upper().replace("-", "")
    if len(cleaned) != 8 or not ISSN.fullmatch(cleaned[:4] + "-" + cleaned[4:]):
        raise ValueError(f"Invalid ISSN syntax: {value!r}")
    total = sum((8 - i) * int(ch) for i, ch in enumerate(cleaned[:7]))
    check = (11 - total % 11) % 11
    expected = "X" if check == 10 else str(check)
    if cleaned[-1] != expected:
        raise ValueError(f"Invalid ISSN check digit: {value!r}")
    return cleaned[:4] + "-" + cleaned[4:]


def valid_issns(values: Any) -> tuple[list[str], list[str]]:
    if not values:
        return [], []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return [], [str(values)]
    good: set[str] = set()
    bad: list[str] = []
    for value in values:
        try:
            normalized = normalize_issn(value)
            if normalized:
                good.add(normalized)
        except ValueError:
            bad.append(str(value))
    return sorted(good), bad


def atomic_bytes(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name("." + path.name + ".partial")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_manifest(path: Path, data: dict) -> None:
    temporary = path.with_name("." + path.name + ".partial")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def stable_name(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest() + ".json"
