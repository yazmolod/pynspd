import re
import ssl
from typing import Any, Generator, Optional, Type

import httpx
from hishel import Controller
from hishel._utils import generate_key
from httpcore import Request

from pynspd.errors import AmbiguousSearchError, UnknownLayer
from pynspd.schemas import NspdFeature
from pynspd.schemas.feature import Feat

# Нет гарантий, что установлены сертификаты Минцифры, поэтому принудительно отключает проверку ssl
SSL_CONTEXT = ssl._create_unverified_context()
SSL_CONTEXT.set_ciphers("ALL:@SECLEVEL=1")


def _cache_key_generator(request: Request, body: Optional[bytes]) -> str:
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

    @staticmethod
    def iter_cn(input_str: str) -> Generator[str, None, None]:
        """Извлечение кадастровых номеров из строки"""
        for cn in re.findall(r"\d+:\d+:\d+:\d+", input_str):
            yield cn

    @staticmethod
    def _cast_features_to_layer_defs(
        raw_features: Optional[list[NspdFeature]], layer_def: Type[Feat]
    ) -> Optional[list[Feat]]:
        """Приводит массив фичей к определенному типу"""
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

    @classmethod
    def _filter_search_by_query(
        cls, features: Optional[list[Feat]], query: str
    ) -> Optional[Feat]:
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
