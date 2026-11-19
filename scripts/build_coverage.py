"""Build catalogue/coverage.csv: one row per publication file and administrative area it covers.

Covers the CGWB reports under downloaded_data/cgwb/ and the journal articles
under downloaded_data/papers/. Reads catalogue/sources.csv and
catalogue/files.csv, parses the ``area`` field
(``State:District`` or ``State:District:Block`` entries separated by ``;``),
canonicalises district spellings to the names used in data/polygons/, and joins
to the districts that intersect the GWR study-area outlines. Sources with no
``area`` are recorded at state (or national) scope using their ``state`` field.

Columns:

- source_id, file_id, local_path, title, item_type, coverage_level, publication_date,
  sampling_start, sampling_end: from the catalogue (sampling dates are blank for most reports)
- scope: national | state | district | block
- state, district, block: canonical names; blank where not applicable
- area_as_given: the original ``area`` token for traceability
- study_area: which outline the district intersects (``jharkhand``/``odisha``), blank if none;
  for state-scope rows, every study area touching that state
- pct_of_district: share of the district inside the study area (blank for non-district rows)
- in_study_area: True when the row's district intersects an outline or the row is state/national scope

Sources whose file sits under downloaded_data/cgwb/national/ are national scope.
A source registered with several files (e.g. two copies of the same article)
yields one set of rows per file so every local_path is listed.

Also writes catalogue/coverage_by_file.csv, the same content collapsed to one
row per registered file, for indexing the PDFs in an external repository:

- file_id, source_id, local_path, original_filename, sha256, size_bytes: from files.csv
- title, item_type, coverage_level, publication_date, sampling_start, sampling_end: from sources.csv
- scope: finest administrative level the file names (national | state | district | block)
- states: ``;``-separated states covered
- n_districts, districts: count and ``;``-separated canonical district names
- blocks: ``;``-separated ``District:Block`` entries where blocks are named
- study_areas: ``;``-separated outlines the file touches
- n_districts_in_study_area, districts_in_study_area: districts intersecting an outline
- in_study_area: True when any row of the file is in a study area
"""

import csv
import sys
from pathlib import Path

import pandas as pd

from groundwaterdata.study_areas import load_districts, study_area_districts

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "catalogue" / "sources.csv"
FILES = ROOT / "catalogue" / "files.csv"
OUTPUT = ROOT / "catalogue" / "coverage.csv"
OUTPUT_BY_FILE = ROOT / "catalogue" / "coverage_by_file.csv"
CGWB_PREFIX = "downloaded_data/cgwb/"
PUBLICATION_PREFIXES = (CGWB_PREFIX, "downloaded_data/papers/")

# Catalogue spellings -> polygon spellings. Source text is kept in area_as_given.
DISTRICT_ALIASES = {
    "Keonjhar": "Kendujhar",
    "Khurda": "Khordha",
    "Nabarangpur": "Nabarangapur",
    "Bolangir": "Balangir",
    "Baleshwar": "Balasore",
    "Sonepur": "Subarnapur",
    "Suvarnapur": "Subarnapur",
    "Anugul": "Angul",
    "Sahebganj": "Sahibganj",
    "Seraikela-Kharsawan": "Saraikela-Kharsawan",
}
DISTRICT_REPORT_LEVELS = {"district_context", "named_blocks", "study_footprint"}

COLUMNS = (
    "source_id", "file_id", "local_path", "title", "item_type", "coverage_level", "publication_date",
    "sampling_start", "sampling_end",
    "scope", "state", "district", "block", "area_as_given", "study_area", "pct_of_district", "in_study_area",
)
BY_FILE_COLUMNS = (
    "file_id", "source_id", "local_path", "original_filename", "sha256", "size_bytes",
    "title", "item_type", "coverage_level", "publication_date", "sampling_start", "sampling_end",
    "scope", "states", "n_districts", "districts", "blocks",
    "study_areas", "n_districts_in_study_area", "districts_in_study_area", "in_study_area",
)
SCOPE_ORDER = ("block", "district", "state", "national")


def joined(values: pd.Series) -> str:
    return ";".join(sorted(set(filter(None, values))))


def collapse_by_file(table: pd.DataFrame, files: pd.DataFrame) -> pd.DataFrame:
    """One row per file: the long coverage rows summarised as delimited lists."""
    records = []
    for file_id, group in table.groupby("file_id", sort=False):
        first = group.iloc[0]
        in_area = group[group.in_study_area & group.district.ne("")]
        records.append({
            **{col: first[col] for col in ("source_id", "local_path", "title", "item_type", "coverage_level",
                                             "publication_date", "sampling_start", "sampling_end")},
            "file_id": file_id,
            "scope": next(s for s in SCOPE_ORDER if (group.scope == s).any()),
            "states": joined(group.state),
            "n_districts": group.district.replace("", pd.NA).nunique(),
            "districts": joined(group.district),
            "blocks": joined(group.loc[group.block.ne(""), "district"] + ":" + group.loc[group.block.ne(""), "block"]),
            "study_areas": joined(group.study_area.str.split(";").explode()),
            "n_districts_in_study_area": in_area.district.nunique(),
            "districts_in_study_area": joined(in_area.district),
            "in_study_area": bool(group.in_study_area.any()),
        })
    by_file = pd.DataFrame(records).merge(
        files[["file_id", "original_filename", "sha256", "size_bytes"]], on="file_id", how="left", validate="one_to_one"
    )
    return by_file[list(BY_FILE_COLUMNS)]


