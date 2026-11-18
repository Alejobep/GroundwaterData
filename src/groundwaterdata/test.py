import json
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from folium.plugins import GroupedLayerControl, MarkerCluster

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
    },
    exclusive_groups=False,
    base_layers=[basemap],
).add_to(m)



import pandas as pd
import folium

# df = pd.read_csv("data/station_locations.csv")

# # Drop rows without coordinates; treat missing categories as "Uncategorized"
# df = df.dropna(subset=["Latitude", "Longitude"]).copy()
# df["Category"] = df["Category"].fillna("Uncategorized").astype(str)


# for category, group in df.groupby("Category"):
#     layer = folium.FeatureGroup(name=category)

#     for _, row in group.iterrows():
#         folium.CircleMarker(
#             location=[row["Latitude"], row["Longitude"]],
#             radius=5,
#             popup=category,
#             tooltip=category,
#             fill=True,
#         ).add_to(layer)

#     layer.add_to(m)

# folium.LayerControl(collapsed=False).add_to(m)


jharkhand_df = pd.read_csv("data/station_locations.csv")
odisha_df = pd.read_csv("data/odisha_locations.csv")

for idx, row in jharkhand_df.iterrows():
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        fill=True,
    ).add_to(m)
    
for idx, row in odisha_df.iterrows():
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        fill=True,
    ).add_to(m)




m.save("map.html")