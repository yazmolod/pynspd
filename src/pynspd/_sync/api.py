import re
from typing import Any, Generator, Optional, Type, Union, cast

from shapely import MultiPolygon, Point, Polygon

from pynspd import asyncio_mock
from pynspd.client import get_client
from pynspd.schemas import Layer36048Feature, NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import SearchResponse


class Nspd:
    def __init__(self):
        self._client = get_client()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Окончание сессии"""
        self._client.close()

    @staticmethod
    def iter_cn(input_str: str) -> Generator[str, None, None]:
        """Извлечение кадастровых номеров из строки"""
        for cn in re.findall(r"\d+:\d+:\d+:\d+", input_str):
            yield cn

    def _search(self, params: dict[str, Any]) -> Optional[SearchResponse]:
        r = self._client.get("/api/geoportal/v2/search/geoportal", params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return SearchResponse.model_validate(r.json())

    def _search_one(self, params: dict[str, Any]) -> Optional[NspdFeature]:
        response = self._search(params)
        if response is None:
            return None
        features = response.data.features
        assert len(features) == 1
        return features[0]

    def search_by_theme(self, query: str, theme_id: int = 1) -> Optional[NspdFeature]:
        """Глобальный поисковой запрос

        Args:
            query (str): поисковой запрос
            theme_id (int): вид объекта (кадастровое деление, объект недвижимости и т.д.)

        Returns:
            Optional[SearchResponse]: положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._search_one(
            params={
                "query": query,
                "thematicSearchId": theme_id,
            }
        )

    def search_by_layers(self, query: str, *layer_ids: int) -> Optional[NspdFeature]:
        """Поисковой запрос по указанным слоям

        Args:
            query (str): поисковой запрос
            *layer_ids (int): id слоев, в которых будет производиться поиск

        Returns:
            Optional[SearchResponse]: положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._search_one(
            params={
                "query": query,
                "layersId": layer_ids,
            }
        )

    def search_by_model(self, query: str, layer_def: Type[Feat]) -> Optional[Feat]:
        """Поиск одного объекта по определению слоя

        Определение слоя можно
        1) импортировать из `pynspd.schemas`, зная его id
        ```
        from pynspd.schemas import Layer36048Feature    # 36048 - id слоя, которое мы подсмотрели из запросов к wms на сайте
        feature = api.search_by_model("77:06:0004002:7207", Layer36048Feature)
        feature.properties.options.cad_num    # IDE знает тип и подсказывает возможные свойства
        ```

        2) воспользоваться методом `NspdFeature.by_title`
        ```
        from pynspd.schemas import NspdFeature
        feature = api.search_by_model("77:06:0004002:7207", NspdFeature.by_title("Земельные участки из ЕГРН"))    # IDE знает весь перечень слоев и подсказывает ввод
        feature.properties.options.cad_num    # свойство будет так же доступно, но IDE уже не знает о нем
        ```

        Args:
            query (str): поисковой запрос
            layer_def (Type[Feat]): Определение слоя

        Returns:
            Optional[Feat]: валидированная модель слоя, если найдено
        """
        feature = self.search_by_layers(query, layer_def.layer_meta.layer_id)
        if feature is None:
            return None
        return layer_def.model_validate(feature.model_dump(by_alias=True))

    def search_zu(self, cn: str) -> Optional[Layer36048Feature]:
        """Поиск ЗУ по кадастровому номеру"""
        layer_def = cast(
            Type[Layer36048Feature], NspdFeature.by_title("Земельные участки из ЕГРН")
        )
        return self.search_by_model(cn, layer_def)

    def search_many_zu(self, cns_string: str) -> list[Layer36048Feature | None]:
        """Поиск всех ЗУ, содержащихся в строке"""
        cns = list(self.iter_cn(cns_string))
        features = asyncio_mock.gather(*[self.search_zu(cn) for cn in cns])
        return features

    def search_in_contour(self, countour: Union[Polygon, MultiPolygon]):
        raise NotImplementedError

    def search_at_point(self, pt: Point):
        raise NotImplementedError
