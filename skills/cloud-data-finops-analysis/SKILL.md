# Cloud data FinOps analysis

Use this skill to assess GCP or AWS data-platform cost signals from an approved assessment specification.

## Required inputs

Before any collection, confirm that the specification declares providers, retention, fixture or live mode, approved resources, accepted evidence, rules, and acceptance criteria. Stop when any of those fields is absent.

## Access boundary

Generate and review the access plan first. Request only job, cost, usage, and resource metadata. Do not read business-table values, modify infrastructure, create commitments, or use credentials stored in a repository. Reject broad GCP roles, broad AWS actions, unapproved billing datasets, unapproved CUR prefixes, and unrestricted Athena paths.

## Analysis procedure

1. Validate the specification and run preflight.
2. Collect only the declared telemetry.
3. Evaluate each rule against the collected evidence.
4. Record evidence, calculation inputs, assumptions, recommendation, confidence, and limitations separately.
5. Generate findings and reports only after all contract checks pass.

## Reporting rule

Treat a signal as an investigation trigger. Do not call it a saving, forecast, or purchase recommendation unless the input, pricing method, units, and assumptions prove that claim.

