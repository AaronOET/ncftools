"""
mesh2pol.py - NetCDF Mesh to Polygon Converter

This script reads a NetCDF file containing 2D mesh data and converts the mesh faces
to polygons, then outputs them as ESRI Shapefiles.

Usage:
    python mesh2pol.py input.nc
    python mesh2pol.py /path/to/mesh.nc --output-dir output
    python mesh2pol.py mesh.nc --crs EPSG:4326 --quiet

Features:
- Command-line interface for batch processing
- Reads UGRID-compliant NetCDF mesh files
- Converts mesh faces to individual polygons
- Creates a dissolved polygon representing the entire mesh area
- Outputs both individual and dissolved polygons as shapefiles
- Configurable output directory and coordinate reference system
- Quiet mode for minimal output
- Provides detailed statistics about the mesh geometry

Input: NetCDF file containing mesh2d data (specified via command line)
Output (in specified directory, default: SHP_NC):
- {filename}_faces.shp (individual polygons for each mesh face)
- {filename}_dissolved.shp (single dissolved polygon of entire mesh)

Requirements: netCDF4, numpy, geopandas, shapely

Author: Generated for mesh processing workflow
Date: June 2025
"""

import netCDF4 as nc
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
from shapely.ops import unary_union
import os
import argparse
import sys

def read_mesh_netcdf(file_path, quiet=False):
    """
    Read mesh data from NetCDF file and extract face coordinates.
    Handles different naming conventions and mixed element types.

    Parameters:
    file_path (str): Path to the NetCDF file
    quiet (bool): Suppress output if True

    Returns:
    tuple: (face_x_coords, face_y_coords, node_x, node_y, face_nodes, var_names)
    """
    print_if_not_quiet(f"Reading NetCDF file: {file_path}", quiet)

    # Open the NetCDF file
    dataset = nc.Dataset(file_path, 'r')

    # Auto-detect variable names (handle different naming conventions)
    var_names = {}
    for var_name in dataset.variables.keys():
        var_lower = var_name.lower()
        if 'node_x' in var_lower:
            var_names['node_x'] = var_name
        elif 'node_y' in var_lower:
            var_names['node_y'] = var_name
        elif 'face_nodes' in var_lower:
            var_names['face_nodes'] = var_name
        elif 'face_x_bnd' in var_lower:
            var_names['face_x_bnd'] = var_name
        elif 'face_y_bnd' in var_lower:
            var_names['face_y_bnd'] = var_name

    # Check if we found all required variables
    required_vars = ['node_x', 'node_y', 'face_nodes', 'face_x_bnd', 'face_y_bnd']
    missing_vars = [var for var in required_vars if var not in var_names]
    if missing_vars:
        dataset.close()
        raise ValueError(f"Missing required variables: {missing_vars}. Available variables: {list(dataset.variables.keys())}")

    # Read the data using detected variable names
    node_x = dataset.variables[var_names['node_x']][:]
    node_y = dataset.variables[var_names['node_y']][:]
    face_nodes = dataset.variables[var_names['face_nodes']][:]
    face_x_coords = dataset.variables[var_names['face_x_bnd']][:]
    face_y_coords = dataset.variables[var_names['face_y_bnd']][:]

    dataset.close()

    if not quiet:
        print("Successfully read mesh data:")
        print(f"  - Number of nodes: {len(node_x)}")
        print(f"  - Number of faces: {len(face_x_coords)}")
        print(f"  - Max nodes per face: {face_x_coords.shape[1]}")
        print(f"  - Variable naming: {var_names['node_x'].split('_')[0]}_*")

    return face_x_coords, face_y_coords, node_x, node_y, face_nodes, var_names

