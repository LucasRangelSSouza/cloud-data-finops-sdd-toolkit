# From access boundary to FinOps findings

Cost analysis often starts with a broad request for access. That is difficult to review and impossible to demonstrate safely in a public repository. This case starts with a smaller question: which metadata is sufficient to identify a cost signal without touching business data?

The answer is encoded in an assessment specification. It declares the providers, retention window, access boundary, evidence needed by a rule, and the expected outputs. The command line validates that contract before it evaluates any telemetry. A second command writes the exact GCP and AWS access request, so a reviewer can see the requested roles, actions, and prohibited paths before a collector runs.

The example uses synthetic telemetry. One BigQuery job bills 3,000 GB without partition pruning. An Athena record is USD 700 above its declared fixture baseline. Those values are signals for investigation. They do not prove a saving, because the fixture has no pricing model, production usage history, or operational constraints.

That distinction changes the report. Each finding keeps evidence, assumptions, recommendation, and confidence separate. The code can say that a job lacks partition pruning. It cannot say how much money a team will save by changing the query. The same rule applies to a cost increase: the next step is to inspect workload and tags, not to buy a commitment from a chart.

The repository also treats access as part of the test surface. It rejects GCP Owner and Editor roles, AWS AdministratorAccess, wildcard actions, unscoped Athena or S3 paths, and CUR collection without an approved prefix. Fixture adapters prove that the collection seam calls only job metadata and Cost Explorer metadata. No test depends on a cloud account.

This is a small reference implementation, but the delivery path is the point. A versioned specification leads to a reviewed access plan, an explicit evidence model, repeatable findings, a report, and a deck. When a live integration becomes necessary, it can inherit those boundaries instead of rediscovering them in production.

## Reproduce the case

```powershell
python -m pip install -e .
make check
python -m cloud_data_finops.cli report --spec tests/fixtures/assessment.json --output artifacts/demo
```

The full technical report and source links are available in `docs/TECHNICAL_REPORT.md`. The example remains synthetic by design.
