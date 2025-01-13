import json
from typing import Annotated, Generic, Literal, TypeVar, Union

import geojson_pydantic.geometries as pyd_geom
import pyproj
import shapely.geometry as shape_geom
from pydantic import BaseModel, Field, StringConstraints, model_validator
from shapely import to_geojson
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

BaseGeomT = TypeVar("BaseGeomT", bound=BaseGeometry)


class CoordinateReferenceSystemProps(BaseModel):
    name: Annotated[str, StringConstraints(pattern=r"EPSG:\d+")]


class CoordinateReferenceSystem(BaseModel):
    type: Literal["name"]
    properties: CoordinateReferenceSystemProps

    @property
    def value(self):
        return int(self.properties.name.split(":")[1])


class ShapeGeometry(BaseModel, Generic[BaseGeomT]):
    @model_validator(mode="before")
    @classmethod
    def force_4326(cls, data: dict) -> dict:
        if data.get("crs") is None:
            return data
        crs = CoordinateReferenceSystem.model_validate(data["crs"])
        if crs.value == 4326:
            return data
        geom = shape_geom.shape(data)
        transformer = pyproj.Transformer.from_crs(
            pyproj.CRS(crs.properties.name),
            pyproj.CRS("EPSG:4326"),
            always_xy=True,
        ).transform
        proj_geom = transform(transformer, geom)
        return json.loads(to_geojson(proj_geom))

    def to_shape(self) -> BaseGeomT:
        """Конвертация в shapely-геометрию"""
        return shape_geom.shape(self)


class Point(pyd_geom.Point, ShapeGeometry[shape_geom.Point]): ...


class LineString(pyd_geom.LineString, ShapeGeometry[shape_geom.LineString]): ...


class Polygon(pyd_geom.Polygon, ShapeGeometry[shape_geom.Polygon]):
    def to_multi_shape(self) -> shape_geom.MultiPolygon:
        return shape_geom.MultiPolygon([self.to_shape()])


class MultiPolygon(pyd_geom.MultiPolygon, ShapeGeometry[shape_geom.MultiPolygon]):
    def to_multi_shape(self) -> shape_geom.MultiPolygon:
        return self.to_shape()


Geometry = Annotated[
    Union[
        Point,
        LineString,
        Polygon,
        MultiPolygon,
    ],
    Field(discriminator="type"),
]
