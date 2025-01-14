import asyncio
import json
import re
from typing import Any, Generator, Optional, Type, Union, cast

import mercantile
import numpy as np
from httpx import Response
from shapely import MultiPolygon, Point, Polygon, to_geojson

from pynspd.client import ProxyTypes, get_async_client
from pynspd.errors import TooBigContour
from pynspd.schemas import Layer36048Feature, Layer36049Feature, NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import SearchResponse
from pynspd.types.enums import ThemeId


class AsyncNspd:
    def __init__(self, retries: int = 0, proxy: Optional[ProxyTypes] = None):
        self._client = get_async_client(
            retries=retries,
            proxy=proxy,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        """Окончание сессии"""
        await self._client.aclose()

    @staticmethod
    def iter_cn(input_str: str) -> Generator[str, None, None]:
        """Извлечение кадастровых номеров из строки"""
        for cn in re.findall(r"\d+:\d+:\d+:\d+", input_str):
            yield cn

    @staticmethod
    def _cast_feature_to_layer_def(
        raw_feature: Optional[NspdFeature], layer_def: Type[Feat]
    ) -> Optional[Feat]:
        """Приведение базовой фичи к фиче конкретного слоя"""
        if raw_feature is None:
            return None
        feature = raw_feature.cast(layer_def)
        return feature

    @staticmethod
    def _cast_features_to_layer_defs(
        raw_features: Optional[list[NspdFeature]], layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Аналог `_cast_feature_to_layer_def` для списка фичей"""
        if raw_features is None:
            return None
        features = [i.cast(layer_def) for i in raw_features]
        return features

    @staticmethod
    def _validate_response(response: Response) -> Optional[list[NspdFeature]]:
        response.raise_for_status()
        features = response.json()["features"]
        if len(features) == 0:
            return None
        return [NspdFeature.model_validate(i) for i in features]

    async def _search(self, params: dict[str, Any]) -> Optional[SearchResponse]:
        r = await self._client.get("/api/geoportal/v2/search/geoportal", params=params)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return SearchResponse.model_validate(r.json())

    async def _search_one(self, params: dict[str, Any]) -> Optional[NspdFeature]:
        response = await self._search(params)
        if response is None:
            return None
        features = response.data.features
        assert len(features) == 1
        return features[0]

    async def search_by_theme(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[NspdFeature]:
        """Глобальный поисковой запрос

        Args:
            query (str): поисковой запрос
            theme_id (int): вид объекта (кадастровое деление, объект недвижимости и т.д.)

        Returns:
            Optional[SearchResponse]: положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return await self._search_one(
            params={
                "query": query,
                "thematicSearchId": theme_id.value,
            }
        )

    async def search_by_layers(
        self, query: str, *layer_ids: int
    ) -> Optional[NspdFeature]:
        """Поисковой запрос по указанным слоям

        Args:
            query (str): поисковой запрос
            *layer_ids (int): id слоев, в которых будет производиться поиск

        Returns:
            Optional[SearchResponse]: положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return await self._search_one(
            params={
                "query": query,
                "layersId": layer_ids,
            }
        )

    async def search_by_model(
        self, query: str, layer_def: Type[Feat]
    ) -> Optional[Feat]:
        """Поиск одного объекта по определению слоя

        Определение слоя можно
        1) импортировать из `pynspd.schemas`, зная его id
        ```
        from pynspd.schemas import Layer36048Feature    # 36048 - id слоя, которое мы подсмотрели из запросов к wms на сайте
        feature = await api.search_by_model("77:06:0004002:7207", Layer36048Feature)
        feature.properties.options.cad_num    # IDE знает тип и подсказывает возможные свойства
        ```

        2) воспользоваться методом `NspdFeature.by_title`
        ```
        from pynspd.schemas import NspdFeature
        feature = await api.search_by_model("77:06:0004002:7207", NspdFeature.by_title("Земельные участки из ЕГРН"))    # IDE знает весь перечень слоев и подсказывает ввод
        feature.properties.options.cad_num    # свойство будет так же доступно, но IDE уже не знает о нем
        ```

        Args:
            query (str): поисковой запрос
            layer_def (Type[Feat]): Определение слоя

        Returns:
            Optional[Feat]: валидированная модель слоя, если найдено
        """
        feature = await self.search_by_layers(query, layer_def.layer_meta.layer_id)
        return self._cast_feature_to_layer_def(feature, layer_def)

    async def search_zu(self, cn: str) -> Optional[Layer36048Feature]:
        """Поиск ЗУ по кадастровому номеру"""
        layer_def = cast(
            Type[Layer36048Feature], NspdFeature.by_title("Земельные участки из ЕГРН")
        )
        return await self.search_by_model(cn, layer_def)

    async def search_many_zu(
        self, cns_string: str
    ) -> list[Optional[Layer36048Feature]]:
        """Поиск всех ЗУ, содержащихся в строке"""
        cns = list(self.iter_cn(cns_string))
        features = await asyncio.gather(*[self.search_zu(cn) for cn in cns])
        return features

    async def search_oks(self, cn: str) -> Optional[Layer36049Feature]:
        """Поиск ОКС по кадастровому номеру"""
        layer_def = cast(Type[Layer36049Feature], NspdFeature.by_title("Здания"))
        return await self.search_by_model(cn, layer_def)

    async def search_many_oks(
        self, cns_string: str
    ) -> list[Optional[Layer36049Feature]]:
        """Поиск всех ОКС, содержащихся в строке"""
        cns = list(self.iter_cn(cns_string))
        features = await asyncio.gather(*[self.search_oks(cn) for cn in cns])
        return features

    async def search_in_contour(
        self,
        countour: Union[Polygon, MultiPolygon],
        *category_ids: int,
        epsg: int = 4326,
    ) -> Optional[list[NspdFeature]]:
        """Поиск объектов в контуре по id категорий слоев

        Args:
            countour (Union[Polygon, MultiPolygon]): Геометрический объект с контуром
            category_ids (int): id категорий слоев
            epsg (int, optional): Система координат контура. Defaults to 4326.

        Returns:
            Optional[list[Feat]]: Список объектов, пересекающихся с контуром, если найден хоть один
        """
        feature_geojson = json.loads(to_geojson(countour))
        feature_geojson["crs"] = {
            "type": "name",
            "properties": {"name": f"EPSG:{epsg}"},
        }
        payload = {
            "categories": [{"id": id_} for id_ in category_ids],
            "geom": {
                "type": "FeatureCollection",
                "features": [
                    {"geometry": feature_geojson, "type": "Feature", "properties": {}}
                ],
            },
        }
        response = await self._client.post(
            "/api/geoportal/v1/intersects",
            params={"typeIntersect": "fullObject"},
            json=payload,
        )
        if response.status_code == 500 and response.json()["code"] == 400004:
            raise TooBigContour
        return self._validate_response(response)

    async def search_in_contour_by_model(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
        epsg: int = 4326,
    ) -> Optional[list[Feat]]:
        """Поиск объектов в контуре по определению слоя

        Args:
            countour (Union[Polygon, MultiPolygon]): Геометрический объект с контуром
            layer_def (Type[Feat]): Модель слоя
            epsg (int, optional): Система координат контура. Defaults to 4326.

        Returns:
            Optional[list[Feat]]: Список объектов, пересекающихся с контуром, если найден хоть один
        """
        raw_features = await self.search_in_contour(
            countour, layer_def.layer_meta.category_id, epsg=epsg
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    async def search_zu_in_contour(
        self, countour: Union[Polygon, MultiPolygon], epsg: int = 4326
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в контуре

        Args:
            countour (Union[Polygon, MultiPolygon]): Геометрический объект с контуром
            epsg (int, optional): Система координат контура. Defaults to 4326.

        Returns:
            Optional[list[Layer36048Feature]]: Список объектов, пересекающихся с контуром, если найден хоть один
        """
        return await self.search_in_contour_by_model(
            countour, Layer36048Feature, epsg=epsg
        )

    async def search_oks_in_contour(
        self, countour: Union[Polygon, MultiPolygon], epsg: int = 4326
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в контуре

        Args:
            countour (Union[Polygon, MultiPolygon]): Геометрический объект с контуром
            epsg (int, optional): Система координат контура. Defaults to 4326.

        Returns:
            Optional[list[Layer36048Feature]]: Список объектов, пересекающихся с контуром, если найден хоть один
        """
        return await self.search_in_contour_by_model(
            countour, Layer36049Feature, epsg=epsg
        )

    async def search_at_point(
        self, pt: Point, layer_id: int
    ) -> Optional[list[NspdFeature]]:
        """Поиск объектов слоя в точке

        Args:
            pt (Point):
            layer_id (int):

        Returns:
            Optional[list[NspdFeature]]: Список объектов, если найдены
        """
        TILE_SIZE = 512
        tile = mercantile.tile(
            pt.x, pt.y, zoom=24
        )  # zoom=24 должно быть достаточно для самого точного совпадения
        tile_bounds = mercantile.bounds(tile)
        i = np.interp(pt.x, [tile_bounds.west, tile_bounds.east], [0, TILE_SIZE])
        j = np.interp(pt.y, [tile_bounds.south, tile_bounds.north], [0, TILE_SIZE])
        bbox = ",".join(
            map(str, mercantile.xy_bounds(tile))
        )  # bbox в 3857, см. комментарий про CRS
        params = {
            "REQUEST": "GetFeatureInfo",
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "INFO_FORMAT": "application/json",
            "FORMAT": "image/png",
            "STYLES": "",
            "TRANSPARENT": "true",
            "QUERY_LAYERS": layer_id,
            "LAYERS": layer_id,
            "WIDTH": TILE_SIZE,
            "HEIGHT": TILE_SIZE,
            "I": int(i),
            "J": TILE_SIZE - int(j),  # отсчет координат для пикселей ведется сверху
            "CRS": "EPSG:3857",  # CRS для bbox
            # можно указать и 4326, но тогда и геометрия будет в 4326
            # Но в других методах мы всегда ждем 3857, поэтому оставляем
            "BBOX": bbox,
            "FEATURE_COUNT": "10",  # Если не указать - вернет только один, даже если попало на границу
        }
        response = await self._client.get(
            f"/api/aeggis/v3/{layer_id}/wms", params=params
        )
        return self._validate_response(response)

    async def search_at_point_by_model(
        self, pt: Point, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в точке (с типизацией)

        Args:
            pt (Point):
            layer_def (Type[Feat]): Тип слоя

        Returns:
            Optional[list[Feat]]: Типизированный список объектов, если найдены
        """
        raw_features = await self.search_at_point(pt, layer_def.layer_meta.layer_id)
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    async def search_zu_at_point(self, pt: Point) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в точке"""
        return await self.search_at_point_by_model(pt, Layer36048Feature)

    async def search_oks_at_point(self, pt: Point) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в точке"""
        return await self.search_at_point_by_model(pt, Layer36049Feature)