def canonical_district(name: str) -> str:
    return DISTRICT_ALIASES.get(name.strip(), name.strip())


def parse_area(area: str) -> list[dict[str, str]]:
    rows = []
    for token in filter(None, (part.strip() for part in area.split(";"))):
        parts = token.split(":")
        if len(parts) not in (2, 3):
            sys.exit(f"area token {token!r} is not State:District or State:District:Block")
        rows.append({
            "scope": "block" if len(parts) == 3 else "district",
            "state": parts[0], "district": canonical_district(parts[1]),
            "block": parts[2] if len(parts) == 3 else "", "area_as_given": token,
        })
    return rows


def main() -> int:
    sources = pd.read_csv(SOURCES, dtype=str, keep_default_na=False)
    files = pd.read_csv(FILES, dtype=str, keep_default_na=False)
    registered = files[files["local_path"].str.startswith(PUBLICATION_PREFIXES)][["file_id", "source_id", "local_path"]]
    publications = registered.merge(sources, on="source_id", how="left", validate="many_to_one")
    if publications["title"].eq("").any():
        sys.exit("publication files without a source row: " + ", ".join(publications.loc[publications["title"].eq(""), "file_id"]))

    known = {(row.st_nm, row.district) for row in load_districts().itertuples()}
    overlaps = study_area_districts()
    overlap_by_district = {
        (row.state, row.district): (row.study_area, row.pct_of_district) for row in overlaps.itertuples()
    }
    study_areas_by_state = overlaps.groupby("state")["study_area"].agg(lambda s: ";".join(sorted(set(s)))).to_dict()

    rows: list[dict[str, object]] = []
    unknown_districts: set[tuple[str, str]] = set()
    for pub in publications.itertuples():
        base = {
            "source_id": pub.source_id, "file_id": pub.file_id, "local_path": pub.local_path, "title": pub.title,
            "item_type": pub.item_type, "coverage_level": pub.coverage_level, "publication_date": pub.publication_date,
            "sampling_start": pub.sampling_start, "sampling_end": pub.sampling_end,
        }
        areas = parse_area(pub.area)
        if not areas:
            if pub.local_path.startswith(CGWB_PREFIX + "national/"):
                rows.append({**base, "scope": "national", "state": "", "district": "", "block": "",
                             "area_as_given": "", "study_area": "", "pct_of_district": "", "in_study_area": True})
                continue
            for state in [s for s in pub.state.split(";") if s] or [""]:
                rows.append({
                    **base, "scope": "state", "state": state, "district": "", "block": "", "area_as_given": "",
                    "study_area": study_areas_by_state.get(state, ""), "pct_of_district": "", "in_study_area": True,
                })
            continue
        for area in areas:
            key = (area["state"], area["district"])
            if key not in known:
                unknown_districts.add(key)
            study_area, pct = overlap_by_district.get(key, ("", ""))
            rows.append({**base, **area, "study_area": study_area, "pct_of_district": pct, "in_study_area": bool(study_area)})

    if unknown_districts:
        sys.exit("districts not found in data/polygons/: " + ", ".join(f"{s}:{d}" for s, d in sorted(unknown_districts)))

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    table = pd.DataFrame(rows)
    print(f"{len(table)} coverage rows for {table.source_id.nunique()} sources -> {OUTPUT.relative_to(ROOT)}")
    by_file = collapse_by_file(table, files)
    by_file.to_csv(OUTPUT_BY_FILE, index=False)
    print(f"{len(by_file)} files -> {OUTPUT_BY_FILE.relative_to(ROOT)}")
    print(table.groupby(["item_type", "scope"]).size().to_string())
    district_rows = table[table.scope.isin(["district", "block"])]
    print(f"\ndistrict/block rows inside a study area: {district_rows.in_study_area.sum()} of {len(district_rows)}")
    # Statewide year books enumerate every district in ``area``; only district-focused
    # reports count as district-level evidence here.
    focused = district_rows[district_rows.coverage_level.isin(DISTRICT_REPORT_LEVELS)]
    for item_type, label in (("report", "district-focused report"), ("article", "district-focused article")):
        covered = set(zip(focused[focused.item_type == item_type].state, focused[focused.item_type == item_type].district))
        missing = overlaps[[(s, d) not in covered for s, d in zip(overlaps.state, overlaps.district)]]
        if not missing.empty:
            print(f"\nstudy-area districts with no {label} (district_context/named_blocks/study_footprint):")
            print(missing[["study_area", "state", "district", "pct_of_district"]].to_string(index=False))
    articles = table[(table.item_type == "article") & table.in_study_area].drop_duplicates("source_id")
    print(f"\narticles touching a study area: {len(articles)} of {table[table.item_type == 'article'].source_id.nunique()}")
    if not articles.empty:
        print(articles[["source_id", "scope", "study_area", "area_as_given", "sampling_start", "sampling_end"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
