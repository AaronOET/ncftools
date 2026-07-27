# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.8.0] - 2026-07-27

### Added

- `rnxml` CLI tool: renames `dimr.xml` to `dimr_config.xml` in place, leaving the
  file contents untouched; refuses to clobber an existing target unless `--force`
  is given, in which case a `.bak` copy of the old target is kept
- Public helper `ncftools.rnxml.rename_xml()` for use from Python

---

## [0.7.0] - 2026-07-27

### Added

- `setncrain` CLI tool: rewrites every `[Meteo]` block of a D-Flow FM `.ext` file to
  use a NetCDF rainfall forcing file (`quantity=rainfall`, `forcingFile=<*.nc>`,
  `forcingFileType=netcdf`), creating the `.ext` from a built-in template and
  registering it as `ExtForceFileNew` when it is missing
- `setncrain` reads the NetCDF time axis and sets `RefDate`, `TStart` and `TStop`
  in the `.mdu` accordingly, converted to the model's `Tunit`; skip with `--no-time`
- Public helper `ncftools.setncrain.set_nc_rainfall()` for use from Python

---

## [0.6.2] - 2026-07-22

### Changed

- `nc2shp`: `create_polygons` now builds mesh face polygons with vectorized
  numpy/shapely array operations instead of a per-face Python loop (~20x
  faster on large meshes); `create_geodataframe` and `dissolve_geodataframe`
  likewise use shapely's vectorized `area`/`union_all` instead of per-geometry
  Python calls
- Raised minimum `shapely` requirement to `>=2.0.0` (needed for the vectorized
  array API)

---

## [0.6.1] - 2026-06-07

### Fixed

- `transzone1`: falls back to geometry-based triangle detection (vertex count) when
  the input shapefile has no `type` attribute column

---

## [0.6.0] - 2026-06-07

### Added

- `transzone1` CLI tool: buffers triangle faces by +1 m to form a transition zone,
  selects all intersecting mesh faces; outputs `trans_zone.shp` and `trans_zone_extend.shp`
- `transzone2` CLI tool: shrinks `trans_zone_extend.shp` by −1 m and selects faces
  fully within the core zone; outputs `trans_zone_core.shp`

---

## [0.5.3] - 2026-06-06

### Changed

- Updated README with documentation for the `--version` command

---

## [0.5.2] - 2026-06-06

### Fixed

- Patch release with minor fixes

---

## [0.5.0] - 2026-06-06

### Added

- `nc2shp` CLI tool: converts a UGRID-compliant NetCDF mesh file to ESRI Shapefiles
  (`{stem}_faces.shp` and `{stem}_dissolved.shp`); supports `--crs` and `--quiet` flags
- `mesh_info` module for querying mesh information from FlowFM NetCDF files

### Changed

- Updated README with version check command documentation

---

## [0.4.0] - 2026-06-06

### Added

- `--version` / `-v` flag to `meshinfo` tool

---

## [0.2.0] - 2026-06-06

### Changed

- `meshinfo` now uses `-i` flag for specifying input files (was a positional argument)
- Enhanced help text with more usage examples

---

## [0.1.0] - 2026-06-06

### Added

- Initial release of `ncftools`
- `meshinfo` CLI tool: displays mesh information from FlowFM NetCDF files
  (node/face/edge counts, element types, spatial extent)
- `ncftools` / `ncftools-info` CLI entry points
- GitHub Actions workflow for publishing to PyPI and TestPyPI
