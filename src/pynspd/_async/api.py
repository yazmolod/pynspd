import json
import re
import warnings
from asyncio import sleep
from functools import wraps
from hashlib import md5
from pathlib import Path
from typing import Any, AsyncGenerator, Literal, Optional, Type, Union

import mercantile
import numpy as np
import ua_generator
from hishel import (
    AsyncBaseStorage,
    AsyncCacheTransport,
    AsyncFileStorage,
    AsyncRedisStorage,
    AsyncSQLiteStorage,
)
from httpx import (
    AsyncBaseTransport,
    AsyncClient,
    AsyncHTTPTransport,
    ConnectError,
    HTTPError,
    ProxyError,
    RemoteProtocolError,
    Response,
    TimeoutException,
)
from httpx._types import ProxyTypes, QueryParamTypes
from shapely import MultiPolygon, Point, Polygon, box, to_geojson

try:
    import anysqlite
except ImportError:
    anysqlite = None  # type: ignore
try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # type: ignore

import pynspd.errors as err
from pynspd.client import (
    NSPD_CACHE_CONTROLLER,
    SSL_CONTEXT,
    BaseNspdClient,
)
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
    async def wrapper(self: "AsyncNspd", *args, **kwargs):
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
                return await func(self, *args, **kwargs)
            except HTTPError as e:
                last_error = e
                if isinstance(e, RemoteProtocolError):
                    logger.debug("%s remote protocol error", logger_suffix)
                elif isinstance(e, ConnectError):
                    logger.debug("%s connection error", logger_suffix)
                elif isinstance(e, TimeoutException):
                    logger.debug("%s timeout", logger_suffix)
                    await sleep(1)
                else:
                    logger.exception("%s unexpected exception", logger_suffix)
                    raise e
            except err.PynspdServerError as e:
                logger.debug("%s unknown server error", logger_suffix)
                last_error = e
            except err.BlockedIP as e:
                logger.debug("%s blocked IP, retrying", logger_suffix)
                last_error = e
                if not self._retry_on_blocked_ip:
                    raise e
            except err.TooManyRequests as e:
                logger.debug("%s too many requests", logger_suffix)
                last_error = e
                await sleep(1)

    return wrapper


