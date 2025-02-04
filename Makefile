.PHONY: unasync autogen tests coverage ruff publish

ruff:
	uv run ruff check --fix && uv run ruff check --select I --fix && ruff format

unasync:
	uv run scripts/unasync.py && make ruff

autogen:
	uv run scripts/autogeneration.py && make ruff

tests:
	uv run coverage run -m pytest

coverage:
	uv run coveralls && uv run coverage html && start "" "htmlcov\index.html"

publish:
	rmdir /s /q dist && uv build && dotenv --file .env -- set UV_PUBLISH_TOKEN %UV_PUBLISH_TOKEN% && uv publish"