"""Filter the merged NWDP files in data/nwdp/ to the locations listed in a CSV.

The locations file needs ``Latitude`` and ``Longitude`` columns. Coordinates
are compared after rounding both sides to five decimals (about one metre),
because location lists are typically exported with fewer decimals than the
eight-decimal NWDP coordinates. Rows are copied unchanged into
``data/nwdp/<name>/<group>.csv``; groups with no matching rows produce no
file. ``filter_log.csv`` records rows kept per group and any locations that
matched nothing.
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERGED_DIR = ROOT / "data" / "nwdp"
DECIMALS = 5
Coordinate = tuple[float, float]


def rounded(latitude: str, longitude: str) -> Coordinate | None:
    try:
        return round(float(latitude), DECIMALS), round(float(longitude), DECIMALS)
    except ValueError:
        return None


def load_locations(path: Path) -> set[Coordinate]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"Latitude", "Longitude"} - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"{path}: missing columns {sorted(missing)}")
        locations = set()
        for row in reader:
            coordinate = rounded(row["Latitude"], row["Longitude"])
            if coordinate is None:
                sys.exit(f"{path}: non-numeric coordinates in row {row}")
            locations.add(coordinate)
    return locations


def filter_file(source: Path, target: Path, locations: set[Coordinate]) -> tuple[int, set[Coordinate]]:
    kept = 0
    matched: set[Coordinate] = set()
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        lat_index, lon_index = header.index("Latitude"), header.index("Longitude")
        rows = []
        for row in reader:
            coordinate = rounded(row[lat_index], row[lon_index])
            if coordinate in locations:
                rows.append(row)
                matched.add(coordinate)
    if rows:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        kept = len(rows)
    return kept, matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("locations", type=Path, help="CSV with Latitude and Longitude columns")
    parser.add_argument("--name", required=True, help="subfolder under data/nwdp/ for the filtered files")
    parser.add_argument("--merged-dir", type=Path, default=MERGED_DIR)
    args = parser.parse_args()

    locations = load_locations(args.locations)
    out_dir = args.merged_dir / args.name
    sources = sorted(path for path in args.merged_dir.glob("*.csv") if path.name != "merge_log.csv")
    if not sources:
        sys.exit(f"no merged files in {args.merged_dir}; run merge_nwdp_files.py first")

    log: list[dict[str, object]] = []
    matched_any: set[Coordinate] = set()
    for source in sources:
        kept, matched = filter_file(source, out_dir / source.name, locations)
        matched_any |= matched
        log.append({"group": source.stem, "rows_kept": kept, "locations_matched": len(matched)})
        print(f"{source.name}: {kept} rows from {len(matched)} locations")

    unmatched = sorted(locations - matched_any)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "filter_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["group", "rows_kept", "locations_matched"])
        writer.writeheader()
        writer.writerows(log)
    with (out_dir / "unmatched_locations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Latitude", "Longitude"])
        writer.writerows(unmatched)
    print(f"\n{len(matched_any)} of {len(locations)} locations found in at least one merged file; "
          f"{len(unmatched)} unmatched listed in {out_dir / 'unmatched_locations.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
