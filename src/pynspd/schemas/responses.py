from typing import Union

from geojson_pydantic import Feature, FeatureCollection
from pydantic import RootModel

from pynspd.schemas._common import CamelModel


class BadResponse(CamelModel):
    code: int
    message: str
    request_id: str


class SearchResponse(CamelModel):
    data: FeatureCollection[Feature]
    meta: list["Meta"]


class Meta(CamelModel):
    total_count: int
    category_id: int


ResponseModel = RootModel[Union[SearchResponse, BadResponse]]
