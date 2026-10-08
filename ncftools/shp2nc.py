#!/usr/bin/env python3
"""
shp2nc - Rebuild a UGRID mesh NetCDF file from a polygon shapefile

Reads a polygon shapefile in which every polygon is one mesh cell (e.g. the
{stem}_faces.shp written by nc2shp, or a mesh exported from QGIS / RGFGRID)
and writes a D-Flow FM 2D net file ({stem}_net.nc):
  - vertices shared by neighbouring cells are merged into one node
    (within a snapping tolerance)
  - every cell is made counter-clockwise, as UGRID / D-Flow FM require
  - edges, edge-face connectivity and face centres are derived
  - numeric shapefile attribute columns are kept as face variables
"""

import argparse
import importlib.metadata
import os
import sys
import warnings

import netCDF4 as nc
import numpy as np
import pandas as pd
import geopandas as gpd
import pyproj
import shapely

FILL = -999


def read_cells(shp_path, crs=None, quiet=False):
    """
    Read the shapefile and return a GeoDataFrame with one Polygon per row.

    MultiPolygons are split into separate cells; interior rings are ignored.
    `crs` is only used when the shapefile has no .prj.
    """
    _print(f"Reading shapefile: {shp_path}", quiet)

    gdf = gpd.read_file(shp_path)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf = gdf.explode(index_parts=False, ignore_index=True)

    bad = ~gdf.geom_type.isin(["Polygon"])
    if bad.any():
        raise TypeError(f"{int(bad.sum())} non-polygon geometries in {shp_path}")
    if gdf.empty:
        raise ValueError(f"No polygons found in {shp_path}")

    holes = shapely.get_num_interior_rings(gdf.geometry.values) > 0
    if holes.any():
        print(f"WARNING: {int(holes.sum())} cells have holes; "
              f"interior rings are ignored.", file=sys.stderr)

    if gdf.crs is None:
        if crs is None:
            raise ValueError("The shapefile has no CRS (.prj); give one with --crs")
        gdf = gdf.set_crs(crs)

    if not quiet:
        print(f"  Cells: {len(gdf):,}  CRS: {gdf.crs}")
    return gdf


def polygons_to_mesh(polygons, tol=1.0e-3, quiet=False):
    """
    Convert polygons to nodes and a face-node table.

    Vertices closer than about `tol` (map units) are merged into one node.

    Returns:
        tuple: (node_x, node_y, face_nodes) where face_nodes is a 0-based
        (n_face, max_nodes) array padded with -1, counter-clockwise.
    """
    rings = shapely.get_exterior_ring(polygons)
    xy, which = shapely.get_coordinates(rings, return_index=True)

    # drop the closing vertex of every ring
    last = np.r_[which[1:] != which[:-1], True]
    xy, which = xy[~last], which[~last]

    # merge shared vertices: snap to a tol-sized lattice, then take unique keys
    key = np.round(xy / tol).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True,
                                  return_inverse=True)
    inverse = inverse.ravel()
    nodes = xy[first]  # keep an original coordinate as the node position

    n_face = len(polygons)
    counts = np.bincount(which, minlength=n_face)
    start = np.r_[0, np.cumsum(counts)[:-1]]
    faces = np.full((n_face, counts.max()), -1, dtype=np.int64)
    faces[which, np.arange(len(which)) - start[which]] = inverse

    # snapping can make consecutive vertices identical; drop those repeats
    for i in range(n_face):
        f = faces[i][faces[i] >= 0]
        keep = f != np.roll(f, 1)
        if not keep.all():
            faces[i] = -1
            faces[i, :keep.sum()] = f[keep]
    nvalid = (faces >= 0).sum(axis=1)
    if (nvalid < 3).any():
        raise ValueError(f"{int((nvalid < 3).sum())} cells collapsed to fewer "
                         f"than 3 nodes; reduce --tol")
    faces = faces[:, :nvalid.max()]

    # orientation: shoelace area over the valid part of each row
    rows = np.arange(n_face)
    area = np.zeros(n_face)
    for k in range(faces.shape[1]):
        nxt = np.where(k + 1 < nvalid, k + 1, 0)
        a, b = faces[:, k], faces[rows, nxt]
        cross = nodes[a, 0] * nodes[b, 1] - nodes[b, 0] * nodes[a, 1]
        area += np.where(k < nvalid, cross, 0.0)
    cw = np.flatnonzero(area < 0)
    for i in cw:
        faces[i, :nvalid[i]] = faces[i, :nvalid[i]][::-1]

    if not quiet:
        print(f"  Nodes: {len(nodes):,}  "
              f"(merged from {len(xy):,} vertices, tol={tol:g})")
        print(f"  Clockwise cells reversed: {len(cw):,} of {n_face:,}")

    return nodes[:, 0], nodes[:, 1], faces


