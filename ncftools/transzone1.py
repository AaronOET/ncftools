#!/usr/bin/env python3
"""
transzone1 - Extract transition zone and intersecting mesh faces

Reads FlowFM_net_faces.shp, buffers triangle faces by +1 m to form a
transition zone, then selects all mesh faces that intersect that zone.
Writes trans_zone.shp and trans_zone_extend.shp.
"""

import argparse
import importlib.metadata
import os
import sys

import geopandas as gpd


def build_transition_zone(faces_shp, output_dir="SHP_TRANS", quiet=False):
    """
    Build transition zone from triangle faces and select intersecting faces.

    Args:
        faces_shp (str): Path to FlowFM_net_faces.shp.
        output_dir (str): Directory for output shapefiles.
        quiet (bool): Suppress non-error output.

    Returns:
        tuple[str, str]: Paths to (trans_zone.shp, trans_zone_extend.shp).
    """
    _print("=== Transition Zone Builder ===", quiet)

    gdf = gpd.read_file(faces_shp)

    if "type" in gdf.columns:
        triangles = gdf[gdf["type"] == "triangle"].copy()
    else:
        # Detect triangles by vertex count (closed ring has 4 coords for 3 unique vertices)
        is_triangle = gdf.geometry.apply(
            lambda g: len(g.exterior.coords) == 4
        )
        triangles = gdf[is_triangle].copy()

    if triangles.empty:
        raise RuntimeError("No triangle faces found in attribute table.")

    _print(f"Triangles found:     {len(triangles)}", quiet)

    triangles["geometry"] = triangles.geometry.buffer(1.0)
    dissolved = triangles.dissolve()[["geometry"]]
    dissolved["zone"] = "transition"

    os.makedirs(output_dir, exist_ok=True)
    out_zone = os.path.join(output_dir, "trans_zone.shp")
    dissolved.to_file(out_zone)
    _print(f"Transition zone:     {out_zone}", quiet)

    zone = gpd.read_file(out_zone)
    if gdf.crs != zone.crs:
        zone = zone.to_crs(gdf.crs)

    selected_idx = gpd.sjoin(
        gdf, zone[["geometry"]], how="inner", predicate="intersects"
    ).index.unique()
    selected = gdf.loc[selected_idx].copy()

    selected_dissolved = selected.dissolve()[["geometry"]]
    selected_dissolved["zone"] = "transition_faces"

    out_faces = os.path.join(output_dir, "trans_zone_extend.shp")
    selected_dissolved.to_file(out_faces)

    if not quiet:
        print(f"Intersecting faces:  {len(selected)}")
        print(f"Transition extend:   {out_faces}")

    return out_zone, out_faces


def _print(msg, quiet=False):
    if not quiet:
        print(msg)


def main():
    parser = argparse.ArgumentParser(
        prog='transzone1',
        description='Extract transition zone and intersecting mesh faces from a shapefile',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  transzone1 -i SHP_NC/FlowFM_net_faces.shp
  transzone1 -i SHP_NC/FlowFM_net_faces.shp -o SHP_TRANS
  transzone1 -i SHP_NC/FlowFM_net_faces.shp -q
        """,
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {importlib.metadata.version("ncftools")}',
    )
    parser.add_argument(
        '-i', '--input',
        default='SHP_NC/FlowFM_net_faces.shp',
        metavar='FILE',
        help='Path to FlowFM_net_faces.shp (default: SHP_NC/FlowFM_net_faces.shp)',
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='SHP_TRANS',
        metavar='DIR',
        help='Output directory for shapefiles (default: SHP_TRANS)',
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output',
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: File '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        zone, faces = build_transition_zone(args.input, args.output_dir, args.quiet)
        if args.quiet:
            print(zone)
            print(faces)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
