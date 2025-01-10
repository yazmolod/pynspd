from typing import TypeVar

import pyproj
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

BaseGeomT = TypeVar("T", bound=BaseGeometry)

epsg4326_proj = pyproj.CRS("EPSG:4326")
epsg3857_proj = pyproj.CRS("EPSG:3857")

project_3857_to_4326 = pyproj.Transformer.from_crs(
    epsg3857_proj, epsg4326_proj, always_xy=True
).transform

project_4326_to_3857 = pyproj.Transformer.from_crs(
    epsg4326_proj, epsg3857_proj, always_xy=True
).transform


def from_3857_to_4326(geom: BaseGeomT) -> BaseGeomT:
    """Перепроецирование геометрии из EPSG:3857 в EPSG:4326"""
    return transform(project_3857_to_4326, geom)


def from_4326_to_3857(geom: BaseGeomT) -> BaseGeomT:
    """Перепроецирование геометрии из EPSG:4326 в EPSG:3857"""
    return transform(project_4326_to_3857, geom)
