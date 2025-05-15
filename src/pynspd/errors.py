class PynspdError(Exception):
    """Базовый класс библиотеки"""


class UnknownLayer(PynspdError):
    """Не найдено определение слоя (по имени, категории и тд)"""


class AmbiguousSearchError(PynspdError):
    """Поисковой запрос выдал неоднозначный результат"""

    def __init__(self, query: str):
        msg = f"Найдено больше одного объекта по запросу {query}"
        super().__init__(msg)


class BlockedIP(PynspdError):
    """НСПД заблокировал доступ по используемому IP"""

    def __init__(self):
        msg = (
            "НСПД заблокировал доступ по используемому IP. "
            "Воспользуйтесь прокси в клиенте или смените его"
        )
        super().__init__(msg)
