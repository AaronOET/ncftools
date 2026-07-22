#!/usr/bin/env python3
"""
nc2shp - Convert NetCDF mesh faces to ESRI Shapefiles

Reads a UGRID-compliant NetCDF mesh file and writes two shapefiles:
  {stem}_faces.shp      - one polygon per mesh face
  {stem}_dissolved.shp  - single dissolved polygon of the entire mesh
"""

import argparse
import importlib.metadata
import os
import sys

import netCDF4 as nc
import numpy as np
import geopandas as gpd
import shapely


def read_mesh_netcdf(file_path, quiet=False):
    """
    Read mesh face coordinates from a UGRID NetCDF file.

    Returns:
        tuple: (face_x_coords, face_y_coords, node_x, node_y, face_nodes, var_names)
    """
    _print(f"Reading NetCDF file: {file_path}", quiet)

    dataset = nc.Dataset(file_path, 'r')

    var_names = {}
    for var_name in dataset.variables:
        vl = var_name.lower()
        if 'node_x' in vl:
            var_names['node_x'] = var_name
        elif 'node_y' in vl:
            var_names['node_y'] = var_name
        elif 'face_nodes' in vl:
            var_names['face_nodes'] = var_name
        elif 'face_x_bnd' in vl:
            var_names['face_x_bnd'] = var_name
        elif 'face_y_bnd' in vl:
            var_names['face_y_bnd'] = var_name

    required = ['node_x', 'node_y', 'face_nodes', 'face_x_bnd', 'face_y_bnd']
    missing = [v for v in required if v not in var_names]
    if missing:
        dataset.close()
        raise ValueError(
            f"Missing required variables: {missing}. "
            f"Available: {list(dataset.variables.keys())}"
        )

    node_x = dataset.variables[var_names['node_x']][:]
    node_y = dataset.variables[var_names['node_y']][:]
    face_nodes = dataset.variables[var_names['face_nodes']][:]
    face_x = dataset.variables[var_names['face_x_bnd']][:]
    face_y = dataset.variables[var_names['face_y_bnd']][:]
    dataset.close()

    if not quiet:
        print(f"  Nodes: {len(node_x):,}  Faces: {len(face_x):,}  "
              f"Max nodes/face: {face_x.shape[1]}")

    return face_x, face_y, node_x, node_y, face_nodes, var_names


def create_polygons(face_x, face_y, quiet=False):
    """
    Build Shapely Polygon objects from mesh face coordinate arrays.

    Vectorized over all faces at once: the per-node validity mask, ring
    coordinates, and polygon construction/repair are computed with numpy
    and shapely's array API rather than a per-face Python loop.

    Returns:
        list[Polygon]
    """
    _print("Creating polygons from mesh faces...", quiet)

    x_data = np.ma.getdata(face_x).astype(np.float64)
    y_data = np.ma.getdata(face_y).astype(np.float64)
    valid = (
        ~np.ma.getmaskarray(face_x)
        & ~np.ma.getmaskarray(face_y)
        & (np.abs(x_data) < 1e30)
        & (np.abs(y_data) < 1e30)
    )

    n_valid_per_face = valid.sum(axis=1)
    keep_face = n_valid_per_face >= 3

    row_idx, col_idx = np.nonzero(valid & keep_face[:, None])
    coords = np.column_stack((x_data[row_idx, col_idx], y_data[row_idx, col_idx]))

    kept_face_ids = np.nonzero(keep_face)[0]
    ring_id = np.full(len(keep_face), -1, dtype=np.int64)
    ring_id[kept_face_ids] = np.arange(kept_face_ids.size)
    ring_indices = ring_id[row_idx]

    rings = shapely.linearrings(coords, indices=ring_indices)
    polys = shapely.polygons(rings)

    bad = ~shapely.is_valid(polys) | shapely.is_empty(polys)
    if bad.any():
        polys[bad] = shapely.buffer(polys[bad], 0)
        bad = ~shapely.is_valid(polys) | shapely.is_empty(polys)

    n_invalid = int(len(face_x) - keep_face.sum()) + int(bad.sum())
    polys = polys[~bad]
    node_counts = n_valid_per_face[kept_face_ids][~bad]

    tri = int((node_counts == 3).sum())
    quad = int((node_counts == 4).sum())

    if not quiet:
        print(f"  Valid polygons: {len(polys)}  "
              f"(triangles: {tri}, quads: {quad}, skipped: {n_invalid})")

    return list(polys)


