.PHONY: unasync autogen test coverage ruff publish

ruff:
	uv run ruff check --fix && uv run ruff check --select I --fix && ruff format

unasync:
	uv run scripts/unasync.py && make ruff

autogen:
	uv run scripts/autogeneration.py && make ruff

test:
	uv run coverage run -m pytest

coverage:
	uv run coverage html && start "" "htmlcov\index.html"

publish:
	rmdir /s /q dist && uv build && dotenv --file .env -- set UV_PUBLISH_TOKEN %UV_PUBLISH_TOKEN% && uv run --no-project -- python -c "import os; print(os.environ['UV_PUBLISH_TOKEN'])"