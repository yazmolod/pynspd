import re
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional, Type

import geopandas as gpd
import typer
from hishel import BaseStorage, FileStorage, SQLiteStorage
from rich import print
from rich.progress import track
from rich.table import Table
from shapely import MultiPolygon, Point, Polygon

from pynspd import Nspd, NspdFeature, UnknownLayer
from pynspd.schemas import BaseFeature

app = typer.Typer(pretty_exceptions_show_locals=False, no_args_is_help=True)
CN_PATTERN = re.compile(r"\d+:\d+:\d+:\d+")


class CacheType(str, Enum):
    FILE = "file"
    SQLITE = "sqlite"


def define_cns(input_: str):
    """Поиск массива к/н в исходной строке или текстовом файле"""
    if CN_PATTERN.match(input_):
        return list(Nspd.iter_cn(input_))
    maybe_file = Path(input_)
    if not maybe_file.exists():
        raise typer.BadParameter("Файл не найден")
    if maybe_file.suffix in (".txt",):
        cns = list(Nspd.iter_cn(maybe_file.read_text("utf-8")))
        if len(cns) == 0:
            raise typer.BadParameter("В файле не найдены кадастровые номера")
        return cns
    raise typer.BadParameter("Неподдерживаемый формат файла")


def define_geoms(input_: Path) -> list[Point] | list[Polygon] | list[MultiPolygon]:
    """Проверка гео-файла и получение геометрии из него"""
    gdf = gpd.read_file(input_)
    geom_types = gdf.geom_type.unique().tolist()
    geometry = gdf.geometry.tolist()
    if len(geom_types) > 1:
        raise typer.BadParameter("Не поддерживаются файла со смешанной геометрией")
    if geom_types[0] not in ("Point", "Polygon", "MultiPolygon"):
        raise typer.BadParameter(f"Не поддерживаемый тип геометрии - {geom_types[0]}")
    return geometry


def define_cache_storage(cache_type: Optional[CacheType]) -> Optional[BaseStorage]:
    """Опредение типа кэш-хранилища"""
    match cache_type:
        case CacheType.FILE:
            return FileStorage()
        case CacheType.SQLITE:
            return SQLiteStorage()
        case _:
            return None


def define_layer_def(layer_name: str) -> Type[BaseFeature]:
    """Определение типа слоя"""
    try:
        return NspdFeature.by_title(layer_name)
    except UnknownLayer:
        raise typer.BadParameter(f"{layer_name} не является слоем с НСПД")


def _get_features_from_list(client: Nspd, cns: list[str]) -> list[NspdFeature] | None:
    features = []
    for cn in track(cns, description="Поиск..."):
        feat = client.find(cn)
        if feat is None:
            print(f"{cn} не найден")
            continue
        features.append(feat)
    if len(features) == 0:
        return None
    return features


def _get_features_from_points(
    client: Nspd, pts: list[Point], layer_def: Type[BaseFeature]
) -> list[BaseFeature] | None:
    features = []
    for pt in track(pts, description="Поиск..."):
        feats = client.search_at_point(pt, layer_def)
        if feats is None:
            print(f"В точке {pt} ничего не найдено")
            continue
        features += feats
    if len(features) == 0:
        return None
    return features


def _get_features_from_polygons(
    client: Nspd, polys: list[Polygon], layer_def: Type[BaseFeature]
) -> list[BaseFeature] | None:
    features = []
    for poly in track(polys, description="Поиск..."):
        feats = client.search_in_contour(poly, layer_def)
        if feats is None:
            print(f"В контуре {poly} ничего не найдено")
            continue
        features += feats
    if len(features) == 0:
        return None
    return features


def process_output(features: list[NspdFeature] | None):
    if features is None:
        print("Ничего не найдено")
        raise typer.Abort()
    for feat in features:
        table = Table("Свойство", "Значение")
        for k, v in feat.properties.cast().options.model_dump_human_readable().items():
            if isinstance(v, date):
                v = v.strftime("%d-%m-%Y")
            elif isinstance(v, float):
                v = str(v)
            if not v:
                continue
            table.add_row(k, v)
        print(table)


@app.command(no_args_is_help=True)
def by_geo(
    input_file: Annotated[
        Path,
        typer.Argument(dir_okay=False),
    ],
    layer_name: Annotated[
        str,
        typer.Argument(),
    ] = "Земельные участки из ЕГРН",
    cache: Annotated[
        Optional[CacheType],
        typer.Option(
            "--cache",
            "-c",
            help="Включить кэширование",
        ),
    ] = None,
):
    """Поиск объектов по геоданным"""
    geoms = define_geoms(input_file)
    layer_def = define_layer_def(layer_name)
    with Nspd(cache_storage=define_cache_storage(cache)) as client:
        if isinstance(geoms[0], Point):
            features = _get_features_from_points(client, geoms, layer_def)
        else:
            features = _get_features_from_polygons(client, geoms, layer_def)
    process_output(features)


@app.command(no_args_is_help=True)
def by_list(
    input: Annotated[
        str,
        typer.Argument(help="Список искомых к/н. Может быть текстовым файлом"),
    ],
    cache: Annotated[
        Optional[CacheType],
        typer.Option(
            "--cache",
            "-c",
            help="Включить кэширование",
        ),
    ] = None,
):
    """Поиск объектов по списку к/н"""
    cns = define_cns(input)
    with Nspd(cache_storage=define_cache_storage(cache)) as client:
        features = _get_features_from_list(client, cns)
    process_output(features)


def main() -> Any:
    return app()
