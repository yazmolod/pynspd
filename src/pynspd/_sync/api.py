import json
from functools import wraps
from time import sleep
from typing import Any, Literal, Optional, Type, Union

import mercantile
import numpy as np
import typing_extensions
from hishel import BaseStorage, CacheTransport, Controller
from httpx import (
    BaseTransport,
    Client,
    HTTPStatusError,
    HTTPTransport,
    RemoteProtocolError,
    Response,
    TimeoutException,
)
from httpx._types import ProxyTypes, QueryParamTypes
from shapely import MultiPolygon, Point, Polygon, to_geojson

from pynspd.client import (
    SSL_CONTEXT,
    BaseNspdClient,
    get_client_args,
    get_controller_args,
)
from pynspd.errors import AmbiguousSearchError, TooBigContour
from pynspd.logger import logger
from pynspd.schemas import Layer36048Feature, Layer36049Feature, NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import (
    NspdTabGroupResponse,
    NspdTabResponse,
    SearchResponse,
)
from pynspd.types.enums import ThemeId


def retry_on_http_error(func):
    """Декоратор для повторения запроса при ошибках запроса"""

    @wraps(func)
    def wrapper(self: "Nspd", *args, **kwargs):
        attempt = 0
        while attempt <= self.retries:
            logger_suffix = f'Wrapped method "{func.__name__}" -'
            try:
                logger.debug("%s start request", logger_suffix)
                return func(self, *args, **kwargs)
            except (TimeoutException, HTTPStatusError) as e:
                if isinstance(e, HTTPStatusError):
                    if e.response.status_code == 429:
                        logger.debug("%s too many requests", logger_suffix)
                        sleep(1)
                    elif e.response.status_code < 500:
                        logger.debug("%s not server error", logger_suffix)
                        raise e
                attempt += 1
                if attempt > self.retries:
                    logger.debug("%s run out attempts", logger_suffix)
                    raise e
                logger.debug("%s attempt %d/%d", logger_suffix, attempt, self.retries)
            except RemoteProtocolError:
                # Запрос иногда рандомно обрывается сервером, проходит при повторном запросе
                logger.debug("%s server disconnect", logger_suffix)

    return wrapper


