# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
