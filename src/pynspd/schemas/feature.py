from typing import ClassVar, Generic, Type, TypeVar

from geojson_pydantic import Feature

from pynspd.errors import UnknownLayer
from pynspd.schemas.geometries import Geometry
from pynspd.schemas.layer_configs import LayerNode
from pynspd.schemas.properties import OptionProperties, Properties
from pynspd.types._autogen_layers import LayerTitle

Props = TypeVar("Props", bound="Properties")
Geom = TypeVar("Geom", bound="Geometry")
Feat = TypeVar("Feat", bound="_BaseFeature")


class _BaseFeature(Feature[Geom, Props], Generic[Geom, Props]):
    layer_meta: ClassVar[LayerNode]


class NspdFeature(_BaseFeature[Geometry, Properties[OptionProperties]]):
    @classmethod
    def by_title(cls, title: LayerTitle) -> Type["NspdFeature"]:
        """Получение модели слоя по имени"""
        root_class = cls.__base__.__base__
        for generic_subclass in root_class.__subclasses__():
            for subclass in generic_subclass.__subclasses__():
                meta = getattr(subclass, "layer_meta", None)
                if meta and meta.title == title:
                    return subclass
        raise UnknownLayer(title)
