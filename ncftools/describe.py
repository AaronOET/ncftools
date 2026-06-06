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
