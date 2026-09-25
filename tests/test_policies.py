"""Unit tests for every rule in the catalog: positive, negative, and boundary cases."""

import unittest

from cloud_data_finops.policies import RULES, evaluate
from tests.helpers import GB, empty_telemetry, job, with_rows

TB = 1000 * GB


def rule_ids(telemetry: dict) -> list[str]:
    return [finding["rule_id"] for finding in evaluate(telemetry)]


def only(telemetry: dict, rule_id: str) -> list[dict]:
    return [finding for finding in evaluate(telemetry) if finding["rule_id"] == rule_id]


class ExcessiveBytesScannedTests(unittest.TestCase):
    def test_positive_large_job(self) -> None:
        findings = only(with_rows("gcp", "jobs", [job("big", 3 * TB)]), "BQ-001")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["calculation"]["result"]["terabytes_billed"], 3.0)

    def test_negative_small_job(self) -> None:
        self.assertEqual(only(with_rows("gcp", "jobs", [job("small", 10 * GB)]), "BQ-001"), [])

    def test_boundary_threshold_is_inclusive(self) -> None:
        self.assertEqual(len(only(with_rows("gcp", "jobs", [job("edge", TB)]), "BQ-001")), 1)
        self.assertEqual(only(with_rows("gcp", "jobs", [job("below", TB - 1)]), "BQ-001"), [])


class RepeatedExpensiveQueryTests(unittest.TestCase):
    def runs(self, count: int, each: int) -> dict:
        return with_rows("gcp", "jobs", [job(f"run-{index}", each, fingerprint="same") for index in range(count)])

    def test_positive_repeated_pattern(self) -> None:
        findings = only(self.runs(3, 400 * GB), "BQ-002")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["estimated_impact"]["value"], 0.8)

    def test_negative_distinct_fingerprints(self) -> None:
        telemetry = with_rows("gcp", "jobs", [job(f"run-{index}", 400 * GB) for index in range(3)])
        self.assertEqual(only(telemetry, "BQ-002"), [])

    def test_boundary_run_count_and_volume(self) -> None:
        self.assertEqual(only(self.runs(2, 600 * GB), "BQ-002"), [])
        self.assertEqual(len(only(self.runs(4, 250 * GB), "BQ-002")), 1)
        self.assertEqual(only(self.runs(4, 250 * GB - 1), "BQ-002"), [])


class MissingPartitionPruningTests(unittest.TestCase):
    def test_positive_unpruned_partitioned_read(self) -> None:
        telemetry = with_rows("gcp", "jobs", [job("scan", 250 * GB, partitioned=True, pruned=False)])
        self.assertEqual(rule_ids(telemetry), ["BQ-003"])

    def test_negative_pruned_or_unpartitioned(self) -> None:
        telemetry = with_rows(
            "gcp",
            "jobs",
            [
                job("pruned", 250 * GB, partitioned=True, pruned=True),
                job("flat", 250 * GB, partitioned=False),
            ],
        )
        self.assertEqual(only(telemetry, "BQ-003"), [])

    def test_boundary_minimum_volume(self) -> None:
        self.assertEqual(len(only(with_rows("gcp", "jobs", [job("edge", 100 * GB, partitioned=True)]), "BQ-003")), 1)
        self.assertEqual(only(with_rows("gcp", "jobs", [job("below", 100 * GB - 1, partitioned=True)]), "BQ-003"), [])

    def test_related_rules_link_findings_on_the_same_job(self) -> None:
        findings = evaluate(with_rows("gcp", "jobs", [job("huge", 2 * TB, partitioned=True)]))
        by_rule = {finding["rule_id"]: finding for finding in findings}
        self.assertEqual(by_rule["BQ-001"]["related_rules"], ["BQ-003"])
        self.assertEqual(by_rule["BQ-003"]["related_rules"], ["BQ-001"])


class InefficientSchedulingTests(unittest.TestCase):
    def schedule(self, runs: float, updates: float) -> dict:
        row = {"fingerprint": "fp-s", "runs_per_day": runs, "source_updates_per_day": updates, "avg_bytes_billed": 50 * GB}
        return with_rows("gcp", "schedules", [row])

    def test_positive_runs_exceed_source_updates(self) -> None:
        findings = only(self.schedule(6, 1), "BQ-004")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["calculation"]["result"]["excess_runs_per_day"], 5)
        self.assertEqual(findings[0]["estimated_impact"]["value"], 7.5)

    def test_negative_aligned_schedule(self) -> None:
        self.assertEqual(only(self.schedule(4, 4), "BQ-004"), [])

    def test_boundary_ratio_and_excess(self) -> None:
        self.assertEqual(len(only(self.schedule(2, 1), "BQ-004")), 1)
        self.assertEqual(only(self.schedule(1.9, 1), "BQ-004"), [])
        self.assertEqual(only(self.schedule(0.5, 0), "BQ-004"), [])
        self.assertEqual(len(only(self.schedule(1, 0), "BQ-004")), 1)


