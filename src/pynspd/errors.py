from typing import Optional

import httpx


class PynspdError(Exception):
    """Базовый класс библиотеки"""


class PynspdServerError(PynspdError):
    """Ошибки сервера НСПД"""

    def __init__(self, response: httpx.Response, msg: Optional[str] = None):
        self.response = response
        if msg is None:
            msg = f"Status code: {response.status_code}; Details: "
            try:
                details: str = response.json()["message"]
                msg += details
            except (KeyError, ValueError):
                msg += "not found"
        super().__init__(msg)


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


class TooBigContour(PynspdError):
    """Контур слишком большой, сервер не может ответить"""

    def __init__(self):
        super().__init__(
            "Попробуйте уменьшить площадь поиска "
            "или воспользоваться методом `.search_in_contour_iter(...)`",
        )
