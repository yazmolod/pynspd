from enum import Enum


class ThemeId(Enum):
    """Вид объекта (для поиска по категории)"""

    REAL_ESTATE_OBJECTS = 1
    """Объекты недвижимости"""

    CADASTRAL_DIVISION = 2
    """Кадастровое деление"""

    ADMINISTRATIVE_TERRITORIAL_DIVISION = 4
    """Административно-территориальное деление"""

    ZONES_AND_TERRITORIES = 5
    """Зоны и территории"""

    TERRITORIAL_ZONES = 7
    """Территориальные зоны"""

    COMPLEXES_OF_OBJECTS = 15
    """Комплексы объектов"""