class Nspd(BaseNspdClient):
    """Клиент для НСПД

    ```python
    with pynspd.Nspd() as nspd:
        feat = nspd.search_zu("77:05:0001005:19")
    ```

    Args:
        timeout:
            Время ожидания ответа.
            Если не установлен - есть вероятность бесконечного ожидания. По умолчанию None.
        retries:
            Количество попыток при неудачном запросе
            (таймаут, неожиданный обрыв соединения, 5хх ошибки). По умолчанию 10.
        proxy:
            Использовать прокси для запросов. По умолчанию None.
        cache_storage:
            Настройка хранения кэша (см. https://hishel.com/advanced/storages/).
            Если установлен, то при повторном запросе результат будет
            извлекаться из хранилища кэша, что сильно увеличивает произвожительность
            и снижает риск ошибки 429 - Too many requests. По умолчанию None.
    """

    def __init__(
        self,
        *,
        timeout: Optional[int] = None,
        retries: int = 10,
        proxy: Optional[ProxyTypes] = None,
        cache_storage: Optional[BaseStorage] = None,
    ):
        super().__init__(retries=retries)
        self._client = self._build_client(
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            cache_storage=cache_storage,
        )

    @staticmethod
    def _build_client(
        timeout: Optional[int],
        retries: int,
        proxy: Optional[ProxyTypes],
        cache_storage: Optional[BaseStorage],
    ) -> Client:
        client_args = get_client_args(timeout)
        transport: BaseTransport = HTTPTransport(
            verify=SSL_CONTEXT, retries=retries, proxy=proxy
        )
        if cache_storage is not None:
            cache_args = get_controller_args()
            controller = Controller(**cache_args)
            transport = CacheTransport(
                transport=transport, storage=cache_storage, controller=controller
            )
        return Client(**client_args, transport=transport)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Завершение сессии"""
        self._client.close()

    def request(
        self,
        method: str,
        url: str,
        params: Optional[QueryParamTypes] = None,
        json: Optional[dict] = None,
    ) -> Response:
        """Базовый запрос к API НСПД"""
        logger.debug("Request %s", url)
        r = self._client.request(method, url, params=params, json=json)
        r.raise_for_status()
        return r

    @retry_on_http_error
    def save_request(
        self,
        method: str,
        url: str,
        params: Optional[QueryParamTypes] = None,
        json: Optional[dict] = None,
    ) -> Response:
        """Базовый запрос к api НСПД с обработкой ошибок"""
        return self.request(method, url, params, json)

    @retry_on_http_error
    def _search(self, params: dict[str, Any]) -> Optional[SearchResponse]:
        try:
            r = self.request("get", "/api/geoportal/v2/search/geoportal", params=params)
            return self._validate_search_response(r)
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise e

    def _search_one(self, params: dict[str, Any]) -> Optional[NspdFeature]:
        response = self._search(params)
        if response is None:
            return None
        features = response.data.features
        if len(features) > 1:
            features = self.filter_features_by_query(params["query"], features)
        if len(features) == 0:
            return None
        if len(features) != 1:
            raise AmbiguousSearchError(params["query"])
        return features[0]

    @typing_extensions.deprecated(
        "Will be removed in 0.7.0; use `.search_in_theme(...)` instead`"
    )
    def search_by_theme(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[NspdFeature]:
        """Поисковой запрос по предустановленной теме

        Args:
            query: Поисковой запрос
            theme_id: Вид объекта (кадастровое деление, объект недвижимости и т.д.)

        Returns:
            Положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self.search_in_theme(query, theme_id)

    def search_in_theme(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[NspdFeature]:
        """Поисковой запрос по предустановленной теме

        Args:
            query: Поисковой запрос
            theme_id: Вид объекта (кадастровое деление, объект недвижимости и т.д.)

        Returns:
            Положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._search_one(
            params={
                "query": query,
                "thematicSearchId": theme_id.value,
            }
        )

    @typing_extensions.deprecated(
        "Will be removed in 0.7.0; use `.search_in_layer(...)` instead`"
    )
    def search_by_layers(self, query: str, *layer_ids: int) -> Optional[NspdFeature]:
        """Поисковой запрос по указанным слоям

        Args:
            query: поисковой запрос
            *layer_ids: id слоев, в которых будет производиться поиск

        Returns:
            Положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._search_one(
            params={
                "query": query,
                "layersId": layer_ids,
            }
        )

    def search_in_layer(self, query: str, layer_id: int) -> Optional[NspdFeature]:
        """Поисковой запрос по указанному слою

        Args:
            query: поисковой запрос
            layer_id: id слоя, в которых будет производиться поиск

        Returns:
            Положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._search_one(
            params={
                "query": query,
                "layersId": layer_id,
            }
        )

    @typing_extensions.deprecated(
        "Will be removed in 0.7.0; use `.search_in_layer_by_model(...)` instead`"
    )
    def search_by_model(self, query: str, layer_def: Type[Feat]) -> Optional[Feat]:
        """Поиск одного объекта по определению слоя

        Args:
            query: Поисковой запрос
            layer_def: Определение слоя

        Returns:
            Валидированная модель слоя, если найдено
        """
        return self.search_in_layer_by_model(query, layer_def)

    def search_in_layer_by_model(
        self, query: str, layer_def: Type[Feat]
    ) -> Optional[Feat]:
        """Поиск объекта по определению слоя

        Args:
            query: Поисковой запрос
            layer_def: Определение слоя

        Returns:
            Валидированная модель слоя, если найдено
        """
        feature = self.search_in_layer(query, layer_def.layer_meta.layer_id)
        if feature is None:
            return None
        return feature.cast(layer_def)

    def search_zu(self, cn: str) -> Optional[Layer36048Feature]:
        """Поиск ЗУ по кадастровому номеру"""
        layer_def = NspdFeature.by_title("Земельные участки из ЕГРН")
        return self.search_in_layer_by_model(cn, layer_def)

    def search_oks(self, cn: str) -> Optional[Layer36049Feature]:
        """Поиск ОКС по кадастровому номеру"""
        layer_def = NspdFeature.by_title("Здания")
        return self.search_in_layer_by_model(cn, layer_def)

    @retry_on_http_error
    def search_in_contour(
        self,
        countour: Union[Polygon, MultiPolygon],
        *category_ids: int,
        epsg: int = 4326,
    ) -> Optional[list[NspdFeature]]:
        """Поиск объектов в контуре по ID категорий слоев

        Args:
            countour: Геометрический объект с контуром
            category_ids: ID категорий слоев
            epsg: Система координат контура. По умолчанию 4326.

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
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
        try:
            response = self.request(
                "post",
                "/api/geoportal/v1/intersects",
                params={"typeIntersect": "fullObject"},
                json=payload,
            )
        except HTTPStatusError as e:
            if e.response.status_code == 500 and e.response.json()["code"] == 400004:
                raise TooBigContour from e
            raise e
        return self._validate_feature_collection_response(response)

    def search_in_contour_by_model(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
        epsg: int = 4326,
    ) -> Optional[list[Feat]]:
        """Поиск объектов в контуре по определению слоя

        Args:
            countour: Геометрический объект с контуром
            layer_def: Модель слоя
            epsg: Система координат контура. По умолчанию 4326.

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
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
            countour: Геометрический объект с контуром
            epsg: Система координат контура. По умолчанию 4326.

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
        """
        return self.search_in_contour_by_model(countour, Layer36048Feature, epsg=epsg)

    def search_oks_in_contour(
        self, countour: Union[Polygon, MultiPolygon], epsg: int = 4326
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в контуре

        Args:
            countour: Геометрический объект с контуром
            epsg: Система координат контура. По умолчанию 4326.

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
        """
        return self.search_in_contour_by_model(countour, Layer36049Feature, epsg=epsg)

    @retry_on_http_error
    def search_at_point(self, pt: Point, layer_id: int) -> Optional[list[NspdFeature]]:
        """Поиск объектов слоя в точке"""
        tile_size = 512
        tile = mercantile.tile(
            pt.x, pt.y, zoom=24
        )  # zoom=24 должно быть достаточно для самого точного совпадения
        tile_bounds = mercantile.bounds(tile)
        i = np.interp(pt.x, [tile_bounds.west, tile_bounds.east], [0, tile_size])
        j = np.interp(pt.y, [tile_bounds.south, tile_bounds.north], [0, tile_size])
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
            "WIDTH": tile_size,
            "HEIGHT": tile_size,
            "I": int(i),
            "J": tile_size - int(j),  # отсчет координат для пикселей ведется сверху
            "CRS": "EPSG:3857",  # CRS для bbox
            # можно указать и 4326, но тогда и геометрия будет в 4326
            # Но в других методах мы всегда ждем 3857, поэтому оставляем
            "BBOX": bbox,
            "FEATURE_COUNT": "10",  # Если не указать - вернет только один, даже если попало на границу
        }
        response = self.request("get", f"/api/aeggis/v3/{layer_id}/wms", params=params)
        return self._validate_feature_collection_response(response)

    def search_at_point_by_model(
        self, pt: Point, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в точке (с типизацией)

        Args:
            pt: Точка поиска
            layer_def: Тип слоя

        Returns:
            Типизированный список объектов, если найдены
        """
        raw_features = self.search_at_point(pt, layer_def.layer_meta.layer_id)
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    def search_zu_at_point(self, pt: Point) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в точке"""
        return self.search_at_point_by_model(pt, Layer36048Feature)

    def search_oks_at_point(self, pt: Point) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в точке"""
        return self.search_at_point_by_model(pt, Layer36049Feature)

    @retry_on_http_error
    def _tab_request(
        self, feat: NspdFeature, tab_class: str, type_: Literal["values", "group"]
    ) -> Optional[dict]:
        if feat.properties.options.no_coords:
            params = {
                "tabClass": tab_class,
                "objdocId": feat.properties.options.objdoc_id,
                "registersId": feat.properties.options.registers_id,
            }
        else:
            params = {
                "tabClass": tab_class,
                "categoryId": feat.properties.category,
                "geomId": feat.id,
            }
        try:
            r = self.request(
                "get", f"/api/geoportal/v1/tab-{type_}-data", params=params
            )
            return r.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise e

    def _tab_values_request(
        self, feat: NspdFeature, tab_class: str
    ) -> Optional[list[str]]:
        resp = self._tab_request(feat, tab_class, "values")
        if resp is None:
            return None
        return NspdTabResponse.model_validate(resp).value

    def _tab_groups_request(
        self, feat: NspdFeature, tab_class: str
    ) -> Optional[dict[str, Optional[list[str]]]]:
        resp = self._tab_request(feat, tab_class, "group")
        if resp is None:
            return None
        item = NspdTabGroupResponse.model_validate(resp).object
        data = {i.title: i.value for i in item}
        if len(data) == 0:
            return None
        return data

    def tab_land_parts(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Части ЗУ\" """
        return self._tab_values_request(feat, "landParts")

    def tab_land_links(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Связанные ЗУ\" """
        return self._tab_values_request(feat, "landLinks")

    def tab_permission_type(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Виды разрешенного использования\" """
        return self._tab_values_request(feat, "permissionType")

    def tab_composition_land(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Состав ЕЗП\" """
        return self._tab_values_request(feat, "compositionLand")

    def tab_build_parts(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Части ОКС\" """
        return self._tab_values_request(feat, "buildParts")

    def tab_objects_list(
        self, feat: NspdFeature
    ) -> Optional[dict[str, Optional[list[str]]]]:
        """
        Получение данных с вкладки \"Объекты\"
        """
        return self._tab_groups_request(feat, "objectsList")
