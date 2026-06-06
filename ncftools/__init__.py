"""
NCFTOOLS - A collection of tools for working with NetCDF files.
"""

__version__ = '0.1.0'

__all__ = [
    'meshinfo',
    'describe',
]

from . import meshinfo
from . import describe
from . import cli
