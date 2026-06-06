"""Buffer trans_zone_faces by -1 m, select FlowFM faces inside it, dissolve, save."""

from pathlib import Path

import geopandas as gpd

BASE_DIR = Path(__file__).resolve().parent
SRC_FACES = BASE_DIR / "SHP_NC" / "FlowFM_net_faces.shp"
TRANS_FACES = BASE_DIR / "SHP_TRANS" / "trans_zone_faces.shp"
OUT_DIR = BASE_DIR / "SHP_TRANS"
OUT_SHP = OUT_DIR / "trans_zone_core.shp"


def main():
    faces = gpd.read_file(SRC_FACES)
    zone = gpd.read_file(TRANS_FACES)
    if zone.crs != faces.crs:
        zone = zone.to_crs(faces.crs)

    zone["geometry"] = zone.geometry.buffer(-1.0)
    zone = zone[~zone.geometry.is_empty & zone.geometry.notna()]
    if zone.empty:
        raise RuntimeError("Negative buffer collapsed the trans_zone_faces geometry.")

    selected_idx = gpd.sjoin(
        faces, zone[["geometry"]], how="inner", predicate="within"
    ).index.unique()
    selected = faces.loc[selected_idx].copy()
    if selected.empty:
        raise RuntimeError("No faces lie inside the buffered trans_zone_faces.")

    dissolved = selected.dissolve()
    dissolved = dissolved[["geometry"]]
    dissolved["zone"] = "transition_core"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dissolved.to_file(OUT_SHP)

    print(f"Selected faces:    {len(selected)}")
    print(f"Output written to: {OUT_SHP}")


if __name__ == "__main__":
    main()
