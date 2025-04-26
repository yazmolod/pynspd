from typer.testing import CliRunner

from pynspd.cli import app

runner = CliRunner()


def test_app():
    result = runner.invoke(app, ["-i", "./tests/data/cn_list.txt"])
    assert result.exit_code == 2
