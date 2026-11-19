# GroundwaterData

Planning an organized groundwater evidence package and companion coverage map
for Jharkhand and Odisha, India.

- [Roadmap](ROADMAP.md): report assessment, phased tasks, map options and release criteria.
- [Task backlog](planning/tasks.csv): priorities, dependencies, ownership and acceptance criteria.
- [Source acquisition queue](planning/source_queue.csv): official sources, papers and manual follow-ups.
- [Catalogue](catalogue/): `sources.csv` inventory, `files.csv` register of original
  files with checksums, and `data_dictionary.csv` defining columns and vocabularies.
- [Input reports](input_reports/): the two original desk studies.
- [CSV coverage notebook](notebooks/data_coverage.ipynb): local inspection and
  a simple ArcGIS-backed visual of station locations against Jharkhand and Odisha.

## Catalogue and file register

`catalogue/sources.csv` holds one row per publication, dataset, portal or
directory: what it is (`item_type`, `evidence_type`, `format`), who published it
and when, where it applies (`state`, `area`, `coverage_level`), how far
acquisition has progressed (`access_status`), and the redistribution decision
(`rights_status`). `planning/source_queue.csv` remains the acquisition tracker;
both share `source_id`. `description`, sampling dates and rights stay blank or
`unknown` until the item has actually been inspected.

Original files are never renamed or edited. Place manual downloads under
`raw/<source_id>/` (gitignored), keeping the publisher's filename, then run

```sh
uv run python scripts/register_files.py --retrieved-on 2026-11-13 --filters "describe portal filters"
```

The script matches files to sources through `local_globs` (default
`raw/<source_id>/**/*`), appends new rows to `catalogue/files.csv` with size and
SHA-256, and stops if a file under `raw/` or `downloaded_data/` belongs to no
source, to two sources, or if a registered original's checksum has changed.
Use `--dry-run` to preview. Without `--retrieved-on` the file modification date
is used; `--filters` defaults to `unknown`.

### CGWB publications repository

`cgwb.gov.in` is unreachable from the development container, so
`scripts/fetch_cgwb_publications.py` is meant to run on a machine with Chrome
and normal internet access. It walks a repository search (default: all
Jharkhand publications), records every result in
`planning/cgwb_search_results.csv` (id, title, posting date, download URL) and
downloads the PDFs into `downloaded_data/cgwb/jharkhand/` keeping the server
filenames. Items already marked `downloaded` in `catalogue/sources.csv` are
skipped. Saved result pages can also be parsed offline with `--from-html`.

```sh
uv run scripts/fetch_cgwb_publications.py --dry-run   # list only
uv run scripts/fetch_cgwb_publications.py             # download, then run register_files.py
# Odisha (state_id=21; Jharkhand is 20)
uv run scripts/fetch_cgwb_publications.py --search-url "https://cgwb.gov.in/cgwbpnm/search?type=2&cat_id=&state_id=21&district_id=&year_of_issue=&name_of_author=&keywords=&search=search"
```

Each new PDF needs a `local_globs` entry on its source row before
`register_files.py` will accept it.

## Inspect a downloaded CSV

Run `uv sync`, open the coverage notebook in VS Code, select the project's
`.venv` Python kernel and run all cells. Change `CSV_PATH` for another export.
The ArcGIS Python API retrieves public Esri outlines; no account is required
and CSV records are not uploaded. Internet is needed for the boundary query.

The first downloaded chemistry file contains 113,586 Tamil Nadu records and
3,828 agency/station IDs, not Jharkhand or Odisha observations. The notebook
compares state labels with coordinates and shows both an overview and a target
zoom. This is coverage screening, not a water-quality risk map or release package.

## Preview the interactive boundary map

From the repository root, run `uv run python src/groundwaterdata/test.py` and
open `map.html` in a browser. The Jharkhand and Odisha boundary layers draw
thin district lines and overlay thicker state outlines computed by merging
each state's districts. The layer menu groups overlays under **Political
Boundaries** and **Study Areas**, with a separate checkbox for each state in
each group.

## Large Odisha water-level files

The CSV-loading cell in [simple.notebook.ipynb](notebooks/simple.notebook.ipynb)
reads the files in `data/odisha/` in 25,000-row chunks, selecting only station
metadata and dates. It retains compact per-file tables in `stations_by_file`
instead of several million telemetry observations in memory. Restart a kernel
that still holds the earlier full DataFrame before running the replacement cell.

These files contain water levels, not chemistry. For a time-series analysis,
filter chunks to the desired station/date range; do not concatenate all chunks
back into one full DataFrame. Level sign, reference datum and possible sentinel
values require source metadata before interpretation.

## Collect locations for mapping

Run `uv run python scripts/collect_locations.py` to recursively scan all CSVs
under `downloaded_data/nwdp/` and write `data/station_locations.csv`. The script
streams rows using Python's standard CSV reader and retains only unique agency/station/state/district/
coordinate/category/data-type combinations. Files outside the NWDP folder
are not scanned.
Different stations at the same coordinates and changed station locations remain
separate records; equivalent numeric coordinate spellings are deduplicated.
Rows with blank coordinates cannot be mapped and are skipped with a per-file
warning. Missing required columns or malformed or out-of-range coordinates
stop the run with an error. Source CSVs remain unchanged.

