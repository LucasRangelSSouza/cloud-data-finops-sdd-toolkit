"""Deterministic policy engine over validated telemetry."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from .catalog import RULES, Rule
from .model import Finding

__all__ = ["RULES", "Rule", "Finding", "evaluate", "evaluate_findings"]


def evaluate_findings(telemetry: dict[str, Any]) -> list[Finding]:
    """Run the enabled rules, cross-reference findings on the same subject, and sort by priority."""
    selection = telemetry.get("rules") or {}
    enabled = selection.get("enabled")
    if enabled is None:
        enabled = sorted(RULES)
    overrides = selection.get("thresholds", {})
    assumptions = telemetry.get("assumptions", {})

    findings: list[Finding] = []
    for rule_id in sorted(enabled):
        rule = RULES[rule_id]
        thresholds = {**rule.thresholds, **overrides.get(rule_id, {})}
        findings.extend(rule.evaluate(telemetry, thresholds, assumptions))

    rules_by_subject: dict[tuple[str, str], set[str]] = defaultdict(set)
    for finding in findings:
        rules_by_subject[(finding.provider, finding.subject)].add(finding.rule_id)
    linked = [replace(finding, related_rules=tuple(sorted(rules_by_subject[(finding.provider, finding.subject)] - {finding.rule_id}))) for finding in findings]
    return sorted(linked, key=lambda finding: finding.sort_key)


def evaluate(telemetry: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding.to_dict() for finding in evaluate_findings(telemetry)]
