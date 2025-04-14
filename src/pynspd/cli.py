from datetime import date
from typing import Any

import typer
from rich import print
from rich.table import Table

from pynspd import Nspd

app = typer.Typer(no_args_is_help=True)


@app.command()
def search(): ...


@app.command()
def find(cn: str):
    with Nspd() as api:
        feat = api.find(cn)
    if feat is None:
        print("Объект не найден")
        raise typer.Exit()
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


def main() -> Any:
    return app()
