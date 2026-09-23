# First-release specification

## Objective

Produce a reproducible, read-only assessment from a versioned GCP/AWS specification. The first release proves the workflow with synthetic telemetry so that anyone can run it without cloud credentials.

## Canonical terms

An *assessment specification* is the JSON contract that declares the providers, retention window, fixture mode, access scope, and telemetry. A *preflight* is a local policy check that runs before any collection. A *finding* contains observed fixture evidence, an explicit assumption, a recommendation, and a confidence level.

## Public commands

| Command | Input | Output | Failure boundary |
| --- | --- | --- | --- |
| `finops validate` | Assessment specification | Contract status | Missing fields, unsupported provider scope, or non-fixture mode |
| `finops preflight` | Assessment specification | Access status | Broad roles, broad actions, incomplete Cost Explorer access, or an unscoped CUR |
| `finops report` | Assessment specification | JSON findings, Markdown report, and PNG evidence cards | Any validation or preflight failure |

## Acceptance criteria

1. A valid synthetic GCP/AWS specification passes validation and preflight.
2. `roles/owner`, `roles/editor`, `AdministratorAccess`, wildcard actions, unrestricted Athena, and unrestricted S3 access fail before report generation.
3. An enabled CUR requires an approved S3 prefix.
4. A fixture containing an oversized, unpartitioned BigQuery job produces `BQ-001`.
5. A fixture containing an AWS service cost at least 50% above its declared baseline produces `AWS-001`.
6. Report generation writes `findings.json`, `report.md`, and `cost-signals.png` deterministically.
7. `make check` compiles the package, runs all tests, and exercises the three CLI commands.

## Non-goals

The first release does not connect to a cloud account, inspect business-table values, calculate savings from a price list, recommend a purchase, change cloud resources, or store provider credentials. Those capabilities require separate approved specifications and test evidence.

