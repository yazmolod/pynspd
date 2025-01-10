.PHONY: unasync autogen test coverage

unasync:
	uv run scripts/unasync.py

autogen:
	uv run scripts/autogeneration.py

test:
	uv run coverage run -m pytest

coverage:
	uv run coverage html && start "" "htmlcov\index.html"