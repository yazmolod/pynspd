import re
from enum import Enum
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Callable,
    Generator,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

import geopandas as gpd
import typer
from hishel import BaseStorage, FileStorage, SQLiteStorage
from pyogrio.errors import DataSourceError
from rich import print
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from shapely import GEOSException, MultiPolygon, Point, Polygon, from_wkt

from pynspd import Nspd, NspdFeature, UnknownLayer
from pynspd.schemas import BaseFeature

app = typer.Typer(pretty_exceptions_show_locals=False, no_args_is_help=True)
CN_PATTERN = re.compile(r"\d+:\d+:\d+:\d+")


T = TypeVar("T")


class CacheType(str, Enum):
    FILE = "file"
    SQLITE = "sqlite"


CacheOption = Annotated[
    Optional[CacheType],
    typer.Option(
        "--cache",
        "-c",
        help="Включить кэширование",
    ),
]
OutputOption = Annotated[
    Optional[Path],
    typer.Option(
        "--output",
        "-o",
        help="Файл, в который будет сохранен результат поиска",
    ),
]

LocalizeOption = Annotated[
    bool,
    typer.Option(
        "--localize",
        "-l",
        help="Использовать названия колонок с сайта, а не из оригинальные",
    ),
]


def define_cns(input_: str) -> list[str]:
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


def define_geoms(input_: str) -> list[Point] | list[Polygon] | list[MultiPolygon]:
    """Проверка гео-файла и получение геометрии из него"""
    maybe_file = Path(input_)
    if maybe_file.exists():
        try:
            gdf = gpd.read_file(input_)
        except DataSourceError as e:
            raise typer.BadParameter(
                f"{input_} не является поддерживаемым файлом"
            ) from e

    else:
        try:
            wkt_geom = from_wkt(input_)
            gdf = gpd.GeoDataFrame([{"geometry": wkt_geom}], crs=4326)
        except GEOSException as e:
            raise typer.BadParameter(
                f"Файл {input_} не существует или не является валидным WKT"
            ) from e
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


def _progress_iter(items: Sequence[T]) -> Generator[T, None, None]:
    cols = [
        SpinnerColumn(),
        TextColumn("{task.description}"),
    ]
    if len(items) > 1:
        cols += [
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ]
    with Progress(
        *cols,
        transient=True,
    ) as progress:
        task = progress.add_task(description="Поиск...", total=len(items))
        for item in items:
            yield item
            progress.update(task, advance=1)


def _get_features_from_list(
    client: Nspd, cns: list[str]
) -> Optional[list[NspdFeature]]:
    features = []
    for cn in _progress_iter(cns):
        feat = client.find(cn)
        if feat is None:
            print(f"{cn} не найден")
            continue
        features.append(feat)
    if len(features) == 0:
        return None
    return features


def _get_features_from_geom(
    method: Callable[
        [Point | Polygon | MultiPolygon, Type[BaseFeature]], Optional[list[BaseFeature]]
    ],
    geoms: list[Point | Polygon | MultiPolygon],
    layer_def: Type[BaseFeature],
) -> Optional[list[BaseFeature]]:
    features = []
    for geom in _progress_iter(geoms):
        feats = method(geom, layer_def)
        if feats is None:
            print(f"В {geom} ничего не найдено")
            continue
        features += feats
    if len(features) == 0:
        return None
    return features


def prepare_features(features: list[NspdFeature], localize: bool) -> gpd.GeoDataFrame:
    prepared_features: list = []
    for feat in features:
        if isinstance(feat, NspdFeature):
            feat = feat.cast()
        if localize:
            props = feat.properties.options.model_dump_human_readable()
            props["Категория"] = feat.properties.category_name
        else:
            props = feat.properties.options.model_dump()
            props["category"] = feat.properties.category_name
        props["geometry"] = feat.geometry.to_shape()
        prepared_features.append(props)
    return gpd.GeoDataFrame(prepared_features, crs=4326).fillna("")


def process_output(
    features: Optional[list[NspdFeature]], output: Optional[Path], localize: bool
) -> None:
    if features is None:
        print("Ничего не найдено")
        raise typer.Abort()
    gdf = prepare_features(features, localize)
    if output is None:
        print(gdf)
    elif output.suffix == ".xlsx":
        gdf.to_excel(output, index=False)
    elif output.suffix == ".csv":
        gdf.to_csv(output, index=False)
    elif output.suffix == ".html":
        gdf.to_html(output, index=False)
    else:
        gdf.to_file(output)
    print(f"[green]Найдено {len(gdf)} объектов, сохранено в файл {output.resolve()}[/]")


@app.command(no_args_is_help=True)
def geo(
    input: Annotated[
        str,
        typer.Argument(help="Путь к файлу с геоданными или WKT"),
    ],
    layer_name: Annotated[
        str,
        typer.Argument(help="Имя слоя с НСПД, в котором нужно производить поиск"),
    ] = "Земельные участки из ЕГРН",
    cache: CacheOption = None,
    output: OutputOption = None,
    localize: LocalizeOption = False,
) -> None:
    """Поиск объектов по геоданным"""
    geoms = define_geoms(input)
    layer_def = define_layer_def(layer_name)
    with Nspd(cache_storage=define_cache_storage(cache)) as client:
        if isinstance(geoms[0], Point):
            features = _get_features_from_geom(client.search_at_point, geoms, layer_def)
        else:
            features = _get_features_from_geom(
                client.search_in_contour, geoms, layer_def
            )
    process_output(features, output, localize)


@app.command(no_args_is_help=True)
def find(
    input: Annotated[
        str,
        typer.Argument(help="Список искомых к/н. Может быть текстовым файлом"),
    ],
    cache: CacheOption = None,
    output: OutputOption = None,
    localize: LocalizeOption = False,
) -> None:
    """Поиск объектов по списку к/н"""
    cns = define_cns(input)
    with Nspd(cache_storage=define_cache_storage(cache)) as client:
        features = _get_features_from_list(client, cns)
    process_output(features, output, localize)


def main() -> Any:
    return app()
