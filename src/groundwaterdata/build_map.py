import json
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from folium.plugins import GroupedLayerControl, MarkerCluster

from groundwaterdata import station_pages
from groundwaterdata.study_areas import load_districts, overlapping_districts

points = pd.read_csv("data/station_locations.csv").dropna(
    subset=["Latitude", "Longitude"]
)

m = folium.Map(location=[20.5, 85.5], zoom_start=6, tiles=None)
basemap = folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Street_Map/MapServer/tile/{z}/{y}/{x}"
    ),
    name="Esri World Street Map",
    attr=(
        "Tiles &copy; Esri — Sources: Esri, TomTom, Garmin, FAO, NOAA, USGS, "
        "&copy; OpenStreetMap contributors, and the GIS User Community"
    ),
).add_to(m)

# for category, rows in points.groupby("Category"):
#     layer = folium.FeatureGroup(name=category.replace("_", " ").title())
#     cluster = MarkerCluster().add_to(layer)

#     for row in rows.itertuples():
#         folium.Marker(
#             [row.Latitude, row.Longitude],
#             tooltip=category,
#             popup=f"{row.Station} — {row.District}, {row.State}",
#         ).add_to(cluster)

#     layer.add_to(m)


data_path = Path("data")



def draw_political_boundaries(path: Path, color: str, layer_name: str) -> folium.FeatureGroup:
    with open(path, "r", encoding="utf-8") as f:
        geo_data = json.load(f)

    districts = gpd.GeoDataFrame.from_features(geo_data["features"])
    state_boundary = districts.geometry.make_valid().union_all().boundary

    boundary_layer = folium.FeatureGroup(name=layer_name).add_to(m)
    folium.GeoJson(
        geo_data,
        style_function=lambda _: {"color": color, "weight": 1},
    ).add_to(boundary_layer)
    folium.GeoJson(
        state_boundary,
        style_function=lambda _: {"color": color, "weight": 4},
        interactive=False,
    ).add_to(boundary_layer)
    return boundary_layer


def draw_study_area(path: Path, color: str, layer_name: str) -> folium.FeatureGroup:
    with open(path, "r", encoding="utf-8") as f:
        geo_data = json.load(f)

    study_area_layer = folium.FeatureGroup(name=layer_name).add_to(m)
    folium.GeoJson(
        geo_data,
        style_function=lambda _: {"color": color, "weight": 2},
    ).add_to(study_area_layer)
    return study_area_layer


jharkhand_pol_bound_path = data_path / "polygons" / "jharkhand.geojson"
odisha_pol_bound_path = data_path / "polygons" / "odisha.geojson"

jharkhand_study_area_path = data_path / "GWR" / "study_area_jharkhand.geojson"
odisha_study_area_path = data_path / "GWR" / "study_area_odisha.geojson"

def draw_overlapping_districts(
    study_area_path: Path, district_paths: list[Path], color: str, layer_name: str
) -> folium.FeatureGroup:
    hits = overlapping_districts(study_area_path, load_districts(district_paths))
    layer = folium.FeatureGroup(name=layer_name).add_to(m)
    folium.GeoJson(
        hits[["st_nm", "district", "dt_code", "overlap_km2", "pct_of_district", "pct_of_study_area", "geometry"]].round(1),
        style_function=lambda _: {
            "color": color, "weight": 2, "fillColor": color, "fillOpacity": 0.25,
        },
        highlight_function=lambda _: {"weight": 3, "fillOpacity": 0.45},
        tooltip=folium.GeoJsonTooltip(
            fields=["district", "st_nm", "overlap_km2", "pct_of_district", "pct_of_study_area"],
            aliases=["District", "State", "Overlap (km²)", "% of district", "% of study area"],
        ),
    ).add_to(layer)
    return layer


