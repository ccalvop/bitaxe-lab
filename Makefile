# Development tasks. Requires uv (https://docs.astral.sh/uv/).
VENV := .venv
BIN  := $(VENV)/bin

.PHONY: venv lint format test check report charts

venv:
	uv venv $(VENV)
	uv pip install --python $(BIN)/python -r requirements-dev.txt

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	shellcheck deploy/*.sh

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test:
	$(BIN)/pytest -q

check: lint test

report:
	cd analysis && ../$(BIN)/python report.py

charts:
	cd analysis && ../$(BIN)/python charts.py
