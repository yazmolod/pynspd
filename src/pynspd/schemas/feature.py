from typing import (
    Any,
    Generator,
    Literal,
    NoReturn,
    Optional,
    Type,
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
    def _iter_layer_defs(cls) -> Generator[Type[BaseFeature], None, None]:
        root_class = cls.__base__.__base__
        for generic_subclass in root_class.__subclasses__():
            for subclass in generic_subclass.__subclasses__():
                meta = getattr(subclass, "layer_meta", None)
                if meta is not None:
                    yield subclass

    @classmethod
    def by_category_id(cls, category_id: int) -> Type[BaseFeature]:
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
        cls, title: Literal["Объекты площадью от 0 до 25 кв. м"]
    ) -> Type[auto.Layer872974Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты площадью от 25 до 40 кв. м"]
    ) -> Type[auto.Layer872975Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты площадью от 40 до 60 кв. м"]
    ) -> Type[auto.Layer872976Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Водная эрозия"]
    ) -> Type[auto.Layer872153Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты площадью от 60 до 80 кв. м"]
    ) -> Type[auto.Layer872977Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Линейная эрозия"]
    ) -> Type[auto.Layer872155Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты площадью от 80 до 100 кв. м"]
    ) -> Type[auto.Layer872978Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты площадью от 100 кв. м"]
    ) -> Type[auto.Layer872979Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Ветровая эрозия"]
    ) -> Type[auto.Layer872164Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Опустынивание"]
    ) -> Type[auto.Layer872182Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Переувлажнение"]
    ) -> Type[auto.Layer872183Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Подтопление"]
    ) -> Type[auto.Layer872202Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Заболачивание"]
    ) -> Type[auto.Layer872203Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Затопление"]
    ) -> Type[auto.Layer872205Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Захламление"]
    ) -> Type[auto.Layer872206Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Обвально-осыпные и оползневые процессы"]
    ) -> Type[auto.Layer872210Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Абразия"]) -> Type[auto.Layer872211Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровые округа"]
    ) -> Type[auto.Layer36945Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территории объектов культурного наследия"]
    ) -> Type[auto.Layer36316Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Иные нарушенные земли "]
    ) -> Type[auto.Layer872212Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровые районы "]
    ) -> Type[auto.Layer36070Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при наземном строительстве "]
    ) -> Type[auto.Layer872213Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровые кварталы"]
    ) -> Type[auto.Layer36071Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при гидротехническом строительстве"]
    ) -> Type[auto.Layer872216Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при недропользовании"]
    ) -> Type[auto.Layer872217Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при промышленном лесопользовании"]
    ) -> Type[auto.Layer872218Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Нарушенные земли при сельскохозяйственном освоении"]
    ) -> Type[auto.Layer872219Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Нарушенные земли при проведении геологоразведочных, испытательных, эксплуатационных и иных работ"
        ],
    ) -> Type[auto.Layer872220Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Нарушенные земли при складировании и захоронении промышленных отходов, загрязнение земель"
        ],
    ) -> Type[auto.Layer872221Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Государственная граница Российской Федерации"]
    ) -> Type[auto.Layer37313Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Гари"]) -> Type[auto.Layer872222Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Негативный процесс отсутствует"]
    ) -> Type[auto.Layer872224Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Субъекты Российской Федерации (линии)"]
    ) -> Type[auto.Layer37314Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Субъекты Российской Федерации (полигоны)"]
    ) -> Type[auto.Layer37315Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Засоление"]) -> Type[auto.Layer872262Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Муниципальные образования (полигональный)"]
    ) -> Type[auto.Layer36278Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Муниципальные образования (линейный)"]
    ) -> Type[auto.Layer36279Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Населённые пункты (полигоны)"]
    ) -> Type[auto.Layer36281Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Населённые пункты (линии)"]
    ) -> Type[auto.Layer37316Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Земельные участки из ЕГРН"]
    ) -> Type[auto.Layer36048Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Земельные участки, образуемые по схеме расположения земельного участка"
        ],
    ) -> Type[auto.Layer37294Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Земельные участки, выставленные на аукцион "]
    ) -> Type[auto.Layer37299Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Земельные участки, свободные от прав третьих лиц"]
    ) -> Type[auto.Layer37298Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal["Земельные участки, образуемые по проекту межевания территории"],
    ) -> Type[auto.Layer36473Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Здания"]) -> Type[auto.Layer36049Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Сооружения"]) -> Type[auto.Layer36328Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Объекты незавершенного строительства"]
    ) -> Type[auto.Layer36329Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Единые недвижимые комплексы"]
    ) -> Type[auto.Layer37433Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Предприятие как имущественный комплекс"]
    ) -> Type[auto.Layer37434Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ объектов культурного наследия"]
    ) -> Type[auto.Layer37577Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ объектов энергетики, связи, транспорта"]
    ) -> Type[auto.Layer37578Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ природных территорий"]
    ) -> Type[auto.Layer37580Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["ЗОУИТ охраняемых объектов и безопасности"]
    ) -> Type[auto.Layer37579Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Literal["Иные ЗОУИТ"]) -> Type[auto.Layer37581Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территориальные зоны"]
    ) -> Type[auto.Layer36315Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Красные линии "]
    ) -> Type[auto.Layer37293Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Особо охраняемые природные территории "]
    ) -> Type[auto.Layer36317Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Охотничьи угодья "]
    ) -> Type[auto.Layer36311Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Лесничества"]
    ) -> Type[auto.Layer36314Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Граница лесопарка"]
    ) -> Type[auto.Layer843763Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Береговые линии (границы водных объектов) (полигональный)"]
    ) -> Type[auto.Layer36469Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Береговые линии (границы водных объектов)(линейный)"]
    ) -> Type[auto.Layer36470Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Особые экономические зоны"]
    ) -> Type[auto.Layer36303Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территории опережающего развития"]
    ) -> Type[auto.Layer36312Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Игорные зоны"]
    ) -> Type[auto.Layer36471Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Территории выполнения комплексных кадастровых работ"]
    ) -> Type[auto.Layer37430Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls,
        title: Literal[
            "Территория проведения мероприятий по ликвидации накопленного вреда окружающей среде, образовавшегося в результате производства химической продукции в г. Усолье-Сибирское Иркутской области"
        ],
    ) -> Type[auto.Layer37295Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Кадастровая стоимость объекта"]
    ) -> Type[auto.Layer37236Feature]: ...

    @overload
    @classmethod
    def by_title(
        cls, title: Literal["Удельный показатель кадастровой стоимости"]
    ) -> Type[auto.Layer37758Feature]: ...

    @overload
    @classmethod
    def by_title(cls, title: Any) -> NoReturn: ...

    # END_AUTOGEN
    @classmethod
    def by_title(cls, title: LayerTitle) -> Type[BaseFeature]:
        """Получение модели слоя по имени"""
        for layer_def in cls._iter_layer_defs():
            if layer_def.layer_meta.title == title:
                return layer_def
        raise UnknownLayer(title)
