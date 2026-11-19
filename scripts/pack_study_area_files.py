"""Zip the publication files whose coverage touches a GWR study area.

Reads catalogue/coverage_by_file.csv (written by build_coverage.py), keeps the
rows with in_study_area == True, optionally narrowed by --scope, verifies each
file's SHA-256 against the catalogue and writes the files into a zip keeping the
``downloaded_data/...`` tree. The selected catalogue rows are included in the
archive as ``coverage_by_file.csv`` so the zip is self-describing.

Usage::

    python scripts/pack_study_area_files.py
    python scripts/pack_study_area_files.py --scope district block --output downloaded_data/district_reports.zip
"""

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_BY_FILE = ROOT / "catalogue" / "coverage_by_file.csv"
DEFAULT_OUTPUT = ROOT / "downloaded_data" / "study_area_publications.zip"
SCOPES = ("national", "state", "district", "block")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="zip path (default: %(default)s)")
    parser.add_argument("--scope", nargs="+", choices=SCOPES, default=list(SCOPES),
                        help="keep only files whose finest scope is one of these (default: all)")
    args = parser.parse_args()

    table = pd.read_csv(COVERAGE_BY_FILE, dtype=str, keep_default_na=False)
    selected = table[table["in_study_area"].eq("True") & table["scope"].isin(args.scope)]
    if selected.empty:
        sys.exit("no files selected")

    missing = [p for p in selected["local_path"] if not (ROOT / p).is_file()]
    if missing:
        sys.exit("files not found on disk: " + ", ".join(missing))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in selected.itertuples():
            path = ROOT / row.local_path
            if sha256_of(path) != row.sha256:
                sys.exit(f"{row.local_path} does not match the sha256 recorded in files.csv")
            archive.write(path, arcname=row.local_path)
            total += path.stat().st_size
        archive.writestr("coverage_by_file.csv", selected.to_csv(index=False))

    print(f"{len(selected)} files ({total / 1e6:.1f} MB) -> {args.output.relative_to(ROOT)} "
          f"({args.output.stat().st_size / 1e6:.1f} MB)")
    print(selected.groupby(["item_type", "scope"]).size().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
