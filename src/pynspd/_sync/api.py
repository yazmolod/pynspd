import json
import re
import warnings
from functools import wraps
from pathlib import Path
from time import sleep
from typing import Any, Literal, Optional, Type, Union

import mercantile
import numpy as np
from hishel import (
    BaseStorage,
    CacheTransport,
    FileStorage,
    RedisStorage,
    SQLiteStorage,
)
from httpx import (
    BaseTransport,
    Client,
    ConnectError,
    HTTPError,
    HTTPStatusError,
    HTTPTransport,
    ProxyError,
    RemoteProtocolError,
    Response,
    TimeoutException,
)
from httpx._types import ProxyTypes, QueryParamTypes
from shapely import MultiPolygon, Point, Polygon, to_geojson

try:
    import sqlite3
except ImportError:
    sqlite3 = None  # type: ignore
try:
    import redis
except ImportError:
    redis = None  # type: ignore

from pynspd.client import (
    NSPD_CACHE_CONTROLLER,
    SSL_CONTEXT,
    BaseNspdClient,
)
from pynspd.errors import BlockedIP
from pynspd.logger import logger
from pynspd.map_types.enums import TabTitle, ThemeId
from pynspd.schemas import Layer36048Feature, Layer36049Feature, NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import (
    NspdTabGroupResponse,
    NspdTabResponse,
    SearchResponse,
)


def retry_on_http_error(func):
    """Декоратор для повторения запроса при ошибках запроса"""

    @wraps(func)
    def wrapper(self: "Nspd", *args, **kwargs):
        attempt = -1
        last_error: Optional[Exception] = None
        while True:
            attempt += 1
            logger_suffix = f'Wrapped method "{func.__name__}", retry {attempt} -'
            if attempt > self._retries:
                logger.debug("%s run out attempts", logger_suffix)
                if last_error is None:
                    last_error = Exception(
                        f"Too many retries ({attempt}/{self._retries})"
                    )
                raise last_error
            try:
                logger.debug("%s start request", logger_suffix)
                return func(self, *args, **kwargs)
            except HTTPError as e:
                last_error = e
                if isinstance(e, RemoteProtocolError):
                    logger.debug("%s remote protocol error", logger_suffix)
                elif isinstance(e, ConnectError):
                    logger.debug("%s connection error", logger_suffix)
                elif isinstance(e, HTTPStatusError):
                    if e.response.status_code == 429:
                        logger.debug("%s too many requests", logger_suffix)
                        sleep(1)
                    elif e.response.status_code < 500:
                        logger.debug("%s not server error", logger_suffix)
                        raise e
                elif isinstance(e, TimeoutException):
                    logger.debug("%s timeout", logger_suffix)
                    sleep(1)
                else:
                    logger.exception("%s unexpected exception", logger_suffix)
                    raise e
            except BlockedIP as e:
                logger.debug("%s blocked IP, retrying", logger_suffix)
                last_error = e
                if not self._retry_on_blocked_ip:
                    raise e

    return wrapper


