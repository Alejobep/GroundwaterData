"""Merge NWDP CSV exports of strictly the same nature into one file per measurement type.

Inputs are the raw NWDP files registered in catalogue/files.csv (never modified).
Each output under data/nwdp/ keeps the original columns and values as delivered;
the only changes are:

- a leading ``file_id`` column linking every row to catalogue/files.csv,
- the per-file ``SlNo`` counter is dropped (it restarts at 1 in every export),
- headers are normalised so encoding variants of the degree sign match,
- the historical ``Quadridaily`` groundwater-level header is renamed to the
  six-hourly telemetry header (both mean four readings per day).

Header-only exports are skipped and recorded in merge_log.csv. Files whose
measurement columns match no known group stop the run.
"""

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ROOT / "catalogue" / "files.csv"
OUT_DIR = ROOT / "data" / "nwdp"
NWDP_PREFIX = "downloaded_data/nwdp/"
ENCODINGS = ("utf-8-sig", "cp1252")

STATION_COLUMNS = (
    "Station", "Agency", "State LGD Code", "State", "District LGD Code", "District",
    "Tehsil", "Block", "Village", "River", "Basin", "Tributary", "Subtributary",
    "SubSubtributary", "Local River", "Latitude", "Longitude",
)
DROP_COLUMNS = ("SlNo",)
RENAME_HEADERS = {
    "Groundwater Level Telemetry Quadridaily (meter)": "Groundwater Level Telemetry 6 Hourly (meter)",
}

# Output name -> the measurement columns (everything after the station block)
# that define the group. Order matters and must match the source exactly.
GROUPS: dict[str, tuple[str, ...]] = {
    "gwl_manual_quarterly": ("RL_MSL", "Data Acquisition Time", "Groundwater Level Quarterly Manual (meter)"),
    "gwl_telemetry_6_hourly": ("RL_MSL", "Data Acquisition Time", "Groundwater Level Telemetry 6 Hourly (meter)"),
    "gwq_chemical_manual": (
        "Data Acquisition Time", "Potential of Hydrogen (pH)", "Electric Conductivity (\u03bcS/cm)",
        "Total Dissolved Solids (mg/L)", "Carbonate (mg/L)", "Bicarbonate (mg/L)",
        "Total Alkalinity (mg/L as CaCO3)", "Chloride (mg/L)", "Nitrate N (mgN/L)", "Sulphate (mg/L)",
        "Phosphate(mg/L)", "Silica(mg/L)", "Fluoride (mg/L)", "Total Hardness (mgCaCO3/L)",
        "Calcium (mg/L)", "Magnesium (mg/L)", "Sodium (mg/L)", "Potassium (mg/L)", "Iron(mg/L)",
        "Arsenic (mg/L)", "Uranium(mg/L)", "Manganese (mg/L)", "Copper (mg/L)", "Lead (mg/L)",
        "Zinc (mg/L)", "Nickel (mg/L)", "Cadmium (mg/L)", "Chromium (mg/L)",
    ),
    "gwq_physical_manual": ("Data Acquisition Time", "Temperature (\u00b0C)", "Turbidity (NTU)"),
    "rwl_telemetry_hourly": (
        "Is_DischargeDataAvailable", "RL_of_zeroGauge", "MeanSeaLevel", "Data Acquisition Time",
        "River Water Level Telemetry Hourly (meter)",
    ),
    "river_discharge_manual_daily": ("Data Acquisition Time", "Manual Daily River Water Discharge (m3/sec)"),
    "river_velocity_discharge_manual_daily": (
        "Data Acquisition Time", "River Water Level (m)", "Area (m2)", "Velocity (m/sec)", "Total_discharge (m3/sec)",
    ),
    "air_temperature_telemetry_hourly": ("Data Acquisition Time", "Air Temperature Telemetry Hourly (\u00b0C)"),
    "relative_humidity_telemetry_hourly": ("Data Acquisition Time", "Telemetry Hourly Relative Humidity (%)"),
    "rainfall_telemetry_hourly": ("Data Acquisition Time", "Telemetry Hourly Rainfall (mm)"),
    "atmospheric_pressure_telemetry_hourly": ("Data Acquisition Time", "Telemetry_Hourly_Atmospheric Pressure (mb)"),
    "solar_radiation_telemetry_hourly": ("Data Acquisition Time", "Solar Radiation (Watt/m2)"),
    "wind_speed_telemetry_hourly": ("Data Acquisition Time", "Telemetry Hourly Wind Speed (Km/Hr)"),
    "wind_direction_telemetry_hourly": ("Data Acquisition Time", "Telemetry Hourly Wind Direction (Degree)"),
}
GROUP_BY_COLUMNS = {columns: name for name, columns in GROUPS.items()}


