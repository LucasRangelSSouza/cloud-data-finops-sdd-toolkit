"""BigQuery rules. Inputs come from job, schedule, and reservation metadata only."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .model import Calculation, EstimatedImpact, Finding, ratio, terabytes

NO_PRICE_MODEL = "Not estimated: the assessment supplies no BigQuery pricing model, edition, or location."
TB_UNIT = "TB (10^12 bytes)"


def excessive_bytes_scanned(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """BQ-001: a single job billed at least the configured byte volume."""
    threshold = thresholds["bytes_billed"]
    findings = []
    for job in telemetry["gcp"].get("jobs", []):
        if job["bytes_billed"] < threshold:
            continue
        findings.append(
            Finding(
                rule_id="BQ-001",
                provider="gcp",
                title="Job billed an excessive number of bytes",
                subject=job["job_id"],
                priority="high",
                evidence_source="gcp.jobs",
                observed_evidence={"job_id": job["job_id"], "bytes_billed": job["bytes_billed"], "fingerprint": job["fingerprint"]},
                calculation=Calculation(
                    inputs={"bytes_billed": job["bytes_billed"], "threshold_bytes": threshold},
                    formula="terabytes_billed = bytes_billed / 10^12; fires when bytes_billed >= threshold_bytes",
                    result={"terabytes_billed": terabytes(job["bytes_billed"])},
                    units={"bytes_billed": "bytes", "terabytes_billed": TB_UNIT},
                    assumptions=("bytes_billed is the billed volume reported by job metadata; it is used as a volume signal, not a price.",),
                ),
                recommendation="Review the query plan, selected columns, and filters for this job before changing the workload.",
                action="Review query plan and filters of the largest job",
                estimated_impact=EstimatedImpact.not_estimated(NO_PRICE_MODEL),
                weight=float(job["bytes_billed"]),
                confidence="high",
            )
        )
    return findings


def repeated_expensive_queries(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """BQ-002: the same query fingerprint ran repeatedly with a large combined volume."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in telemetry["gcp"].get("jobs", []):
        groups[job["fingerprint"]].append(job)
    findings = []
    for fingerprint in sorted(groups):
        jobs = groups[fingerprint]
        total = sum(job["bytes_billed"] for job in jobs)
        if len(jobs) < thresholds["min_runs"] or total < thresholds["total_bytes_billed"]:
            continue
        average = total / len(jobs)
        repeated_tb = terabytes((len(jobs) - 1) * average)
        findings.append(
            Finding(
                rule_id="BQ-002",
                provider="gcp",
                title="Expensive query pattern runs repeatedly",
                subject=fingerprint,
                priority="medium",
                evidence_source="gcp.jobs",
                observed_evidence={"fingerprint": fingerprint, "run_count": len(jobs), "total_bytes_billed": total},
                calculation=Calculation(
                    inputs={
                        "run_count": len(jobs),
                        "total_bytes_billed": total,
                        "min_runs": thresholds["min_runs"],
                        "threshold_total_bytes": thresholds["total_bytes_billed"],
                    },
                    formula="repeated_terabytes = (run_count - 1) * (total_bytes_billed / run_count) / 10^12",
                    result={"average_terabytes_per_run": terabytes(average), "repeated_terabytes": repeated_tb},
                    units={"total_bytes_billed": "bytes", "repeated_terabytes": TB_UNIT},
                    assumptions=(
                        "The fingerprint groups jobs with the same normalized query; query text is not collected.",
                        "The estimate is an upper bound that holds only if one run's result could serve the other runs.",
                    ),
                ),
                recommendation="Check whether results can be materialized, cached, or shared across runs before changing the schedule.",
                action="Evaluate materializing or caching the repeated query",
                estimated_impact=EstimatedImpact(
                    value=repeated_tb,
                    unit=f"{TB_UNIT} in the assessment period (upper bound)",
                    basis="Volume billed by every run after the first; it is not a monetary saving.",
                ),
                weight=float(total),
                confidence="medium",
            )
        )
    return findings


