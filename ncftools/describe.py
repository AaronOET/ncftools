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
            meshinfo FlowFM_net.nc       # Display mesh info for a given file
            meshinfo grid.nc             # Any FlowFM mesh NetCDF file
    """,
    'nc2shp': """
        Convert a NetCDF mesh file to ESRI Shapefiles.

        Reads a UGRID-compliant NetCDF mesh file and writes:
          {stem}_faces.shp      one polygon per mesh face
          {stem}_dissolved.shp  single dissolved polygon of the entire mesh
                                (only written with -d/--dissolve)

        Examples:
            nc2shp FlowFM_net.nc
            nc2shp mesh.nc -d          # also write the dissolved polygon
            nc2shp mesh.nc -o output --crs EPSG:4326
            nc2shp mesh.nc -q
    """,
    'shp2nc': """
        Rebuild a UGRID mesh NetCDF file from a cell-polygon shapefile.

        Reads a polygon shapefile in which every polygon is one mesh cell
        (e.g. {stem}_faces.shp from nc2shp, or a QGIS / RGFGRID export) and
        writes a D-Flow FM 2D net file, {stem}_net.nc by default:
          - vertices shared by neighbouring cells are merged into one node
            (within --tol, default 0.001 map units)
          - cells are made counter-clockwise; edges and face centres derived
          - numeric shapefile attributes are kept as face variables

        Examples:
            shp2nc mesh.shp
            shp2nc mesh.shp -o FlowFM_net.nc
            shp2nc mesh.shp --tol 0.01 --node-z -5.0
            shp2nc mesh.shp --crs EPSG:3826   # only if mesh.prj is missing
    """,
    'transzone1': """
        Extract transition zone and intersecting mesh faces from a shapefile.

        Reads FlowFM_net_faces.shp, buffers triangle faces by +1 m to form a
        transition zone, then selects all mesh faces that intersect that zone.
        Writes two shapefiles to the output directory:
          trans_zone.shp        dissolved transition zone geometry
          trans_zone_faces.shp  all faces intersecting the transition zone

        Examples:
            transzone1 SHP_NC/FlowFM_net_faces.shp
            transzone1 SHP_NC/FlowFM_net_faces.shp -o SHP_TRANS
            transzone1 SHP_NC/FlowFM_net_faces.shp -q
    """,
    'transzone2': """
        Extract core transition zone faces (fully within shrunk zone).

        Reads FlowFM_net_faces.shp and trans_zone_faces.shp (output of
        transzone1), shrinks the transition zone by -1 m, then selects only
        the faces that lie completely within the shrunk zone.
        Writes one shapefile to the output directory:
          trans_zone_core.shp   faces fully inside the core transition zone

        Examples:
            transzone2 SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_faces.shp
            transzone2 SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_faces.shp -o SHP_TRANS
            transzone2 SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_faces.shp -q
    """,
    'setncrain': """
        Point a D-Flow FM model at a NetCDF rainfall forcing file.

        Rewrites every [Meteo] block of the .ext file to use the given NetCDF
        file as rainfall forcing:
          quantity=rainfall, forcingFile=<*.nc>, forcingFileType=netcdf
        If the .ext file is missing it is created from a built-in template and
        registered in the .mdu as ExtForceFileNew.

        The NetCDF time axis is read and the model times in the .mdu are set
        to match it (in the model's Tunit):
          RefDate  midnight of the first time stamp
          TStart   offset of the first time stamp from RefDate
          TStop    offset of the last  time stamp from RefDate

        Examples:
            setncrain -i May28_Event.nc
            setncrain -i data/May28_Event.nc --ext dflowfm/FM_model_bnd.ext
            setncrain -i May28_Event.nc --no-time
            setncrain -i May28_Event.nc --no-backup --as-given
    """,
    'rnxml': """
        Rename dimr.xml to dimr_config.xml.

        D-HYDRO / Delft3D FM writes its DIMR control file as dimr.xml, while
        the DIMR runner expects dimr_config.xml. This tool renames the file in
        place, leaving its contents untouched.

        If the target name already exists the rename is refused unless --force
        is given, in which case a .bak copy of the old target is kept.

        Examples:
            rnxml
            rnxml model/dimr.xml
            rnxml dimr.xml -o dimr_config.xml --force
            rnxml dimr.xml -q
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
