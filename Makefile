.PHONY: install test lint lint-all lint-types format clean run-daemon stop-daemon status pre-commit test-all test-coverage test-integration dev-sync

PYTHON := python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
LINT_PATHS := argus_py/alerts argus_py/dashboard argus_py/security

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	$(VENV)/bin/pre-commit install

test:
	$(PYTEST) tests/unit/ -v --tb=short

test-integration:
	$(PYTEST) tests/integration/ -v --tb=short

test-all:
	$(PYTEST) tests/ -v --tb=short

test-coverage:
	$(PYTEST) tests/unit/ --cov=argus_py --cov-report=html

lint:
	$(VENV)/bin/flake8 $(LINT_PATHS) --max-line-length=100 --ignore=E203,W503

lint-types:
	$(VENV)/bin/mypy $(LINT_PATHS) --ignore-missing-imports

lint-all:
	$(VENV)/bin/flake8 argus_py/ Scripts/
	$(VENV)/bin/mypy argus_py/ --ignore-missing-imports

format:
	$(VENV)/bin/black argus_py/ Scripts/ tests/
	$(VENV)/bin/isort argus_py/ Scripts/ tests/

pre-commit:
	$(VENV)/bin/pre-commit run --all-files

run-daemon:
	./Scripts/phase19ctl.sh start

stop-daemon:
	./Scripts/phase19ctl.sh stop

status:
	./Scripts/phase19ctl.sh status

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov

dev-sync:
	$(PIP) freeze > requirements-frozen.txt
