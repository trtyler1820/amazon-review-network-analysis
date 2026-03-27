VENV := venv/bin
PYTHON := $(VENV)/python3
PYTEST := $(VENV)/pytest
PIP := $(VENV)/pip

.PHONY: test coverage clean run-web clean-data help

## Run unit tests (no integration tests)
test:
	$(PYTEST) tests/test_models.py tests/test_analysis.py -v

## Run all tests including integration (requires full dataset)
test-all:
	$(PYTEST) tests/ -v

## Run tests with coverage report
coverage:
	$(PYTEST) tests/test_models.py tests/test_analysis.py \
		--cov=graph_logic --cov-report=term-missing -v

## Run the full data cleaning pipeline
clean-data:
	$(PYTHON) scripts/clean_data.py

## Run cleaning pipeline on a small sample (100 records/file)
sample:
	$(PYTHON) scripts/clean_data.py --sample-size 100

## Launch the Streamlit web app (Phase 3)
run-web:
	$(VENV)/streamlit run web/app.py

## Install / sync dependencies
install:
	$(PIP) install -r requirements.txt

## Remove Python and test artifacts
clean:
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} +
	find . -name "*.pyc" -not -path "./venv/*" -delete
	rm -f .coverage coverage.xml
	rm -rf htmlcov/ .pytest_cache/

help:
	@grep -E '^##' Makefile | sed 's/## //'
