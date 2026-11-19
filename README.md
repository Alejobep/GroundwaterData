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

From the repository root, run `uv run python src/groundwaterdata/build_map.py`
and open `index.html` in a browser. The Jharkhand and Odisha boundary layers
draw thin district lines and overlay thicker state outlines computed by merging
each state's districts. The layer menu groups overlays under **Political
Boundaries**, **Study Areas**, **Overlapping Districts**, **WRIS Lithologs** and
**NWDP Locations**, with a separate checkbox for each state in each group.

### Station time-series popups

When the filtered NWDP files exist under `data/nwdp/<area>_study_area/` (see
`scripts/filter_nwdp_by_locations.py`), the build also writes one Plotly page
per location to `stations/` and links it from the NWDP marker: the tooltip lists
the station name(s) and the records available (type, count, year span), and
clicking opens the page in the popup. Pages load plotly.js from a CDN and are
fetched only on click, so `index.html` stays small; keep `stations/` next to it
when publishing. For plotting only, hourly telemetry is reduced to daily means
(daily totals for rainfall), placeholder values such as `-999` are masked, and
groundwater levels beyond 500 m are treated as glitches — the CSVs are untouched.

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

## Source coverage by district

Run `uv run python scripts/build_coverage.py` to write `catalogue/coverage.csv`,
one row per publication file (CGWB reports under `downloaded_data/cgwb/`, GSI
state geology volumes under `downloaded_data/gsi/` and
journal articles under `downloaded_data/papers/`) and administrative area it
covers. Each row carries `file_id` and `local_path` so the opaque download names
(for example `1742896698840549400file.pdf` or `1-s2.0-S2212613915000355-main.pdf`)
can be read off directly, plus `sampling_start`/`sampling_end` where the catalogue
records them (mainly articles). The `area`
field of `sources.csv` (`State:District` or `State:District:Block` tokens) is
parsed and district spellings are canonicalised to those in `data/polygons/`;
sources without an `area` are recorded at state scope, and the file under
`downloaded_data/cgwb/national/` at national scope. Each district row is joined
to the districts intersecting the GWR study-area outlines, computed in
`src/groundwaterdata/study_areas.py` (equal-area EPSG:7755, districts under
1 % overlap dropped); the map in `src/groundwaterdata/test.py` highlights the
same districts, so the table and the map cannot drift apart. The run prints the
study-area districts that still lack a district-focused report or article, and
the articles whose footprint touches a study area. Statewide year
books enumerate every district in `area`, so filter on `coverage_level` when
counting district-level evidence. Filter on `item_type` (`report`/`article`) to
separate the two collections.

The same run also writes `catalogue/coverage_by_file.csv`: the long table
collapsed to exactly one row per registered PDF (148 files), with
`original_filename`, `sha256` and `size_bytes` from `files.csv` and the
districts, blocks and study areas as `;`-separated lists. Use this one to index
the PDFs held in an external repository; use `coverage.csv` when you need to
filter by district.

The in-study-area PDFs are mirrored in a shared Google Drive folder.
`uv run python scripts/list_drive_files.py` walks that folder (public link, no
login) and writes `catalogue/drive_files.csv` (`drive_path`, `drive_file_id`,
`drive_url` per item); `build_coverage.py` joins it on `original_filename` so
every `coverage_by_file.csv` row carries `drive_path` and `drive_url` (blank
when the file is not on Drive). The same run writes
`catalogue/coverage_by_file_drive.csv` for the spreadsheet kept on Drive: only
the files with a Drive copy, addressed by `path` inside the shared folder
(`study_area_files/odisha/Koraput.pdf`) with `drive_url` beside it, and the
repository path demoted to `repo_path`. Re-run both scripts after adding files
to Drive.

`uv run python scripts/pack_study_area_files.py` zips the files with
`in_study_area == True` (78 PDFs, ~480 MB) into
`downloaded_data/study_area_publications.zip`, preserving the
`downloaded_data/...` tree and embedding the matching `coverage_by_file.csv`
rows as a manifest. Each file's SHA-256 is checked against `files.csv` before
it is added. `--scope district block` keeps only district-focused files and
`--output` changes the destination.
