from typing import Optional, Type, TypeVar, cast

from pynspd.client import get_async_client
from pynspd.schemas import Layer36048Feature, NspdFeature
from pynspd.schemas.responses import SearchResponse

T = TypeVar("T", bound=NspdFeature)


class AsyncNspd:
    def __init__(self):
        self._client = get_async_client()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc): ...

    async def search_request(
        self, query: str, *layer_ids: int
    ) -> Optional[SearchResponse]:
        """Поисковой запрос по указанным слоям

        Args:
            query (str): поисковой запрос
            *layer_ids (int): id слоев, в которых будет производиться поиск

        Returns:
            Optional[SearchResponse]: положительный ответ от сервиса, либо None, если ничего не найдено
        """
        r = await self._client.get(
            "/api/geoportal/v2/search/geoportal",
            params={
                "query": query,
                "layersId": layer_ids,
            },
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return SearchResponse.model_validate(r.json())

    async def search_one(self, query: str, layer_def: Type[T]) -> Optional[T]:
        response = await self.search_request(query, layer_def.layer_meta.layer_id)
        if response is None:
            return None
        assert len(response.data.features) == 1
        feature = response.data.features[0]
        return layer_def.model_validate(feature.model_dump())

    # async def search_many(self, query: str, *layer_def: Type[T]) -> Optional[T]:
    #     ...

    async def find_zu(self, cn: str) -> Optional[Layer36048Feature]:
        m = await self.search_one(cn, NspdFeature.by_title("Земельные участки из ЕГРН"))
        return cast(Layer36048Feature, m) if m is not None else None

    # async def find_oks(self, cn: str) -> Optional[OksFeature]:
    #     return await self.search_one(cn, LayerIdMap['Здания'], OksFeature)

    # async def find_zu_or_oks(self, cn: str):
    #     return await self.search_request(cn, LayerIdMap['Земельные участки из ЕГРН'], LayerIdMap['Здания'])

    # async def find_in_contour(self, countour):
    #     "не больше 40, но в ошибке есть id"
    #     ...

    # async def find_at_point(self, pt):
    #     ...
