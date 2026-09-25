# Project memory

## Scope

This repository is a public, fixture-first reference for specification-driven data FinOps assessments across GCP and AWS. It must never contain customer data, credentials, private cloud identifiers, or live billing exports.

## Current state

- v0.2.0: 9 policy rules across GCP (BigQuery bytes scanned, repeated expensive queries, missing partition pruning, inefficient scheduling, reservation slot utilization) and AWS (service/region cost anomaly, tag cost anomaly, idle resources, commitment/discount coverage). See [docs/rule-catalog.md](docs/rule-catalog.md) for thresholds and the finding model.
- A seeded synthetic multi-cloud telemetry generator (`cloud_data_finops.synthetic`, default seed `20260901`) replaces the old external Node-based deck generator; the report/deck path now depends only on pinned Python packages (`requirements-dev.txt`).
- `deck` produces a byte-reproducible seven-slide PPTX built with `python-pptx` directly (no external renderer). `scripts/reproduce.py` rebuilds every artifact from the checked-in fixture and compares SHA-256 against `docs/evidence/release-fixture/SHA256SUMS`; the fixture spec produces 11 findings.
- `make check` runs format, ruff lint, compile, secret scan, a documentation link check, 126 unit tests, and the four core CLI commands. CI mirrors this.
- Deleted: `scripts/build_deck.mjs` and the untracked `outputs/` folder — depended on a private, non-reproducible `@oai/artifact-tool` package and were never committed.

## Decisions

- Canonical interfaces: `finops validate|preflight|access-plan|report|deck|synth`.
- Findings separate observed evidence, calculation (inputs/formula/units/assumptions), recommendation, estimated impact, and confidence; several rules deliberately report no monetary estimate without a pricing input.
- Local tests use only synthetic fixtures; live-provider collectors remain out of scope, gated by the same preflight/safety guards tested in `tests/test_access.py` and `tests/test_safety.py`.

## Next verifiable task

A mocked-then-live GCP/AWS adapter path, gated behind an explicit, separately authorized access plan; extend `partition_pruned`/`source_updates_per_day` derivations once a live adapter exists to test them against.
