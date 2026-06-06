#!/usr/bin/env python3
"""
meshinfo - Display mesh information from FlowFM NetCDF files
Uses netCDF4 Python bindings
"""

import argparse
import importlib.metadata
import os
import sys

import netCDF4 as nc
import numpy as np


def show_mesh_info(nc_file):
    """
    Display mesh information from a FlowFM NetCDF file.

    Args:
        nc_file (str): Path to the FlowFM NetCDF mesh file
    """
    dataset = nc.Dataset(nc_file, 'r')

    print(f"FlowFM Mesh Information from: {nc_file}")
    print("=" * 60)

    nodes = dataset.dimensions['Mesh2d_nNodes'].size
    faces = dataset.dimensions['Mesh2d_nFaces'].size
    edges = dataset.dimensions['Mesh2d_nEdges'].size

    print(f"Number of mesh nodes:     {nodes:,}")
    print(f"Number of mesh faces:     {faces:,}")
    print(f"Number of mesh edges:     {edges:,}")

    if 'Mesh2d_face_nodes' in dataset.variables:
        face_nodes = dataset.variables['Mesh2d_face_nodes'][:]
        fill_value = dataset.variables['Mesh2d_face_nodes']._FillValue
        valid_nodes = np.sum(face_nodes != fill_value, axis=1)

        triangles = int(np.sum(valid_nodes == 3))
        quads = int(np.sum(valid_nodes == 4))

        print("\nElement Types:")
        print(f"  Triangular elements:    {triangles:,}")
        print(f"  Quadrilateral elements: {quads:,}")
        print(f"  Total elements:         {triangles + quads:,}")

    if 'Mesh2d_node_x' in dataset.variables and 'Mesh2d_node_y' in dataset.variables:
        x_coords = dataset.variables['Mesh2d_node_x'][:]
        y_coords = dataset.variables['Mesh2d_node_y'][:]

        print("\nSpatial extent:")
        print(f"  X range: {np.min(x_coords):.1f} to {np.max(x_coords):.1f}")
        print(f"  Y range: {np.min(y_coords):.1f} to {np.max(y_coords):.1f}")

    dataset.close()


def main():
    parser = argparse.ArgumentParser(
        prog='meshinfo',
        description='Display mesh information from FlowFM NetCDF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  meshinfo -i FlowFM_net.nc        # Specify a NetCDF mesh file
  meshinfo -i grid.nc              # Use any FlowFM mesh file
  meshinfo -h                      # Show this help message

The tool displays:
  - Number of nodes, faces, and edges
  - Element type distribution (triangles vs quadrilaterals)
  - Spatial extent (X and Y coordinate ranges)
        """,
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {importlib.metadata.version("ncftools")}',
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        metavar='FILE',
        help='Path to the FlowFM NetCDF mesh file',
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: File '{args.input}' not found.")
        print(f"Current directory: {os.getcwd()}")
        print("Please check the file path and try again.")
        sys.exit(1)

    try:
        show_mesh_info(args.input)
    except Exception as e:
        print(f"Error reading NetCDF file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
