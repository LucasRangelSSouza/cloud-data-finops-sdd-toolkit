"""Deterministic report outputs: JSON findings, a Markdown report, and PNG evidence cards."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from .policies.catalog import RULES  # noqa: E402

PALETTE = {"navy": "#0F172A", "blue": "#2563EB", "cyan": "#22D3EE", "green": "#10B981", "neutral": "#E2E8F0", "slate": "#475569"}
SOURCES = [
    ("BigQuery INFORMATION_SCHEMA.JOBS required roles", "https://cloud.google.com/bigquery/docs/information-schema-jobs"),
    ("Google Cloud Billing access control", "https://cloud.google.com/billing/docs/access-control"),
    ("AWS Cost Explorer authorization reference", "https://docs.aws.amazon.com/service-authorization/latest/reference/list_ce.html"),
    ("Athena IAM guidance", "https://docs.aws.amazon.com/athena/latest/ug/security-iam-athena.html"),
]
CHART_MARKDOWN = (
    "![Synthetic cost signals: largest BigQuery job volume, largest AWS cost increase, and idle slot-hours, each in its own unit](cost-signals.png)"
)
LIMITATIONS = [
    "All telemetry is synthetic and generated from a fixed seed; no finding describes a real organization, project, account, or bill.",
    "No pricing model is applied. Byte volumes, slot-hours, and USD differences are evidence or upper-bound estimates, not savings.",
    "Thresholds are catalog defaults documented in docs/rule-catalog.md; a real assessment must review them against its own workload.",
    "Commitment observations never become purchase recommendations unless history, an approved discount rate, and a confirmed forecast are all supplied.",
    "Collectors use injected fixture clients. Live query templates pass the safety guards in tests but have not been run against a provider.",
]


def signal_cards(findings: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Pick one headline signal per unit so different units are never plotted on one axis."""
    cards = []

    def largest(rule_id: str, key: str) -> float | None:
        values = [finding["calculation"]["result"][key] for finding in findings if finding["rule_id"] == rule_id]
        return max(values) if values else None

    tb = largest("BQ-001", "terabytes_billed")
    if tb is not None:
        cards.append((f"{tb:,.1f} TB", "Largest BigQuery job (bytes billed)", PALETTE["blue"]))
    usd = largest("AWS-001", "increase_usd")
    if usd is not None:
        cards.append((f"USD {usd:,.0f}", "Largest AWS increase vs baseline", PALETTE["cyan"]))
    slot_hours = largest("BQ-005", "idle_slot_hours")
    if slot_hours is not None:
        cards.append((f"{slot_hours:,.0f}", "Idle baseline slot-hours", PALETTE["green"]))
    return cards


def write_cost_signal_chart(output_directory: Path, findings: list[dict[str, Any]]) -> None:
    cards = signal_cards(findings)
    if not cards:
        return
    figure, axes = plt.subplots(1, len(cards), figsize=(10, 4.2))
    figure.subplots_adjust(left=0.02, right=0.98, top=0.86, bottom=0.08, wspace=0.06)
    axes = [axes] if len(cards) == 1 else list(axes)
    figure.set_facecolor("#F8FAFC")
    figure.suptitle("Synthetic data-platform cost signals", color=PALETTE["navy"], x=0.03, y=0.95, ha="left", weight="bold")
    for axis, (value, label, color) in zip(axes, cards, strict=True):
        axis.set_facecolor("#F8FAFC")
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.axis("off")
        axis.add_patch(FancyBboxPatch((0.04, 0.10), 0.92, 0.72, boxstyle="round,pad=0.02,rounding_size=0.04", linewidth=0, facecolor="#FFFFFF"))
        axis.add_patch(FancyBboxPatch((0.10, 0.68), 0.14, 0.035, boxstyle="round,pad=0.01,rounding_size=0.02", linewidth=0, facecolor=color))
        axis.text(0.10, 0.50, value, ha="left", va="center", color=PALETTE["navy"], fontsize=21, weight="bold")
        axis.text(0.10, 0.32, label, ha="left", va="center", color=PALETTE["slate"], fontsize=10)
    figure.text(0.03, 0.02, "Separate units per card. Synthetic fixture data; not a saving.", color=PALETTE["slate"], fontsize=9)
    figure.savefig(output_directory / "cost-signals.png", dpi=150, metadata={"Software": None})
    plt.close(figure)


