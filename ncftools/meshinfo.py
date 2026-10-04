#!/usr/bin/env python3
"""
meshinfo - Display mesh information from FlowFM NetCDF files
Uses netCDF4 Python bindings
"""

import argparse
import os
import sys

import netCDF4 as nc
import numpy as np


MAX_CELL_NODES = 6  # D-Flow FM only treats closed polygons up to 6 nodes as cells


def find_net_cells(x, y, links):
    """
    Derive the 2D cells of an old-format net file from its node-link graph.

    Traces every face of the planar graph by walking half-edges with the face
    kept on the left. Counter-clockwise faces of at most MAX_CELL_NODES nodes
    are cells; the outer boundary and unmeshed holes are not.

    Args:
        x, y (ndarray): Node coordinates
        links (ndarray): (nLinks, 2) zero-based node indices

    Returns:
        ndarray: Number of nodes of each cell
    """
    n_links = len(links)
    if n_links == 0:
        return np.array([], dtype=int)

    src = np.concatenate([links[:, 0], links[:, 1]])
    dst = np.concatenate([links[:, 1], links[:, 0]])
    twin = np.concatenate([np.arange(n_links, 2 * n_links), np.arange(n_links)])

    # Sort half-edges around each origin node by direction (counter-clockwise)
    angle = np.arctan2(y[dst] - y[src], x[dst] - x[src])
    order = np.lexsort((angle, src))
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    degree = np.bincount(src, minlength=len(x))
    start = np.concatenate([[0], np.cumsum(degree)[:-1]])

    # Next half-edge in the face: the one preceding the twin around the end node
    s = start[dst]
    nxt = order[s + (rank[twin] - s - 1) % degree[dst]]

    # Label each face cycle by its smallest half-edge index (pointer jumping)
    label = np.arange(len(nxt))
    jump = nxt
    for _ in range(int(np.ceil(np.log2(len(nxt)))) + 1):
        label = np.minimum(label, label[jump])
        jump = jump[jump]

    n_nodes = np.bincount(label, minlength=len(nxt))
    area2 = np.bincount(label, weights=x[src] * y[dst] - x[dst] * y[src],
                        minlength=len(nxt))
    is_cell = (n_nodes >= 3) & (n_nodes <= MAX_CELL_NODES) & (area2 > 0)
    return n_nodes[is_cell]


def _read_ugrid(dataset):
    """Read counts and coordinates from a UGRID (Mesh2d_*) file."""
    info = {
        'nodes': dataset.dimensions['Mesh2d_nNodes'].size,
        'faces': dataset.dimensions['Mesh2d_nFaces'].size,
        'edges': dataset.dimensions['Mesh2d_nEdges'].size,
        'face_sizes': None,
        'x': None,
        'y': None,
    }

    if 'Mesh2d_face_nodes' in dataset.variables:
        face_nodes = dataset.variables['Mesh2d_face_nodes'][:]
        fill_value = dataset.variables['Mesh2d_face_nodes']._FillValue
        info['face_sizes'] = np.sum(face_nodes != fill_value, axis=1)

    if 'Mesh2d_node_x' in dataset.variables and 'Mesh2d_node_y' in dataset.variables:
        info['x'] = dataset.variables['Mesh2d_node_x'][:]
        info['y'] = dataset.variables['Mesh2d_node_y'][:]

    return info


def _read_net(dataset):
    """Read counts and coordinates from an old-format (NetNode/NetLink) net file."""
    x = np.asarray(dataset.variables['NetNode_x'][:], dtype=float)
    y = np.asarray(dataset.variables['NetNode_y'][:], dtype=float)
    links = np.asarray(dataset.variables['NetLink'][:], dtype=np.int64)
    start_index = getattr(dataset.variables['NetLink'], 'start_index', 1)
    face_sizes = find_net_cells(x, y, links - start_index)

    return {
        'nodes': len(x),
        'faces': len(face_sizes),
        'edges': len(links),
        'face_sizes': face_sizes,
        'x': x,
        'y': y,
    }


def show_mesh_info(nc_file):
    """
    Display mesh information from a FlowFM NetCDF file.

    Supports both UGRID map/net files (Mesh2d_* variables) and old-format
    net files (NetNode_x/NetNode_y/NetLink), whose cells are derived from
    the links.

    Args:
        nc_file (str): Path to the FlowFM NetCDF mesh file
    """
    with nc.Dataset(nc_file, 'r') as dataset:
        if 'Mesh2d_nNodes' in dataset.dimensions:
            info = _read_ugrid(dataset)
            derived = False
        elif all(v in dataset.variables for v in ('NetNode_x', 'NetNode_y', 'NetLink')):
            info = _read_net(dataset)
            derived = True
        else:
            raise ValueError('no Mesh2d_* or NetNode/NetLink variables found')

    print(f"FlowFM Mesh Information from: {nc_file}")
    print("=" * 60)

    nodes, faces, edges = info['nodes'], info['faces'], info['edges']
    suffix = "  (derived from NetLink)" if derived else ""

    print(f"Number of mesh nodes:     {nodes:,}")
    print(f"Number of mesh faces:     {faces:,}{suffix}")
    print(f"Number of mesh edges:     {edges:,}")

    if info['face_sizes'] is not None:
        valid_nodes = info['face_sizes']

        triangles = int(np.sum(valid_nodes == 3))
        quads = int(np.sum(valid_nodes == 4))
        others = int(np.sum(valid_nodes > 4))

        print("\nElement Types:")
        print(f"  Triangular elements:    {triangles:,}")
        print(f"  Quadrilateral elements: {quads:,}")
        if others:
            print(f"  5-6 sided elements:     {others:,}")
        print(f"  Total elements:         {triangles + quads + others:,}")

    if info['x'] is not None and len(info['x']):
        x_coords, y_coords = info['x'], info['y']

        print("\nSpatial extent:")
        print(f"  X range: {np.min(x_coords):.1f} to {np.max(x_coords):.1f}")
        print(f"  Y range: {np.min(y_coords):.1f} to {np.max(y_coords):.1f}")


def main():
    parser = argparse.ArgumentParser(
        prog='meshinfo',
        description='Display mesh information from FlowFM NetCDF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  meshinfo                         # Use default FlowFM_net.nc
  meshinfo grid.nc                 # Use any FlowFM mesh file
  meshinfo -i grid.nc              # Same, with the -i flag
  meshinfo -h                      # Show this help message

The tool displays:
  - Number of nodes, faces, and edges
  - Element type distribution (triangles vs quadrilaterals)
  - Spatial extent (X and Y coordinate ranges)
        """,
    )

    parser.add_argument(
        'file',
        nargs='?',
        metavar='FILE',
        help='Path to the FlowFM NetCDF mesh file (default: FlowFM_net.nc)',
    )
    parser.add_argument(
        '-i', '--input',
        metavar='FILE',
        help='Same as FILE (kept for backward compatibility)',
    )

    args = parser.parse_args()

    if args.file and args.input:
        parser.error('give the mesh file either as FILE or with -i, not both')
    args.input = args.file or args.input or 'FlowFM_net.nc'

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
