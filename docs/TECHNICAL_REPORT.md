# Synthetic cloud data FinOps assessment

## Summary

This report records a reproducible assessment run over the repository fixture `tests/fixtures/assessment.json`. The input represents no organization, billing account, project, or production workload. It exists to demonstrate a specification-driven path from access review to evidence, findings, and a report.

The run produced two findings from the release fixture. `BQ-001` identifies a 3,000 GB BigQuery job without partition pruning. `AWS-001` identifies an Amazon Athena cost of USD 1,400 against a USD 700 fixture baseline. Neither finding estimates savings or authorizes a cloud change.

## Scope and method

The assessment specification declares both providers, a 30-day retention window, and fixture mode. The CLI validates the contract, runs a least-privilege preflight, generates a provider-specific access plan, routes fixture telemetry through injected adapters, evaluates policies, and writes structured findings.

BigQuery job metadata access uses `roles/bigquery.user` and `roles/bigquery.resourceViewer`, the roles Google documents for `INFORMATION_SCHEMA.JOBS`. Cost Explorer access is limited to `ce:GetCostAndUsage` and `ce:GetDimensionValues`. The repository rejects Owner, Editor, AdministratorAccess, wildcard actions, unrestricted Athena and S3 actions, and a CUR path without an approved prefix.

## Findings

### BQ-001: High-volume job without partition pruning

The fixture contains `job-expensive` with 3,000,000,000,000 billed bytes and `partition_pruned: false`. The policy reports 3,000 GB as a volume signal. The next action is to inspect partition filters and the query plan. The report does not infer a price because no price card, edition, location, or billing export was supplied.

### AWS-001: Athena cost above the fixture baseline

The fixture records Amazon Athena in `us-east-1` at USD 1,400 against a USD 700 baseline. The policy reports the USD 700 difference as an observed comparison. The next action is to inspect workload, tags, and query patterns before evaluating reservations or commitments.

## Verification

`make check` compiles the package, runs the CLI contract tests, adapter tests, workflow test, and policy tests. The release fixture yields deterministic JSON findings, Markdown output, and an evidence image. The test suite currently contains eleven tests.

## Limitations

The collectors use injected fixture clients. They do not authenticate to GCP or AWS, query table content, read a billing export, query CUR, or change infrastructure. The access plan documents a request boundary; it does not grant permissions. A live assessment requires a separate approved specification, provider credentials outside the repository, and adapter tests for the authorized resources.

## Sources

- [BigQuery INFORMATION_SCHEMA.JOBS required roles](https://cloud.google.com/bigquery/docs/information-schema-jobs)
- [Google Cloud Billing access control](https://cloud.google.com/billing/docs/access-control)
- [AWS Cost Explorer authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ce.html)
- [Athena IAM guidance](https://docs.aws.amazon.com/athena/latest/ug/security-iam-athena.html)

