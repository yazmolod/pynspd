import re
from datetime import datetime
from typing import Annotated, Generic, Optional, Type, TypeVar, overload

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pynspd.errors import UnknownLayer
from pynspd.schemas._common import CamelModel

OptProps = TypeVar("OptProps", bound="OptionProperties")
T = TypeVar("T", bound="OptionProperties")


class NspdProperties(CamelModel, Generic[OptProps]):
    category: int
    category_name: str
    options: OptProps
    system_info: Optional["SystemInfoProperties"] = None
    cadastral_districts_code: Optional[int] = None
    descr: Optional[str] = None
    external_key: Optional[str] = None
    interaction_id: Optional[int] = None
    label: Optional[str] = None
    subcategory: Optional[int] = None

    @overload
    def cast(self, option_def: None = None) -> "NspdProperties[OptionProperties]": ...

    @overload
    def cast(self, option_def: Type[T]) -> "NspdProperties[T]": ...

    def cast(self, option_def: Optional[Type[T]] = None):
        if option_def is None:
            model = NspdProperties[OptionProperties.by_category_id(self.category)]
        else:
            model = NspdProperties[option_def]
        return model.model_validate(self.model_dump(by_alias=True))


class OptionProperties(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        use_attribute_docstrings=True,
    )

    no_coords: Annotated[bool, Field(alias="geocoderObject", default=False)]

    @model_validator(mode="before")
    @classmethod
    def valid_date(cls, values: dict) -> dict:
        for k, v in values.items():
            if (
                k in cls.model_fields
                and "datetime.date" in str(cls.model_fields[k].annotation)
                and re.match(r"\d+\.\d+\.\d+", v)
            ):
                values[k] = datetime.strptime(v, "%d.%m.%Y")
        return values

    @classmethod
    def by_category_id(cls, category_id: int) -> Type["OptionProperties"]:
        """Получение модели по категории"""
        for sub_class in cls.__subclasses__():
            if sub_class.__name__ == f"Options{category_id}":
                return sub_class
        raise UnknownLayer(category_id)

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
