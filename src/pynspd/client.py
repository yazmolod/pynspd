import re
import ssl
from typing import Any, Generator, Optional, Type

import httpx

from pynspd.errors import UnknownLayer
from pynspd.schemas import NspdFeature
from pynspd.schemas.feature import Feat
from pynspd.schemas.responses import SearchResponse

# Нет гарантий, что установлены сертификаты Минцифры, поэтому принудительно отключает проверку ssl
SSL_CONTEXT = ssl._create_unverified_context()
SSL_CONTEXT.set_ciphers("ALL:@SECLEVEL=1")


def get_client_args(timeout: Optional[int]) -> dict:
    return dict(
        base_url="https://nspd.gov.ru",
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Referer": "https://nspd.gov.ru",
            "Host": "nspd.gov.ru",
        },
    )


def get_controller_args() -> dict:
    return dict(
        force_cache=True,
        cacheable_status_codes=[200, 204, 404, 301, 308],
    )


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
        features = response.json()["features"]
        if len(features) == 0:
            return None
        return [NspdFeature.model_validate(i) for i in features]

    @staticmethod
    def _validate_search_response(response: httpx.Response) -> Optional[SearchResponse]:
        return SearchResponse.model_validate(response.json())

    @staticmethod
    def filter_features_by_query(
        query: str, features: list[NspdFeature]
    ) -> list[NspdFeature]:
        """Поиск точного совпадения поискового запроса в наборе фичей"""

        def in_upper_props(query: str, props: dict[str, Any]) -> bool:
            # если есть в верхнеуровневых свойствах - это точное совпадение
            for v in props.values():
                if v == query:
                    return True
            return False

        def in_option_props(query: str, opts: dict[str, Any]) -> bool:
            # в опциональных свойствах проверяем ключ свойства
            for k, v in opts.items():
                if v == query and "parent" not in k:
                    return True
            return False

        def is_known_category(feat: NspdFeature) -> bool:
            # убеждаемся, что это отображаемая категория
            try:
                feat.cast()
                return True
            except UnknownLayer:
                return False

        filtered_features = []
        for f in features:
            if query not in f.properties.model_dump_json():
                continue
            # иногда поиск дает результат не только по к/н, но и прочим полям
            # например, родительский к/н для помещений
            props = f.properties.model_dump()
            opts = props.pop("options")
            if (
                in_upper_props(query, props) or in_option_props(query, opts)
            ) and is_known_category(f):
                filtered_features.append(f)
        return filtered_features
