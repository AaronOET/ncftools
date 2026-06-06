"""
NCFTOOLS - A collection of tools for working with NetCDF files.
"""

__version__ = '0.4.0'

__all__ = [
    'meshinfo',
    'nc2shp',
    'describe',
]

from . import meshinfo
from . import nc2shp
from . import describe
from . import cli
