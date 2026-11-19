#!/usr/bin/env python3
"""Copy the CGWB PDFs that fall inside the study areas into a subfolder.

Scans a root folder recursively, matches files by name against
``catalogue/coverage_by_file.csv`` (rows with ``in_study_area == True``) and
copies the matches into ``<root>/<subfolder>/<category>/``, where category is
``papers``, ``jharkhand``, ``odisha`` or ``national`` as recorded in the
catalogue (``--layout tree`` keeps the subfolder layout found under root,
``--layout flat`` puts everything in one folder). Only the Python standard
library is required, so it runs on a stock macOS Python.

Usage:
    python3 copy_study_area_files.py /path/to/pdfs
    python3 copy_study_area_files.py /path/to/pdfs --csv coverage_by_file.csv
    python3 copy_study_area_files.py /path/to/pdfs --layout tree --verify --dry-run
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "catalogue" / "coverage_by_file.csv"
DEFAULT_SUBFOLDER = "study_area"


def load_targets(csv_path: Path) -> dict[str, dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = csv.DictReader(fh)
        targets: dict[str, dict[str, str]] = {}
        for row in rows:
            if row.get("in_study_area", "").strip().lower() != "true":
                continue
            name = row.get("original_filename") or Path(row["local_path"]).name
            targets[name] = row
    return targets


def category_of(row: dict[str, str]) -> str:
    """papers / jharkhand / odisha / national, taken from the catalogue path."""
    parts = Path(row["local_path"]).parts
    if "papers" in parts:
        return "papers"
    if "cgwb" in parts:
        idx = parts.index("cgwb")
        if idx + 2 < len(parts):
            return parts[idx + 1]
    return (row.get("scope") or "other").lower()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="Folder that contains the PDFs (searched recursively)")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to coverage_by_file.csv")
    ap.add_argument("--subfolder", default=DEFAULT_SUBFOLDER, help="Destination subfolder name inside root")
    ap.add_argument(
        "--layout",
        choices=("category", "tree", "flat"),
        default="category",
        help="category: <subfolder>/<papers|jharkhand|odisha|national>/ (default); "
        "tree: mirror the source subfolders; flat: everything in <subfolder>/",
    )
    ap.add_argument("--verify", action="store_true", help="Check SHA-256 against the catalogue before copying")
    ap.add_argument("--move", action="store_true", help="Move instead of copy")
    ap.add_argument("--dry-run", action="store_true", help="Only report what would happen")
    args = ap.parse_args()

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 1
    if not args.csv.is_file():
        print(f"error: catalogue not found at {args.csv}", file=sys.stderr)
        return 1

    targets = load_targets(args.csv)
    dest_root = root / args.subfolder
    found: dict[str, Path] = {}
    skipped_hash: list[Path] = []

    for path in root.rglob("*.pdf"):
        if dest_root in path.parents or not path.is_file():
            continue
        row = targets.get(path.name)
        if row is None:
            continue
        if args.verify and row.get("sha256") and sha256_of(path) != row["sha256"]:
            skipped_hash.append(path)
            continue
        found.setdefault(path.name, path)

    action = "move" if args.move else "copy"
    for name, src in sorted(found.items()):
        if args.layout == "category":
            dest = dest_root / category_of(targets[name]) / src.name
        elif args.layout == "tree":
            dest = dest_root / src.relative_to(root)
        else:
            dest = dest_root / src.name
        print(f"{action}: {src.relative_to(root)} -> {dest.relative_to(root)}")
        if args.dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if args.move:
            shutil.move(str(src), str(dest))
        else:
            shutil.copy2(src, dest)

    missing = sorted(set(targets) - set(found))
    print(f"\n{len(found)}/{len(targets)} study-area files found under {root}")
    if skipped_hash:
        print(f"{len(skipped_hash)} skipped due to SHA-256 mismatch:")
        for p in skipped_hash:
            print(f"  {p.relative_to(root)}")
    if missing:
        print(f"{len(missing)} not found:")
        for name in missing:
            print(f"  {name}  ({targets[name].get('title', '')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
