.PHONY: unasync autogen tests coverage lint publish docs

install:
	uv sync --all-groups --all-extras --frozen && uv run pre-commit install

lint:
	uv run ruff check --fix && uv run ruff check --select I --fix && ruff format

unasync:
	uv run scripts/unasync.py && make lint

autogen:
	uv run scripts/autogeneration.py && make lint

tests:
	uv run coverage run -m pytest

coverage:
	uv run coveralls && uv run coverage html && start "" "htmlcov\index.html"

publish:
	rmdir /s /q dist && uv build && dotenv --file .env -- set UV_PUBLISH_TOKEN %UV_PUBLISH_TOKEN% && uv publish"

docs:
	uv run mkdocs serve