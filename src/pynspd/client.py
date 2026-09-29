import os
import re
import socket
import ssl
import warnings
from collections.abc import Generator
from typing import Any, TypeVar
from urllib.parse import urlencode

import httpx2 as httpx
import ua_generator
from hishel import Controller
from hishel._utils import generate_key
from httpcore import Request

from pynspd.errors import AmbiguousSearchError, UnknownLayer
from pynspd.schemas import NspdFeature
from pynspd.schemas.feature import Feat

T = TypeVar("T")


# Нет гарантий, что установлены сертификаты Минцифры, поэтому принудительно отключает проверку ssl
SSL_CONTEXT = ssl._create_unverified_context()
SSL_CONTEXT.set_ciphers("ALL:@SECLEVEL=1")


def _cache_key_generator(request: Request, body: bytes | None) -> str:
    body = body or b""
    key = generate_key(request, body)
    return f"pynspd-{key}"


NSPD_CACHE_CONTROLLER = Controller(
    force_cache=True,
    cacheable_status_codes=[200, 204, 404, 301, 308],
    key_generator=_cache_key_generator,
)


class BaseNspdClient:
    """Базовый класс, не зависящий от sync/async контекста"""

    DNS_HOST = "nspd.gov.ru"
    DNS_URL = "https://" + DNS_HOST

    @staticmethod
    def iter_cn(input_str: str) -> Generator[str, None, None]:
        """Извлечение кадастровых номеров из строки"""
        yield from re.findall(r"\d+:\d+:\d+:\d+", input_str)

    @staticmethod
    def _cast_features_to_layer_defs(
        raw_features: list[NspdFeature] | None, layer_def: type[Feat]
    ) -> list[Feat] | None:
        """Приводит массив фичей к определенному типу"""
        if raw_features is None:
            return None
        features = [i.cast(layer_def) for i in raw_features]
        return features

    @staticmethod
    def _validate_feature_collection_response(
        response: httpx.Response,
    ) -> list[NspdFeature] | None:
        features = response.json()["features"]
        if len(features) == 0:
            return None
        return [NspdFeature.model_validate(i) for i in features]

    @classmethod
    def _filter_search_by_query(
        cls, features: list[Feat] | None, query: str
    ) -> Feat | None:
        if features is None:
            return None
        features = list(
            filter(lambda f: query in f.properties.model_dump_json(), features)
        )
        if len(features) > 1:
            features = cls._filter_features_by_query(features, query)
        if len(features) == 0:
            return None
        if len(features) != 1:
            raise AmbiguousSearchError(query)
        return features[0]

    @staticmethod
    def _filter_features_by_query(features: list[Feat], query: str) -> list[Feat]:
        """Поиск точного совпадения поискового запроса в наборе фичей"""

        def in_upper_props(query: str, props: dict[str, Any]) -> bool:
            # если есть в верхнеуровневых свойствах - это точное совпадение
            return any(v == query for v in props.values())

        def in_option_props(query: str, opts: dict[str, Any]) -> bool:
            # в опциональных свойствах проверяем ключ свойства
            return any(v == query and "parent" not in k for k, v in opts.items())

        def is_known_category(feat: Feat) -> bool:
            # убеждаемся, что это отображаемая категория
            try:
                feat.cast()  # type: ignore[union-attr]
                return True
            except UnknownLayer:
                return False

        filtered_features = []
        for f in features:
            # иногда поиск дает результат не только по к/н, но и прочим полям
            # например, родительский к/н для помещений
            props = f.properties.model_dump()
            opts = props.pop("options")
            if (
                in_upper_props(query, props) or in_option_props(query, opts)
            ) and is_known_category(f):
                filtered_features.append(f)
        return filtered_features

    @staticmethod
    def _str_var(var_name: str, var: T, trust_env: bool):
        if not trust_env:
            return var
        env_var_name = f"PYNSPD_{var_name.upper()}"
        env_var = os.getenv(env_var_name)
        if env_var is not None:
            if var is not None:
                warnings.warn(
                    f"Используется переменная окружения {env_var_name}, "
                    f"аргумент '{var_name}' проигнорирован",
                    stacklevel=4,
                )
            return env_var
        return var

    @classmethod
    def _int_var(cls, var_name: str, var: T, trust_env: bool):
        d = cls._str_var(var_name, var, trust_env)
        if d is None:
            return None
        return int(d)

    @classmethod
    def _bool_var(cls, var_name: str, var: T, trust_env: bool):
        d = cls._str_var(var_name, var, trust_env)
        if isinstance(d, bool):
            return d
        return bool(isinstance(d, str) and d.lower() in ("true", "1"))

    @classmethod
    def _get_headers(cls) -> dict[str, str]:
        query_params = {
            # Используем минимум для получения 200,
            # чтобы не наткнуться на сайд-эффекты
            "thematic": "PKK",
        }
        return {
            "User-Agent": ua_generator.generate().text,
            "Referer": cls.DNS_URL + "/map?" + urlencode(query_params),
            "Host": cls.DNS_HOST,
        }

    @classmethod
    def _get_ip(cls) -> str:
        ips = socket.gethostbyname_ex(cls.DNS_HOST)[2]
        if len(ips) == 0:
            raise RuntimeError("Can't resolve nspd.gov.ru")
        return ips[0]
