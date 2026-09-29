from collections.abc import Generator
from typing import (
    Any,
    Literal,
    NoReturn,
    TypeVar,
    Union,
    overload,
)

from pynspd.errors import UnknownLayer
from pynspd.map_types._autogen_layers import LayerTitle
from pynspd.schemas import _autogen_features as auto
from pynspd.schemas.base_feature import BaseFeature
from pynspd.schemas.geometries import Geometry
from pynspd.schemas.properties import NspdProperties, OptionProperties

Feat = TypeVar("Feat", bound=Union["BaseFeature", "NspdFeature"])


class NspdFeature(BaseFeature[Geometry, NspdProperties[OptionProperties]]):
    """Базовый класс для валидации GeoJSON-объекта из НСПД"""

    @classmethod
    def _iter_layer_defs(cls) -> Generator[type[BaseFeature], None, None]:
        root_class = cls.__base__.__base__
        for generic_subclass in root_class.__subclasses__():
            for subclass in generic_subclass.__subclasses__():
                meta = getattr(subclass, "layer_meta", None)
                if meta is not None:
                    yield subclass

    @classmethod
    def by_category_id(cls, category_id: int) -> type[BaseFeature]:
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
    def cast(self, layer_def: type[Feat]) -> Feat: ...

    def cast(self, layer_def: type[Feat] | None = None):
        """Приведение объекта к одному из типов перечня определений слоев

        Args:
            layer_def:
                Класс определение слоя. Если не указан, то попытается определить по свойствам. По умолчанию None.

        Raises:
            UnknownLayer: Не удалось определить тип слоя по свойствам

        Returns:
            Объект, приведенный к типу его слоя
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

    # START_AUTOGEN: title_overload

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Земельные участки из ЕГРН"]
    ) -> type[auto.Layer36048Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровая стоимость объекта"]
    ) -> type[auto.Layer37236Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Удельный показатель кадастровой стоимости"]
    ) -> type[auto.Layer37758Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Здания"]) -> type[auto.Layer36049Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровые кварталы"]
    ) -> type[auto.Layer36071Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровые районы "]
    ) -> type[auto.Layer36070Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Сооружения"]) -> type[auto.Layer36328Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты незавершенного строительства"]
    ) -> type[auto.Layer36329Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ объектов культурного наследия"]
    ) -> type[auto.Layer37577Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ объектов энергетики, связи, транспорта"]
    ) -> type[auto.Layer37578Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ природных территорий"]
    ) -> type[auto.Layer37580Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ охраняемых объектов и безопасности"]
    ) -> type[auto.Layer37579Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Иные ЗОУИТ"]) -> type[auto.Layer37581Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal["Земельные участки, образуемые по проекту межевания территории"],
    ) -> type[auto.Layer36473Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровые округа"]
    ) -> type[auto.Layer36945Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Красные линии "]
    ) -> type[auto.Layer879243Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Земельные участки, образуемые по схеме расположения земельного участка"
        ],
    ) -> type[auto.Layer37294Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Территория проведения мероприятий по ликвидации накопленного вреда окружающей среде, образовавшегося в результате производства химической продукции в г. Усолье-Сибирское Иркутской области"
        ],
    ) -> type[auto.Layer37295Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Водная эрозия"]
    ) -> type[auto.Layer872153Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Линейная эрозия"]
    ) -> type[auto.Layer872155Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Ветровая эрозия"]
    ) -> type[auto.Layer872164Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Опустынивание"]
    ) -> type[auto.Layer872182Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Переувлажнение"]
    ) -> type[auto.Layer872183Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Подтопление"]
    ) -> type[auto.Layer872202Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Заболачивание"]
    ) -> type[auto.Layer872203Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Затопление"]
    ) -> type[auto.Layer872205Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Захламление"]
    ) -> type[auto.Layer872206Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Обвально-осыпные и оползневые процессы"]
    ) -> type[auto.Layer872210Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Абразия"]) -> type[auto.Layer872211Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Иные нарушенные земли "]
    ) -> type[auto.Layer872212Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при наземном строительстве "]
    ) -> type[auto.Layer872213Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при гидротехническом строительстве"]
    ) -> type[auto.Layer872216Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при недропользовании"]
    ) -> type[auto.Layer872217Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при промышленном лесопользовании"]
    ) -> type[auto.Layer872218Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при сельскохозяйственном освоении"]
    ) -> type[auto.Layer872219Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Нарушенные земли при проведении геологоразведочных, испытательных, эксплуатационных и иных работ"
        ],
    ) -> type[auto.Layer872220Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Нарушенные земли при складировании и захоронении промышленных отходов, загрязнение земель"
        ],
    ) -> type[auto.Layer872221Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Гари"]) -> type[auto.Layer872222Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Негативный процесс отсутствует"]
    ) -> type[auto.Layer872224Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Засоление"]) -> type[auto.Layer872262Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Земельные участки, свободные от прав третьих лиц"]
    ) -> type[auto.Layer37298Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Земельные участки, выставленные на аукцион "]
    ) -> type[auto.Layer37299Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Государственная граница Российской Федерации"]
    ) -> type[auto.Layer37313Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территории выполнения комплексных кадастровых работ"]
    ) -> type[auto.Layer37430Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Единые недвижимые комплексы"]
    ) -> type[auto.Layer37433Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Предприятие как имущественный комплекс"]
    ) -> type[auto.Layer37434Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Субъекты Российской Федерации (линии)"]
    ) -> type[auto.Layer875815Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Субъекты Российской Федерации (полигоны)"]
    ) -> type[auto.Layer875817Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Муниципальные образования (полигональный)"]
    ) -> type[auto.Layer875819Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Муниципальные образования (линейный)"]
    ) -> type[auto.Layer875824Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Населённые пункты (полигоны)"]
    ) -> type[auto.Layer875831Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Береговые линии (границы водных объектов) (полигональный)"]
    ) -> type[auto.Layer875832Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Береговые линии (границы водных объектов)(линейный)"]
    ) -> type[auto.Layer875835Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территориальные зоны"]
    ) -> type[auto.Layer875838Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территории объектов культурного наследия"]
    ) -> type[auto.Layer875840Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Особо охраняемые природные территории "]
    ) -> type[auto.Layer875845Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Особые экономические зоны"]
    ) -> type[auto.Layer875846Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Охотничьи угодья"]
    ) -> type[auto.Layer875847Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территории опережающего развития"]
    ) -> type[auto.Layer875848Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Игорные зоны"]
    ) -> type[auto.Layer875865Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Лесничества"]
    ) -> type[auto.Layer875866Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Граница лесопарка"]
    ) -> type[auto.Layer875874Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Населённые пункты (линии)"]
    ) -> type[auto.Layer875882Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Any) -> NoReturn: ...

    # END_AUTOGEN
    @classmethod
    def by_title(cls, title: LayerTitle) -> type[BaseFeature]:
        """Получение модели слоя по имени"""
        for layer_def in cls._iter_layer_defs():
            if layer_def.layer_meta.title == title:
                return layer_def
        raise UnknownLayer(title)
