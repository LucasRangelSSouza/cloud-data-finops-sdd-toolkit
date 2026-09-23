# Project memory

## Scope

This repository is a public, fixture-first reference for specification-driven data FinOps assessments across GCP and AWS. It must never contain customer data, credentials, private cloud identifiers, or live billing exports.

## Current state

- The first vertical slice is implemented and covered by CLI contract tests.
- `validate` checks the fixture-mode assessment contract.
- `preflight` rejects broad GCP and AWS permissions before collection.
- `access-plan` emits the reviewed GCP/AWS read-only request only after validation and preflight pass.
- `report` emits deterministic JSON findings and a Markdown report from synthetic telemetry.
- `report` also emits separate-unit PNG evidence cards. The visual was reviewed locally after replacing an invalid mixed-unit bar chart.
- Fixture reporting now routes GCP job metadata and AWS Cost Explorer metadata through injected adapter clients before policy evaluation.

## Decisions

- Canonical interfaces: `finops validate`, `finops preflight`, and `finops report`.
- Local tests use only the Python standard library and synthetic fixtures.
- GCP and AWS adapters accept injected metadata clients. They do not import SDKs, call a network, request table content, or query CUR in the first release.
- Live-provider collectors remain out of scope until their least-privilege access contracts and adapter tests exist.

## Evidence

- `tests/test_cli.py` covers the four command contracts; `tests/test_adapters.py` proves metadata-only collector behavior; `tests/test_workflow.py` covers the fixture workflow.
- `tests/fixtures/assessment.json` is the only current input fixture.
- `scripts/check.py` runs compilation, tests, validation, preflight, and report generation.
- `docs/SPEC.md` records the first-release contract and acceptance criteria.
- `docs/evidence/release-fixture/synthetic-finops-assessment.pptx` is a structurally validated, visually reviewed four-slide deck generated from the synthetic release fixture.

## Next verifiable task

Add a fixture-backed collection workflow that routes injected GCP/AWS metadata through policy evaluation, without adding provider credentials or business-table extraction.
