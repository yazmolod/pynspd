import json
from functools import wraps
from hashlib import md5
from time import sleep
from typing import Any, Generator, Literal, Optional, Type, Union

import mercantile
import numpy as np
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
from shapely import MultiPolygon, Point, Polygon, box, to_geojson
from typing_extensions import deprecated

from pynspd.client import (
    SSL_CONTEXT,
    BaseNspdClient,
    get_client_args,
    get_controller_args,
)
from pynspd.errors import TooBigContour
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
                    elif e.response.status_code < 500:
                        logger.debug("%s not server error", logger_suffix)
                        raise e
                attempt += 1
                if attempt > self.retries:
                    logger.debug("%s run out attempts", logger_suffix)
                    raise e
                sleep(1)
                logger.debug("%s attempt %d/%d", logger_suffix, attempt, self.retries)
            except RemoteProtocolError:
                # Запрос иногда рандомно обрывается сервером, проходит при повторном запросе
                logger.debug("%s server disconnect", logger_suffix)

    return wrapper


class Nspd(BaseNspdClient):
    """Клиент для НСПД

    ```python
    with pynspd.Nspd() as nspd:
        feat = nspd.find_zu("77:05:0001005:19")
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
    def safe_request(
        self,
        method: str,
        url: str,
        params: Optional[QueryParamTypes] = None,
        json: Optional[dict] = None,
    ) -> Response:
        """Базовый запрос к api НСПД с обработкой ошибок"""
        return self.request(method, url, params, json)

    ####################
    ### QUERY SEARCH ###
    ####################

    @retry_on_http_error
    def _search(self, params: dict[str, Any]) -> Optional[list[NspdFeature]]:
        """Базовый поисковый запрос на НСПД"""
        try:
            r = self.request("get", "/api/geoportal/v2/search/geoportal", params=params)
            return SearchResponse.model_validate(r.json()).data.features
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise e

    def search(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[list[NspdFeature]]:
        """Поисковой запрос по предустановленной теме

        Args:
            query: Поисковой запрос
            theme_id:
                Вид объекта (кадастровое деление, объект недвижимости и т.д.).
                По умолчанию: объекты недвижимости

        Returns:
            Положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._search(
            params={
                "query": query,
                "thematicSearchId": theme_id.value,
            }
        )

    def search_in_layer(
        self, query: str, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск объекта по определению слоя

        Args:
            query: Поисковой запрос
            layer_def: Определение слоя

        Returns:
            Валидированная модель слоя, если найдено
        """
        raw_features = self._search(
            params={
                "query": query,
                "layersId": layer_def.layer_meta.layer_id,
            }
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    def find(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[NspdFeature]:
        """Найти объект по предустановленной теме

        Args:
            query: Поисковой запрос
            theme_id:
                Вид объекта (кадастровое деление, объект недвижимости и т.д.).
                По умолчанию: объекты недвижимости

        Returns:
            Положительный ответ от сервиса, либо None, если ничего не найдено
        """
        return self._filter_search_by_query(self.search(query, theme_id), query)

    def find_in_layer(self, query: str, layer_def: Type[Feat]) -> Optional[Feat]:
        """Найти объект по определению слоя

        Args:
            query: Поисковой запрос
            layer_def: Определение слоя

        Returns:
            Валидированная модель слоя, если найдено
        """
        return self._filter_search_by_query(
            self.search_in_layer(query, layer_def), query
        )

    ######################
    ### POLYGON SEARCH ###
    ######################

    @retry_on_http_error
    def _search_in_contour(
        self,
        countour: Union[Polygon, MultiPolygon],
        *category_ids: int,
    ) -> Optional[list[NspdFeature]]:
        """Поиск объектов в контуре по ID категорий слоев

        Args:
            countour: Геометрический объект с контуром
            category_ids: ID категорий слоев

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
        """
        feature_geojson = json.loads(to_geojson(countour))
        feature_geojson["crs"] = {
            "type": "name",
            "properties": {"name": "EPSG:4326"},
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

    def search_in_contour(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в контуре

        Args:
            countour: Геометрический объект с контуром
            layer_def: Модель слоя

        Raises:
            TooBigContour: Слишком много объектов в контуре

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
        """
        raw_features = self._search_in_contour(
            countour, layer_def.layer_meta.category_id
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    def _iter_search_in_box(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        layer_def: Type[Feat],
    ) -> Generator[Feat, None, None]:
        """Рекурсивный поиск объектов в границах"""

        def split_extent(xmin: float, ymin: float, xmax: float, ymax: float):
            midx = (xmax + xmin) / 2
            midy = (ymax + ymin) / 2
            yield xmin, ymin, midx, midy
            yield midx, midy, xmax, ymax
            yield midx, ymin, xmax, midy
            yield xmin, midy, midx, ymax

        try:
            feats = self.search_in_contour(box(xmin, ymin, xmax, ymax), layer_def)
            if feats is None:
                return
            for f in feats:
                yield f
        except TooBigContour:
            for sp_xmin, sp_ymin, sp_xmax, sp_ymax in split_extent(
                xmin, ymin, xmax, ymax
            ):
                for f in self._iter_search_in_box(
                    sp_xmin, sp_ymin, sp_xmax, sp_ymax, layer_def
                ):
                    yield f

    def search_in_contour_iter(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
        *,
        only_intersects: bool = False,
    ) -> Generator[Feat, None, None]:
        """Поиск объектов в указанных границах.

        Внимание: количество запросов кратно зависит от площади поиска.
        Если вы хотите вручную обрабатывать ошибку `TooBigContour`,
        используйте метод `search_in_contour(...)`

        Args:
            countour: Геометрический объект с контуром
            layer_def: Модель слоя
            only_intersects:
                Возвращать только те объекты,
                которые пересекаются с изначальным контуром. По умолчанию False

        Returns:
            Генератор объектов слоя в указанной области
        """
        cache = set()
        xmin, ymin, xmax, ymax = countour.bounds
        for feat in self._iter_search_in_box(xmin, ymin, xmax, ymax, layer_def):
            cache_id = md5(feat.model_dump_json().encode()).hexdigest()
            if cache_id in cache:
                continue
            cache.add(cache_id)
            if only_intersects and not countour.intersects(feat.geometry.to_shape()):
                continue
            yield feat

    ####################
    ### POINT SEARCH ###
    ####################

    @retry_on_http_error
    def _search_at_point(self, pt: Point, layer_id: int) -> Optional[list[NspdFeature]]:
        """Поиск объектов слоя в точке"""
        tile_size = 512
        tile = mercantile.tile(
            pt.x, pt.y, zoom=24
        )  # zoom=24 должно быть достаточно для самого точного совпадения
        tile_bounds = mercantile.bounds(tile)
        i = np.interp(pt.x, [tile_bounds.west, tile_bounds.east], [0, tile_size])
        j = np.interp(pt.y, [tile_bounds.south, tile_bounds.north], [0, tile_size])
        bbox = ",".join(map(str, tile_bounds))
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
            "CRS": "EPSG:4326",  # CRS для bbox
            "BBOX": bbox,
            "FEATURE_COUNT": "10",  # Иначе вернет только один, даже если попало на границу
        }
        response = self.request(
            "get",
            f"/api/aeggis/v3/{layer_id}/wms",
            params=params,  # type: ignore[arg-type]
        )
        return self._validate_feature_collection_response(response)

    def search_at_point(self, pt: Point, layer_def: Type[Feat]) -> Optional[list[Feat]]:
        """Поиск объектов слоя в точке (с типизацией)

        Args:
            pt: Точка поиска
            layer_def: Тип слоя

        Returns:
            Типизированный список объектов, если найдены
        """
        raw_features = self._search_at_point(pt, layer_def.layer_meta.layer_id)
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    def search_at_coords(
        self, lat: float, lng: float, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в координатах

        Args:
            lat: Широта
            lng: Долгота
            layer_def: Тип слоя

        Returns:
            Типизированный список объектов, если найдены
        """
        return self.search_at_point(Point(lng, lat), layer_def)

    ####################
    ### TAB REQUESTS ###
    ####################

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

    #################
    ### SHORTCUTS ###
    #################

    def find_zu(self, query: str) -> Optional[Layer36048Feature]:
        """Найти ЗУ по кадастровому номеру"""
        return self._filter_search_by_query(self.search_zu(query), query)

    def find_oks(self, query: str) -> Optional[Layer36049Feature]:
        """Найти ОКС по кадастровому номеру"""
        return self._filter_search_by_query(self.search_oks(query), query)

    def search_zu_at_point(self, pt: Point) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в точке"""
        return self.search_at_point(pt, Layer36048Feature)

    def search_oks_at_point(self, pt: Point) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в точке"""
        return self.search_at_point(pt, Layer36049Feature)

    def search_zu(self, cn: str) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ по кадастровому номеру"""
        return self.search_in_layer(cn, Layer36048Feature)

    def search_oks(self, cn: str) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС по кадастровому номеру"""
        return self.search_in_layer(cn, Layer36049Feature)

    def search_zu_at_coords(
        self, lat: float, lng: float
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в координатах"""
        return self.search_at_coords(lat, lng, Layer36048Feature)

    def search_oks_at_coords(
        self, lat: float, lng: float
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в координатах"""
        return self.search_at_coords(lat, lng, Layer36049Feature)

    def search_zu_in_contour(
        self, countour: Union[Polygon, MultiPolygon]
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в контуре"""
        return self.search_in_contour(countour, Layer36048Feature)

    def search_oks_in_contour(
        self, countour: Union[Polygon, MultiPolygon]
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в контуре"""
        return self.search_in_contour(countour, Layer36049Feature)

    def search_zu_in_contour_iter(
        self,
        countour: Union[Polygon, MultiPolygon],
        *,
        only_intersects: bool = False,
    ) -> Generator[Layer36048Feature, None]:
        """Поиск ЗУ в контуре"""
        for f in self.search_in_contour_iter(
            countour, Layer36048Feature, only_intersects=only_intersects
        ):
            yield f

    def search_oks_in_contour_iter(
        self,
        countour: Union[Polygon, MultiPolygon],
        *,
        only_intersects: bool = False,
    ) -> Generator[Layer36049Feature, None]:
        """Поиск ОКС в контуре"""
        for f in self.search_in_contour_iter(
            countour, Layer36049Feature, only_intersects=only_intersects
        ):
            yield f

    ####################
    ### DEPRECATIONS ###
    ####################

    @deprecated("Will be removed in 0.8.0; use `.find(...)` instead`")
    def search_in_theme(
        self, query: str, theme_id: ThemeId = ThemeId.REAL_ESTATE_OBJECTS
    ) -> Optional[NspdFeature]:
        return self.find(query, theme_id)

    @deprecated("Will be removed in 0.8.0; use `.find_in_layer(...)` instead`")
    def search_in_layer_by_model(
        self, query: str, layer_def: Type[Feat]
    ) -> Optional[Feat]:
        return self.find_in_layer(query, layer_def)

    @deprecated("Will be removed in 0.8.0; use `.search_at_point(...)` instead`")
    def search_at_point_by_model(
        self, pt: Point, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        return self.search_at_point(pt, layer_def)

    @deprecated("Will be removed in 0.8.0; use `.search_in_contour(...)` instead`")
    def search_in_contour_by_model(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
    ) -> Optional[list[Feat]]:
        return self.search_in_contour(countour, layer_def)
