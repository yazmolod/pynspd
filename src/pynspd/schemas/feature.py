from typing import ClassVar, Generic, Type, TypeVar, overload

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
    """Базовая фича, приходящая из API, не привязанная к слою"""

    @classmethod
    def by_title(cls, title: LayerTitle) -> Type["Feat"]:
        """Получение модели слоя по имени"""
        root_class = cls.__base__.__base__
        for generic_subclass in root_class.__subclasses__():
            for subclass in generic_subclass.__subclasses__():
                meta = getattr(subclass, "layer_meta", None)
                if meta and meta.title == title:
                    return subclass
        raise UnknownLayer(title)

    @overload
    def cast(
        self, layer_def: None = None
    ) -> _BaseFeature[Geometry, Properties[OptionProperties]]: ...

    @overload
    def cast(self, layer_def: Type[Feat]) -> Feat: ...

    def cast(self, layer_def: Type[Feat] | None = None):
        """Приведение объекта к одному из типов перечня определений слоев

        Args:
            layer_def (Optional[Type[Feat]], optional):
                Класс определение слоя. Если не указан, то попытается определить по свойствам. Defaults to None.

        Raises:
            UnknownLayer: Не удалось определить тип слоя по свойствам

        Returns:
            Feat: объект, приведенный к типу его слоя
        """
        if layer_def is None:
            assert self.properties is not None
            layer_def = self.by_title(self.properties.category_name)  # type: ignore[arg-type]
        return layer_def.model_validate(self.model_dump(by_alias=True))