def _value(value: Any) -> str:
    return "`" + json.dumps(value, sort_keys=True) + "`"


def render_markdown(specification: dict[str, Any], findings: list[dict[str, Any]], *, include_chart: bool = True) -> str:
    period = specification["period"]
    priorities = Counter(finding["priority"] for finding in findings)
    providers = Counter(finding["provider"] for finding in findings)
    lines = [
        "# Cloud data FinOps assessment",
        "",
        f"> **Synthetic data.** Generated from `{specification['scope'].get('data_origin', 'synthetic')}` fixture telemetry. "
        "No value in this report describes a real environment, bill, or saving.",
        "",
        "## Summary",
        "",
        f"- Assessment: `{specification['assessment_id']}`",
        f"- Period: {period['start']} to {period['end']}",
        f"- Rules evaluated: {len(specification.get('rules', {}).get('enabled', RULES))}",
        f"- Findings: {len(findings)} (high {priorities['high']}, medium {priorities['medium']}, low {priorities['low']})",
        f"- By provider: GCP {providers['gcp']}, AWS {providers['aws']}",
        "",
        "## Scope and access boundary",
        "",
        f"- GCP project roles: {', '.join(sorted(specification['gcp']['roles']))}",
        f"- AWS actions: {', '.join(sorted(specification['aws']['actions']))}",
        "- Business-table content access: none. Write access: none. Commitment purchases: none.",
        "",
        "## Findings overview",
        "",
        "| Priority | Rule | Subject | Finding | Confidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        lines.append(f"| {finding['priority']} | {finding['rule_id']} | `{finding['subject']}` | {finding['title']} | {finding['confidence']} |")
    lines.append("")
    if include_chart:
        lines.extend(
            [
                CHART_MARKDOWN,
                "",
            ]
        )
    lines.extend(["## Findings", ""])
    for finding in findings:
        calculation = finding["calculation"]
        impact = finding["estimated_impact"]
        lines.extend(
            [
                f"### {finding['rule_id']} · {finding['subject']}: {finding['title']}",
                "",
                f"Priority: {finding['priority']}. Provider: `{finding['provider']}`. Evidence source: `{finding['evidence_source']}`.",
                "",
                "#### Observed evidence",
                "",
            ]
        )
        lines.extend(f"- `{key}`: {_value(value)}" for key, value in finding["observed_evidence"].items())
        lines.extend(["", "#### Calculation", "", f"- Formula: `{calculation['formula']}`"])
        lines.extend(f"- Input `{key}`: {_value(value)}" for key, value in calculation["inputs"].items())
        lines.extend(f"- Result `{key}`: {_value(value)}" for key, value in calculation["result"].items())
        lines.extend(f"- Unit of `{key}`: {unit}" for key, unit in calculation["units"].items())
        lines.extend(f"- Assumption: {assumption}" for assumption in calculation["assumptions"])
        lines.extend(["", "#### Recommendation", "", finding["recommendation"], "", "#### Estimated impact", ""])
        if impact["value"] is None:
            lines.append(impact["basis"])
        else:
            lines.append(f"{impact['value']:,} {impact['unit']}. Basis: {impact['basis']}")
        lines.extend(["", "#### Confidence", "", finding["confidence"], ""])
        if finding["related_rules"]:
            lines.extend([f"Related findings on the same subject: {', '.join(finding['related_rules'])}.", ""])
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in LIMITATIONS)
    lines.extend(["", "## Sources", ""])
    lines.extend(f"- [{label}]({url})" for label, url in SOURCES)
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def write_findings(output_directory: Path, findings: list[dict[str, Any]]) -> None:
    write_text(output_directory / "findings.json", json.dumps(findings, indent=2, sort_keys=True) + "\n")


def write_report(output_directory: Path, specification: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    write_findings(output_directory, findings)
    write_cost_signal_chart(output_directory, findings)
    write_text(output_directory / "report.md", render_markdown(specification, findings, include_chart=bool(signal_cards(findings))))
