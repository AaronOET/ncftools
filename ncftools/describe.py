#!/usr/bin/env python
"""
Command-line utility to display descriptions of ncftools functionality.
"""

import argparse
from textwrap import dedent

TOOL_DESCRIPTIONS = {
    'meshinfo': """
        Display mesh information from FlowFM NetCDF files.

        This tool reads a FlowFM NetCDF mesh file and reports the number of
        nodes, faces, and edges, element type distribution (triangles vs
        quadrilaterals), and the spatial extent of the mesh.

        Examples:
            meshinfo -i FlowFM_net.nc    # Display mesh info for a given file
            meshinfo -i grid.nc          # Any FlowFM mesh NetCDF file
    """,
    'nc2shp': """
        Convert a NetCDF mesh file to ESRI Shapefiles.

        Reads a UGRID-compliant NetCDF mesh file and writes two shapefiles:
          {stem}_faces.shp      one polygon per mesh face
          {stem}_dissolved.shp  single dissolved polygon of the entire mesh

        Examples:
            nc2shp -i FlowFM_net.nc
            nc2shp -i mesh.nc -o output --crs EPSG:4326
            nc2shp -i mesh.nc -q
    """,
    'transzone1': """
        Extract transition zone and intersecting mesh faces from a shapefile.

        Reads FlowFM_net_faces.shp, buffers triangle faces by +1 m to form a
        transition zone, then selects all mesh faces that intersect that zone.
        Writes two shapefiles to the output directory:
          trans_zone.shp        dissolved transition zone geometry
          trans_zone_faces.shp  all faces intersecting the transition zone

        Examples:
            transzone1 -i SHP_NC/FlowFM_net_faces.shp
            transzone1 -i SHP_NC/FlowFM_net_faces.shp -o SHP_TRANS
            transzone1 -i SHP_NC/FlowFM_net_faces.shp -q
    """,
    'transzone2': """
        Extract core transition zone faces (fully within shrunk zone).

        Reads FlowFM_net_faces.shp and trans_zone_faces.shp (output of
        transzone1), shrinks the transition zone by -1 m, then selects only
        the faces that lie completely within the shrunk zone.
        Writes one shapefile to the output directory:
          trans_zone_core.shp   faces fully inside the core transition zone

        Examples:
            transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_faces.shp
            transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_faces.shp -o SHP_TRANS
            transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_faces.shp -q
    """,
}


def main():
    parser = argparse.ArgumentParser(
        prog='ncftools-info',
        description='Display descriptions of ncftools commands',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'tool',
        nargs='?',
        choices=list(TOOL_DESCRIPTIONS.keys()),
        help='Tool name to describe (omit to list all tools)',
    )
    args = parser.parse_args()

    if args.tool:
        print(f"\n--- {args.tool} ---")
        print(dedent(TOOL_DESCRIPTIONS[args.tool]))
    else:
        print("\nNCFTOOLS — NetCDF utility commands\n")
        for tool, desc in TOOL_DESCRIPTIONS.items():
            first_line = dedent(desc).strip().splitlines()[0]
            print(f"  {tool:<14} {first_line}")
        print("\nRun 'ncftools-info <tool>' for details on a specific command.")


if __name__ == "__main__":
    main()
