# From access boundary to FinOps findings

**Versioned reference:** [v0.2.0](https://github.com/LucasRangelSSouza/cloud-data-finops-sdd-toolkit/tree/v0.2.0)

Cost analysis often starts with a broad request for access. That is difficult to review and impossible to demonstrate safely in a public repository. This case starts with a smaller question: which metadata is sufficient to identify a cost signal without touching business data?

The answer is encoded in an assessment specification. It declares the providers, retention window, access boundary, evidence needed by a rule, and the expected outputs. The command line validates that contract before it evaluates any telemetry. A second command writes the exact GCP and AWS access request, so a reviewer can see the requested roles, actions, and prohibited paths before a collector runs.

The example uses a seeded synthetic multi-cloud telemetry generator, not a real cloud bill. On the checked-in fixture, nine rules produce eleven findings: an oversized BigQuery scan, a query pattern repeated without partition pruning, an inefficient schedule, low reservation utilization, two AWS service/region cost anomalies, a tag-level anomaly, an idle resource, and a commitment-coverage observation. Those values are signals for investigation. They do not prove a saving, because most rules deliberately carry no pricing model.

That distinction changes the report. Each finding keeps observed evidence, the calculation (inputs, formula, units, assumptions), a recommendation, an estimated impact, and a confidence level separate. The code can say that a job lacks partition pruning. It cannot say how much money a team will save by changing the query. The commitment rule goes further: it withholds any dollar estimate until it has complete evidence — at least twelve months of history, an approved discount rate, and a confirmed usage forecast. Short of that, the finding says plainly what evidence is missing.

The repository also treats access as part of the test surface. It rejects GCP Owner and Editor roles, AWS AdministratorAccess, wildcard actions, unscoped Athena or S3 paths, and CUR collection without an approved prefix. Fixture adapters prove that the collection seam calls only job metadata and Cost Explorer metadata. No test depends on a cloud account.

This is a small reference implementation, but the delivery path is the point. A versioned specification leads to a reviewed access plan, an explicit evidence model, repeatable findings, a report, and a seven-slide deck built directly with `python-pptx`, with no external renderer and no dependency outside the pinned Python packages. A release script rebuilds every artifact from the fixture and checks it against a versioned SHA-256 manifest, so a change to a rule or a report layout cannot drift from its recorded evidence unnoticed. When a live integration becomes necessary, it can inherit those boundaries instead of rediscovering them in production.

## Reproduce the case

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python scripts/reproduce.py
```

The full technical report, rule catalog, and source links are in [`docs/TECHNICAL_REPORT.md`](../docs/TECHNICAL_REPORT.md) and [`docs/rule-catalog.md`](../docs/rule-catalog.md). The example remains synthetic by design.
