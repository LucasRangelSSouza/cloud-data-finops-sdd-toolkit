PYTHON ?= python
SPEC ?= tests/fixtures/assessment.json

.PHONY: install check format lint test docs-check secret-scan reproduce demo evidence clean

install:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install --no-deps -e .

check:
	$(PYTHON) scripts/check.py

format:
	$(PYTHON) -m ruff format cloud_data_finops tests scripts
	$(PYTHON) -m ruff check --fix cloud_data_finops tests scripts

lint:
	$(PYTHON) -m ruff format --check cloud_data_finops tests scripts
	$(PYTHON) -m ruff check cloud_data_finops tests scripts

test:
	$(PYTHON) -m unittest discover -s tests -t .

docs-check:
	$(PYTHON) scripts/check_links.py

secret-scan:
	$(PYTHON) scripts/secret_scan.py

reproduce:
	$(PYTHON) scripts/reproduce.py

demo:
	$(PYTHON) -m cloud_data_finops.cli report --spec $(SPEC) --output artifacts/demo

evidence:
	$(PYTHON) scripts/update_evidence.py

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('artifacts', 'build', 'dist', '.ruff_cache')]"