def create_geodataframe(polygons, crs="EPSG:3826"):
    """Build a GeoDataFrame from a list of Shapely polygons."""
    data = {
        'face_id': range(len(polygons)),
        'area': shapely.area(polygons),
        'type': [
            'triangle' if len(p.exterior.coords) == 4
            else 'quadrilateral' if len(p.exterior.coords) == 5
            else 'other'
            for p in polygons
        ],
    }
    return gpd.GeoDataFrame(data, geometry=polygons, crs=crs)


def dissolve_geodataframe(gdf, quiet=False):
    """Dissolve all polygons into a single geometry."""
    _print("Dissolving polygons...", quiet)
    geom = shapely.union_all(gdf.geometry.values)
    dissolved = gpd.GeoDataFrame(
        {'id': [1], 'total_area': [geom.area], 'count': [len(gdf)]},
        geometry=[geom],
        crs=gdf.crs,
    )
    _print(f"  Total area: {geom.area:.2f} sq units", quiet)
    return dissolved


def mesh_to_shp(input_file, output_dir="SHP_NC", crs="EPSG:3826", quiet=False):
    """
    Convert a NetCDF mesh file to face and dissolved shapefiles.

    Args:
        input_file (str): Path to the input NetCDF file.
        output_dir (str): Directory for output shapefiles.
        crs (str): CRS for output shapefiles.
        quiet (bool): Suppress non-error output.

    Returns:
        tuple[str, str]: Paths to (faces_shp, dissolved_shp).
    """
    _print("=== NetCDF Mesh to Shapefile Converter ===", quiet)

    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(input_file))[0]
    out_faces = os.path.join(output_dir, f"{stem}_faces.shp")
    out_dissolved = os.path.join(output_dir, f"{stem}_dissolved.shp")

    face_x, face_y, node_x, node_y, face_nodes, var_names = read_mesh_netcdf(
        input_file, quiet
    )
    polygons = create_polygons(face_x, face_y, quiet)

    if not polygons:
        raise RuntimeError("No valid polygons were created from the mesh.")

    gdf = create_geodataframe(polygons, crs)
    _print(f"Saving faces shapefile:    {out_faces}", quiet)
    gdf.to_file(out_faces)

    dissolved = dissolve_geodataframe(gdf, quiet)
    _print(f"Saving dissolved shapefile: {out_dissolved}", quiet)
    dissolved.to_file(out_dissolved)

    if not quiet:
        bounds = gdf.total_bounds
        counts = gdf['type'].value_counts()
        print("\n=== SUMMARY ===")
        print(f"  Input:     {input_file}")
        print(f"  Faces:     {out_faces}")
        print(f"  Dissolved: {out_dissolved}")
        print(f"  Faces processed: {len(face_x):,}  Valid: {len(polygons):,}")
        print(f"  CRS: {gdf.crs}")
        for t, n in counts.items():
            print(f"  {t}: {n} ({n/len(gdf)*100:.1f}%)")
        print(f"  Area — min: {gdf.geometry.area.min():.2f}  "
              f"max: {gdf.geometry.area.max():.2f}  "
              f"mean: {gdf.geometry.area.mean():.2f}")
        print(f"  X: {bounds[0]:.2f} to {bounds[2]:.2f}")
        print(f"  Y: {bounds[1]:.2f} to {bounds[3]:.2f}")

    return out_faces, out_dissolved


def _print(msg, quiet=False):
    if not quiet:
        print(msg)


def main():
    parser = argparse.ArgumentParser(
        prog='nc2shp',
        description='Convert a NetCDF mesh file to ESRI Shapefiles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nc2shp -i FlowFM_net.nc
  nc2shp -i mesh.nc -o output --crs EPSG:4326
  nc2shp -i mesh.nc -q
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
        help='Path to the NetCDF mesh file',
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='SHP_NC',
        metavar='DIR',
        help='Output directory for shapefiles (default: SHP_NC)',
    )
    parser.add_argument(
        '--crs',
        default='EPSG:3826',
        help='Coordinate reference system (default: EPSG:3826)',
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
        faces, dissolved = mesh_to_shp(
            args.input, args.output_dir, args.crs, args.quiet
        )
        if args.quiet:
            print(faces)
            print(dissolved)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()