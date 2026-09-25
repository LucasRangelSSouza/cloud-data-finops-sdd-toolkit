# Reproduce the synthetic assessment

This guide rebuilds every release artifact from the checked-in synthetic fixture and compares the result with the checksums in [`docs/evidence/release-fixture/SHA256SUMS`](evidence/release-fixture/SHA256SUMS). No cloud account, credential, or network call is needed after the Python packages are installed.

## Requirements

- Python 3.12 (CI uses 3.12; the package declares `>=3.10`, but the checksums below were recorded with 3.12).
- The locked packages in [`requirements-dev.txt`](../requirements-dev.txt): `matplotlib==3.8.4`, `python-pptx==1.0.2`, `ruff==0.16.4`, and their pinned transitive dependencies.
- GNU Make is optional. Every target has a plain Python equivalent below.

## One command

```bash
make install
make reproduce
```

Without Make (Windows PowerShell or any shell):

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python scripts/reproduce.py
```

`scripts/reproduce.py` does three things:

1. checks that `tests/fixtures/assessment.json` is byte-identical to the output of `cloud_data_finops.synthetic` with the default seed (`20260901`);
2. runs validation, preflight, the access plan, collection through the fixture adapters, the nine rules, the Markdown report, the PNG evidence cards, and the PPTX deck into `artifacts/reproduce/`;
3. compares each artifact's SHA-256 with the versioned manifest and exits with status 1 if a strict artifact differs.

Expected output:

```text
ok   fixture matches cloud_data_finops.synthetic (default seed)
ok   access-plan.json  28976f9bee05a9091008a9d8e6506b7369f936f2858f34b787d72d4652d3930c
ok   findings.json  e4ca61ca9a634f52c2fcde3dc20538e0879a59d15bede9601869f7cdbc8c014f
ok   report.md  f87c4869e40e921ab805c7429abe158e6b3158490457299187fbf1482e7f1f06
ok   synthetic-finops-assessment.pptx  f52c8c7b3a1e72c17bc4671a47a81cbf8daa70ac31c88f6e5b4243a68886a0e7
ok   cost-signals.png  ddda9dcf0f73d1ca23ea647f7e46dac9aec894cb61573b51de2a813b84167082
11 findings written to artifacts/reproduce
```

## Expected artifacts

| Artifact | Content | SHA-256 | Comparison |
| --- | --- | --- | --- |
| `access-plan.json` | Provider-specific read-only access request | `28976f9bee05a9091008a9d8e6506b7369f936f2858f34b787d72d4652d3930c` | strict |
| `findings.json` | 11 structured findings from 9 rules | `e4ca61ca9a634f52c2fcde3dc20538e0879a59d15bede9601869f7cdbc8c014f` | strict |
| `report.md` | Technical report with evidence, calculations, limitations, and sources | `f87c4869e40e921ab805c7429abe158e6b3158490457299187fbf1482e7f1f06` | strict |
| `synthetic-finops-assessment.pptx` | Seven-slide executive deck | `f52c8c7b3a1e72c17bc4671a47a81cbf8daa70ac31c88f6e5b4243a68886a0e7` | strict |
| `cost-signals.png` | Three evidence cards, one unit each | `ddda9dcf0f73d1ca23ea647f7e46dac9aec894cb61573b51de2a813b84167082` | informational |

The PNG checksum is informational because font rasterization can differ between operating systems even with the same matplotlib version. The deck contains no images and is written with fixed ZIP timestamps, fixed core properties, and uncompressed entries, so its bytes depend only on the findings, the fixture, and the python-pptx version.

A regression test ([`tests/test_regression.py`](../tests/test_regression.py)) fails if these checksums, the manifest, and the generated artifacts drift apart.

## Other commands

| Goal | Make | Plain Python |
| --- | --- | --- |
| Full verification gate | `make check` | `python scripts/check.py` |
| Tests only | `make test` | `python -m unittest discover -s tests -t .` |
| Report and deck into `artifacts/demo` | `make demo` | `python -m cloud_data_finops.cli report --spec tests/fixtures/assessment.json --output artifacts/demo` |
| Deck only | | `python -m cloud_data_finops.cli deck --spec tests/fixtures/assessment.json --output artifacts/deck.pptx` |
| New synthetic specification | | `python -m cloud_data_finops.cli synth --seed 7 --output artifacts/seed-7.json` |
| Regenerate fixture, goldens, and evidence after an intended change | `make evidence` | `python scripts/update_evidence.py` |

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ruff is not installed` from `make check` | Dev dependencies missing | `python -m pip install -r requirements-dev.txt` |
| `FAIL fixture` | `tests/fixtures/assessment.json` was edited by hand or the generator changed | Revert the fixture, or run `make evidence` and review the diff if the change is intended |
| `FAIL findings.json` or `FAIL report.md` | Rule, threshold, or report-layout change without regenerated evidence | Run `make evidence`, review the diff, and commit the fixture, goldens, and evidence together |
| `FAIL synthetic-finops-assessment.pptx` only | A different python-pptx or lxml version | Install the exact pins from `requirements-dev.txt` |
| `note cost-signals.png` | Different font rasterization on another OS | Informational only; inspect the image visually |
| JSON or Markdown checksums differ right after a fresh clone on Windows | Git converted line endings | The repository ships `.gitattributes` with `eol=lf`; run `git add --renormalize .` or re-clone |
| `make: command not found` | GNU Make is not installed | Use the plain Python commands in the table above |
| `python` resolves to an older interpreter | Several Python versions installed | Call the interpreter explicitly, for example `py -3.12` on Windows, or `make check PYTHON="py -3.12"` |

## Teardown

Everything the commands write goes under `artifacts/` (ignored by Git) or a temporary directory.

```bash
make clean
```

Without Make: delete the `artifacts/`, `build/`, `dist/`, and `.ruff_cache/` directories. To remove the environment, delete the virtual environment you installed into, or run `python -m pip uninstall cloud-data-finops-sdd-toolkit`.
