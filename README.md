# NCFTOOLS

A collection of Python tools for working with NetCDF files.

## Installation

```bash
pip install -e .
```

## Features

- **meshinfo**: Display mesh information from FlowFM NetCDF files (node/face/edge counts, element types, spatial extent)
- **nc2shp**: Convert a UGRID-compliant NetCDF mesh file to ESRI Shapefiles
- **transzone1**: Build a transition zone from triangle mesh faces and select all intersecting faces
- **transzone2**: Extract the core transition zone — faces fully within the shrunk zone

## Usage

### Check version

```bash
ncftools --version
```

### List all available commands

```bash
ncftools-info
```

### meshinfo

Display mesh information from a FlowFM NetCDF file.

```bash
meshinfo -i FlowFM_net.nc
meshinfo -h
```

### nc2shp

Convert a NetCDF mesh file to ESRI Shapefiles. Outputs `{stem}_faces.shp` and `{stem}_dissolved.shp` in the output directory.

```bash
nc2shp -i FlowFM_net.nc
nc2shp -i mesh.nc -o output --crs EPSG:4326
nc2shp -i mesh.nc -q
```

### transzone1

Buffer triangle mesh faces by +1 m to form a transition zone, then select all faces that intersect it.
Outputs `trans_zone.shp` and `trans_zone_extend.shp`.

```bash
transzone1 -i SHP_NC/FlowFM_net_faces.shp
transzone1 -i SHP_NC/FlowFM_net_faces.shp -o SHP_TRANS
transzone1 -i SHP_NC/FlowFM_net_faces.shp -q
```

### transzone2

Shrink `trans_zone_extend.shp` (output of `transzone1`) by −1 m and select faces fully within the core zone.
Outputs `trans_zone_core.shp`.

```bash
transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp
transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp -o SHP_TRANS
transzone2 -i SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp -q
```

## Python API

```python
from ncftools import meshinfo

meshinfo.show_mesh_info("FlowFM_net.nc")
```
