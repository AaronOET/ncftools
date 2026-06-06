# NCFTOOLS

A collection of Python tools for working with NetCDF files.

## Installation

```bash
pip install -e .
```

## Features

- **meshinfo**: Display mesh information from FlowFM NetCDF files (node/face/edge counts, element types, spatial extent)

## Usage

### Command-line

```bash
# List all available commands
ncftools-info

# Display mesh information from a FlowFM NetCDF file
meshinfo -f FlowFM_net.nc

# Show help for meshinfo
meshinfo -h
```

### Python API

```python
from ncftools import meshinfo

# Display mesh info for a NetCDF file
meshinfo.show_mesh_info("FlowFM_net.nc")
```
