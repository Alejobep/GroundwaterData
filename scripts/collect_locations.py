"""Collect unique station locations without loading observations into memory."""

import csv
import math
from collections import Counter
from pathlib import Path
from sys import stderr


COLUMNS = ("Agency", "Station", "State", "District", "Latitude", "Longitude")
MEASUREMENTS = {
    "Groundwater Level Quarterly Manual (meter)": ("groundwater_level", "manual_quarterly"),
    "Groundwater Level Telemetry 6 Hourly (meter)": ("groundwater_level", "telemetry_6_hourly"),
    "Groundwater Level Telemetry Quadridaily (meter)": ("groundwater_level", "telemetry_6_hourly"),
    "Potential of Hydrogen (pH)": ("groundwater_quality_chemical", "manual"),
    "Turbidity (NTU)": ("groundwater_quality_physical", "manual"),
    "Telemetry Hourly Relative Humidity (%)": ("relative_humidity", "telemetry_hourly"),
    "Telemetry_Hourly_Atmospheric Pressure (mb)": ("atmospheric_pressure", "telemetry_hourly"),
    "Telemetry Hourly Rainfall (mm)": ("rainfall", "telemetry_hourly"),
    "Manual Daily River Water Discharge (m3/sec)": ("river_discharge", "manual_daily"),
    "River Water Level (m)": ("river_water_level", "manual_daily"),
    "Area (m2)": ("river_cross_section_area", "manual_daily"),
    "Velocity (m/sec)": ("river_velocity", "manual_daily"),
    "Total_discharge (m3/sec)": ("river_discharge", "manual_daily"),
    "River Water Level Telemetry Hourly (meter)": ("river_water_level", "telemetry_hourly"),
    "Solar Radiation (Watt/m2)": ("solar_radiation", "telemetry_hourly"),
    "Air Temperature Telemetry Hourly (\u00baC)": ("air_temperature", "telemetry_hourly"),
    "Telemetry Hourly Wind Direction (Degree)": ("wind_direction", "telemetry_hourly"),
    "Telemetry Hourly Wind Speed (Km/Hr)": ("wind_speed", "telemetry_hourly"),
}
ENCODINGS = {
    "temprature_tele_hr_jharkhand_jh_1961_2020.csv": "cp1252",
}
Location = tuple[str, str, str, str, float, float]
CategorizedLocation = tuple[str, str, str, str, float, float, str]
TypedLocation = tuple[str, str, str, str, float, float, str, str]


def collect_locations(files: list[Path]) -> list[TypedLocation]:
    locations: set[TypedLocation] = set()
    for path in files:
        missing_coordinates = 0
        encoding = ENCODINGS.get(path.name, "utf-8-sig")
        if encoding != "utf-8-sig":
            print(f"Reading {path.name} with explicit {encoding} encoding")
        with path.open(encoding=encoding, newline="") as stream:
            reader = csv.DictReader(stream)
            missing = set(COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path}: missing columns {sorted(missing)}")
            measurement_headers = set(MEASUREMENTS).intersection(reader.fieldnames or [])
            if not measurement_headers:
                raise ValueError(f"{path}: no recognized measurement columns")
            categories = {MEASUREMENTS[header] for header in measurement_headers}
            for row in reader:
                raw_latitude, raw_longitude = row["Latitude"], row["Longitude"]
                try:
                    if raw_latitude is None or raw_longitude is None:
                        raise ValueError("missing coordinate fields")
                    latitude = float(raw_latitude) if raw_latitude.strip() else None
                    longitude = float(raw_longitude) if raw_longitude.strip() else None
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"{path}, line {reader.line_num}: invalid coordinates"
                    ) from error
                if not (
                    (latitude is None or math.isfinite(latitude) and -90 <= latitude <= 90)
                    and (longitude is None or math.isfinite(longitude) and -180 <= longitude <= 180)
                ):
                    raise ValueError(
                        f"{path}, line {reader.line_num}: coordinates out of range"
                    )
                if latitude is None or longitude is None:
                    missing_coordinates += 1
                    continue
                point = (
                    row["Agency"], row["Station"], row["State"], row["District"],
                    latitude, longitude,
                )
                for category, data_type in categories:
                    locations.add((*point, category, data_type))
        if missing_coordinates:
            print(f"{path}: skipped {missing_coordinates:,} rows with blank coordinates", file=stderr)
        print(f"Read {path.name}; {len(locations):,} unique locations so far")
    return sorted(locations)


def report_overlap(locations: list[TypedLocation]) -> set[CategorizedLocation]:
    by_category: dict[str, dict[str, set[Location]]] = {}
    counts = Counter()
    for agency, station, state, district, latitude, longitude, category, data_type in locations:
        by_category.setdefault(category, {}).setdefault(data_type, set()).add(
            (agency, station, state, district, latitude, longitude)
        )
        counts[(category, data_type, state)] += 1
    for (category, data_type, state), count in sorted(counts.items()):
        print(f"{category} / {data_type} / {state}: {count:,} station locations")
    shared: set[CategorizedLocation] = set()
    for category, by_type in sorted(by_category.items()):
        occurrences = Counter(point for points in by_type.values() for point in points)
        matches = {point for point, count in occurrences.items() if count > 1}
        shared.update((*point, category) for point in matches)
        if len(by_type) > 1:
            print(f"{category}: {len(matches):,} exact locations shared across data types")
    return shared


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "downloaded_data" / "nwdp"
    output = root / "data" / "station_locations.csv"
    files = sorted(
        path for path in source.rglob("*.csv", case_sensitive=False) if path.is_file()
    )
    if not files:
        raise FileNotFoundError(f"No input CSVs found under {source}")
    locations = collect_locations(files)
    shared = report_overlap(locations)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow((*COLUMNS, "Category", "Data Type", "Shared Location"))
        for agency, station, state, district, latitude, longitude, category, data_type in locations:
            point = (agency, station, state, district, latitude, longitude)
            writer.writerow((*point, category, data_type, (*point, category) in shared))
    print(f"Saved {len(locations):,} station-location/category/type rows to {output}")


if __name__ == "__main__":
    main()
