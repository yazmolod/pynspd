from typing import Annotated, Generic, Union

import geojson_pydantic.geometries as pyd_geom
import shapely.geometry as shape_geom
from pydantic import Field

from pynspd.utils import BaseGeomT, from_3857_to_4326


class ShapeGeometry(Generic[BaseGeomT]):
    def to_shape(self, epsg4326: bool = True) -> BaseGeomT:
        """Конвертация в shapely-геометрию

        Args:
            epsg4326 (bool, optional): переводить ли в систему координат EPSG:4326. Defaults to True.

        Returns:
            BaseGeomT: геометрия
        """
        geom = shape_geom.shape(self)
        if epsg4326:
            geom = from_3857_to_4326(geom)
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
