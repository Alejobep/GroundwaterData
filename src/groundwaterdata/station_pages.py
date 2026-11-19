"""Per-location time-series pages for the merged NWDP files under data/nwdp/.

Each study-area folder produced by scripts/filter_nwdp_by_locations.py holds one
CSV per measurement type. This module groups every row by location (coordinates
rounded to five decimals, the same key the filter script uses), builds one
Plotly HTML page per location and returns a short summary for map tooltips.

Pages load plotly.js from a CDN so each file stays small, and the map popup
embeds them in an iframe so index.html only carries the link.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PALETTE = px.colors.qualitative.D3

DECIMALS = 5
SKIP_FILES = {"filter_log.csv", "unmatched_locations.csv", "merge_log.csv"}
TIME_COLUMN = "Data Acquisition Time"
META_COLUMNS = {
    "file_id", "Station", "Agency", "State LGD Code", "State", "District LGD Code",
    "District", "Tehsil", "Block", "Village", "River", "Basin", "Tributary",
    "Subtributary", "SubSubtributary", "Local River", "Latitude", "Longitude",
    "RL_MSL", TIME_COLUMN, "Is_DischargeDataAvailable", "RL_of_zeroGauge", "MeanSeaLevel",
}
DESCRIBE_COLUMNS = ["Station", "Agency", "District", "Block", "Village"]
# Measurement types where the hourly/6-hourly telemetry is reduced to daily values
# before plotting; everything else is plotted as delivered.
DAILY_AGGREGATION = {"rainfall_telemetry_hourly": "sum"}
# NWDP exports encode missing readings as these placeholder numbers; they are masked
# in the plots only, the merged CSVs keep them as delivered.
SENTINEL_VALUES = {-999.0, 999.0, -1000.0, 1000.0, -9999.0, 9999.0}
# Groundwater levels beyond this depth (m) are telemetry glitches, not readings.
GWL_ABS_LIMIT = 500.0
GRID_COLUMNS = 3

Coordinate = tuple[float, float]


@dataclass
class LocationData:
    coordinate: Coordinate
    stations: pd.DataFrame = field(default_factory=pd.DataFrame)
    series: dict[str, pd.DataFrame] = field(default_factory=dict)

    @property
    def page_name(self) -> str:
        lat, lon = self.coordinate
        return f"{lat:.{DECIMALS}f}_{lon:.{DECIMALS}f}.html"

    @property
    def names(self) -> list[str]:
        return sorted(self.stations["Station"].dropna().astype(str).unique())

    def title(self) -> str:
        names = ", ".join(self.names) or "Unnamed station"
        return f"{names} ({self.coordinate[0]:.5f}, {self.coordinate[1]:.5f})"

    def summary_lines(self) -> list[str]:
        lines = []
        for group, frame in self.series.items():
            years = frame[TIME_COLUMN].dt.year
            lines.append(f"{label(group)}: {len(frame)} obs, {years.min()}–{years.max()}")
        return lines


def label(group: str) -> str:
    return group.replace("_", " ").replace("gwl", "GWL").replace("gwq", "GWQ").replace("rwl", "RWL")


def rounded(latitude: float, longitude: float) -> Coordinate:
    return round(float(latitude), DECIMALS), round(float(longitude), DECIMALS)


def load_locations(area_dir: Path) -> dict[Coordinate, LocationData]:
    """Read every merged CSV in a study-area folder and index its rows by location."""
    locations: dict[Coordinate, LocationData] = {}
    if not area_dir.is_dir():
        return locations

    for path in sorted(area_dir.glob("*.csv")):
        if path.name in SKIP_FILES:
            continue
        frame = pd.read_csv(path, low_memory=False)
        frame = frame.dropna(subset=["Latitude", "Longitude", TIME_COLUMN])
        frame[TIME_COLUMN] = pd.to_datetime(frame[TIME_COLUMN], format="%d-%m-%Y %H:%M", errors="coerce")
        frame = frame.dropna(subset=[TIME_COLUMN])
        measurements = [c for c in frame.columns if c not in META_COLUMNS]
        key = list(zip(frame["Latitude"].round(DECIMALS), frame["Longitude"].round(DECIMALS)))

        for coordinate, rows in frame.groupby(pd.Series(key, index=frame.index)):
            location = locations.setdefault(coordinate, LocationData(coordinate))
            description = rows[[c for c in DESCRIBE_COLUMNS if c in rows.columns]].drop_duplicates()
            location.stations = pd.concat([location.stations, description]).drop_duplicates()
            series = rows[["Station", TIME_COLUMN, *measurements]].sort_values(TIME_COLUMN)
            series = mask_sentinels(path.stem, series, measurements)
            if series.empty:
                continue
            location.series[path.stem] = aggregate(path.stem, series, measurements)
    return locations


def mask_sentinels(group: str, series: pd.DataFrame, measurements: list[str]) -> pd.DataFrame:
    series = series.copy()
    for column in measurements:
        values = pd.to_numeric(series[column], errors="coerce")
        invalid = values.isin(SENTINEL_VALUES)
        if group.startswith("gwl"):
            invalid |= values.abs() > GWL_ABS_LIMIT
        series[column] = values.mask(invalid)
    return series.dropna(subset=measurements, how="all")


def aggregate(group: str, series: pd.DataFrame, measurements: list[str]) -> pd.DataFrame:
    """Resample telemetry to daily values, keeping empty days so gaps break the line."""
    if "hourly" not in group:
        return series
    how = DAILY_AGGREGATION.get(group, "mean")
    daily = (
        series.set_index(TIME_COLUMN)
        .groupby("Station")[measurements]
        .resample("D")
        .agg(how)
        .reset_index()
    )
    return daily[["Station", TIME_COLUMN, *measurements]]


def build_figure(location: LocationData) -> go.Figure:
    panels = []
    for group, frame in location.series.items():
        measurements = [c for c in frame.columns if c not in ("Station", TIME_COLUMN)]
        measurements = [c for c in measurements if frame[c].notna().any()]
        panels.extend((group, column, frame) for column in measurements)

    # Single-parameter measurement groups get a full-width row; multi-parameter groups
    # (water chemistry) are laid out in a grid of small panels.
    layout: list[list[tuple[str, str, pd.DataFrame]]] = []
    for group in location.series:
        group_panels = [p for p in panels if p[0] == group]
        width = 1 if len(group_panels) == 1 else GRID_COLUMNS
        for i in range(0, len(group_panels), width):
            layout.append(group_panels[i : i + width])

    rows = len(layout)
    fig = make_subplots(
        rows=rows,
        cols=GRID_COLUMNS,
        specs=[
            [{"colspan": GRID_COLUMNS}, None, None] if len(row) == 1 else [{}] * GRID_COLUMNS
            for row in layout
        ],
        subplot_titles=[panel_title(*p[:2]) for row in layout for p in row],
        vertical_spacing=min(0.08, 0.6 / max(rows, 1)),
        horizontal_spacing=0.06,
    )

    colors = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(location.names)}
    for r, row in enumerate(layout, start=1):
        for c, (group, column, frame) in enumerate(row, start=1):
            if "hourly" in group:
                mode = "lines"
            elif group.startswith("gwq"):
                mode = "markers"
            else:
                mode = "lines+markers"
            marker_size = 4 if len(row) == 1 else 6
            for station, part in frame.groupby("Station"):
                fig.add_trace(
                    go.Scattergl(
                        x=part[TIME_COLUMN],
                        y=part[column],
                        mode=mode,
                        name=str(station),
                        legendgroup=str(station),
                        showlegend=(r == 1 and c == 1),
                        marker={"size": marker_size, "color": colors.get(str(station))},
                        line={"width": 1, "color": colors.get(str(station))},
                        connectgaps=False,
                    ),
                    row=r,
                    col=c,
                )
            # Manual GWL is depth below ground (positive), telemetry reports it as a
            # negative elevation; reverse the axis only when deeper means larger.
            if group.startswith("gwl") and frame[column].median() > 0:
                fig.update_yaxes(autorange="reversed", row=r, col=c)

    fig.update_layout(
        title={"text": location.title(), "x": 0.01},
        height=sum(260 if len(row) == 1 else 200 for row in layout) + 80,
        margin={"l": 50, "r": 20, "t": 70, "b": 40},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right", "yanchor": "bottom"},
        template="plotly_white",
        hovermode="x unified",
    )
    fig.update_annotations(font_size=12)
    return fig


def panel_title(group: str, column: str) -> str:
    if "hourly" in group:
        how = "daily total" if DAILY_AGGREGATION.get(group) == "sum" else "daily mean"
        return f"{column} — {how}"
    return column


def write_pages(locations: dict[Coordinate, LocationData], out_dir: Path) -> dict[Coordinate, str]:
    """Write one HTML page per location; return the relative file name for each."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = {}
    for coordinate, location in locations.items():
        if not location.series:
            continue
        fig = build_figure(location)
        fig.write_html(
            out_dir / location.page_name,
            include_plotlyjs="cdn",
            full_html=True,
            config={"displaylogo": False, "responsive": True},
        )
        pages[coordinate] = location.page_name
    return pages


def popup_html(page_href: str, location: LocationData, width: int = 720, height: int = 480) -> str:
    details = location.stations.fillna("-").astype(str)
    header = "<br>".join(
        f"<b>{row.Station}</b> · {row.Agency} · {row.District}"
        + (f" · {row.Block}" if getattr(row, "Block", "-") != "-" else "")
        for row in details.itertuples(index=False)
    )
    return (
        f'<div style="font: 12px sans-serif; margin-bottom: 4px">{header}</div>'
        f'<iframe src="{page_href}" width="{width}" height="{height}" '
        'style="border: none" loading="lazy"></iframe>'
    )


def tooltip_html(location: LocationData) -> str:
    names = ", ".join(location.names) or "Unnamed station"
    lines = [f"<b>{names}</b>", *location.summary_lines()]
    return "<br>".join(lines)
