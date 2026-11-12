# GroundwaterData

Planning an organized groundwater evidence package and companion coverage map
for Jharkhand and Odisha, India.

- [Roadmap](ROADMAP.md): report assessment, phased tasks, map options and release criteria.
- [Task backlog](planning/tasks.csv): priorities, dependencies, ownership and acceptance criteria.
- [Source acquisition queue](planning/source_queue.csv): official sources, papers and manual follow-ups.
- [Input reports](input_reports/): the two original desk studies.
- [CSV coverage notebook](notebooks/data_coverage.ipynb): local inspection and
  a simple ArcGIS-backed visual of station locations against Jharkhand and Odisha.

## Inspect a downloaded CSV

Run `uv sync`, open the coverage notebook in VS Code, select the project's
`.venv` Python kernel and run all cells. Change `CSV_PATH` for another export.
The ArcGIS Python API retrieves public Esri outlines; no account is required
and CSV records are not uploaded. Internet is needed for the boundary query.

The first downloaded chemistry file contains 113,586 Tamil Nadu records and
3,828 agency/station IDs, not Jharkhand or Odisha observations. The notebook
compares state labels with coordinates and shows both an overview and a target
zoom. This is coverage screening, not a water-quality risk map or release package.

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

Run `uv run python scripts/collect_locations.py` to scan all CSVs under
`data/odisha/` and `data/jharkhand/`
and write `data/station_locations.csv`. The script streams rows using Python's
standard CSV reader and retains only unique agency/station/state/district/
coordinate/category/data-type combinations. Generated files outside the state
folders are not scanned.
Different stations at the same coordinates and changed station locations remain
separate records; equivalent numeric coordinate spellings are deduplicated.
Missing required columns or invalid coordinates stop with a file/line error
rather than silently omitting records. Source CSVs remain unchanged.

`Category` describes the measured quantity, such as `groundwater_level`,
`river_water_level`, `rainfall` or `air_temperature`. `Data Type` describes its
method/frequency: `manual_quarterly`, `manual_daily`, `telemetry_6_hourly` or
`telemetry_hourly`. Header mappings are shared across states. Multi-measurement
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
The current downloads contain groundwater-level categories only for Odisha
and river/weather categories only for Jharkhand; missing state/category coverage
means not present in the local archive, not that such data do not exist.
To inspect overlaps, use `locations[locations["Shared Location"]]`; use separate
map layers or panels to see coincident points that otherwise obscure each other.

The final cells in [simple.notebook.ipynb](notebooks/simple.notebook.ipynb)
extract and plot station `25M03BW008` in Nayagarh, which has both quarterly
manual and six-hourly telemetry readings. Only that location's records from
2021 onward are retained. The chart preserves raw signs and shows an overlapping
date-range zoom; confirm measurement datum/sign conventions before comparing
the two sources quantitatively.