def normalise_header(name: str) -> str:
    name = name.strip().replace("\u00ba", "\u00b0").replace("\ufffd", "\u00b0")
    name = unicodedata.normalize("NFKC", name)
    return RENAME_HEADERS.get(name, name)


def detect_encoding(path: Path) -> str:
    for encoding in ENCODINGS:
        try:
            with path.open(encoding=encoding) as handle:
                for _ in handle:
                    pass
            return encoding
        except UnicodeDecodeError:
            continue
    sys.exit(f"{path.name}: none of {ENCODINGS} decode this file; inspect before adding a fallback")


def registered_nwdp_files() -> list[tuple[str, Path]]:
    with FILES.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    files = [
        (row["file_id"], ROOT / row["local_path"])
        for row in rows
        if row["local_path"].startswith(NWDP_PREFIX) and row["format"] == "csv"
    ]
    missing = [path for _, path in files if not path.exists()]
    if missing:
        sys.exit("Registered files missing on disk:\n" + "\n".join(str(p) for p in missing))
    return sorted(files, key=lambda item: item[1].name)


def read_header(path: Path, encoding: str) -> list[str]:
    with path.open(newline="", encoding=encoding) as handle:
        return [normalise_header(column) for column in next(csv.reader(handle))]


def classify(path: Path, header: list[str]) -> str:
    kept = [column for column in header if column not in DROP_COLUMNS]
    station = tuple(kept[: len(STATION_COLUMNS)])
    if station != STATION_COLUMNS:
        sys.exit(f"{path.name}: unexpected station columns {station}")
    measurement = tuple(kept[len(STATION_COLUMNS):])
    group = GROUP_BY_COLUMNS.get(measurement)
    if group is None:
        sys.exit(f"{path.name}: measurement columns match no known group: {measurement}")
    return group


def append_file(path: Path, encoding: str, file_id: str, out_path: Path, write_header: bool) -> int:
    """Stream rows from one export onto the group file, preserving values as delivered."""
    rows = 0
    with path.open(newline="", encoding=encoding) as source, out_path.open("a", newline="", encoding="utf-8") as target:
        reader = csv.reader(source)
        writer = csv.writer(target)
        header = [normalise_header(column) for column in next(reader)]
        keep = [index for index, column in enumerate(header) if column not in DROP_COLUMNS]
        if write_header:
            writer.writerow(["file_id"] + [header[index] for index in keep])
        for row in reader:
            if not row:
                continue
            writer.writerow([file_id] + [row[index] for index in keep])
            rows += 1
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    log: list[dict[str, object]] = []
    started: set[str] = set()
    totals: dict[str, int] = {}

    for file_id, path in registered_nwdp_files():
        encoding = detect_encoding(path)
        header = read_header(path, encoding)
        group = classify(path, header)
        out_path = args.out_dir / f"{group}.csv"
        if group not in started:
            out_path.unlink(missing_ok=True)

        with path.open(encoding=encoding) as handle:
            data_lines = sum(1 for _ in handle) - 1
        entry: dict[str, object] = {
            "file_id": file_id, "file": path.name, "group": group, "encoding": encoding,
            "rows": data_lines, "status": "",
        }
        if data_lines <= 0:
            entry["status"] = "skipped: header only"
        else:
            rows = append_file(path, encoding, file_id, out_path, write_header=group not in started)
            started.add(group)
            totals[group] = totals.get(group, 0) + rows
            entry["rows"] = rows
            entry["status"] = "merged"
            if encoding != ENCODINGS[0]:
                entry["status"] += f" (decoded as {encoding})"
        log.append(entry)
        print(f"{file_id} {path.name} -> {group}: {entry['status']} ({entry['rows']} rows)")

    with (args.out_dir / "merge_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(log[0]))
        writer.writeheader()
        writer.writerows(log)
    print("\nrows per merged file:")
    for group, rows in sorted(totals.items()):
        print(f"  {group}.csv: {rows}")
    unused = sorted(set(GROUPS) - set(totals))
    if unused:
        print("groups with no data: " + ", ".join(unused))
    return 0


if __name__ == "__main__":
    sys.exit(main())