class Nspd(BaseNspdClient):
    """Клиент для НСПД

    Example:
    ```python
    with pynspd.Nspd() as nspd:
        feat = nspd.find_zu("77:05:0001005:19")
    ```

    Args:
        client_timeout:
            Время ожидания ответа.
            Если не установлен - есть вероятность бесконечного ожидания. По умолчанию None.
        client_retries:
            Количество попыток при неудачном запросе
            (таймаут, неожиданный обрыв соединения, 5хх ошибки). По умолчанию 10.
        client_retry_on_blocked_ip:
            При получении ошибки 403 (доступ заблокирован для вашего IP),
            продолжать попытки запроса до исчерпания retries.
            Рекомендуется использовать только c rotating proxy. По умолчанию False.
        client_proxy:
            Адрес для проксирования запросов. По умолчанию None.
        client_dns_resolve:
            Использовать в запросах IP адрес НСПД вместо доменного имени.
            Рекомендуется включить, если используемый прокси
            не может сам разрешать доменные имена.
            По умолчанию False.
        cache_folder_path:
            Путь для файлового хранилища кэша. По умолчанию None.
        cache_sqlite_url:
            Строка подключения для sqlite-хранилища кэша. По умолчанию None.
        cache_redis_url:
            Строка подключения для redis-хранилища кэша. По умолчанию None.
        cache_ttl:
            Количество времени (в секундах) сколько будет храниться кэш. По умолчанию None.
        cache_storage:
            Ручная настройка объекта хранилища кэша (см. https://hishel.com/advanced/storages/).
        trust_env:
            Использовать переменные окружения для инициализации.
            По умолчанию True.
    """

    def __init__(
        self,
        *,
        client_timeout: Optional[int] = None,
        client_retries: Optional[int] = None,
        client_retry_on_blocked_ip: Optional[bool] = None,
        client_proxy: Optional[ProxyTypes] = None,
        client_dns_resolve: Optional[bool] = None,
        cache_storage: Optional[BaseStorage] = None,
        cache_folder_path: Optional[Union[str, Path]] = None,
        cache_sqlite_url: Optional[str] = None,
        cache_redis_url: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        trust_env: bool = True,
    ):
        self._timeout = self._int_var("client_timeout", client_timeout, trust_env)
        self._retries = self._int_var("client_retries", client_retries, trust_env) or 10
        self._retry_on_blocked_ip = (
            self._bool_var(
                "client_retry_on_blocked_ip", client_retry_on_blocked_ip, trust_env
            )
            or False
        )
        self._proxy = self._str_var("client_proxy", client_proxy, trust_env)
        self._dns_resolve = (
            self._bool_var("client_dns_resolve", client_dns_resolve, trust_env) or False
        )

        self._cache_folder_path = self._str_var(
            "cache_folder_path", cache_folder_path, trust_env
        )
        self._cache_sqlite_url = self._str_var(
            "cache_sqlite_url", cache_sqlite_url, trust_env
        )
        self._cache_redis_url = self._str_var(
            "cache_redis_url", cache_redis_url, trust_env
        )
        self._cache_ttl = self._int_var("cache_ttl", cache_ttl, trust_env)
        self._cache_storage = cache_storage
        if (
            sum(
                [
                    int(bool(i))
                    for i in (
                        self._cache_folder_path,
                        self._cache_sqlite_url,
                        self._cache_redis_url,
                        self._cache_ttl,
                        self._cache_storage,
                    )
                ]
            )
            > 1
        ):
            raise ValueError("Допустимо выбрать только один вариант хранилища кэша")

        self._client: Optional[Client] = None

    def _build_cache_storage(self) -> Optional[BaseStorage]:
        if self._cache_folder_path is not None:
            return FileStorage(
                base_path=Path(self._cache_folder_path), ttl=self._cache_ttl
            )
        elif self._cache_sqlite_url is not None:
            if sqlite3 is None:
                raise RuntimeError(
                    "Не установлены необходимые модули для кэширования этого типа. "
                    "Убедитесь, что вы установили `pynspd` с расширением `sqlite`.\n"
                    "```pip install pynspd[sqlite]```"
                )
            conn = sqlite3.connect(self._cache_sqlite_url, check_same_thread=False)
            return SQLiteStorage(connection=conn, ttl=self._cache_ttl)
        elif self._cache_redis_url is not None:
            if redis is None:
                raise RuntimeError(
                    "Не установлены необходимые модули для кэширования этого типа. "
                    "Убедитесь, что вы установили `pynspd` с расширением `redis`.\n"
                    "```pip install pynspd[redis]```"
                )
            client = redis.Redis.from_url(self._cache_redis_url)
            return RedisStorage(client=client, ttl=self._cache_ttl)
        return None

    def _build_client(self) -> Client:
        transport: BaseTransport = HTTPTransport(
            verify=SSL_CONTEXT, retries=self._retries, proxy=self._proxy
        )
        if self._cache_storage is None:
            self._cache_storage = self._build_cache_storage()
        if self._cache_storage is not None:
            transport = CacheTransport(
                transport=transport,
                storage=self._cache_storage,
                controller=NSPD_CACHE_CONTROLLER,
            )

        base_url = (
            "https://nspd.gov.ru" if not self._dns_resolve else "https://2.63.246.76"
        )
        return Client(
            base_url=base_url,
            timeout=self._timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
                "Referer": "https://nspd.gov.ru",
                "Host": "nspd.gov.ru",
            },
            transport=transport,
        )

    def _rebuild_client_with_dns_resolve(self):
        assert not self._dns_resolve
        assert self._client is not None
        assert self._client.base_url == "https://nspd.gov.ru"
        warnings.warn(
            "Текущий прокси не может сам разрешать доменные имена, "
            "рекомендуется использовать client_dns_resolve=True, "
            "чтобы клиент заранее подставлял IP-адреса и уменьшал нагрузку на соединение",
            stacklevel=7,
        )
        self._client.close()
        self._dns_resolve = True
        self._client = self._build_client()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Завершение сессии"""
        if self._client is not None:
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
        if self._client is None:
            self._client = self._build_client()
        try:
            r = self._client.request(method, url, params=params, json=json)
        except ProxyError as e:
            # Прокси не поддерживает DNS-resolve, необходимо использовать IP-адрес
            # https://github.com/encode/httpx/issues/203#issuecomment-1017726203
            msg = str(e)
            if (
                "Connection not allowed by ruleset" in msg
                or "503 Target host denied" in msg
            ) and not self._dns_resolve:
                logger.debug("Proxy can't resolve dns; change to ip mode")
                self._rebuild_client_with_dns_resolve()
                return self.request(method, url, params, json)
            raise e
        if r.status_code == 403:
            raise BlockedIP
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
        response = self.request(
            "post",
            "/api/geoportal/v1/intersects",
            params={"typeIntersect": "fullObject"},
            json=payload,
        )
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

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
        """
        raw_features = self._search_in_contour(
            countour, layer_def.layer_meta.category_id
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

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
        data = {}
        for i in item:
            title = re.sub(r"[\s:]+$", "", i.title)
            data[title] = i.value
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

    def get_tab_data(self, feat: NspdFeature, tab_name: TabTitle):
        """Получение данных с указанной вкладки"""
        match tab_name:
            case "Части ЗУ":
                return self.tab_land_parts(feat)
            case "Связанные ЗУ":
                return self.tab_land_links(feat)
            case "Виды разрешенного использования":
                return self.tab_permission_type(feat)
            case "Состав ЕЗП":
                return self.tab_composition_land(feat)
            case "Части ОКС":
                return self.tab_build_parts(feat)
            case "Объекты":
                return self.tab_objects_list(feat)

    #################
    ### SHORTCUTS ###
    #################

    def find_landplot(self, query: str) -> Optional[Layer36048Feature]:
        """Найти ЗУ по кадастровому номеру"""
        return self._filter_search_by_query(self.search_landplots(query), query)

    def find_building(self, query: str) -> Optional[Layer36049Feature]:
        """Найти ОКС по кадастровому номеру"""
        return self._filter_search_by_query(self.search_buildings(query), query)

    def search_landplots_at_point(self, pt: Point) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в точке"""
        return self.search_at_point(pt, Layer36048Feature)

    def search_buildings_at_point(self, pt: Point) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в точке"""
        return self.search_at_point(pt, Layer36049Feature)

    def search_landplots(self, cn: str) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ по кадастровому номеру"""
        return self.search_in_layer(cn, Layer36048Feature)

    def search_buildings(self, cn: str) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС по кадастровому номеру"""
        return self.search_in_layer(cn, Layer36049Feature)

    def search_landplots_at_coords(
        self, lat: float, lng: float
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в координатах"""
        return self.search_at_coords(lat, lng, Layer36048Feature)

    def search_buildings_at_coords(
        self, lat: float, lng: float
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в координатах"""
        return self.search_at_coords(lat, lng, Layer36049Feature)

    def search_landplots_in_contour(
        self, countour: Union[Polygon, MultiPolygon]
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в контуре"""
        return self.search_in_contour(countour, Layer36048Feature)

    def search_buildings_in_contour(
        self, countour: Union[Polygon, MultiPolygon]
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в контуре"""
        return self.search_in_contour(countour, Layer36049Feature)
