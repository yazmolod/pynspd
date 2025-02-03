from typing import Annotated, Optional, Union

from geojson_pydantic import FeatureCollection
from pydantic import BaseModel, BeforeValidator, RootModel

from pynspd.schemas import NspdFeature
from pynspd.schemas._common import CamelModel


class BadResponse(CamelModel):
    """Ошибка на поисковой запрос"""

    code: int
    message: str
    request_id: str


class SearchResponse(CamelModel):
    """Положительный ответ на поисковой запрос"""

    data: FeatureCollection[NspdFeature]
    meta: list["Meta"]


class Meta(CamelModel):
    """Метаданные ответа на поисковой запрос"""

    total_count: int
    category_id: int


ResponseModel = RootModel[Union[SearchResponse, BadResponse]]


class NspdTabResponse(BaseModel):
    title: str
    value: Annotated[
        Optional[list[str]],
        BeforeValidator(
            lambda x: None if isinstance(x, list) and len(x) == 1 and x[0] == "" else x
        ),
    ]


class NspdTabGroupResponse(BaseModel):
    title: str
    object: list[NspdTabResponse]
