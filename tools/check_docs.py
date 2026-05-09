#!/usr/bin/env python3
"""Validate documentation examples and internal Markdown links."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = (
    "README.md",
    "docs",
    "tests/README.md",
    "integrations/windows-webview-host/README.md",
)
FLAG_RE = re.compile(r"--[A-Za-z][A-Za-z0-9-]*")
LISTENER_COMMAND_RE = re.compile(r"(?<![\w-])(?:listen\.py|rl-statsapi-listen)(?![\w-])")
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def main() -> int:
    markdown_files = list(iter_markdown_files())
    errors: list[str] = []

    supported_flags = get_listener_flags()
    command_lines = check_listener_command_flags(markdown_files, supported_flags, errors)
    link_count = check_internal_markdown_links(markdown_files, errors)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "docs check passed: "
        f"{command_lines} listener command lines, {link_count} internal Markdown links"
    )
    return 0


def iter_markdown_files() -> list[Path]:
    files: set[Path] = set()
    for doc_path in DOC_PATHS:
        path = ROOT / doc_path
        if path.is_dir():
            files.update(path.rglob("*.md"))
        elif path.exists():
            files.add(path)
    return sorted(files)


def get_listener_flags() -> set[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "listen.py"), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(FLAG_RE.findall(result.stdout))


def check_listener_command_flags(
    markdown_files: list[Path],
    supported_flags: set[str],
    errors: list[str],
) -> int:
    command_lines = 0
    for path in markdown_files:
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not LISTENER_COMMAND_RE.search(line):
                continue
            command_lines += 1
            for flag in FLAG_RE.findall(line):
                if flag not in supported_flags:
                    errors.append(
                        f"{relative}:{line_number}: unknown listen.py flag {flag!r}"
                    )
    return command_lines


def check_internal_markdown_links(markdown_files: list[Path], errors: list[str]) -> int:
    link_count = 0
    for path in markdown_files:
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                target = match.group(1).strip().split()[0].strip("<>")
                if is_external_link(target):
                    continue
                link_count += 1
                validate_internal_link(path, relative, line_number, target, errors)
    return link_count


def is_external_link(target: str) -> bool:
    parsed = urlsplit(target)
    return bool(parsed.scheme or parsed.netloc)


def validate_internal_link(
    source_path: Path,
    source_relative: Path,
    line_number: int,
    target: str,
    errors: list[str],
) -> None:
    parsed = urlsplit(target)
    target_path = source_path if not parsed.path else source_path.parent / unquote(parsed.path)
    target_path = target_path.resolve()

    try:
        target_path.relative_to(ROOT)
    except ValueError:
        errors.append(f"{source_relative}:{line_number}: link escapes repository: {target}")
        return

    if not target_path.exists():
        errors.append(f"{source_relative}:{line_number}: missing link target: {target}")
        return

    if parsed.fragment and target_path.suffix.lower() == ".md":
        anchors = markdown_anchors(target_path)
        fragment = unquote(parsed.fragment)
        if fragment not in anchors:
            errors.append(
                f"{source_relative}:{line_number}: missing heading anchor "
                f"{fragment!r} in {target_path.relative_to(ROOT)}"
            )


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue

        slug = github_heading_slug(match.group(2))
        duplicate_count = counts.get(slug, 0)
        counts[slug] = duplicate_count + 1
        if duplicate_count:
            slug = f"{slug}-{duplicate_count}"
        anchors.add(slug)
    return anchors


def github_heading_slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


if __name__ == "__main__":
    raise SystemExit(main())
