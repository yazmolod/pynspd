from typing import Any, Literal, Optional

from pydantic import ConfigDict, field_serializer, field_validator, model_validator

from pynspd.schemas._common import CamelModel


class LayersTree(CamelModel):
    layers: list["LayerNode"]
    tree: Any


class LayerNode(CamelModel):
    title: str
    layer_tree_id: int
    layer_id: int
    layer_type: Literal["wms"]
    geometry_type: Literal["Polygon", "LineString", "Point", "GeometryCollection"]
    layer_name: str
    layer_visible_by_default: bool
    category_id: int

    @field_validator("geometry_type", mode="before")
    @classmethod
    def _geometry_type_validator(cls, v: str):
        alias_dict = {
            "POLYGON": "Polygon",
            "LINESTRING": "LineString",
            "POINT": "Point",
            "MULTITYPE": "GeometryCollection",
        }
        return alias_dict[v]

    @field_serializer("geometry_type")
    @classmethod
    def _geometry_type_serializer(cls, v: str):
        alias_dict = {
            "Polygon": "POLYGON",
            "LineString": "LINESTRING",
            "Point": "POINT",
            "GeometryCollection": "MULTITYPE",
        }
        return alias_dict[v]


class Card(CamelModel):
    title: Any
    card: list["CardField"]


class CardField(CamelModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key_name: str
    key_value: str
    key_type: Literal["str", "float", "date"]
    padding: bool
    default_value: str
    show_empty: bool
    prefix: Optional[str] = None
    postfix: Optional[str] = None

    @model_validator(mode="after")
    def _update_mistyped_data(self):
        # тип в конфиге отличается от реального
        if self.key_value == "specified_area":
            self.key_type = "Union[str, float]"
        return self

    @field_validator("key_value", mode="before")
    @classmethod
    def _key_value_validator(cls, v: str):
        assert v.startswith("properties.options.")
        return v.replace("properties.options.", "")

    @field_validator("key_type", mode="before")
    @classmethod
    def _key_type_validator(cls, v: str):
        alias_dict = {
            "text": "str",
            "number": "float",
            "date": "date",
            "href": "str",
        }
        return alias_dict[v]
