import asyncio
import subprocess

from jinja2 import Template

from pynspd.client import get_async_client
from pynspd.schemas.layer_configs import Card, CardField, LayerNode, LayersTree

CLIENT = get_async_client()


TYPES_TEMPLATE = """# autogenerated
from typing import Literal


LayerTitle = Literal[
    {%- for layer in layers %}
    "{{ layer.title }}",
    {%- endfor %}
]
"""

SCHEMAS_TEMPLATE = """# autogenerated
from typing import Union, Annotated, Optional
from datetime import date

from geojson_pydantic import (
    Feature, 
    MultiPolygon, 
    Polygon, 
    MultiLineString, 
    LineString, 
    MultiPoint, 
    Point, 
    GeometryCollection,
)
from pydantic import Field

from pynspd.schemas.layer_configs import LayerNode
from pynspd.schemas.base_feature import NspdFeature, NspdProperties, OptionProperties


{% for category_id, fields in layers_fields.items() %}
class Options{{ category_id }}(OptionProperties): {% if fields|length == 0 %}...{% endif %}
    {%- for field in fields %}
    {{ field.key_value }}: Annotated[
        Optional[{{field.key_type}}],
        Field(default=None, description="{{field.key_name}}{% if field.postfix != None %} ({{ field.postfix }}){% endif %}")
    ]
    {%- endfor %}
{% endfor %}


{% for layer in layers %}
class Layer{{ layer.layer_id }}Feature(NspdFeature[
    {%- if layer.geometry_type == 'Polygon' %}
    Union[Multi{{ layer.geometry_type }}, {{ layer.geometry_type }}],
    {% else %}
    {{ layer.geometry_type }},
    {% endif -%}
    NspdProperties[Options{{ layer.category_id }}]
]):
    layer_meta = LayerNode.model_validate({{ layer.model_dump(by_alias=True) }})
{% endfor %}
"""


def generate_files(layers: list[LayerNode], layers_fields: dict[int, Card]):
    output = Template(SCHEMAS_TEMPLATE).render(
        layers=layers, layers_fields=layers_fields
    )
    with open("src/pynspd/schemas/_autogen_features.py", "w", encoding="utf-8") as file:
        file.write(output)
    output = Template(TYPES_TEMPLATE).render(layers=layers)
    with open("src/pynspd/types/_autogen_layers.py", "w", encoding="utf-8") as file:
        file.write(output)


async def get_layer_tree() -> LayersTree:
    r = (
        await CLIENT.get("/api/geoportal/v1/layers-theme-tree", params={"themeId": 1})
    ).raise_for_status()
    tree = LayersTree.model_validate(r.json())
    return tree


async def get_layers_fields(layers: list[LayerNode]) -> dict[int, list[CardField]]:
    layers_fields = {}
    for layer in layers:
        if layer.category_id in layers_fields:
            continue
        r = (
            await CLIENT.get(
                f"/api/geoportal/v1/geom-card-display-settings/{layer.category_id}"
            )
        ).raise_for_status()
        card = Card.model_validate(r.json())
        fields = []
        for field in card.card:
            if field.key_value == "-":
                continue
            if field.key_value == "":
                continue
            if not field.key_value.isascii():
                continue
            if " " in field.key_value:
                continue
            fields.append(field)
        layers_fields[layer.category_id] = fields
    return layers_fields


def lint_and_format():
    subprocess.call(".venv/Scripts/ruff.exe check --fix src/pynspd/**/_autogen*.py")
    subprocess.call(
        ".venv/Scripts/ruff.exe check --select I --fix src/pynspd/**/_autogen*.py"
    )
    subprocess.call(".venv/Scripts/ruff.exe format src/pynspd/**/_autogen*.py")


async def main():
    tree = await get_layer_tree()
    layers = tree.layers
    layers_fields = await get_layers_fields(layers)
    generate_files(layers, layers_fields)
    lint_and_format()


if __name__ == "__main__":
    asyncio.run(main())
