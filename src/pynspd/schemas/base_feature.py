from datetime import datetime
from typing import ClassVar, Generic, Optional, Self, Type, TypeVar

from geojson_pydantic import Feature
from geojson_pydantic.features import Geom, Props
from pydantic import BaseModel, ConfigDict

from pynspd.schemas.layer_configs import LayerNode
from pynspd.schemas.responses import CamelModel
from pynspd.types._autogen_layers import LayerTitle

OptProps = TypeVar("OptProps", bound="OptionProperties")


class NspdFeature(Feature[Geom, Props], Generic[Geom, Props]):
    layer_meta: ClassVar[LayerNode]

    @classmethod
    def by_title(cls: Type[Self], title: LayerTitle) -> Type[Self]:
        """Получение модели слоя по имени"""
        for generic_subclass in cls.__subclasses__():
            for subclass in generic_subclass.__subclasses__():
                meta = subclass.layer_meta
                if meta.title == title:
                    return subclass
        raise KeyError


class NspdProperties(CamelModel, Generic[OptProps]):
    category: int
    category_name: str
    options: OptProps
    systemInfo: "SystemInfoProperties"
    cadastral_districts_code: Optional[int] = None
    descr: Optional[str] = None
    external_key: Optional[str] = None
    interaction_id: Optional[int] = None
    label: Optional[str] = None
    subcategory: Optional[int] = None


class OptionProperties(BaseModel):
    model_config = ConfigDict(extra="allow")

    def model_dump_human_readable(self):
        """Генерация словря с ключами, аналогичным карточке на сайте"""
        data = self.model_dump()
        alias = {k: v.description for k, v in self.model_fields.items()}
        aliased_data = {
            alias[k]: v for k, v in data.items() if k not in self.model_extra.keys()
        }
        return aliased_data


class SystemInfoProperties(CamelModel):
    inserted: datetime
    inserted_by: str
    updated: datetime
    updated_by: str


# class NspdFeature(Feature[Geom, Props], Generic[Geom, Props]):
#     @overload
#     def shapely_geometry(self) -> sh_geom.Point: ...

#     @overload
#     def shapely_geometry(self) -> sh_geom.MultiPoint: ...

#     @overload
#     def shapely_geometry(self) -> sh_geom.LineString: ...

#     @overload
#     def shapely_geometry(self) -> sh_geom.MultiLineString: ...

#     @overload
#     def shapely_geometry(self) -> sh_geom.Polygon: ...

#     @overload
#     def shapely_geometry(self) -> sh_geom.MultiPolygon: ...

#     def shapely_geometry(self) -> Union[sh_geom.Point, sh_geom.MultiPoint, sh_geom.LineString, sh_geom.MultiLineString, sh_geom.Polygon, sh_geom.MultiPolygon]:
#         if isinstance(self.geometry, pyd_geom.Point):
#             return cast(sh_geom.Point, sh_geom.shape(self.geometry))
#         if isinstance(self.geometry, pyd_geom.MultiPoint):
#             return cast(sh_geom.MultiPoint, sh_geom.shape(self.geometry))
#         if isinstance(self.geometry, pyd_geom.LineString):
#             return cast(sh_geom.LineString, sh_geom.shape(self.geometry))
#         if isinstance(self.geometry, pyd_geom.MultiLineString):
#             return cast(sh_geom.MultiLineString, sh_geom.shape(self.geometry))
#         if isinstance(self.geometry, pyd_geom.Polygon):
#             return cast(sh_geom.Polygon, sh_geom.shape(self.geometry))
#         if isinstance(self.geometry, pyd_geom.MultiPolygon):
#             return cast(sh_geom.MultiPolygon, sh_geom.shape(self.geometry))
#         raise NotImplementedError("Unsupported Geom type")