def create_polygons_from_faces(face_x_coords, face_y_coords, face_nodes, quiet=False):
    """
    Create Shapely polygons from mesh face coordinates.
    Handles mixed element types (triangles and quadrilaterals).

    Parameters:
    face_x_coords (array): X coordinates of face corners
    face_y_coords (array): Y coordinates of face corners
    face_nodes (array): Face-node connectivity
    quiet (bool): Suppress output if True

    Returns:
    list: List of Shapely Polygon objects
    """
    print_if_not_quiet("Creating polygons from mesh faces...", quiet)

    polygons = []
    valid_polygons = 0
    triangle_count = 0
    quad_count = 0
    invalid_count = 0

    for i in range(len(face_x_coords)):
        # Get the coordinates for this face
        x_coords = face_x_coords[i]
        y_coords = face_y_coords[i]

        # Remove fill values and create coordinate pairs
        coords = []
        for j in range(len(x_coords)):
            if not np.ma.is_masked(x_coords[j]) and not np.ma.is_masked(y_coords[j]):
                # Check for fill values (common in NetCDF files)
                if abs(x_coords[j]) < 1e30 and abs(y_coords[j]) < 1e30:
                    coords.append((float(x_coords[j]), float(y_coords[j])))

        # Determine element type based on number of valid coordinates
        num_coords = len(coords)

        # Need at least 3 points to form a polygon
        if num_coords >= 3:
            try:
                # Close the polygon if it's not already closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])

                # Create polygon
                polygon = Polygon(coords)

                # Check if polygon is valid
                if polygon.is_valid and not polygon.is_empty:
                    polygons.append(polygon)
                    valid_polygons += 1

                    # Count element types
                    if num_coords == 3:
                        triangle_count += 1
                    elif num_coords == 4:
                        quad_count += 1
                else:
                    # Try to fix invalid polygons
                    fixed_polygon = polygon.buffer(0)
                    if fixed_polygon.is_valid and not fixed_polygon.is_empty:
                        polygons.append(fixed_polygon)
                        valid_polygons += 1

                        # Count element types
                        if num_coords == 3:
                            triangle_count += 1
                        elif num_coords == 4:
                            quad_count += 1
                    else:
                        invalid_count += 1

            except Exception as e:
                invalid_count += 1
                if not quiet:
                    print(f"Warning: Could not create polygon for face {i}: {e}")
                continue
        else:
            invalid_count += 1

    if not quiet:
        print(f"Created {valid_polygons} valid polygons out of {len(face_x_coords)} faces")
        print(f"  - Triangles: {triangle_count}")
        print(f"  - Quadrilaterals: {quad_count}")
        if invalid_count > 0:
            print(f"  - Invalid/skipped: {invalid_count}")

    return polygons

def parse_arguments():
    """
    Parse command line arguments.

    Returns:
    argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Convert NetCDF mesh file to polygon shapefiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mesh2pol.py input.nc
  python mesh2pol.py /path/to/mesh.nc
  python mesh2pol.py mesh.nc --output-dir output
  python mesh2pol.py mesh.nc --crs EPSG:4326
        """
    )

    parser.add_argument(
        "input_file",
        help="Path to the NetCDF mesh file to process"
    )

    parser.add_argument(
        "--output-dir", "-o",
        default="SHP_NC",
        help="Output directory for shapefiles (default: SHP_NC)"
    )

    parser.add_argument(
        "--crs",
        default="EPSG:28992",
        help="Coordinate Reference System for output shapefiles (default: EPSG:28992)"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-error output"
    )

    return parser.parse_args()

def print_if_not_quiet(message, quiet=False):
    """Print message if not in quiet mode."""
    if not quiet:
        print(message)

def create_geodataframe(polygons, crs="EPSG:28992", quiet=False):
    """
    Create a GeoDataFrame from the list of polygons.

    Parameters:
    polygons (list): List of Shapely Polygon objects
    crs (str): Coordinate Reference System
    quiet (bool): Suppress output if True

    Returns:
    GeoDataFrame: GeoDataFrame containing the polygons
    """
    print_if_not_quiet("Creating GeoDataFrame...", quiet)

    # Create a dataframe with polygon IDs, areas, and element types
    data = {
        'face_id': range(len(polygons)),
        'area': [poly.area for poly in polygons],
        'type': ['triangle' if len(list(poly.exterior.coords)) == 4 else
                        'quadrilateral' if len(list(poly.exterior.coords)) == 5 else
                        'other' for poly in polygons]
    }

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(data, geometry=polygons)

    # Set coordinate reference system
    gdf.crs = crs

    if not quiet:
        print(f"GeoDataFrame created with {len(gdf)} polygons")
        # Count element types
        element_counts = gdf['type'].value_counts()
        for elem_type, count in element_counts.items():
            print(f"  - {elem_type}: {count}")

    return gdf

