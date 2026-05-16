.PHONY: help install sync test lint format typecheck check build clean run

help:
	@grep -E '^[a-zA-Z_-]+:' Makefile

install:
	uv sync
	uv sync --project dwdweather

sync: install

test:
	uv run pytest tests/

lint:
	uv run ruff check dwdweather

format:
	uv run ruff format dwdweather
	uv run ruff check --fix dwdweather

typecheck:
	uv run mypy dwdweather

check: lint typecheck test

build:
	uv build --project dwdweather

clean:
	rm -rf dist/ dwdweather/dist/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

run:
	uv run --project dwdweather dwdweather $(ARGS)
