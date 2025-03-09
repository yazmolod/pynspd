from typing import ClassVar, Generic, TypeVar

from geojson_pydantic import Feature

from pynspd.schemas.geometries import Geometry
from pynspd.schemas.layer_configs import LayerNode
from pynspd.schemas.properties import NspdProperties

Props = TypeVar("Props", bound="NspdProperties")
Geom = TypeVar("Geom", bound="Geometry")


class BaseFeature(Feature[Geom, Props], Generic[Geom, Props]):
    layer_meta: ClassVar[LayerNode]
    """Определение слоя из конфига НСПД"""

    # переопределяем поля из geojson-pydantic, т.к. там они не обязательные
    geometry: Geom
    properties: Props

    def __repr__(self):
        title = self.properties.get_title()
        if title is not None:
            return f"NspdFeature<{self.properties.category_name}: {title}>"
        return f"NspdFeature<{self.properties.category_name}>"