def missing_partition_pruning(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """BQ-003: a job read a partitioned table without pruning partitions."""
    findings = []
    for job in telemetry["gcp"].get("jobs", []):
        if not job["references_partitioned_table"] or job["partition_pruned"]:
            continue
        if job["bytes_billed"] < thresholds["min_bytes_billed"]:
            continue
        findings.append(
            Finding(
                rule_id="BQ-003",
                provider="gcp",
                title="Partitioned table read without partition pruning",
                subject=job["job_id"],
                priority="high",
                evidence_source="gcp.jobs",
                observed_evidence={
                    "job_id": job["job_id"],
                    "references_partitioned_table": True,
                    "partition_pruned": False,
                    "bytes_billed": job["bytes_billed"],
                },
                calculation=Calculation(
                    inputs={"bytes_billed": job["bytes_billed"], "min_bytes_billed": thresholds["min_bytes_billed"]},
                    formula="fires when references_partitioned_table and not partition_pruned and bytes_billed >= min_bytes_billed",
                    result={"terabytes_billed": terabytes(job["bytes_billed"])},
                    units={"bytes_billed": "bytes", "terabytes_billed": TB_UNIT},
                    assumptions=("The reduction from pruning depends on filter selectivity, which job metadata does not reveal.",),
                ),
                recommendation="Add or correct a filter on the partitioning column and confirm pruning in the query plan.",
                action="Add a partition filter and confirm pruning",
                estimated_impact=EstimatedImpact.not_estimated("Not estimated: the share of partitions a filter would skip is unknown."),
                weight=float(job["bytes_billed"]),
                confidence="high",
            )
        )
    return findings


def inefficient_scheduling(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """BQ-004: a scheduled query runs more often than its source data changes."""
    findings = []
    for schedule in telemetry["gcp"].get("schedules", []):
        runs = schedule["runs_per_day"]
        updates = schedule["source_updates_per_day"]
        excess = round(runs - updates, 4)
        if excess < thresholds["min_excess_runs_per_day"] or runs < thresholds["min_run_to_update_ratio"] * updates:
            continue
        excess_tb = terabytes(excess * schedule["avg_bytes_billed"] * 30)
        findings.append(
            Finding(
                rule_id="BQ-004",
                provider="gcp",
                title="Scheduled query runs more often than its source changes",
                subject=schedule["fingerprint"],
                priority="medium",
                evidence_source="gcp.schedules",
                observed_evidence={
                    "fingerprint": schedule["fingerprint"],
                    "runs_per_day": runs,
                    "source_updates_per_day": updates,
                    "avg_bytes_billed": schedule["avg_bytes_billed"],
                },
                calculation=Calculation(
                    inputs={
                        "runs_per_day": runs,
                        "source_updates_per_day": updates,
                        "avg_bytes_billed": schedule["avg_bytes_billed"],
                        "days": 30,
                    },
                    formula="excess_terabytes_30d = (runs_per_day - source_updates_per_day) * avg_bytes_billed * 30 / 10^12",
                    result={"excess_runs_per_day": excess, "excess_terabytes_30d": excess_tb},
                    units={"runs_per_day": "runs/day", "avg_bytes_billed": "bytes", "excess_terabytes_30d": TB_UNIT},
                    assumptions=(
                        "Runs and source updates are counted from job metadata over the assessment window.",
                        "A run that starts before the source changes again returns the same result as the previous run.",
                    ),
                ),
                recommendation="Align the schedule with source refreshes or trigger it on source updates, after confirming freshness requirements.",
                action="Align schedule frequency with source refreshes",
                estimated_impact=EstimatedImpact(
                    value=excess_tb,
                    unit=f"{TB_UNIT} per 30 days (upper bound)",
                    basis="Volume billed by runs that start between source updates; it is not a monetary saving.",
                ),
                weight=excess_tb,
                confidence="medium",
            )
        )
    return findings


def reservation_utilization(telemetry: dict[str, Any], thresholds: dict[str, float], _: dict[str, Any]) -> list[Finding]:
    """BQ-005: a reservation's baseline slots were mostly idle over a sufficient window."""
    findings = []
    for reservation in telemetry["gcp"].get("reservations", []):
        baseline = reservation["baseline_slots"]
        if baseline == 0 or reservation["hours_observed"] < thresholds["min_hours_observed"]:
            continue
        utilization = ratio(reservation["avg_slots_used"], baseline)
        if utilization > thresholds["max_avg_utilization"]:
            continue
        idle_slot_hours = round((baseline - reservation["avg_slots_used"]) * reservation["hours_observed"], 1)
        findings.append(
            Finding(
                rule_id="BQ-005",
                provider="gcp",
                title="Reservation baseline slots are mostly idle",
                subject=reservation["reservation_id"],
                priority="medium",
                evidence_source="gcp.reservations",
                observed_evidence={
                    "reservation_id": reservation["reservation_id"],
                    "baseline_slots": baseline,
                    "avg_slots_used": reservation["avg_slots_used"],
                    "peak_slots_used": reservation["peak_slots_used"],
                    "hours_observed": reservation["hours_observed"],
                },
                calculation=Calculation(
                    inputs={
                        "baseline_slots": baseline,
                        "avg_slots_used": reservation["avg_slots_used"],
                        "hours_observed": reservation["hours_observed"],
                        "max_avg_utilization": thresholds["max_avg_utilization"],
                    },
                    formula="utilization = avg_slots_used / baseline_slots; idle_slot_hours = (baseline_slots - avg_slots_used) * hours_observed",
                    result={"utilization": utilization, "idle_slot_hours": idle_slot_hours},
                    units={"baseline_slots": "slots", "utilization": "ratio", "idle_slot_hours": "slot-hours"},
                    assumptions=(
                        "Average slot usage comes from reservation timeline metadata for the observed hours.",
                        "Peak usage is shown because a lower baseline can delay queries during peaks.",
                    ),
                ),
                recommendation=(
                    "Review baseline and autoscaling settings with the workload owner against peak usage; this is an observation, not a capacity change."
                ),
                action="Review reservation baseline against peak usage",
                estimated_impact=EstimatedImpact(
                    value=idle_slot_hours,
                    unit="slot-hours of idle baseline capacity in the observed window",
                    basis="Observed capacity minus observed average use; no price is applied.",
                ),
                weight=idle_slot_hours,
                confidence="medium",
            )
        )
    return findings