def build_edges(faces):
    """
    Derive edges from a 0-based face-node table.

    Returns:
        tuple: (edge_nodes, edge_faces), both (n_edge, 2), 0-based, -1 where
        an edge has only one neighbouring face (mesh boundary).
    """
    n_face, n_max = faces.shape
    nvalid = (faces >= 0).sum(axis=1)
    k = np.arange(n_max)
    nxt = np.where(k + 1 < nvalid[:, None], k + 1, 0)
    valid = k < nvalid[:, None]

    a = faces[valid]
    b = faces[np.arange(n_face)[:, None], nxt][valid]
    face_of = np.broadcast_to(np.arange(n_face)[:, None], faces.shape)[valid]

    pairs = np.sort(np.column_stack((a, b)), axis=1)
    edge_nodes, inverse = np.unique(pairs, axis=0, return_inverse=True)
    inverse = inverse.ravel()

    order = np.argsort(inverse, kind="stable")
    inv_sorted = inverse[order]
    group_start = np.r_[0, np.flatnonzero(np.diff(inv_sorted)) + 1]
    col = np.arange(len(order)) - np.repeat(
        group_start, np.diff(np.r_[group_start, len(order)]))
    if (col > 1).any():
        raise ValueError("Some edges are shared by more than two cells; "
                         "the polygons overlap")

    edge_faces = np.full((len(edge_nodes), 2), -1, dtype=np.int64)
    edge_faces[inv_sorted, col] = face_of[order]
    return edge_nodes, edge_faces


def _crs_attrs(crs):
    """CF grid-mapping attributes for the CRS variable, D-Flow FM style."""
    attrs = {"name": crs.name}
    try:
        cf = crs.to_cf()
    except pyproj.exceptions.CRSError:
        cf = {}
    for key, val in cf.items():
        if key != "crs_wkt" and val is not None:
            attrs[key] = val
    epsg = crs.to_epsg() or 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # lossy PROJ string notice
        proj4 = crs.to_proj4()
    attrs.update({
        "epsg": np.int32(epsg),
        "EPSG_code": f"EPSG:{epsg}" if epsg else "",
        "value": "value is equal to EPSG code",
        "proj4_params": proj4,
        "wkt": crs.to_wkt(),
    })
    return attrs, epsg


