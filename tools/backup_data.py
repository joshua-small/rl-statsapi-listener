#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import tarfile
from datetime import datetime
from pathlib import Path


DEFAULT_DATA_DIR = Path(".data")
DEFAULT_OUTPUT_DIR = Path(".local/backups")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_backup_files(data_dir: Path, include_logs: bool) -> list[Path]:
    files: list[Path] = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        if not include_logs and path.suffix == ".log":
            continue
        files.append(path)
    return files


def build_manifest(data_dir: Path, files: list[Path]) -> str:
    lines = ["sha256  bytes  path"]
    for path in files:
        rel_path = path.relative_to(data_dir).as_posix()
        lines.append(f"{sha256_file(path)}  {path.stat().st_size}  {rel_path}")
    return "\n".join(lines) + "\n"


def backup_data(data_dir: Path, output_dir: Path, include_logs: bool) -> Path:
    data_dir = data_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()

    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")
    if not data_dir.is_dir():
        raise NotADirectoryError(f"Data path is not a directory: {data_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = output_dir / f"rl-statsapi-data-{timestamp}.tar.gz"

    files = iter_backup_files(data_dir, include_logs=include_logs)
    manifest = build_manifest(data_dir, files)

    with tarfile.open(archive_path, "w:gz") as archive:
        for path in files:
            archive.add(path, arcname=f".data/{path.relative_to(data_dir).as_posix()}")
        manifest_bytes = manifest.encode("utf-8")
        info = tarfile.TarInfo(".data/MANIFEST.sha256")
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now().timestamp())
        archive.addfile(info, io.BytesIO(manifest_bytes))

    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up local RL StatsAPI .data files")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Data directory to back up (default: .data)")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for backup archives (default: .local/backups)",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Include .log files. This can make the backup much larger.",
    )
    args = parser.parse_args()

    archive_path = backup_data(Path(args.data_dir), Path(args.output_dir), include_logs=args.include_logs)
    print(f"Created backup: {archive_path}")


if __name__ == "__main__":
    main()