class AsyncNspd(BaseNspdClient):
    """Асинхронный клиент для НСПД

    Example:
    ```python
    async with pynspd.AsyncNspd() as nspd:
        feat = await nspd.find_zu("77:05:0001005:19")
    ```

    Args:
        client_timeout:
            Время ожидания ответа.
            Если не установлен - есть вероятность бесконечного ожидания. По умолчанию `None`.
        client_retries:
            Количество попыток при неудачном запросе
            (таймаут, неожиданный обрыв соединения, 5хх ошибки). По умолчанию `10`.
        client_retry_on_blocked_ip:
            При получении ошибки 403 (доступ заблокирован для вашего IP),
            продолжать попытки запроса до исчерпания retries.
            Рекомендуется использовать только c ротируемыми прокси. По умолчанию `False`.
        client_proxy:
            Адрес для проксирования запросов. По умолчанию `None`.
        client_dns_resolve:
            Использовать в запросах IP адрес НСПД вместо доменного имени.
            Рекомендуется включить, если используемый прокси
            не может сам разрешать доменные имена.
            По умолчанию `False`.
        cache_folder_path:
            Путь до папки для кэша запросов.. По умолчанию `None`.
        cache_sqlite_url:
            Строка подключения для sqlite-хранилища кэша. По умолчанию `None`.
        cache_redis_url:
            Строка подключения для redis-хранилища кэша. По умолчанию `None`.
        cache_ttl:
            Количество времени (в секундах) сколько будет храниться кэш. По умолчанию `None`.
        cache_storage:
            Ручная настройка объекта хранилища кэша (см. https://hishel.com/advanced/storages/). По умолчанию `None`.
        trust_env:
            Использовать переменные окружения для инициализации.
            По умолчанию `True`.
    """

    def __init__(
        self,
        *,
        client_timeout: Optional[int] = None,
        client_retries: Optional[int] = None,
        client_retry_on_blocked_ip: Optional[bool] = None,
        client_proxy: Optional[ProxyTypes] = None,
        client_dns_resolve: Optional[bool] = None,
        cache_storage: Optional[AsyncBaseStorage] = None,
        cache_folder_path: Optional[Union[str, Path]] = None,
        cache_sqlite_url: Optional[str] = None,
        cache_redis_url: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        trust_env: bool = True,
    ):
        self._timeout = self._int_var("client_timeout", client_timeout, trust_env)
        self._retries = self._int_var("client_retries", client_retries, trust_env)
        if self._retries is None:
            self._retries = 10
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

        self._client: Optional[AsyncClient] = None
        self._last_response: Optional[Response] = None

    async def _build_cache_storage(self) -> Optional[AsyncBaseStorage]:
        if self._cache_folder_path is not None:
            return AsyncFileStorage(
                base_path=Path(self._cache_folder_path), ttl=self._cache_ttl
            )
        elif self._cache_sqlite_url is not None:
            if anysqlite is None:
                raise RuntimeError(
                    "Не установлены необходимые модули для кэширования этого типа. "
                    "Убедитесь, что вы установили `pynspd` с расширением `sqlite`.\n"
                    "```pip install pynspd[sqlite]```"
                )
            conn = await anysqlite.connect(
                self._cache_sqlite_url, check_same_thread=False
            )
            return AsyncSQLiteStorage(connection=conn, ttl=self._cache_ttl)
        elif self._cache_redis_url is not None:
            if redis is None:
                raise RuntimeError(
                    "Не установлены необходимые модули для кэширования этого типа. "
                    "Убедитесь, что вы установили `pynspd` с расширением `redis`.\n"
                    "```pip install pynspd[redis]```"
                )
            client = redis.Redis.from_url(self._cache_redis_url)
            return AsyncRedisStorage(client=client, ttl=self._cache_ttl)
        return None

    async def _build_client(self) -> AsyncClient:
        transport: AsyncBaseTransport = AsyncHTTPTransport(
            verify=SSL_CONTEXT, retries=self._retries, proxy=self._proxy
        )
        if self._cache_storage is None:
            self._cache_storage = await self._build_cache_storage()
        if self._cache_storage is not None:
            transport = AsyncCacheTransport(
                transport=transport,
                storage=self._cache_storage,
                controller=NSPD_CACHE_CONTROLLER,
            )

        host = self.DNS_HOST if not self._dns_resolve else self.IP_HOST
        return AsyncClient(
            base_url="https://" + host,
            timeout=self._timeout,
            headers={
                "User-Agent": ua_generator.generate().text,
                "Referer": self.DNS_URL,
                "Host": self.DNS_HOST,
            },
            transport=transport,
        )

    async def _rebuild_client_with_dns_resolve(self):
        assert not self._dns_resolve
        assert self._client is not None
        assert self._client.base_url == self.DNS_URL
        warnings.warn(
            "Текущий прокси не может сам разрешать доменные имена, "
            "рекомендуется использовать client_dns_resolve=True, "
            "чтобы клиент заранее подставлял IP-адреса и уменьшал нагрузку на соединение",
            stacklevel=7,
        )
        await self._client.aclose()
        self._dns_resolve = True
        self._client = await self._build_client()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        """Завершение сессии"""
        if self._client is not None:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[QueryParamTypes] = None,
        json: Optional[dict] = None,
    ) -> Response:
        """Базовый запрос к API НСПД"""
        logger.debug("Request %s", url)
        if self._client is None:
            self._client = await self._build_client()
        try:
            r = await self._client.request(method, url, params=params, json=json)
        except ProxyError as e:
            # Прокси не поддерживает DNS-resolve, необходимо использовать IP-адрес
            # https://github.com/encode/httpx/issues/203#issuecomment-1017726203
            msg = str(e)
            if (
                "Connection not allowed by ruleset" in msg
                or "503 Target host denied" in msg
            ) and not self._dns_resolve:
                logger.debug("Proxy can't resolve dns; change to ip mode")
                await self._rebuild_client_with_dns_resolve()
                return await self.request(method, url, params, json)
            raise e
        self._last_response = r
        code = r.status_code
        if code == 403:
            raise err.BlockedIP(r)
        if code == 404:
            raise err.NotFound(r)
        if code == 429:
            raise err.TooManyRequests(r)
        if code >= 500:
            raise err.PynspdServerError(r)
        if not str(code).startswith("2"):
            raise err.PynspdResponseError(r)
        return r

    @retry_on_http_error
    async def safe_request(
        self,
        method: str,
        url: str,
        params: Optional[QueryParamTypes] = None,
        json: Optional[dict] = None,
    ) -> Response:
        """Базовый запрос к api НСПД с обработкой ошибок"""
        return await self.request(method, url, params, json)

    ####################
    ### QUERY SEARCH ###
    ####################

    @retry_on_http_error
    async def _search(self, params: dict[str, Any]) -> Optional[list[NspdFeature]]:
        """Базовый поисковый запрос на НСПД"""
        try:
            r = await self.request(
                "get", "/api/geoportal/v2/search/geoportal", params=params
            )
            return SearchResponse.model_validate(r.json()).data.features
        except err.NotFound:
            return None

    async def search(
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
        return await self._search(
            params={
                "query": query,
                "thematicSearchId": theme_id.value,
            }
        )

    async def search_in_layer(
        self, query: str, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск по определению слоя

        Args:
            query: Поисковой запрос
            layer_def: Определение слоя

        Returns:
            Массив валидированных объектов, если что-то найдено
        """
        raw_features = await self._search(
            params={
                "query": query,
                "layersId": layer_def.layer_meta.layer_id,
            }
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    async def search_in_layers(
        self, query: str, *layer_defs: Type[Feat]
    ) -> Optional[list[NspdFeature]]:
        """Поиск по определениям слоев

        Args:
            query: Поисковой запрос
            layer_defs: Определения слоев

        Returns:
            Массив невалидированных объектов, если что-то найдено
        """
        return await self._search(
            params={
                "query": query,
                "layersId": [i.layer_meta.layer_id for i in layer_defs],
            }
        )

    async def find(
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
        return self._filter_search_by_query(await self.search(query, theme_id), query)

    async def find_in_layer(self, query: str, layer_def: Type[Feat]) -> Optional[Feat]:
        """Найти объект по определению слоя

        Args:
            query: Поисковой запрос
            layer_def: Определение слоя

        Returns:
            Валидированная модель слоя, если найдено
        """
        return self._filter_search_by_query(
            await self.search_in_layer(query, layer_def), query
        )

    ######################
    ### POLYGON SEARCH ###
    ######################

    @retry_on_http_error
    async def _search_in_contour(
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
            response = await self.request(
                "post",
                "/api/geoportal/v1/intersects",
                params={"typeIntersect": "fullObject"},
                json=payload,
            )
            return self._validate_feature_collection_response(response)
        except err.PynspdServerError as e:
            if '"code":400104' in e.response.text:
                raise err.TooBigContour from e
            raise e
        except json.decoder.JSONDecodeError as e:
            raise err.TooBigContour from e

    async def search_in_contour(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в контуре

        Args:
            countour: Геометрический объект с контуром
            layer_def: Модель слоя

        Raises:
            TooBigContour: НСПД не может обработать такой контур

        Returns:
            Список объектов, пересекающихся с контуром, если найден хоть один
        """
        raw_features = await self._search_in_contour(
            countour, layer_def.layer_meta.category_id
        )
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    async def _iter_search_in_box(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        layer_def: Type[Feat],
    ) -> AsyncGenerator[Feat, None]:
        """Рекурсивный поиск объектов в границах"""

        def split_extent(xmin: float, ymin: float, xmax: float, ymax: float):
            midx = (xmax + xmin) / 2
            midy = (ymax + ymin) / 2
            yield xmin, ymin, midx, midy
            yield midx, midy, xmax, ymax
            yield midx, ymin, xmax, midy
            yield xmin, midy, midx, ymax

        try:
            logger_prefix = "Search [%.2f, %.2f, %.2f, %.2f]: " % (
                xmin,
                ymin,
                xmax,
                ymax,
            )
            logger.debug(logger_prefix + "start")
            feats = await self.search_in_contour(box(xmin, ymin, xmax, ymax), layer_def)
            if feats is None:
                logger.debug(logger_prefix + "empty")
                return
            logger.debug(logger_prefix + "success")
            for f in feats:
                yield f
        except err.TooBigContour:
            logger.debug(logger_prefix + "failed, split tiles")
            for sp_xmin, sp_ymin, sp_xmax, sp_ymax in split_extent(
                xmin, ymin, xmax, ymax
            ):
                async for f in self._iter_search_in_box(
                    sp_xmin, sp_ymin, sp_xmax, sp_ymax, layer_def
                ):
                    yield f

    async def search_in_contour_iter(
        self,
        countour: Union[Polygon, MultiPolygon],
        layer_def: Type[Feat],
        *,
        only_intersects: bool = False,
    ) -> AsyncGenerator[Feat, None]:
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
        async for feat in self._iter_search_in_box(xmin, ymin, xmax, ymax, layer_def):
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
    async def _search_at_point(
        self, pt: Point, layer_id: int
    ) -> Optional[list[NspdFeature]]:
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
        response = await self.request(
            "get",
            f"/api/aeggis/v3/{layer_id}/wms",
            params=params,  # type: ignore[arg-type]
        )
        return self._validate_feature_collection_response(response)

    async def search_at_point(
        self, pt: Point, layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Поиск объектов слоя в точке (с типизацией)

        Args:
            pt: Точка поиска
            layer_def: Тип слоя

        Returns:
            Типизированный список объектов, если найдены
        """
        raw_features = await self._search_at_point(pt, layer_def.layer_meta.layer_id)
        return self._cast_features_to_layer_defs(raw_features, layer_def)

    async def search_at_coords(
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
        return await self.search_at_point(Point(lng, lat), layer_def)

    ####################
    ### TAB REQUESTS ###
    ####################

    @retry_on_http_error
    async def _tab_request(
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
            r = await self.request(
                "get", f"/api/geoportal/v1/tab-{type_}-data", params=params
            )
            return r.json()
        except err.NotFound:
            return None

    async def _tab_values_request(
        self, feat: NspdFeature, tab_class: str
    ) -> Optional[list[str]]:
        resp = await self._tab_request(feat, tab_class, "values")
        if resp is None:
            return None
        return NspdTabResponse.model_validate(resp).value

    async def _tab_groups_request(
        self, feat: NspdFeature, tab_class: str
    ) -> Optional[dict[str, Optional[list[str]]]]:
        resp = await self._tab_request(feat, tab_class, "group")
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

    async def tab_land_parts(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Части ЗУ\" """
        return await self._tab_values_request(feat, "landParts")

    async def tab_land_links(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Связанные ЗУ\" """
        return await self._tab_values_request(feat, "landLinks")

    async def tab_permission_type(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Виды разрешенного использования\" """
        return await self._tab_values_request(feat, "permissionType")

    async def tab_composition_land(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Состав ЕЗП\" """
        return await self._tab_values_request(feat, "compositionLand")

    async def tab_build_parts(self, feat: NspdFeature) -> Optional[list[str]]:
        """Получение данных с вкладки \"Части ОКС\" """
        return await self._tab_values_request(feat, "buildParts")

    async def tab_objects_list(
        self, feat: NspdFeature
    ) -> Optional[dict[str, Optional[list[str]]]]:
        """
        Получение данных с вкладки \"Объекты\"
        """
        return await self._tab_groups_request(feat, "objectsList")

    async def get_tab_data(self, feat: NspdFeature, tab_name: TabTitle):
        """Получение данных с указанной вкладки"""
        match tab_name:
            case "Части ЗУ":
                return await self.tab_land_parts(feat)
            case "Связанные ЗУ":
                return await self.tab_land_links(feat)
            case "Виды разрешенного использования":
                return await self.tab_permission_type(feat)
            case "Состав ЕЗП":
                return await self.tab_composition_land(feat)
            case "Части ОКС":
                return await self.tab_build_parts(feat)
            case "Объекты":
                return await self.tab_objects_list(feat)

    #################
    ### SHORTCUTS ###
    #################

    async def find_landplot(self, query: str) -> Optional[Layer36048Feature]:
        """Найти ЗУ по кадастровому номеру"""
        return self._filter_search_by_query(await self.search_landplots(query), query)

    async def find_building(self, query: str) -> Optional[Layer36049Feature]:
        """Найти ОКС по кадастровому номеру"""
        return self._filter_search_by_query(await self.search_buildings(query), query)

    async def search_landplots_at_point(
        self, pt: Point
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в точке"""
        return await self.search_at_point(pt, Layer36048Feature)

    async def search_buildings_at_point(
        self, pt: Point
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в точке"""
        return await self.search_at_point(pt, Layer36049Feature)

    async def search_landplots(self, cn: str) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ по кадастровому номеру"""
        return await self.search_in_layer(cn, Layer36048Feature)

    async def search_buildings(self, cn: str) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС по кадастровому номеру"""
        return await self.search_in_layer(cn, Layer36049Feature)

    async def search_landplots_at_coords(
        self, lat: float, lng: float
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в координатах"""
        return await self.search_at_coords(lat, lng, Layer36048Feature)

    async def search_buildings_at_coords(
        self, lat: float, lng: float
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в координатах"""
        return await self.search_at_coords(lat, lng, Layer36049Feature)

    async def search_landplots_in_contour(
        self, countour: Union[Polygon, MultiPolygon]
    ) -> Optional[list[Layer36048Feature]]:
        """Поиск ЗУ в контуре"""
        return await self.search_in_contour(countour, Layer36048Feature)

    async def search_buildings_in_contour(
        self, countour: Union[Polygon, MultiPolygon]
    ) -> Optional[list[Layer36049Feature]]:
        """Поиск ОКС в контуре"""
        return await self.search_in_contour(countour, Layer36049Feature)
