class PynspdError(Exception):
    """Базовый класс библиотеки"""


class UnknownBadSearchResponse(PynspdError):
    """Неожиданный ответ при поиске"""


class UnknownLayer(PynspdError):
    """Не найдено определение слоя (по имени, категории и тд)"""


class AmbiguousSearchError(PynspdError):
    """Поисковой запрос выдал неоднозначный результат"""

    def __init__(self, query: str):
        msg = f"Найдено больше одного объекта по запросу {query}"
        super().__init__(msg)
