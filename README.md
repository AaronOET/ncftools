# NCFTOOLS

A collection of Python tools for working with NetCDF files.

## Installation

```bash
pip install -e .
```

## Features

- **meshinfo**: Display mesh information from FlowFM NetCDF files (node/face/edge counts, element types, spatial extent)
- **nc2shp**: Convert a UGRID-compliant NetCDF mesh file to ESRI Shapefiles
- **shp2nc**: Rebuild a UGRID mesh NetCDF (D-Flow FM net file) from a cell-polygon shapefile
- **transzone1**: Build a transition zone from triangle mesh faces and select all intersecting faces
- **transzone2**: Extract the core transition zone — faces fully within the shrunk zone
- **setncrain**: Point a D-Flow FM model (`.ext` / `.mdu`) at a NetCDF rainfall forcing file
- **rnxml**: Rename `dimr.xml` to `dimr_config.xml`

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

Display mesh information from a FlowFM NetCDF file. UGRID (`Mesh2d_*`), D-Flow FM 2D3D
(`mesh2d_*`, e.g. from RGFGRID) and old-format (`NetNode`/`NetLink`) net files are
detected automatically.

```bash
meshinfo FlowFM_net.nc
meshinfo -h
```

### nc2shp

Convert a NetCDF mesh file to ESRI Shapefiles. Outputs `{stem}_faces.shp` in the output
directory. Pass `-d`/`--dissolve` to additionally write `{stem}_dissolved.shp`, a single
polygon dissolved from all mesh faces (slower on large meshes).

```bash
nc2shp FlowFM_net.nc
nc2shp mesh.nc -d
nc2shp mesh.nc -o output --crs EPSG:4326
nc2shp mesh.nc -q
```

### shp2nc

Rebuild a D-Flow FM 2D net file (UGRID, `mesh2d_*` variables) from a polygon shapefile in
which every polygon is one mesh cell — the reverse of `nc2shp`. Vertices shared by
neighbouring cells are merged into one node (within `--tol`, default 0.001 map units),
cells are made counter-clockwise, and edges and face centres are derived. Numeric
shapefile attributes are kept as face variables. The CRS comes from the `.prj`; `--crs`
is used only when it is missing. Writes `{stem}_net.nc` unless `-o` is given.

```bash
shp2nc mesh.shp
shp2nc mesh.shp -o FlowFM_net.nc
shp2nc mesh.shp --tol 0.01 --node-z -5.0
shp2nc mesh.shp -q
```

### transzone1

Buffer triangle mesh faces by +1 m to form a transition zone, then select all faces that intersect it.
Outputs `trans_zone.shp` and `trans_zone_extend.shp`.

Triangles are identified from the `type` attribute column when present; otherwise they are
detected automatically by vertex count (closed rings with 3 unique vertices).

```bash
transzone1 SHP_NC/FlowFM_net_faces.shp
transzone1 SHP_NC/FlowFM_net_faces.shp -o SHP_TRANS
transzone1 SHP_NC/FlowFM_net_faces.shp -q
```

### transzone2

Shrink `trans_zone_extend.shp` (output of `transzone1`) by −1 m and select faces fully within the core zone.
Outputs `trans_zone_core.shp`.

```bash
transzone2 SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp
transzone2 SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp -o SHP_TRANS
transzone2 SHP_NC/FlowFM_net_faces.shp -z SHP_TRANS/trans_zone_extend.shp -q
```

### setncrain

Point a D-Flow FM model at a NetCDF rainfall forcing file.

Every `[Meteo]` block in the `.ext` file is rewritten to
`quantity=rainfall`, `forcingFile=<your .nc>`, `forcingFileType=netcdf`.
If the `.ext` file does not exist it is created from a built-in template and
registered in the `.mdu` as `ExtForceFileNew`.

The NetCDF time axis is read and the model times in the `.mdu` are set to match it
(expressed in the model's `Tunit`):

| Key | Value |
| --- | --- |
| `RefDate` | midnight of the first time stamp |
| `TStart` | offset of the first time stamp from `RefDate` |
| `TStop` | offset of the last time stamp from `RefDate` |

The `forcingFile` path is written relative to the `.ext` file (D-Flow FM resolves it
that way); use `--as-given` to write it exactly as typed. `.bak` copies of the
modified files are written unless `--no-backup` is given.

```bash
setncrain -i May28_Event.nc
setncrain -i data/May28_Event.nc --ext dflowfm/FM_model_bnd.ext
setncrain -i May28_Event.nc --mdu dflowfm/FM_model.mdu --no-time
setncrain -i May28_Event.nc --no-backup --as-given
setncrain -i May28_Event.nc -q
```

### rnxml

Rename `dimr.xml` to `dimr_config.xml`, the name the DIMR runner expects. The file
stays in its folder and its contents are not touched.

If `dimr_config.xml` already exists the rename is refused; pass `--force` to
overwrite it (a `.bak` copy of the old target is kept unless `--no-backup`).

```bash
rnxml
rnxml model/dimr.xml
rnxml dimr.xml -o dimr_config.xml --force
rnxml dimr.xml -q
```

## Python API

```python
from ncftools import meshinfo

meshinfo.show_mesh_info("FlowFM_net.nc")
```
