from datetime import datetime
from typing import Annotated, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from pynspd.schemas._common import CamelModel

OptProps = TypeVar("OptProps", bound="OptionProperties")


class Properties(CamelModel, Generic[OptProps]):
    category: int
    category_name: str
    options: OptProps
    systemInfo: Optional["SystemInfoProperties"] = None
    cadastral_districts_code: Optional[int] = None
    descr: Optional[str] = None
    external_key: Optional[str] = None
    interaction_id: Optional[int] = None
    label: Optional[str] = None
    subcategory: Optional[int] = None


class OptionProperties(BaseModel):
    model_config = ConfigDict(extra="allow")

    no_coords: Annotated[bool, Field(alias="geocoderObject", default=False)]

    def model_dump_human_readable(self):
        """Генерация словаря с ключами, аналогичным карточке на сайте"""
        data = self.model_dump()
        alias = {
            k: v.description for k, v in self.model_fields.items() if v.description
        }
        aliased_data = {alias[k]: v for k, v in data.items() if k in alias}
        return aliased_data


class SystemInfoProperties(CamelModel):
    inserted: datetime
    inserted_by: str
    updated: datetime
    updated_by: str
