# Cloud data FinOps assessment

Assessment: `demo-2026-09`

## Findings

![Synthetic data-platform cost signals](cost-signals.png)

### BQ-001 — High-volume BigQuery job without partition pruning

Provider: `gcp`

Evidence:

- `job_id`: job-expensive
- `bytes_billed`: 3000000000000
- `bytes_billed_gb`: 3,000 GB
- `partition_pruned`: False

Assumption: Bytes billed are used as a volume signal; pricing is not inferred from this fixture.

Recommendation: Review partition filters and validate the query plan before changing the workload.

Confidence: high

### AWS-001 — AWS service cost exceeds the declared baseline

Provider: `aws`

Evidence:

- `service`: Amazon Athena
- `region`: us-east-1
- `cost_usd`: 1400.0
- `baseline_usd`: 700.0
- `increase_usd`: 700.0

Assumption: The fixture baseline is a comparison point, not a forecast or a savings commitment.

Recommendation: Inspect workload, tags, and query patterns before changing reservations or commitments.

Confidence: medium

## Evidence and assumptions

This report was generated from synthetic fixture data. It does not represent a customer environment, a real saving, or a purchase recommendation.
