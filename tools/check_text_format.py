#!/usr/bin/env python3
"""Check basic text-file formatting for tracked source and docs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cs",
    ".css",
    ".csproj",
    ".html",
    ".js",
    ".json",
    ".manifest",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}


def main() -> int:
    errors: list[str] = []
    for path in iter_tracked_text_files():
        check_file(path, errors)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("text format check passed")
    return 0


def iter_tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        path = ROOT / line
        if path.suffix.lower() in TEXT_SUFFIXES:
            paths.append(path)
    return sorted(paths)


def check_file(path: Path, errors: list[str]) -> None:
    relative = path.relative_to(ROOT)
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        errors.append(f"{relative}: missing final newline")

    for line_number, line in enumerate(data.splitlines(), start=1):
        if line.rstrip(b" \t") != line:
            errors.append(f"{relative}:{line_number}: trailing whitespace")


if __name__ == "__main__":
    raise SystemExit(main())