def write_net_nc(out_path, node_x, node_y, faces, crs, face_data=None,
                 node_z=None):
    """
    Write a UGRID-1.0 net file laid out like an RGFGRID / D-Flow FM 2D3D net
    file (mesh2d_* names, 1-based indices, -999 fill values).
    """
    crs = pyproj.CRS.from_user_input(crs)
    edge_nodes, edge_faces = build_edges(faces)
    n_node, n_edge, n_face = len(node_x), len(edge_nodes), len(faces)

    valid = faces >= 0
    safe = np.where(valid, faces, 0)
    x_bnd = np.where(valid, node_x[safe], FILL)
    y_bnd = np.where(valid, node_y[safe], FILL)

    polys = shapely.polygons(
        shapely.linearrings(np.column_stack((node_x[safe[valid]],
                                             node_y[safe[valid]])),
                            indices=np.nonzero(valid)[0]))
    centroids = shapely.get_coordinates(shapely.centroid(polys))
    edge_x = node_x[edge_nodes].mean(axis=1)
    edge_y = node_y[edge_nodes].mean(axis=1)

    if crs.is_geographic:
        gm = "wgs84"
        units = {"x": "degrees_east", "y": "degrees_north"}
        std = {"x": "longitude", "y": "latitude"}
    else:
        gm = "projected_coordinate_system"
        units = {"x": "m", "y": "m"}
        std = {"x": "projection_x_coordinate", "y": "projection_y_coordinate"}

    def one_based(a):
        return np.where(a >= 0, a + 1, FILL).astype(np.int32)

    with nc.Dataset(out_path, "w", format="NETCDF4") as ds:
        ds.institution = "ncftools"
        ds.source = f"shp2nc (ncftools {_version()})"
        ds.Conventions = "CF-1.8 UGRID-1.0 Deltares-0.10"

        nN, nE, nF = "mesh2d_nNodes", "mesh2d_nEdges", "mesh2d_nFaces"
        nM = "mesh2d_nMax_face_nodes"
        ds.createDimension(nN, n_node)
        ds.createDimension(nE, n_edge)
        ds.createDimension(nF, n_face)
        ds.createDimension(nM, faces.shape[1])
        ds.createDimension("Two", 2)

        crs_attrs, epsg = _crs_attrs(crs)
        v = ds.createVariable(gm, "i4")
        v.setncatts(crs_attrs)
        v.assignValue(epsg)

        v = ds.createVariable("mesh2d", "i4")
        v.setncatts({
            "cf_role": "mesh_topology",
            "long_name": "Topology data of 2D mesh",
            "topology_dimension": np.int32(2),
            "node_coordinates": "mesh2d_node_x mesh2d_node_y",
            "node_dimension": nN,
            "max_face_nodes_dimension": nM,
            "edge_node_connectivity": "mesh2d_edge_nodes",
            "edge_dimension": nE,
            "edge_coordinates": "mesh2d_edge_x mesh2d_edge_y",
            "face_node_connectivity": "mesh2d_face_nodes",
            "face_dimension": nF,
            "edge_face_connectivity": "mesh2d_edge_faces",
            "face_coordinates": "mesh2d_face_x mesh2d_face_y",
        })
        v.assignValue(0)

        def coord(name, dims, data, axis, what, fill=None, **extra):
            var = ds.createVariable(name, "f8", dims, fill_value=fill)
            var.setncatts({
                "units": units[axis],
                "standard_name": std[axis],
                "long_name": f"{axis}-coordinate of {what}",
                **extra,
            })
            var[:] = data

        coord("mesh2d_node_x", (nN,), node_x, "x", "mesh nodes")
        coord("mesh2d_node_y", (nN,), node_y, "y", "mesh nodes")

        v = ds.createVariable("mesh2d_node_z", "f8", (nN,), fill_value=float(FILL))
        v.setncatts({
            "mesh": "mesh2d",
            "location": "node",
            "coordinates": "mesh2d_node_x mesh2d_node_y",
            "standard_name": "altitude",
            "long_name": "z-coordinate of mesh nodes",
            "units": "m",
            "grid_mapping": gm,
        })
        v[:] = np.full(n_node, FILL if node_z is None else node_z, dtype=float)

        coord("mesh2d_edge_x", (nE,), edge_x, "x", "mesh edges (midpoint)")
        coord("mesh2d_edge_y", (nE,), edge_y, "y", "mesh edges (midpoint)")

        def connectivity(name, dims, data, role, long_name):
            var = ds.createVariable(name, "i4", dims, fill_value=np.int32(FILL))
            var.setncatts({"cf_role": role, "long_name": long_name,
                           "start_index": np.int32(1)})
            var[:] = one_based(data)

        connectivity("mesh2d_edge_nodes", (nE, "Two"), edge_nodes,
                     "edge_node_connectivity",
                     "Start and end nodes of mesh edges")
        connectivity("mesh2d_face_nodes", (nF, nM), faces,
                     "face_node_connectivity",
                     "Vertex nodes of mesh faces (counterclockwise)")
        connectivity("mesh2d_edge_faces", (nE, "Two"), edge_faces,
                     "edge_face_connectivity",
                     "Neighboring faces of mesh edges")

        coord("mesh2d_face_x", (nF,), centroids[:, 0], "x",
              "mesh face (centroid)", bounds="mesh2d_face_x_bnd")
        coord("mesh2d_face_y", (nF,), centroids[:, 1], "y",
              "mesh face (centroid)", bounds="mesh2d_face_y_bnd")
        coord("mesh2d_face_x_bnd", (nF, nM), x_bnd, "x",
              "mesh face corners (bounds)", fill=float(FILL))
        coord("mesh2d_face_y_bnd", (nF, nM), y_bnd, "y",
              "mesh face corners (bounds)", fill=float(FILL))

        for col, values in (face_data or {}).items():
            var = ds.createVariable(f"mesh2d_{col}", values.dtype, (nF,))
            var.setncatts({"mesh": "mesh2d", "location": "face",
                           "long_name": f"shapefile attribute {col}"})
            var[:] = values

    return n_node, n_edge, n_face


