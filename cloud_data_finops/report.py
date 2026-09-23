from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def write_cost_signal_chart(output_directory: Path, findings: list[dict[str, Any]]) -> None:
    signals: list[tuple[str, float, str, str]] = []
    for finding in findings:
        evidence = finding["evidence"]
        if finding["id"] == "BQ-001":
            signals.append(("BigQuery bytes billed", float(evidence["bytes_billed_gb"]), "GB", "#2563EB"))
        if finding["id"] == "AWS-001":
            signals.append(("Athena cost increase", float(evidence["increase_usd"]), "USD", "#F59E0B"))

    figure, axes = plt.subplots(1, len(signals), figsize=(9, 4.5), layout="constrained")
    if len(signals) == 1:
        axes = [axes]
    figure.set_facecolor("#F8FAFC")
    figure.suptitle("Synthetic data-platform cost signals", color="#0F172A", x=0.05, ha="left", weight="bold")
    figure.text(0.05, 0.89, "Separate units. Values are not compared across cards.", color="#475569", fontsize=10)
    for axis, (label, value, unit, color) in zip(axes, signals):
        axis.set_facecolor("#F8FAFC")
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.axis("off")
        card = FancyBboxPatch(
            (0.04, 0.12), 0.92, 0.68,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            linewidth=0,
            facecolor="#FFFFFF",
        )
        axis.add_patch(card)
        axis.add_patch(FancyBboxPatch(
            (0.10, 0.65), 0.12, 0.035,
            boxstyle="round,pad=0.01,rounding_size=0.02",
            linewidth=0,
            facecolor=color,
        ))
        axis.text(
            0.10,
            0.51,
            f"{value:,.0f} {unit}",
            ha="left",
            va="center",
            color="#0F172A",
            fontsize=24,
            weight="bold",
        )
        axis.text(0.10, 0.35, label, ha="left", va="center", color="#334155", fontsize=11)
    figure.savefig(output_directory / "cost-signals.png", dpi=200)
    plt.close(figure)


def write_report(output_directory: Path, specification: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "findings.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_cost_signal_chart(output_directory, findings)

    sections = [
        "# Cloud data FinOps assessment",
        "",
        f"Assessment: `{specification['assessment_id']}`",
        "",
        "## Findings",
        "",
        "![Synthetic data-platform cost signals](cost-signals.png)",
        "",
    ]
    for finding in findings:
        sections.extend([
            f"### {finding['id']} — {finding['title']}",
            "",
            f"Provider: `{finding['provider']}`",
            "",
            "Evidence:",
            "",
        ])
        for key, value in finding["evidence"].items():
            formatted = f"{value:,.0f} GB" if key == "bytes_billed_gb" else str(value)
            sections.append(f"- `{key}`: {formatted}")
        sections.extend([
            "",
            f"Assumption: {finding['assumption']}",
            "",
            f"Recommendation: {finding['recommendation']}",
            "",
            f"Confidence: {finding['confidence']}",
            "",
        ])
    sections.extend([
        "## Evidence and assumptions",
        "",
        "This report was generated from synthetic fixture data. It does not represent a customer environment, a real saving, or a purchase recommendation.",
    ])
    (output_directory / "report.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
