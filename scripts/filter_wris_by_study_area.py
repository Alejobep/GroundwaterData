"""Filter a WRIS GeoJSON layer to the study areas, with a buffer around them.

Mirrors the point filter in notebooks/data_processing.ipynb: each study-area
polygon in data/GWR is buffered (10 km by default) and the features falling
inside the buffered outline are kept. Buffering is done in the UTM zone
estimated for each study area so the distance is in true metres (EPSG:3857
over-shrinks distances by ~8 % at these latitudes); pass ``--crs 3857`` to
reproduce the notebook exactly.

Outputs, per study area, in ``data/wris/<name>_study_area/``:
  <layer>.geojson   kept features (EPSG:4326) with two extra columns:
                    ``inside_study_area`` (strictly within the outline) and
                    ``distance_km`` (0 inside, otherwise distance to outline)
  <layer>.csv       same rows without geometry, for quick inspection
  filter_log.csv    counts per study area

Point layers use ``within``; polygon/line layers use ``intersects``.

Usage:
    .venv/bin/python scripts/filter_wris_by_study_area.py
    .venv/bin/python scripts/filter_wris_by_study_area.py --buffer-km 15
    .venv/bin/python scripts/filter_wris_by_study_area.py "downloaded_data/wris/Aquifer Material.geojson"
"""

import argparse
import csv
import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAYER = ROOT / "downloaded_data" / "wris" / "Litholog.geojson"
POLYGONS_DIR = ROOT / "data" / "GWR"
OUT_DIR = ROOT / "data" / "wris"


def study_areas(polygons_dir: Path) -> dict[str, gpd.GeoDataFrame]:
    areas = {}
    for path in sorted(polygons_dir.glob("study_area_*.geojson")):
        areas[path.stem.removeprefix("study_area_")] = gpd.read_file(path)
    if not areas:
        sys.exit(f"no study_area_*.geojson in {polygons_dir}")
    return areas


def filter_layer(layer: gpd.GeoDataFrame, area: gpd.GeoDataFrame, buffer_m: float, crs) -> gpd.GeoDataFrame:
    metric_crs = area.estimate_utm_crs() if crs == "utm" else crs
    area_m = area.to_crs(metric_crs)
    layer_m = layer.to_crs(metric_crs)
    outline = area_m.union_all()
    buffered = outline.buffer(buffer_m)

    is_point = layer_m.geom_type.isin(["Point", "MultiPoint"]).all()
    mask = layer_m.within(buffered) if is_point else layer_m.intersects(buffered)
    kept = layer_m[mask].copy()
    kept["inside_study_area"] = kept.within(outline) if is_point else kept.intersects(outline)
    kept["distance_km"] = (kept.distance(outline) / 1000).round(2)
    return kept.to_crs(4326)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("layer", type=Path, nargs="?", default=DEFAULT_LAYER, help="WRIS GeoJSON to filter")
    parser.add_argument("--buffer-km", type=float, default=10.0, help="buffer around the study area outline")
    parser.add_argument("--crs", default="utm", help="metric CRS for buffering: 'utm' (default, per area) or an EPSG code")
    parser.add_argument("--polygons-dir", type=Path, default=POLYGONS_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    crs = "utm" if args.crs == "utm" else int(args.crs)
    layer = gpd.read_file(args.layer)
    print(f"{args.layer.name}: {len(layer)} features, buffer {args.buffer_km:g} km")

    for name, area in study_areas(args.polygons_dir).items():
        kept = filter_layer(layer, area, args.buffer_km * 1000, crs)
        inside = int(kept["inside_study_area"].sum())
        out_dir = args.out_dir / f"{name}_study_area"
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = args.layer.stem.replace(" ", "_")
        kept.to_file(out_dir / f"{stem}.geojson", driver="GeoJSON")
        kept.drop(columns="geometry").to_csv(out_dir / f"{stem}.csv", index=False)

        log_path = out_dir / "filter_log.csv"
        rows = []
        if log_path.exists():
            with log_path.open(newline="", encoding="utf-8") as handle:
                rows = [r for r in csv.DictReader(handle) if r["layer"] != stem]
        rows.append({"layer": stem, "buffer_km": args.buffer_km, "kept": len(kept),
                     "inside_study_area": inside, "in_buffer_only": len(kept) - inside})
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

        shown = out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir
        print(f"  {name}: {len(kept)} kept ({inside} inside outline, {len(kept) - inside} in buffer only)"
              f" -> {shown}/{stem}.geojson")
    return 0


if __name__ == "__main__":
    sys.exit(main())