def draw_wris_layer(path: Path, color: str, layer_name: str) -> folium.FeatureGroup:
    """Filtered WRIS points from filter_wris_by_study_area.py; hollow markers are buffer-only."""
    layer = folium.FeatureGroup(name=layer_name).add_to(m)
    gdf = gpd.read_file(path)
    if gdf.empty:
        return layer

    fields = [
        "Location", "Block", "District", "State", "Major_Lithology",
        "Depth_of_Drill__m_", "Static_Water_Level__mbgl_", "Year_of_Drill", "distance_km",
    ]
    aliases = [
        "Location", "Block", "District", "State", "Major lithology",
        "Drill depth (m)", "SWL (m bgl)", "Year drilled", "Distance to outline (km)",
    ]
    folium.GeoJson(
        gdf[fields + ["inside_study_area", "geometry"]],
        marker=folium.CircleMarker(radius=5, weight=2),
        style_function=lambda feature: {
            "color": color,
            "fillColor": color,
            "fillOpacity": 0.8 if feature["properties"]["inside_study_area"] else 0.0,
        },
        highlight_function=lambda _: {"radius": 8, "weight": 3},
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases),
    ).add_to(layer)
    return layer


def draw_locations(
    path: Path, nwdp_dir: Path, color: str, layer_name: str
) -> folium.FeatureGroup:
    """Station locations inside a study area (from the notebook's 10 km filter).

    When the merged NWDP files for the area exist under data/nwdp/, each marker
    gets a tooltip summarising the available records and a popup with an
    interactive time-series page written to stations/.
    """
    layer = folium.FeatureGroup(name=layer_name).add_to(m)
    locations = pd.read_csv(path).dropna(subset=["Latitude", "Longitude"])
    nwdp = station_pages.load_locations(nwdp_dir)
    pages = station_pages.write_pages(nwdp, STATION_PAGES_DIR)

    for row in locations.itertuples(index=False):
        coordinate = station_pages.rounded(row.Latitude, row.Longitude)
        data = nwdp.get(coordinate)
        tooltip = f"{row.Latitude:.5f}, {row.Longitude:.5f}"
        popup = None
        if data is not None and coordinate in pages:
            tooltip = station_pages.tooltip_html(data)
            popup = folium.Popup(
                station_pages.popup_html(f"{STATION_PAGES_DIR.name}/{pages[coordinate]}", data),
                max_width=760,
            )
        folium.CircleMarker(
            location=[row.Latitude, row.Longitude],
            radius=2.5,
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            tooltip=tooltip,
            popup=popup,
        ).add_to(layer)
    return layer


district_paths = [jharkhand_pol_bound_path, odisha_pol_bound_path]
wris_path = data_path / "wris"
nwdp_path = data_path / "nwdp"
STATION_PAGES_DIR = Path("stations")

GroupedLayerControl(
    groups={
        "Political Boundaries": [
            draw_political_boundaries(jharkhand_pol_bound_path, "#3388ff", "Jharkhand"),
            draw_political_boundaries(odisha_pol_bound_path, "#ff5733", "Odisha"),
        ],
        "Study Areas": [
            draw_study_area(jharkhand_study_area_path, "#3388ff", "Jharkhand"),
            draw_study_area(odisha_study_area_path, "#ff5733", "Odisha"),
        ],
        "Overlapping Districts": [
            draw_overlapping_districts(jharkhand_study_area_path, district_paths, "#9b59b6", "Jharkhand study area"),
            draw_overlapping_districts(odisha_study_area_path, district_paths, "#f39c12", "Odisha study area"),
        ],
        "WRIS Lithologs (10 km buffer)": [
            draw_wris_layer(wris_path / "jharkhand_study_area" / "Litholog.geojson", "#1b7837", "Jharkhand"),
            draw_wris_layer(wris_path / "odisha_study_area" / "Litholog.geojson", "#b2182b", "Odisha"),
        ],
        "NWDP Locations (10 km buffer)": [
            draw_locations(
                data_path / "jharkhand_locations.csv", nwdp_path / "jharkhand_study_area", "#3388ff", "Jharkhand"
            ),
            draw_locations(
                data_path / "odisha_locations.csv", nwdp_path / "odisha_study_area", "#ff5733", "Odisha"
            ),
        ],
    },
    exclusive_groups=False,
    base_layers=[basemap],
).add_to(m)

m.save("index.html")