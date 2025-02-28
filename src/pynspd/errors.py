class UnknownBadSearchResponse(Exception):
    """Неожиданный ответ при поиске"""


class UnknownLayer(Exception):
    """Не найдено определение слоя (по имени, категории и тд)"""


class TooBigContour(Exception):
    """Контур слишком большой, сервер не может ответить"""

    def __init__(self):
        super().__init__("Попробуйте уменьшить площадь поиска")


class AmbiguousSearchError(Exception):
    def __init__(self, query: str):
        msg = f"Найдено больше одного объекта по запросу {query}"
        super().__init__(msg)
