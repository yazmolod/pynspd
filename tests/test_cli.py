from pathlib import Path

import pytest
from typer.testing import CliRunner

from pynspd import __version__
from pynspd.cli import app

runner = CliRunner()


@pytest.fixture()
def output_file(request):
    file: Path = Path.cwd() / ("test" + request.param)
    yield file
    assert file.exists()
    file.unlink()


def test_cn_list_text():
    result = runner.invoke(app, ["search", "77:01:0001057:76"])
    assert result.exit_code == 0


@pytest.mark.parametrize("output_file", [".xlsx"], indirect=True)
def test_cn_list_file(output_file: Path):
    result = runner.invoke(
        app,
        [
            "search",
            "-o",
            output_file.name,
            "-l",
            "./tests/data/cn_list.txt",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("output_file", [".csv"], indirect=True)
def test_geo_file(output_file: Path):
    result = runner.invoke(
        app, ["geo", "-o", output_file.name, "./tests/data/poly.gpkg"]
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("output_file", [".gpkg"], indirect=True)
def test_geo_text(output_file: Path):
    result = runner.invoke(
        app, ["geo", "-o", output_file.name, "Point (37.562 55.605)"]
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("output_file", [".geojson"], indirect=True)
def test_geo_coords(output_file: Path):
    result = runner.invoke(
        app,
        [
            "geo",
            "-o",
            output_file.name,
            "   53.193168, 50.106273 53.193704, 50.105026   ",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("output_file", [".geojson"], indirect=True)
def test_geo_coords_file(output_file: Path):
    result = runner.invoke(
        app, ["geo", "-o", output_file.name, "./tests/data/pt_list.txt"]
    )
    assert result.exit_code == 0


def test_version():
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_bad_text_input():
    result = runner.invoke(app, ["search", "./tests/data/missing_file.txt"])
    assert result.exit_code == 2
    assert "Нужно ввести валидные кадастровые номера" in result.stdout

    result = runner.invoke(app, ["search", "./tests/data/empty_list.txt"])
    assert result.exit_code == 2
    assert "В файле не найдены кадастровые номера" in result.stdout

    result = runner.invoke(app, ["search", "./tests/data/lines.gpkg"])
    assert result.exit_code == 2
    assert "Невозможно прочитать файл" in result.stdout


def test_bad_geom_input():
    result = runner.invoke(app, ["geo", "./tests/data/cn_list.txt"])
    assert result.exit_code == 2
    assert "не является поддерживаемым файлом" in result.stdout

    result = runner.invoke(app, ["geo", "Bad WKT"])
    assert result.exit_code == 2
    assert "не является валидным WKT" in result.stdout

    result = runner.invoke(app, ["geo", "./tests/data/lines.gpkg"])
    assert result.exit_code == 2
    assert "Не поддерживаемый тип геометрии" in result.stdout


def test_empty_output():
    result = runner.invoke(app, ["search", "-p", "fuzzbuzz"])
    assert result.exit_code == 1
    assert "Ничего не найдено" in result.stdout

    result = runner.invoke(
        app, ["geo", "Point (37.55342908811032743 55.59951468019968246)"]
    )
    assert result.exit_code == 1
    assert "Ничего не найдено" in result.stdout


def test_bad_layer_name():
    result = runner.invoke(
        app,
        ["geo", "./tests/data/poly.gpkg", "-c", "---test-layer-name", "Hello World"],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "не является слоем НСПД" in result.stdout


def test_tab_output():
    result = runner.invoke(app, ["search", "77:07:0006001:1020", "--tab-objects"])
    assert result.exit_code == 0
    assert "Помещения (количество)" in result.stdout
    result = runner.invoke(
        app, ["geo", "Point (37.5106798 55.729467)", "--tab-objects"]
    )
    assert result.exit_code == 0
    assert "Объект недвижимости" in result.stdout


def test_cities_parse():
    result = runner.invoke(
        app,
        [
            "search",
            "-pc",
            "---test-layer-names",
            "Муниципальные образования (полигональный)",
            "---test-layer-names",
            "Населённые пункты (полигоны)",
            "Обнинск",
        ],
    )
    assert result.exit_code == 0
    # два разных субъекта в выводе
    assert "29415000000" in result.stdout
    assert "29415000000" in result.stdout