`Category` describes the measured quantity, such as `groundwater_level`,
`river_water_level`, `rainfall` or `air_temperature`. Chemical and physical
groundwater-quality exports have separate categories. `Data Type` describes
its method/frequency: `manual_quarterly`, `manual_daily`, `telemetry_6_hourly`,
`telemetry_hourly`, or `manual` for quality exports without a declared
frequency. Header mappings are shared across states. Multi-measurement
river files contribute to each recognized category, and equivalent discharge
headers share one category. The historical `Quadridaily` header is grouped with
six-hourly telemetry. Files without recognized measurement headers fail explicitly.
This is declared frequency, not verification of sampling intervals.

The historical Jharkhand temperature file has an explicit CP1252 encoding
override; other files remain strict UTF-8. New schema/encoding variants need
inspection rather than a silent fallback. Categories describe locations present
in source files with those columns, not confirmation of nonblank or QA-valid
measurements at every point. Header-only files contribute no locations.

`Shared Location` marks exact agency/station/state/district/coordinate matches
present in multiple data types **within the same category**. Coincident coordinates alone do
not establish well identity, and matching locations do not establish overlapping
observation dates. Each shared location has one row per data type.

Load the small result in the notebook and inspect state/category coverage:

```python
locations = pd.read_csv("../data/station_locations.csv", dtype={"Station": "string"})
display(pd.crosstab(locations["Category"], locations["State"]))
points = gpd.GeoDataFrame(
    locations,
    geometry=gpd.points_from_xy(locations.Longitude, locations.Latitude),
    crs="EPSG:4326",
)
points = points.to_crs(admin.crs)
category = "rainfall"
selected = points[points["Category"] == category].drop_duplicates(
    ["Agency", "Station", "State", "District", "Latitude", "Longitude"]
)
fig, ax = draw_map()
for state, color in [("Jharkhand", "#F28E2B"), ("Odisha", "#4E79A7")]:
    subset = selected[selected["State"] == state]
    if not subset.empty:
        subset.plot(ax=ax, color=color, markersize=8, label=state, zorder=6)
if not selected.empty:
    ax.legend()
ax.set_title(f"{category}: station coverage")
plt.show()
```

Confirm the source coordinate datum before assigning WGS84. Add the plotting
line before `plt.show()` in the map cell. The output is a coverage inventory,
not validated water-level or chemistry data.
Optionally filter `Data Type` before plotting to show one method/frequency.
Missing state/category coverage means not present in the local archive,
not that such data do not exist.
To inspect overlaps, use `locations[locations["Shared Location"]]`; use separate
map layers or panels to see coincident points that otherwise obscure each other.

The final cells in [simple.notebook.ipynb](notebooks/simple.notebook.ipynb)
extract and plot station `25M03BW008` in Nayagarh, which has both quarterly
manual and six-hourly telemetry readings. Only that location's records from
2021 onward are retained. The chart preserves raw signs and shows an overlapping
date-range zoom; confirm measurement datum/sign conventions before comparing
the two sources quantitatively.


## Merge NWDP exports of the same nature

Run `uv run python scripts/merge_nwdp_files.py` to compile the NWDP CSVs
registered in `catalogue/files.csv` into one file per measurement type under
`data/nwdp/`, for example `gwl_manual_quarterly.csv`,
`gwl_telemetry_6_hourly.csv`, `gwq_chemical_manual.csv`,
`gwq_physical_manual.csv`, `rwl_telemetry_hourly.csv` and one file per
hourly climate variable. A file joins a group only when its measurement
columns match that group exactly; an unrecognised header stops the run.

Rows are streamed with the standard CSV reader, so values and column order
are kept as delivered. The only changes are a leading `file_id` column
(linking to `catalogue/files.csv`), the removal of the per-export `SlNo`
counter, header normalisation of the degree-sign encoding variants, and the
rename of the historical `Quadridaily` groundwater-level header to the
six-hourly telemetry header. The 2026-2030 header-only exports are skipped;
`merge_log.csv` records each file's group, detected encoding, row count and
status. Sentinel values such as `-999`, sign conventions and outliers are
not altered. `data/nwdp/` is a regenerable build output and is ignored by git.

To restrict the merged files to a study area, list its locations in a CSV with
`Latitude` and `Longitude` columns and run, for example,
`uv run python scripts/filter_nwdp_by_locations.py data/jharkhand_locations.csv --name jharkhand_study_area`.
Coordinates are matched after rounding both sides to five decimals, because
location lists carry fewer decimals than the eight-decimal NWDP exports. Rows
are copied unchanged into `data/nwdp/<name>/`, one file per group that has
matches; `filter_log.csv` gives rows and locations per group and
`unmatched_locations.csv` lists locations found in no merged file.
