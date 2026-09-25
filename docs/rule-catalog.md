# Rule catalog

The policy engine runs nine rules. Each rule reads one telemetry dataset, compares it with documented thresholds, and emits findings in the model described below. The code lives in [`cloud_data_finops/policies/`](../cloud_data_finops/policies/), and every rule has positive, negative, and boundary tests in [`tests/test_policies.py`](../tests/test_policies.py).

Thresholds are defaults. A specification can disable rules with `rules.enabled` or override a threshold with `rules.thresholds.<rule_id>.<name>`; validation rejects unknown rule identifiers and threshold names.

## Finding model

| Field | Content |
| --- | --- |
| `observed_evidence` | Values copied from the validated telemetry row, without transformation. |
| `calculation` | `inputs`, `formula`, `result`, `units`, and `assumptions` for every derived number, including the threshold that fired. |
| `recommendation` / `action` | The next investigation step, in full and in a short form for the deck. |
| `estimated_impact` | `value`, `unit`, and `basis`. When the inputs do not support an estimate, `value` and `unit` are `null` and `basis` says why. No rule converts volume into money without a pricing input. |
| `confidence` | `high` when the metadata states the condition directly, `medium` when the finding depends on an assumption, `low` when the telemetry is indirect. |
| `priority`, `related_rules` | Ordering for the report and deck, and other rules that fired on the same subject. |

Findings are sorted by priority, then rule identifier, then magnitude (largest first), then subject.

## Rules

| Rule | Name | Dataset | Fires when | Default thresholds | Estimated impact |
| --- | --- | --- | --- | --- | --- |
| BQ-001 | Excessive bytes scanned | `gcp.jobs` | `bytes_billed >= bytes_billed` | 10^12 bytes | Not estimated (no pricing model) |
| BQ-002 | Repeated expensive queries | `gcp.jobs` | same `fingerprint` runs `>= min_runs` times and the total is `>= total_bytes_billed` | 3 runs; 10^12 bytes | `(runs - 1) * average bytes / 10^12` TB, upper bound |
| BQ-003 | Missing partition pruning | `gcp.jobs` | job reads a partitioned table, `partition_pruned` is false, and `bytes_billed >= min_bytes_billed` | 10^11 bytes | Not estimated (filter selectivity unknown) |
| BQ-004 | Inefficient scheduling pattern | `gcp.schedules` | `runs_per_day >= min_run_to_update_ratio * source_updates_per_day` and the excess is `>= min_excess_runs_per_day` | ratio 2.0; 1 run/day | `excess runs/day * avg bytes * 30 / 10^12` TB per 30 days, upper bound |
| BQ-005 | Reservation slot utilization observation | `gcp.reservations` | `avg_slots_used / baseline_slots <= max_avg_utilization` over at least `min_hours_observed` | 0.30; 168 hours | idle slot-hours in the observed window; no price applied |
| AWS-001 | Service and region cost anomaly | `aws.costs` | `cost >= min_ratio_to_baseline * baseline` and `cost - baseline >= min_increase_usd`; a zero baseline is skipped | 1.5; USD 100 | Not estimated (avoidable share unknown) |
| AWS-002 | Tag cost anomaly | `aws.tag_costs` | same test as AWS-001 per tag value; a null tag value is reported as `(untagged)` | 1.5; USD 100 | Not estimated |
| AWS-003 | Idle or underutilized data-platform resource | `aws.resources` | `utilization <= max_utilization` over at least `min_observed_days` | 0.10; 14 days | `monthly_cost * (1 - utilization)` USD per month, upper bound under a linear-cost assumption |
| CMT-001 | Commitment and discount coverage observation | `aws.commitments` | at least `min_months` of history, `coverage_ratio <= max_coverage_ratio`, and coefficient of variation `<= max_coefficient_of_variation` | 3 months; 0.5; 0.15 | Only with complete evidence (see below) |

All boundaries are inclusive: a value equal to its threshold fires the rule.

## Commitment rule and purchase recommendations

CMT-001 reports steady on-demand usage with low commitment coverage. It recommends evaluating a purchase only when all of these are present:

1. at least `complete_evidence_months` (default 12) months of history;
2. an approved `discount_rate` between 0 and 1 in `assumptions.commitments.<service>`;
3. `usage_forecast_confirmed: true` from the workload owner in the same block.

Without them, the recommendation starts with "No purchase recommendation", `estimated_impact.value` is `null`, and `calculation.result.missing_evidence` lists what is missing. With complete evidence, the estimate is `lowest monthly on-demand cost * discount_rate` USD per month.

## Telemetry that a rule needs

| Dataset | Source (live blueprint) | Access | Collected in fixture mode |
| --- | --- | --- | --- |
| `gcp.jobs` | `INFORMATION_SCHEMA.JOBS_BY_PROJECT` | `roles/bigquery.user`, `roles/bigquery.resourceViewer` | yes |
| `gcp.schedules` | aggregate of scheduled runs in the same JOBS view | same | yes |
| `gcp.reservations` | `INFORMATION_SCHEMA.RESERVATIONS_TIMELINE` | same | yes |
| `aws.costs`, `aws.tag_costs` | Cost Explorer `GetCostAndUsage` grouped by service/region or by the declared tag | `ce:GetCostAndUsage`, `ce:GetDimensionValues` | yes |
| `aws.resources` | CloudWatch `GetMetricData` | `cloudwatch:GetMetricData`, only with `resource_utilization` in `aws.optional_telemetry` | yes (approved in the fixture) |
| `aws.commitments` | Cost Explorer coverage APIs | `ce:GetSavingsPlansCoverage`, `ce:GetReservationCoverage`, only with `commitment_coverage` approved | yes (approved in the fixture) |

The live query templates pass the safety guards in [`tests/test_safety.py`](../tests/test_safety.py). They have not been run against a provider. Some normalized fields, such as `partition_pruned` and `source_updates_per_day`, need a derivation step that a live adapter would have to implement and test first.
