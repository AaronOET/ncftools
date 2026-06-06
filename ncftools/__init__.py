"""
NCFTOOLS - A collection of tools for working with NetCDF files.
"""

__version__ = '0.6.1'

__all__ = [
    'meshinfo',
    'nc2shp',
    'transzone1',
    'transzone2',
    'describe',
]

from . import meshinfo
from . import nc2shp
from . import transzone1
from . import transzone2
from . import describe
from . import cli
