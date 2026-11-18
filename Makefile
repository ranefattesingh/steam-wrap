.DEFAULT_GOAL := help
PY := .venv/bin/python

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv and install app + dev dependencies (uv if present, else pip)
	@if command -v uv >/dev/null 2>&1; then \
		uv venv .venv && uv pip install --python $(PY) -e ".[dev]"; \
	else \
		python3 -m venv .venv 2>/dev/null || python3 -m venv --without-pip .venv; \
		if [ -x .venv/bin/pip ]; then .venv/bin/pip install -e ".[dev]"; \
		else pip --python $(PY) install -e ".[dev]"; fi; \
	fi

run: ## Run the dev server with auto-reload on :8000
	$(PY) -m uvicorn app:app --reload --port 8000

test: ## Run the test suite
	$(PY) -m pytest

lint: ## Lint, check formatting and type-check
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy steam_wrap app.py

format: ## Auto-format and auto-fix lint issues
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

docker: ## Build the Docker image
	docker build -t steam-wrap:latest .

.PHONY: help install run test lint format docker
