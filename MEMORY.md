# Project memory

## Scope

This repository is a public, fixture-first reference for specification-driven data FinOps assessments across GCP and AWS. It must never contain customer data, credentials, private cloud identifiers, or live billing exports.

## Current state

- The first vertical slice is implemented and covered by CLI contract tests.
- `validate` checks the fixture-mode assessment contract.
- `preflight` rejects broad GCP and AWS permissions before collection.
- `report` emits deterministic JSON findings and a Markdown report from synthetic telemetry.
- `report` also emits separate-unit PNG evidence cards. The visual was reviewed locally after replacing an invalid mixed-unit bar chart.

## Decisions

- Canonical interfaces: `finops validate`, `finops preflight`, and `finops report`.
- Local tests use only the Python standard library and synthetic fixtures.
- Live-provider collectors remain out of scope until their least-privilege access contracts and adapter tests exist.

## Evidence

- `tests/test_cli.py` covers the first three command contracts.
- `tests/fixtures/assessment.json` is the only current input fixture.
- `scripts/check.py` runs compilation, tests, validation, preflight, and report generation.
- `docs/SPEC.md` records the first-release contract and acceptance criteria.

## Next verifiable task

Add provider access-plan artifacts and fixture-backed adapters without adding provider credentials or business-table extraction.
