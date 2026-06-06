import netCDF4 as nc
import numpy as np
import argparse
import sys
import os

def show_mesh_info(nc_file):
    """
    Show mesh information from FlowFM_net.nc file
    """
    try:
        # Open the NetCDF file
        dataset = nc.Dataset(nc_file, 'r')
        
        print(f"FlowFM Mesh Information from: {nc_file}")
        print("=" * 60)
        
        # Get mesh dimensions
        nodes = dataset.dimensions['Mesh2d_nNodes'].size
        faces = dataset.dimensions['Mesh2d_nFaces'].size  
        edges = dataset.dimensions['Mesh2d_nEdges'].size
        
        print(f"Number of mesh nodes:     {nodes:,}")
        print(f"Number of mesh faces:     {faces:,}")
        print(f"Number of mesh edges:     {edges:,}")
        
        # Analyze face types
        if 'Mesh2d_face_nodes' in dataset.variables:
            face_nodes = dataset.variables['Mesh2d_face_nodes'][:]
            
            # Count nodes per face (excluding fill values)
            fill_value = dataset.variables['Mesh2d_face_nodes']._FillValue
            valid_nodes = np.sum(face_nodes != fill_value, axis=1)
            
            triangles = np.sum(valid_nodes == 3)
            quads = np.sum(valid_nodes == 4)
            
            print("\nElement Types:")
            print(f"  Triangular elements:    {triangles:,}")
            print(f"  Quadrilateral elements: {quads:,}")
            print(f"  Total elements:         {triangles + quads:,}")
          # Additional mesh info
        # if 'Mesh2d_node_z' in dataset.variables:
        #     z_coords = dataset.variables['Mesh2d_node_z'][:]
        #     print("\nDepth range:")
        #     print(f"  Minimum depth: {np.min(z_coords):.3f} m")
        #     print(f"  Maximum depth: {np.max(z_coords):.3f} m")
        
        # Coordinate bounds
        if 'Mesh2d_node_x' in dataset.variables and 'Mesh2d_node_y' in dataset.variables:
            x_coords = dataset.variables['Mesh2d_node_x'][:]
            y_coords = dataset.variables['Mesh2d_node_y'][:]
            
            print("\nSpatial extent:")
            print(f"  X range: {np.min(x_coords):.1f} to {np.max(x_coords):.1f}")
            print(f"  Y range: {np.min(y_coords):.1f} to {np.max(y_coords):.1f}")
        
        dataset.close()
        
    except Exception as e:
        print(f"Error reading NetCDF file: {e}")

def main():
    """
    Main function to parse command line arguments and show mesh information
    """
    # Create argument parser with detailed description and examples
    parser = argparse.ArgumentParser(
        description='Display comprehensive mesh information from FlowFM NetCDF files',
        epilog='''
Examples:
  python mesh_info.py                          # Use default FlowFM_net.nc file
  python mesh_info.py -f my_mesh.nc            # Specify custom NetCDF file
  python mesh_info.py --file grid.nc           # Long form option
  python mesh_info.py -h                       # Show this help message

The script analyzes FlowFM mesh files and displays:
  - Number of nodes, faces, and edges
  - Element type distribution (triangles vs quadrilaterals)
  - Spatial extent (X and Y coordinate ranges)
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add argument for NetCDF file
    parser.add_argument(
        '-f', '--file',
        default='FlowFM_net.nc',
        help='Path to the FlowFM NetCDF mesh file (default: FlowFM_net.nc)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.isfile(args.file):
        print(f"Error: File '{args.file}' not found.")
        print(f"Current directory: {os.getcwd()}")
        print("Please check the file path and try again.")
        sys.exit(1)
    
    # Show mesh information
    show_mesh_info(args.file)

if __name__ == "__main__":
    main()
