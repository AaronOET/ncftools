#!/usr/bin/env python3
"""
ncinfo - List the variables in NetCDF files

For every variable prints its name, dimensions, shape, data type, units and
long name. With -d/--dims the file's dimensions (name, size, unlimited) are
listed as well.
"""

import argparse
import importlib.metadata
import os
import sys

import netCDF4 as nc


def read_info(file_path):
    """
    Read variable and dimension metadata from a NetCDF file.

    Returns:
        tuple: (variables, dimensions) where variables is a list of dicts with
        keys name, dims, shape, dtype, units, long_name, and dimensions is a
        list of dicts with keys name, size, unlimited.
    """
    with nc.Dataset(file_path, 'r') as ds:
        dimensions = [
            {'name': name, 'size': len(dim), 'unlimited': dim.isunlimited()}
            for name, dim in ds.dimensions.items()
        ]
        variables = []
        for name, var in ds.variables.items():
            attrs = var.ncattrs()
            long_name = var.getncattr('long_name') if 'long_name' in attrs else (
                var.getncattr('standard_name') if 'standard_name' in attrs else '')
            variables.append({
                'name': name,
                'dims': var.dimensions,
                'shape': var.shape,
                'dtype': str(var.dtype),
                'units': var.getncattr('units') if 'units' in attrs else '',
                'long_name': str(long_name),
            })
    return variables, dimensions


def show_nc_info(file_path, dims=False):
    """Print the variables (and, with dims=True, the dimensions) of a file."""
    variables, dimensions = read_info(file_path)

    print(f"NetCDF file: {file_path}")
    print("=" * 60)

    if dims:
        print(f"\nDimensions ({len(dimensions)}):")
        if dimensions:
            w = max(len(d['name']) for d in dimensions)
            for d in dimensions:
                unlimited = '  (unlimited)' if d['unlimited'] else ''
                print(f"  {d['name']:<{w}}  {d['size']:>12,}{unlimited}")
        else:
            print("  (none)")

    print(f"\nVariables ({len(variables)}):")
    if not variables:
        print("  (none)")
        return

    rows = []
    for v in variables:
        dim_str = f"({', '.join(v['dims'])})" if v['dims'] else '()'
        shape_str = ' x '.join(f"{n:,}" for n in v['shape']) if v['shape'] else 'scalar'
        rows.append((v['name'], v['dtype'], shape_str, dim_str, v['units'],
                     v['long_name']))

    headers = ('Name', 'Type', 'Shape', 'Dimensions', 'Units', 'Long name')
    widths = [max(len(h), *(len(r[i]) for r in rows))
              for i, h in enumerate(headers[:-1])]
    fmt = '  ' + '  '.join(f"{{:<{w}}}" for w in widths) + '  {}'
    print(fmt.format(*headers))
    print(fmt.format(*('-' * w for w in widths), '-' * len(headers[-1])))
    for r in rows:
        print(fmt.format(*r).rstrip())


def main():
    parser = argparse.ArgumentParser(
        prog='ncinfo',
        description='List the variables in NetCDF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ncinfo FlowFM_map.nc
  ncinfo FlowFM_map.nc -d          # also list the dimensions
  ncinfo a.nc b.nc c.nc
  ncinfo *.nc --dims
        """,
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {importlib.metadata.version("ncftools")}',
    )
    parser.add_argument(
        'files',
        nargs='+',
        metavar='FILE',
        help='NetCDF file(s) to inspect',
    )
    parser.add_argument(
        '-d', '--dims',
        action='store_true',
        help='Also list the dimensions (name, size, unlimited)',
    )

    args = parser.parse_args()

    failed = False
    for i, path in enumerate(args.files):
        if i:
            print()
        if not os.path.isfile(path):
            print(f"Error: File '{path}' not found.", file=sys.stderr)
            failed = True
            continue
        try:
            show_nc_info(path, args.dims)
        except Exception as e:
            print(f"Error reading '{path}': {e}", file=sys.stderr)
            failed = True

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