def shp_to_nc(input_file, output_file=None, tol=1.0e-3, crs=None, node_z=None,
              quiet=False):
    """
    Convert a cell-polygon shapefile to a UGRID mesh NetCDF file.

    Args:
        input_file (str): Path to the input polygon shapefile.
        output_file (str): Output NetCDF path (default: {stem}_net.nc in the
            current directory).
        tol (float): Node merge tolerance in map units.
        crs (str): CRS to use when the shapefile has no .prj.
        node_z (float): Constant bed level for mesh2d_node_z (default: missing).
        quiet (bool): Suppress non-error output.

    Returns:
        str: Path to the written NetCDF file.
    """
    _print("=== Shapefile to NetCDF Mesh Converter ===", quiet)

    if output_file is None:
        stem = os.path.splitext(os.path.basename(input_file))[0]
        output_file = f"{stem}_net.nc"
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    gdf = read_cells(input_file, crs, quiet)

    _print("Building mesh topology...", quiet)
    node_x, node_y, faces = polygons_to_mesh(gdf.geometry.values, tol, quiet)

    face_data = {}
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        series = gdf[col]
        if (pd.api.types.is_numeric_dtype(series)
                and not pd.api.types.is_bool_dtype(series)):
            face_data[col] = series.to_numpy()

    _print(f"Writing NetCDF file: {output_file}", quiet)
    n_node, n_edge, n_face = write_net_nc(
        output_file, node_x, node_y, faces, gdf.crs, face_data, node_z
    )

    if not quiet:
        nvalid = (faces >= 0).sum(axis=1)
        x0, y0, x1, y1 = gdf.total_bounds
        print("\n=== SUMMARY ===")
        print(f"  Input:  {input_file}")
        print(f"  Output: {output_file}")
        print(f"  Nodes: {n_node:,}  Edges: {n_edge:,}  Faces: {n_face:,}")
        print(f"  triangles: {int((nvalid == 3).sum())}  "
              f"quadrilaterals: {int((nvalid == 4).sum())}  "
              f"other: {int((nvalid > 4).sum())}")
        if face_data:
            print(f"  Face attributes: {', '.join(face_data)}")
        print(f"  CRS: {gdf.crs}")
        print(f"  X: {x0:.2f} to {x1:.2f}")
        print(f"  Y: {y0:.2f} to {y1:.2f}")

    return output_file


def _version():
    try:
        return importlib.metadata.version("ncftools")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _print(msg, quiet=False):
    if not quiet:
        print(msg)


def main():
    parser = argparse.ArgumentParser(
        prog='shp2nc',
        description='Rebuild a UGRID mesh NetCDF file from a cell-polygon shapefile',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  shp2nc mesh.shp                   # writes mesh_net.nc
  shp2nc -i mesh.shp                # same, with the -i flag
  shp2nc mesh.shp -o FlowFM_net.nc
  shp2nc mesh.shp --tol 0.01 --node-z -5.0
  shp2nc mesh.shp --crs EPSG:3826   # only used if mesh.prj is missing
  shp2nc mesh.shp -q
        """,
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {_version()}',
    )
    parser.add_argument(
        'file',
        nargs='?',
        metavar='FILE',
        help='Path to the polygon shapefile (one polygon per mesh cell)',
    )
    parser.add_argument(
        '-i', '--input',
        metavar='FILE',
        help='Same as FILE',
    )
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        help='Output NetCDF file (default: {stem}_net.nc in the current directory)',
    )
    parser.add_argument(
        '--tol',
        type=float,
        default=1.0e-3,
        help='Node merge tolerance in map units (default: 0.001)',
    )
    parser.add_argument(
        '--node-z',
        type=float,
        default=None,
        metavar='Z',
        help='Constant bed level written to mesh2d_node_z (default: missing, -999)',
    )
    parser.add_argument(
        '--crs',
        default=None,
        help='CRS to use when the shapefile has no .prj (e.g. EPSG:3826)',
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output',
    )

    args = parser.parse_args()

    if args.file and args.input:
        parser.error('give the shapefile either as FILE or with -i, not both')
    args.input = args.file or args.input
    if not args.input:
        parser.error('the shapefile is required (give it as FILE or with -i)')
    if args.tol <= 0:
        parser.error('--tol must be positive')

    if not os.path.isfile(args.input):
        print(f"Error: File '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        out = shp_to_nc(args.input, args.output, args.tol, args.crs,
                        args.node_z, args.quiet)
        if args.quiet:
            print(out)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
