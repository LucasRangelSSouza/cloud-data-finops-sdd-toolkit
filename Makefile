.PHONY: check demo

check:
	python scripts/check.py

demo:
	python -m cloud_data_finops.cli report --spec tests/fixtures/assessment.json --output artifacts/demo

