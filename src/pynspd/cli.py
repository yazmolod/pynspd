import re
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

from pynspd import Nspd, NspdFeature, __version__
from pynspd.errors import UnknownLayer
from pynspd.schemas import BaseFeature

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
    help="Утилита командной строки для поиска на НСПД",
)
CN_PATTERN = re.compile(r"\d+:\d+:\d+:\d+")


T = TypeVar("T")


OutputOption = Annotated[
    Optional[Path],
    typer.Option(
        "--output",
        "-o",
        help=(
            "Файл, в который будет сохранен результат поиска. "
            "Поддерживаются гео- (.gpkg, .geojson и пр.) и табличные форматы (.xlsx, .csv)"
        ),
        rich_help_panel="General Options",
    ),
]

LocalizeOption = Annotated[
    bool,
    typer.Option(
        "--localize",
        "-l",
        help="Использовать названия колонок с сайта, а не из оригинальные",
        rich_help_panel="General Options",
    ),
]

TabObjectsOption = Annotated[
    bool,
    typer.Option(
        "--tab-objects",
        help='Получить данные со вкладки "Объекты" для найденных объектов',
        rich_help_panel="General Options",
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
    coords_pattern = re.compile(r"(\d{2,3}\.\d+),? *(\d{2,3}\.\d+)")
    if maybe_file.suffix == ".txt":
        pts_text = maybe_file.read_text("utf-8")
    else:
        pts_text = input_
    pts_text = pts_text.strip()
    if coords_pattern.match(pts_text):
        coords = [list(map(float, i)) for i in coords_pattern.findall(pts_text)]
        pts = [Point(*i[::-1]) for i in coords]
        geoseries = gpd.GeoSeries(pts, crs=4326)
    elif maybe_file.exists():
        try:
            geoseries = gpd.read_file(input_).geometry
        except DataSourceError as e:
            raise typer.BadParameter(
                f"{input_} не является поддерживаемым файлом"
            ) from e
    else:
        try:
            wkt_geom = from_wkt(input_)
            geoseries = gpd.GeoSeries([wkt_geom], crs=4326)
        except GEOSException as e:
            raise typer.BadParameter(
                f"Файл {input_} не существует или не является валидным WKT"
            ) from e
    geom_types = geoseries.geom_type.unique().tolist()
    geometry = geoseries.tolist()
    if len(geom_types) > 1:
        raise typer.BadParameter("Не поддерживаются файла со смешанной геометрией")
    if geom_types[0] not in ("Point", "Polygon", "MultiPolygon"):
        raise typer.BadParameter(f"Не поддерживаемый тип геометрии - {geom_types[0]}")
    return geometry


def define_layer_def(layer_name: str) -> Type[BaseFeature]:
    """Определение типа слоя"""
    try:
        return NspdFeature.by_title(layer_name)
    except UnknownLayer as e:
        raise typer.BadParameter(f"{layer_name} не является слоем НСПД") from e


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
    missing = []
    for cn in _progress_iter(cns):
        feat = client.find(cn)
        if feat is None:
            missing.append(cn)
            continue
        features.append(feat)
    if missing:
        print(
            f":warning-emoji: [orange3] Не найдены {len(missing)} из {len(cns)} объектов:"
        )
        for m in missing:
            print(f"[orange3]   - {m}")
        print()
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
    missing_count = 0
    for geom in _progress_iter(geoms):
        feats = method(geom, layer_def)
        if feats is None:
            missing_count += 1
            continue
        features += feats
    if missing_count:
        print(
            f":warning-emoji: [orange3] Ничего не найдено в {missing_count} из {len(geoms)} локаций"
        )
        print()
    if len(features) == 0:
        return None
    return features


def _get_tab_object(client: Nspd, features: list[NspdFeature]) -> list[NspdFeature]:
    """Получение данных из вкладки"""
    for feat in _progress_iter(features):
        data = client.tab_objects_list(feat)
        if data is None:
            continue
        assert feat.properties.options.model_extra is not None
        feat.properties.options.model_extra["tab"] = data
    return features


def prepare_features(features: list[NspdFeature], localize: bool) -> gpd.GeoDataFrame:
    prepared_features: list = []
    for feat in features:
        if isinstance(feat, NspdFeature):
            feat = feat.cast()
        assert feat.properties.options.model_extra is not None
        props: dict[str, Any] = feat.properties.options.model_extra.pop("tab", {})
        if localize:
            props.update(feat.properties.options.model_dump_human_readable())
            props["Категория"] = feat.properties.category_name
        else:
            props.update(feat.properties.options.model_dump())
            props["category"] = feat.properties.category_name
        props["geometry"] = feat.geometry.to_shape()
        prepared_features.append(props)
    return gpd.GeoDataFrame(prepared_features, crs=4326).fillna("")


def process_output(
    features: Optional[list[NspdFeature]], output: Optional[Path], localize: bool
) -> None:
    if features is None:
        print("[red]Ничего не найдено")
        raise typer.Abort()
    gdf = prepare_features(features, localize)
    if output is None:
        print(gdf.T)
        return
    elif output.suffix == ".xlsx":
        gdf.to_excel(output, index=False)
    elif output.suffix == ".csv":
        gdf.to_csv(output, index=False)
    else:
        gdf.to_file(output)
    print(f"[green]Найдено {len(gdf)} объектов, сохранено в файл {output.resolve()}[/]")


def version_callback(version: bool = False) -> None:
    if version:
        print(__version__)
        raise typer.Exit()


@app.callback()
def common(
    version: Annotated[
        bool,
        typer.Option(
            "-v",
            "--version",
            help="Show current version",
            is_eager=True,
            callback=version_callback,
        ),
    ] = False,
):
    pass


@app.command(no_args_is_help=True)
def geo(
    input: Annotated[
        str,
        typer.Argument(
            help="Путь к файлу с геоданными, координаты точек или WKT",
            show_default=False,
        ),
    ],
    layer_name: Annotated[
        str,
        typer.Argument(help="Имя слоя с НСПД, в котором нужно производить поиск"),
    ] = "Земельные участки из ЕГРН",
    output: OutputOption = None,
    localize: LocalizeOption = False,
    add_tab_object: TabObjectsOption = False,
) -> None:
    """Поиск объектов по геоданным"""
    geoms = define_geoms(input)
    layer_def = define_layer_def(layer_name)
    with Nspd() as client:
        if isinstance(geoms[0], Point):
            features = _get_features_from_geom(client.search_at_point, geoms, layer_def)
        else:
            features = _get_features_from_geom(
                client.search_in_contour, geoms, layer_def
            )
        if features and add_tab_object:
            _get_tab_object(client, features)
    process_output(features, output, localize)


@app.command(no_args_is_help=True)
def find(
    input: Annotated[
        str,
        typer.Argument(
            help="Список искомых к/н. Может быть текстовым файлом", show_default=False
        ),
    ],
    output: OutputOption = None,
    localize: LocalizeOption = False,
    add_tab_object: TabObjectsOption = False,
) -> None:
    """Поиск объектов по списку к/н"""
    cns = define_cns(input)
    with Nspd() as client:
        features = _get_features_from_list(client, cns)
        if features and add_tab_object:
            features = _get_tab_object(client, features)
    process_output(features, output, localize)


def main() -> Any:
    return app()
