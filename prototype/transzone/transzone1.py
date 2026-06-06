"""Extract triangle mesh cells from FlowFM_net_faces.shp, buffer, dissolve, save.

Then select all faces that intersect the resulting trans_zone and dissolve them.
"""

from pathlib import Path

import geopandas as gpd

BASE_DIR = Path(__file__).resolve().parent
SRC_SHP = BASE_DIR / "SHP_NC" / "FlowFM_net_faces.shp"
OUT_DIR = BASE_DIR / "SHP_TRANS"
OUT_SHP = OUT_DIR / "trans_zone.shp"
OUT_FACES_SHP = OUT_DIR / "trans_zone_faces.shp"


def main():
    gdf = gpd.read_file(SRC_SHP)

    triangles = gdf[gdf["type"] == "triangle"].copy()
    if triangles.empty:
        raise RuntimeError("No triangle faces found in attribute table.")

    triangles["geometry"] = triangles.geometry.buffer(1.0)

    dissolved = triangles.dissolve()
    dissolved = dissolved[["geometry"]]
    dissolved["zone"] = "transition"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dissolved.to_file(OUT_SHP)

    print(f"Triangles extracted: {len(triangles)}")
    print(f"Output written to:   {OUT_SHP}")

    # Select faces that intersect the trans_zone, then dissolve.
    faces = gpd.read_file(SRC_SHP)
    zone = gpd.read_file(OUT_SHP)
    if faces.crs != zone.crs:
        zone = zone.to_crs(faces.crs)

    selected_idx = gpd.sjoin(
        faces, zone[["geometry"]], how="inner", predicate="intersects"
    ).index.unique()
    selected = faces.loc[selected_idx].copy()

    selected_dissolved = selected.dissolve()
    selected_dissolved = selected_dissolved[["geometry"]]
    selected_dissolved["zone"] = "transition_faces"

    selected_dissolved.to_file(OUT_FACES_SHP)

    print(f"Intersecting faces:  {len(selected)}")
    print(f"Output written to:   {OUT_FACES_SHP}")


if __name__ == "__main__":
    main()
