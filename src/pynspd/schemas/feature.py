from typing import Generator, Optional, Type, TypeVar, overload

from pynspd.errors import UnknownLayer
from pynspd.schemas.base_feature import BaseFeature
from pynspd.schemas.geometries import Geometry
from pynspd.schemas.properties import NspdProperties, OptionProperties
from pynspd.types._autogen_layers import LayerTitle

Feat = TypeVar("Feat", bound="BaseFeature")


class NspdFeature(BaseFeature[Geometry, NspdProperties[OptionProperties]]):
    """Базовая фича, приходящая из API, не привязанная к слою"""

    @classmethod
    def _iter_layer_defs(cls) -> Generator[Type["NspdFeature"], None, None]:
        root_class = cls.__base__.__base__
        for generic_subclass in root_class.__subclasses__():
            for subclass in generic_subclass.__subclasses__():
                meta = getattr(subclass, "layer_meta", None)
                if meta is not None:
                    yield subclass

    @classmethod
    def by_title(cls, title: LayerTitle) -> Type["NspdFeature"]:
        """Получение модели слоя по имени"""
        for layer_def in cls._iter_layer_defs():
            if layer_def.layer_meta.title == title:
                return layer_def
        raise UnknownLayer(title)

    @classmethod
    def by_category_id(cls, category_id: int) -> Type["NspdFeature"]:
        """Получение модели по категории"""
        for layer_def in cls._iter_layer_defs():
            if layer_def.layer_meta.category_id == category_id:
                return layer_def
        raise UnknownLayer(category_id)

    @overload
    def cast(
        self, layer_def: None = None
    ) -> BaseFeature[Geometry, NspdProperties[OptionProperties]]: ...

    @overload
    def cast(self, layer_def: Type[Feat]) -> Feat: ...

    def cast(self, layer_def: Optional[Type[Feat]] = None):
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
            try:
                layer_def = self.by_title(self.properties.category_name)
            except UnknownLayer:
                # скрытый слой, пробуем определить свойства по категории
                similiar_def = self.by_category_id(self.properties.category)
                props_def = similiar_def.model_fields["properties"].annotation
                layer_def = BaseFeature[Geometry, props_def]
        return layer_def.model_validate(self.model_dump(by_alias=True))