class ReservationUtilizationTests(unittest.TestCase):
    def reservation(self, avg: float, hours: int = 720, baseline: int = 500) -> dict:
        row = {"reservation_id": "res", "baseline_slots": baseline, "avg_slots_used": avg, "peak_slots_used": max(avg, 400.0), "hours_observed": hours}
        return with_rows("gcp", "reservations", [row])

    def test_positive_idle_baseline(self) -> None:
        findings = only(self.reservation(90.0), "BQ-005")
        self.assertEqual(findings[0]["calculation"]["result"]["utilization"], 0.18)
        self.assertEqual(findings[0]["estimated_impact"]["value"], 295200.0)

    def test_negative_busy_reservation_or_no_baseline(self) -> None:
        self.assertEqual(only(self.reservation(300.0), "BQ-005"), [])
        self.assertEqual(only(self.reservation(0.0, baseline=0), "BQ-005"), [])

    def test_boundary_utilization_and_window(self) -> None:
        self.assertEqual(len(only(self.reservation(150.0), "BQ-005")), 1)
        self.assertEqual(only(self.reservation(150.5), "BQ-005"), [])
        self.assertEqual(only(self.reservation(90.0, hours=167), "BQ-005"), [])
        self.assertEqual(len(only(self.reservation(90.0, hours=168), "BQ-005")), 1)


class ServiceRegionAnomalyTests(unittest.TestCase):
    def cost(self, cost: float, baseline: float) -> dict:
        return with_rows("aws", "costs", [{"service": "Amazon Athena", "region": "us-east-1", "cost_usd": cost, "baseline_usd": baseline}])

    def test_positive_doubled_cost(self) -> None:
        findings = only(self.cost(1400.0, 700.0), "AWS-001")
        self.assertEqual(findings[0]["calculation"]["result"]["increase_usd"], 700.0)
        self.assertIsNone(findings[0]["estimated_impact"]["value"])

    def test_negative_stable_or_new_spend(self) -> None:
        self.assertEqual(only(self.cost(120.0, 125.0), "AWS-001"), [])
        self.assertEqual(only(self.cost(900.0, 0.0), "AWS-001"), [])

    def test_boundary_ratio_and_minimum_increase(self) -> None:
        self.assertEqual(len(only(self.cost(300.0, 200.0), "AWS-001")), 1)
        self.assertEqual(only(self.cost(299.99, 200.0), "AWS-001"), [])
        self.assertEqual(only(self.cost(150.0, 100.0), "AWS-001"), [])


class TagAnomalyTests(unittest.TestCase):
    def tag(self, value: str | None, cost: float, baseline: float) -> dict:
        return with_rows("aws", "tag_costs", [{"tag_key": "team", "tag_value": value, "cost_usd": cost, "baseline_usd": baseline}])

    def test_positive_untagged_spend(self) -> None:
        findings = only(self.tag(None, 650.0, 300.0), "AWS-002")
        self.assertEqual(findings[0]["subject"], "team=(untagged)")
        self.assertIn("owner", findings[0]["recommendation"])

    def test_negative_stable_tag(self) -> None:
        self.assertEqual(only(self.tag("analytics", 900.0, 850.0), "AWS-002"), [])

    def test_boundary_ratio(self) -> None:
        self.assertEqual(len(only(self.tag("ml", 450.0, 300.0), "AWS-002")), 1)
        self.assertEqual(only(self.tag("ml", 449.0, 300.0), "AWS-002"), [])


class IdleResourceTests(unittest.TestCase):
    def resource(self, utilization: float, days: int) -> dict:
        row = {"resource_id": "cluster", "type": "redshift-cluster", "utilization": utilization, "observed_days": days, "monthly_cost_usd": 2200.0}
        return with_rows("aws", "resources", [row])

    def test_positive_idle_cluster(self) -> None:
        findings = only(self.resource(0.04, 30), "AWS-003")
        self.assertEqual(findings[0]["estimated_impact"]["value"], 2112.0)
        self.assertEqual(findings[0]["confidence"], "low")

    def test_negative_busy_or_insufficient_telemetry(self) -> None:
        self.assertEqual(only(self.resource(0.45, 30), "AWS-003"), [])
        self.assertEqual(only(self.resource(0.02, 7), "AWS-003"), [])

    def test_boundary_utilization_and_window(self) -> None:
        self.assertEqual(len(only(self.resource(0.10, 14), "AWS-003")), 1)
        self.assertEqual(only(self.resource(0.1001, 14), "AWS-003"), [])
        self.assertEqual(only(self.resource(0.10, 13), "AWS-003"), [])


