"""Districts intersecting the GWR study-area outlines, shared by the map and the coverage table."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[2]
DISTRICT_FILES = (ROOT / "data" / "polygons" / "jharkhand.geojson", ROOT / "data" / "polygons" / "odisha.geojson")
STUDY_AREA_FILES = {
    "jharkhand": ROOT / "data" / "GWR" / "study_area_jharkhand.geojson",
    "odisha": ROOT / "data" / "GWR" / "study_area_odisha.geojson",
}
EQUAL_AREA_CRS = "EPSG:7755"  # WGS 84 / India NSF LCC, metres
MIN_DISTRICT_OVERLAP_PCT = 1.0  # drop boundary-digitising slivers


def load_districts(paths=DISTRICT_FILES) -> gpd.GeoDataFrame:
    frames = [gpd.read_file(path) for path in paths]
    return pd.concat(frames, ignore_index=True).set_crs("EPSG:4326", allow_override=True)


def _polygons_only(geom):
    """make_valid can return GeometryCollections (polygons plus stray lines); keep the polygons."""
    parts = [g for g in getattr(geom, "geoms", [geom]) if g.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.unary_union(parts)


def overlapping_districts(study_area_path: Path, districts: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Districts from any state that intersect the study area, with overlap statistics in EPSG:4326."""
    districts = load_districts() if districts is None else districts
    study_area = gpd.read_file(study_area_path).to_crs(EQUAL_AREA_CRS).union_all()

    projected = districts.to_crs(EQUAL_AREA_CRS)
    projected["geometry"] = projected.geometry.make_valid()
    hits = projected[projected.intersects(study_area)].copy()
    hits["overlap_km2"] = hits.intersection(study_area).area / 1e6
    hits["pct_of_district"] = 100 * hits["overlap_km2"] / (hits.area / 1e6)
    hits["pct_of_study_area"] = 100 * hits["overlap_km2"] / (study_area.area / 1e6)
    hits = hits[hits["pct_of_district"] >= MIN_DISTRICT_OVERLAP_PCT].copy()
    hits["geometry"] = hits.geometry.apply(_polygons_only)
    return hits.sort_values("overlap_km2", ascending=False).to_crs("EPSG:4326")


def study_area_districts() -> pd.DataFrame:
    """One row per (study_area, state, district) with overlap statistics, no geometry."""
    districts = load_districts()
    rows = []
    for name, path in STUDY_AREA_FILES.items():
        hits = overlapping_districts(path, districts)
        for hit in hits.itertuples():
            rows.append({
                "study_area": name, "state": hit.st_nm, "district": hit.district, "dt_code": hit.dt_code,
                "overlap_km2": round(hit.overlap_km2, 1), "pct_of_district": round(hit.pct_of_district, 1),
                "pct_of_study_area": round(hit.pct_of_study_area, 1),
            })
    return pd.DataFrame(rows)
