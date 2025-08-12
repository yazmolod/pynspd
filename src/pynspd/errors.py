import httpx


class PynspdError(Exception):
    """Базовый класс ошибок библиотеки"""


class UnknownLayer(PynspdError):
    """Не найдено определение слоя (по имени, категории и тд)"""


class AmbiguousSearchError(PynspdError):
    """Поисковой запрос выдал неоднозначный результат"""

    def __init__(self, query: str):
        msg = f"Найдено больше одного объекта по запросу {query}"
        super().__init__(msg)


class TooBigContour(PynspdError):
    """Контур слишком большой, сервер не может ответить"""

    def __init__(self):
        super().__init__(
            "Попробуйте уменьшить площадь поиска "
            "или воспользоваться методом `.search_in_contour_iter(...)`",
        )


class PynspdResponseError(PynspdError):
    """Базовый класс ошибок для неуспешных запросов"""

    def __init__(self, response: httpx.Response):
        self.response = response
        try:
            details: str = response.json()["message"]
        except (KeyError, ValueError):
            details = "-"
        msg = (
            f"{self.__class__.__doc__}\n"
            f"Status code: {response.status_code}\n"
            f"Details: {details}"
        )
        super().__init__(msg)


class PynspdServerError(PynspdResponseError):
    """Серверная ошибка"""


class BlockedIP(PynspdResponseError):
    """Доступ заблокирован"""


class TooManyRequests(PynspdResponseError):
    """Слишком много запросов"""


class NotFound(PynspdResponseError):
    """Ничего не найдено"""
