import re
from pathlib import Path

SUBS = [
    ("import asyncio", "from pynspd import asyncio_mock"),
    ("async def", "def"),
    ("async with", "with"),
    ("await ", ""),
    ("async for", "for"),
    ("get_async_client", "get_client"),
    ("__aenter__", "__enter__"),
    ("__aexit__", "__exit__"),
    ("AsyncClient", "Client"),
    ("AsyncNspd", "Nspd"),
    ("aclose", "close"),
    ("@pytest.mark.asyncio", ""),
    ("asyncio", "asyncio_mock"),
]
COMPILED_SUBS = [
    (re.compile(r"(^|\b)" + regex + r"($|\b)"), repl) for regex, repl in SUBS
]


def unasync_file(file: Path):
    in_file = file.resolve()
    out_file = Path(str(in_file).replace("_async", "_sync"))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with (
        open(in_file, "r", encoding="utf-8") as in_stream,
        open(out_file, "w", encoding="utf-8") as out_stream,
    ):
        for line in in_stream:
            for pat, repl in COMPILED_SUBS:
                line = pat.sub(repl, line)
            out_stream.write(line)


def main():
    cwd = Path.cwd().resolve()
    folders = [cwd / "src", cwd / "tests"]
    for folder in folders:
        for async_folder in folder.glob("**/_async"):
            for file in async_folder.glob("**/*.py"):
                unasync_file(file)


if __name__ == "__main__":
    main()