def dissolve_polygons(gdf, quiet=False):
    """
    Dissolve all polygons into a single multipolygon.

    Parameters:
    gdf (GeoDataFrame): Input GeoDataFrame with polygons
    quiet (bool): Suppress output if True

    Returns:
    GeoDataFrame: GeoDataFrame with dissolved polygon
    """
    print_if_not_quiet("Dissolving polygons...", quiet)

    # Create a single dissolved polygon
    dissolved_geom = unary_union(gdf.geometry.tolist())

    # Create new GeoDataFrame with dissolved geometry
    dissolved_gdf = gpd.GeoDataFrame({
        'id': [1],
        'total_area': [dissolved_geom.area],
        'count': [len(gdf)]
    }, geometry=[dissolved_geom], crs=gdf.crs)

    if not quiet:
        print(f"Dissolved {len(gdf)} polygons into single geometry")
        print(f"Total area: {dissolved_geom.area:.2f} square units")

    return dissolved_gdf

def main():
    """
    Main function to process NetCDF mesh file and create shapefiles.
    """
    # Parse command line arguments
    args = parse_arguments()

    input_file = args.input_file
    output_dir = args.output_dir
    crs = args.crs
    quiet = args.quiet

    print_if_not_quiet("=== NetCDF Mesh to Polygon Converter ===", quiet)

    # Validate input file exists
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print_if_not_quiet(f"Created output directory: {output_dir}", quiet)    # Output files in the specified directory
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_individual = os.path.join(output_dir, f"{base_name}_faces.shp")
    output_dissolved = os.path.join(output_dir, f"{base_name}_dissolved.shp")

    try:
        # Step 1: Read mesh data from NetCDF
        print_if_not_quiet(f"Processing file: {input_file}", quiet)
        face_x_coords, face_y_coords, node_x, node_y, face_nodes, var_names = read_mesh_netcdf(input_file, quiet)

        # Step 2: Create polygons from mesh faces
        polygons = create_polygons_from_faces(face_x_coords, face_y_coords, face_nodes, quiet)

        if not polygons:
            print("Error: No valid polygons were created!", file=sys.stderr)
            sys.exit(1)

        # Step 3: Create GeoDataFrame
        gdf = create_geodataframe(polygons, crs, quiet)

        # Step 4: Save individual polygons to shapefile
        print_if_not_quiet(f"Saving individual polygons to: {output_individual}", quiet)
        gdf.to_file(output_individual)
        print_if_not_quiet(f"Successfully saved {len(gdf)} polygons", quiet)

        # Step 5: Dissolve polygons
        dissolved_gdf = dissolve_polygons(gdf, quiet)

        # Step 6: Save dissolved polygon to shapefile
        print_if_not_quiet(f"Saving dissolved polygon to: {output_dissolved}", quiet)
        dissolved_gdf.to_file(output_dissolved)
        print_if_not_quiet("Successfully saved dissolved polygon", quiet)

        # Print summary statistics (only if not quiet)
        if not quiet:
            print("\n=== SUMMARY ===")
            print(f"Input file: {input_file}")
            print(f"Output directory: {output_dir}")
            print(f"Individual polygons shapefile: {output_individual}")
            print(f"Dissolved polygon shapefile: {output_dissolved}")
            print(f"Number of mesh faces processed: {len(face_x_coords)}")
            print(f"Number of valid polygons created: {len(polygons)}")
            print(f"Total area of all polygons: {gdf.geometry.area.sum():.2f} square units")
            print(f"Coordinate Reference System: {gdf.crs}")
            print(f"Variable naming convention: {var_names['node_x'].split('_')[0]}_*")

            # Element type statistics
            element_counts = gdf['type'].value_counts()
            print("\n=== ELEMENT TYPE STATISTICS ===")
            for elem_type, count in element_counts.items():
                percentage = (count / len(gdf)) * 100
                print(f"{elem_type}: {count} ({percentage:.1f}%)")

            # Additional geometry statistics
            print("\n=== GEOMETRY STATISTICS ===")
            print(f"Min polygon area: {gdf.geometry.area.min():.2f}")
            print(f"Max polygon area: {gdf.geometry.area.max():.2f}")
            print(f"Mean polygon area: {gdf.geometry.area.mean():.2f}")
            print("Total mesh extent:")
            bounds = gdf.total_bounds
            print(f"  X: {bounds[0]:.2f} to {bounds[2]:.2f} (width: {bounds[2]-bounds[0]:.2f})")
            print(f"  Y: {bounds[1]:.2f} to {bounds[3]:.2f} (height: {bounds[3]-bounds[1]:.2f})")
        else:
            # In quiet mode, just print the output files
            print("Output files created:")
            print(f"  {output_individual}")
            print(f"  {output_dissolved}")

    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found!", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if not quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
