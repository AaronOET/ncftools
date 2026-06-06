#!/usr/bin/env python3
"""
transzone2 - Extract core transition zone faces

Reads FlowFM_net_faces.shp and trans_zone_extend.shp (output of transzone1),
shrinks the transition zone by -1 m, then selects only the faces that lie
completely within the shrunk zone. Writes trans_zone_core.shp.
"""

import argparse
import importlib.metadata
import os
import sys

import geopandas as gpd


def build_transition_core(faces_shp, zone_faces_shp, output_dir="SHP_TRANS", quiet=False):
    """
    Shrink transition zone and select fully-contained mesh faces.

    Args:
        faces_shp (str): Path to FlowFM_net_faces.shp.
        zone_faces_shp (str): Path to trans_zone_extend.shp (from transzone1).
        output_dir (str): Directory for output shapefile.
        quiet (bool): Suppress non-error output.

    Returns:
        str: Path to trans_zone_core.shp.
    """
    _print("=== Transition Core Extractor ===", quiet)

    faces = gpd.read_file(faces_shp)
    zone = gpd.read_file(zone_faces_shp)

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

    dissolved = selected.dissolve()[["geometry"]]
    dissolved["zone"] = "transition_core"

    os.makedirs(output_dir, exist_ok=True)
    out_core = os.path.join(output_dir, "trans_zone_core.shp")
    dissolved.to_file(out_core)

    if not quiet:
        print(f"Selected faces:    {len(selected)}")
        print(f"Output written to: {out_core}")

    return out_core


def _print(msg, quiet=False):
    if not quiet:
        print(msg)


def main():
    parser = argparse.ArgumentParser(
        prog='transzone2',
        description='Extract core transition zone faces (fully within shrunk zone)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp
  transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp -o SHP_TRANS
  transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp -q
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
        '-z', '--zone-faces',
        default='SHP_TRANS/trans_zone_extend.shp',
        metavar='FILE',
        help='Path to trans_zone_extend.shp from transzone1 (default: SHP_TRANS/trans_zone_extend.shp)',
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='SHP_TRANS',
        metavar='DIR',
        help='Output directory for shapefile (default: SHP_TRANS)',
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

    if not os.path.isfile(args.zone_faces):
        print(f"Error: File '{args.zone_faces}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        core = build_transition_core(
            args.input, args.zone_faces, args.output_dir, args.quiet
        )
        if args.quiet:
            print(core)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
