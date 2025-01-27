import json
from functools import wraps
from typing import Any, Optional, Type, Union, cast

import mercantile
import numpy as np
from httpx import HTTPStatusError
from shapely import MultiPolygon, Point, Polygon, to_geojson

from pynspd import asyncio_mock
from pynspd.client import BaseNspdClient, ProxyTypes, get_client
from pynspd.errors import TooBigContour
from pynspd.schemas import Layer36048Feature, Layer36049Feature, NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import SearchResponse
from pynspd.types.enums import ThemeId


def retry_on_http_status_error(func):
    """Декоратор для повторения запроса при ошибке httpx.HTTPStatusError"""

    @wraps(func)
    def wrapper(self: "Nspd", *args, **kwargs):
        attempt = 0
        while attempt <= self.retries:
            try:
                return func(self, *args, **kwargs)
            except HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise e
                attempt += 1
                if attempt > self.retries:
                    raise e

    return wrapper


class Nspd(BaseNspdClient):
    def __init__(
        self,
        timeout: Optional[int] = None,
        retries: int = 10,
        proxy: Optional[ProxyTypes] = None,
    ):
        """Клиент для НСПД

        Usage:
        >>> with pynspd.Nspd() as nspd:
        >>>     feat = nspd.search_zu("77:05:0001005:19")

        Args:
            timeout (Optional[int], optional): Время ожидания ответа. Defaults to None.
            retries (int, optional): Количество попыток при неудачном запросе (таймаут или 5хх ошибки). Defaults to 10.
            proxy (Optional[ProxyTypes], optional): Использовать прокси для запросов. Defaults to None.
        """
        super().__init__(retries=retries)
        self._client = get_client(
            timeout=timeout,
            retries=retries,
            proxy=proxy,
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Окончание сессии"""
        self._client.close()

    @retry_on_http_status_error
    def _search(self, params: dict[str, Any]) -> Optional[SearchResponse]:
        r = self._client.get("/api/geoportal/v2/search/geoportal", params=params)
        return self._validate_search_response(r)

    def _search_one(self, params: dict[str, Any]) -> Optional[NspdFeature]:
        response = self._search(params)
        if response is None:
            return None
        features = response.data.features
        # иногда поиск багует и дает помимо нужного еще и рандомный результат
        if len(features) > 1:
            features = list(
                filter(
                    lambda x: params["query"] in x.properties.model_dump_json(),
                    features,
                )
            )
        if len(features) == 0:
            return None
        assert len(features) == 1
        return features[0]

    def search_by_theme(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[NspdFeature]:
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
                "thematicSearchId": theme_id.value,
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

        Args:
            query (str): поисковой запрос
            layer_def (Type[Feat]): Определение слоя

        Returns:
            Optional[Feat]: валидированная модель слоя, если найдено
        """
        feature = self.search_by_layers(query, layer_def.layer_meta.layer_id)
        return self._cast_feature_to_layer_def(feature, layer_def)

    def search_zu(self, cn: str) -> Optional[Layer36048Feature]:
        """Поиск ЗУ по кадастровому номеру"""
        layer_def = cast(
            Type[Layer36048Feature], NspdFeature.by_title("Земельные участки из ЕГРН")
        )
        return self.search_by_model(cn, layer_def)

    def search_many_zu(self, cns_string: str) -> list[Optional[Layer36048Feature]]:
        """Поиск всех ЗУ, содержащихся в строке"""
        cns = list(self.iter_cn(cns_string))
        features = asyncio_mock.gather(*[self.search_zu(cn) for cn in cns])
        return features

    def search_oks(self, cn: str) -> Optional[Layer36049Feature]:
        """Поиск ОКС по кадастровому номеру"""
        layer_def = cast(Type[Layer36049Feature], NspdFeature.by_title("Здания"))
        return self.search_by_model(cn, layer_def)

    def search_many_oks(self, cns_string: str) -> list[Optional[Layer36049Feature]]:
        """Поиск всех ОКС, содержащихся в строке"""
        cns = list(self.iter_cn(cns_string))
        features = asyncio_mock.gather(*[self.search_oks(cn) for cn in cns])
        return features

    @retry_on_http_status_error
    def search_in_contour(
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
        response = self._client.post(
            "/api/geoportal/v1/intersects",
            params={"typeIntersect": "fullObject"},
            json=payload,
        )
        if response.status_code == 500 and response.json()["code"] == 400004:
            raise TooBigContour
        return self._validate_feature_collection_response(response)

    def search_in_contour_by_model(
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
        raw_features = self.search_in_contour(
            countour, layer_def.layer_meta.category_id, epsg=epsg
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    def search_zu_in_contour(
        self, countour: Union[Polygon, MultiPolygon], epsg: int = 4326
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в контуре

        Args:
            countour (Union[Polygon, MultiPolygon]): Геометрический объект с контуром
            epsg (int, optional): Система координат контура. Defaults to 4326.

        Returns:
            Optional[list[Layer36048Feature]]: Список объектов, пересекающихся с контуром, если найден хоть один
        """
        return self.search_in_contour_by_model(countour, Layer36048Feature, epsg=epsg)

    def search_oks_in_contour(
        self, countour: Union[Polygon, MultiPolygon], epsg: int = 4326
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в контуре

        Args:
            countour (Union[Polygon, MultiPolygon]): Геометрический объект с контуром
            epsg (int, optional): Система координат контура. Defaults to 4326.

        Returns:
            Optional[list[Layer36048Feature]]: Список объектов, пересекающихся с контуром, если найден хоть один
        """
        return self.search_in_contour_by_model(countour, Layer36049Feature, epsg=epsg)

    @retry_on_http_status_error
    def search_at_point(self, pt: Point, layer_id: int) -> Optional[list[NspdFeature]]:
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
        response = self._client.get(f"/api/aeggis/v3/{layer_id}/wms", params=params)
        return self._validate_feature_collection_response(response)

    def search_at_point_by_model(
        self, pt: Point, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в точке (с типизацией)

        Args:
            pt (Point):
            layer_def (Type[Feat]): Тип слоя

        Returns:
            Optional[list[Feat]]: Типизированный список объектов, если найдены
        """
        raw_features = self.search_at_point(pt, layer_def.layer_meta.layer_id)
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    def search_zu_at_point(self, pt: Point) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в точке"""
        return self.search_at_point_by_model(pt, Layer36048Feature)

    def search_oks_at_point(self, pt: Point) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в точке"""
        return self.search_at_point_by_model(pt, Layer36049Feature)
