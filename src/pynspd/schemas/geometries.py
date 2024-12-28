from typing import Annotated, Generic, TypeVar, Union

import geojson_pydantic.geometries as pyd_geom
import pyproj
import shapely.geometry as shape_geom
from pydantic import Field
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

T = TypeVar("T", bound=BaseGeometry)
epsg4326_proj = pyproj.CRS("EPSG:4326")
epsg3857_proj = pyproj.CRS("EPSG:3857")
project = pyproj.Transformer.from_crs(
    epsg3857_proj, epsg4326_proj, always_xy=True
).transform


class ShapeGeometry(Generic[T]):
    def to_shape(self, epsg4326: bool = True) -> T:
        """Конвертация в shapely-геометрию

        Args:
            epsg4326 (bool, optional): переводить ли в систему координат EPSG:4326. Defaults to True.

        Returns:
            T: геометрия
        """
        geom = shape_geom.shape(self)
        if epsg4326:
            geom = transform(project, geom)
        return geom


class Point(pyd_geom.Point, ShapeGeometry[shape_geom.Point]): ...


class LineString(pyd_geom.LineString, ShapeGeometry[shape_geom.LineString]): ...


class Polygon(pyd_geom.Polygon, ShapeGeometry[shape_geom.Polygon]):
    def to_multi_shape(self, epsg4326: bool = True) -> shape_geom.MultiPolygon:
        return shape_geom.MultiPolygon([self.to_shape(epsg4326=epsg4326)])


class MultiPolygon(pyd_geom.MultiPolygon, ShapeGeometry[shape_geom.MultiPolygon]):
    def to_multi_shape(self, epsg4326: bool = True) -> shape_geom.MultiPolygon:
        return self.to_shape(epsg4326=epsg4326)


Geometry = Annotated[
    Union[
        Point,
        LineString,
        Polygon,
        MultiPolygon,
    ],
    Field(discriminator="type"),
]
