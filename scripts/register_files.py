"""Register original files under catalogue/files.csv with SHA-256 checksums.

Every source in catalogue/sources.csv owns the files matched by its
``local_globs`` (default ``raw/<source_id>/**/*``). Files found under ``raw/``
or ``downloaded_data/`` that no source claims, or that two sources claim, stop
the run so nothing is silently skipped or double counted. Already registered
files are re-hashed; a changed checksum is reported as an error because raw
originals must never be modified in place.
"""

import argparse
import csv
import hashlib
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "catalogue" / "sources.csv"
FILES = ROOT / "catalogue" / "files.csv"
SCAN_ROOTS = ("raw", "downloaded_data")
FILE_COLUMNS = (
    "file_id", "source_id", "original_filename", "local_path", "format",
    "size_bytes", "sha256", "retrieved_on", "filters_applied", "notes",
)
KNOWN_FORMATS = {
    "pdf", "csv", "xlsx", "xls", "zip", "geojson", "shp", "gpkg", "html", "json", "txt", "docx",
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def claimed_files(sources: list[dict[str, str]]) -> dict[Path, str]:
    """Map each matched file to its owning source_id; error on double claims."""
    owner: dict[Path, str] = {}
    for source in sources:
        source_id = source["source_id"]
        globs = source.get("local_globs", "").strip() or f"raw/{source_id}/**/*"
        for pattern in globs.split(";"):
            for path in sorted(ROOT.glob(pattern.strip())):
                if not path.is_file() or path.name.startswith("."):
                    continue
                if path in owner and owner[path] != source_id:
                    sys.exit(f"{path.relative_to(ROOT)} claimed by both {owner[path]} and {source_id}")
                owner[path] = source_id
    return owner


def unclaimed_files(owner: dict[Path, str]) -> list[Path]:
    return [
        path
        for scan_root in SCAN_ROOTS
        for path in sorted((ROOT / scan_root).rglob("*"))
        if path.is_file() and not path.name.startswith(".") and path not in owner
    ]


def file_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix if suffix in KNOWN_FORMATS else "other"


def retrieved_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--retrieved-on",
        help="Retrieval date (YYYY-MM-DD) for newly registered files; defaults to file modification date",
    )
    parser.add_argument(
        "--filters",
        default="unknown",
        help="filters_applied text for newly registered files (default: unknown)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report without writing files.csv")
    args = parser.parse_args()
    if args.retrieved_on:
        date.fromisoformat(args.retrieved_on)

    sources = read_rows(SOURCES)
    if not sources:
        sys.exit(f"{SOURCES.relative_to(ROOT)} is missing or empty")
    owner = claimed_files(sources)
    stray = unclaimed_files(owner)
    if stray:
        listing = "\n  ".join(str(p.relative_to(ROOT)) for p in stray)
        sys.exit(f"Files not claimed by any source in sources.csv; add a source or local_globs:\n  {listing}")

    existing = read_rows(FILES)
    by_path = {row["local_path"]: row for row in existing}
    next_number = 1 + max((int(row["file_id"][1:]) for row in existing), default=0)
    added: list[dict[str, str]] = []
    changed: list[str] = []
    missing = [p for p in by_path if not (ROOT / p).exists()]

    for path, source_id in sorted(owner.items()):
        rel = path.relative_to(ROOT).as_posix()
        digest = sha256_of(path)
        if rel in by_path:
            if by_path[rel]["sha256"] != digest:
                changed.append(rel)
            continue
        added.append({
            "file_id": f"F{next_number:04d}",
            "source_id": source_id,
            "original_filename": path.name,
            "local_path": rel,
            "format": file_format(path),
            "size_bytes": str(path.stat().st_size),
            "sha256": digest,
            "retrieved_on": args.retrieved_on or retrieved_date(path),
            "filters_applied": args.filters,
            "notes": "",
        })
        next_number += 1

    for row in added:
        print(f"new  {row['file_id']}  {row['source_id']:<20} {row['local_path']}")
    for rel in missing:
        print(f"missing on disk  {rel}")
    print(f"{len(existing)} registered, {len(added)} new, {len(changed)} changed, {len(missing)} missing")

    if changed:
        listing = "\n  ".join(changed)
        sys.exit(f"Checksum changed for registered originals; restore them or register a new copy:\n  {listing}")
    if args.dry_run or not added:
        return 0
    with FILES.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(existing + added)
    return 0


if __name__ == "__main__":
    sys.exit(main())
