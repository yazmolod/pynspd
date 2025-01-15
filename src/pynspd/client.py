import re
import ssl
from typing import Generator, Optional, Type

import httpx
from httpx._types import ProxyTypes

from pynspd.schemas import NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import SearchResponse

# Нет гарантий, что установлены сертификаты Минцифры, поэтому принудительно отключает проверку ssl
SSL_CONTEXT = ssl._create_unverified_context()
SSL_CONTEXT.set_ciphers("ALL:@SECLEVEL=1")


def _get_client_args(timeout, retries, proxy):
    return (
        dict(
            base_url="https://nspd.gov.ru",
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
                "Referer": "https://nspd.gov.ru",
            },
        ),
        dict(verify=SSL_CONTEXT, retries=retries, proxy=proxy),
    )


def get_async_client(
    timeout: Optional[int] = 10, retries: int = 10, proxy: Optional[ProxyTypes] = None
) -> httpx.AsyncClient:
    client_args, transport_args = _get_client_args(timeout, retries, proxy)
    transport = httpx.AsyncHTTPTransport(**transport_args)
    return httpx.AsyncClient(**client_args, transport=transport)


def get_client(
    timeout: Optional[int] = 10, retries: int = 10, proxy: Optional[ProxyTypes] = None
) -> httpx.Client:
    client_args, transport_args = _get_client_args(timeout, retries, proxy)
    transport = httpx.HTTPTransport(**transport_args)
    return httpx.Client(**client_args, transport=transport)


class BaseNspdClient:
    """Базовый класс, не зависящий от sync/async контекста"""

    def __init__(self, retries: int):
        self.retries = retries

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
    def _validate_feature_collection_response(
        response: httpx.Response,
    ) -> Optional[list[NspdFeature]]:
        response.raise_for_status()
        features = response.json()["features"]
        if len(features) == 0:
            return None
        return [NspdFeature.model_validate(i) for i in features]

    @staticmethod
    def _validate_search_response(response: httpx.Response) -> Optional[SearchResponse]:
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return SearchResponse.model_validate(response.json())