class CommitmentCoverageTests(unittest.TestCase):
    def commitment(self, history: list[float], coverage: float = 0.0, assumptions: dict | None = None) -> dict:
        telemetry = with_rows("aws", "commitments", [{"service": "AWS Glue", "monthly_on_demand_usd": history, "coverage_ratio": coverage}])
        telemetry["assumptions"] = assumptions or {}
        return telemetry

    def test_positive_steady_usage_without_purchase_when_evidence_is_incomplete(self) -> None:
        finding = only(self.commitment([410.0, 395.0, 420.0, 405.0, 415.0, 400.0]), "CMT-001")[0]
        self.assertTrue(finding["recommendation"].startswith("No purchase recommendation"))
        self.assertIsNone(finding["estimated_impact"]["value"])
        self.assertEqual(len(finding["calculation"]["result"]["missing_evidence"]), 3)

    def test_positive_complete_evidence_allows_a_documented_estimate(self) -> None:
        assumptions = {"commitments": {"AWS Glue": {"discount_rate": 0.2, "usage_forecast_confirmed": True}}}
        finding = only(self.commitment([400.0] * 12, assumptions=assumptions), "CMT-001")[0]
        self.assertEqual(finding["estimated_impact"], {"value": 80.0, "unit": "USD per month", "basis": finding["estimated_impact"]["basis"]})
        self.assertIn("lowest observed", finding["estimated_impact"]["basis"])
        self.assertFalse(finding["recommendation"].startswith("No purchase"))

    def test_negative_volatile_or_covered_usage(self) -> None:
        self.assertEqual(only(self.commitment([300.0, 700.0, 1400.0]), "CMT-001"), [])
        self.assertEqual(only(self.commitment([400.0] * 6, coverage=0.8), "CMT-001"), [])

    def test_boundary_history_and_coverage(self) -> None:
        self.assertEqual(only(self.commitment([400.0, 400.0]), "CMT-001"), [])
        self.assertEqual(len(only(self.commitment([400.0] * 3), "CMT-001")), 1)
        self.assertEqual(len(only(self.commitment([400.0] * 3, coverage=0.5), "CMT-001")), 1)
        self.assertEqual(only(self.commitment([400.0] * 3, coverage=0.51), "CMT-001"), [])
        partial = {"commitments": {"AWS Glue": {"discount_rate": 0.2, "usage_forecast_confirmed": True}}}
        eleven = only(self.commitment([400.0] * 11, assumptions=partial), "CMT-001")[0]
        self.assertIsNone(eleven["estimated_impact"]["value"])


class FindingModelTests(unittest.TestCase):
    REQUIRED = {
        "rule_id",
        "provider",
        "title",
        "subject",
        "priority",
        "evidence_source",
        "observed_evidence",
        "calculation",
        "recommendation",
        "action",
        "estimated_impact",
        "confidence",
        "related_rules",
    }

    def test_every_rule_emits_the_separated_finding_model(self) -> None:
        from cloud_data_finops.workflow import collect_fixture_telemetry
        from tests.helpers import load_fixture

        findings = evaluate(collect_fixture_telemetry(load_fixture()))
        self.assertEqual({finding["rule_id"] for finding in findings}, set(RULES))
        for finding in findings:
            self.assertEqual(set(finding), self.REQUIRED)
            self.assertEqual(set(finding["calculation"]), {"inputs", "formula", "result", "units", "assumptions"})
            self.assertTrue(finding["calculation"]["assumptions"])
            impact = finding["estimated_impact"]
            self.assertTrue(impact["basis"])
            self.assertEqual(impact["value"] is None, impact["unit"] is None)
            self.assertNotIn("saving", (impact["unit"] or "").lower())

    def test_rule_selection_and_threshold_override(self) -> None:
        telemetry = with_rows("gcp", "jobs", [job("big", 3 * TB, partitioned=True)])
        telemetry["rules"] = {"enabled": ["BQ-003"]}
        self.assertEqual(rule_ids(telemetry), ["BQ-003"])
        telemetry["rules"] = {"thresholds": {"BQ-001": {"bytes_billed": 4 * TB}}}
        self.assertNotIn("BQ-001", rule_ids(telemetry))

    def test_findings_are_sorted_by_priority_then_rule_then_magnitude(self) -> None:
        telemetry = empty_telemetry()
        telemetry["aws"]["costs"] = [
            {"service": "AWS Glue", "region": "us-east-1", "cost_usd": 480.0, "baseline_usd": 300.0},
            {"service": "Amazon Athena", "region": "us-east-1", "cost_usd": 1400.0, "baseline_usd": 700.0},
        ]
        telemetry["aws"]["resources"] = [{"resource_id": "r", "type": "t", "utilization": 0.0, "observed_days": 30, "monthly_cost_usd": 10.0}]
        subjects = [finding["subject"] for finding in evaluate(telemetry)]
        self.assertEqual(subjects, ["Amazon Athena / us-east-1", "AWS Glue / us-east-1", "r"])


if __name__ == "__main__":
    unittest.main()
