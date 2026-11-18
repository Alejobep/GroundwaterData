import geopandas as gpd
from pathlib import Path


# KML_files
kml_files = ["/workspaces/GroundwaterData/data/GWR/study_area_jharkhand.kml", "/workspaces/GroundwaterData/data/GWR/study_area_odisha.kml" ]

for kml in kml_files:
    input_path = Path(kml)
    print(input_path.is_file())
    name = input_path.name
    output_name = name.replace('.kml', '.geojson')
    output_path = input_path.parent / output_name

    gdf = gpd.read_file(input_path, driver='KML')
    gdf.to_file(output_path, driver='GeoJSON')


