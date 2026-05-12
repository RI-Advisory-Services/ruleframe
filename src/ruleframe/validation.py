from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .bundle import RuleBundle
from .result import Finding, ValidationResult


def validate_dataframe(df: pd.DataFrame, bundle: RuleBundle) -> ValidationResult:
    """Minimal v0 validation loop based on simple equals and is_blank operators.

    This intentionally starts small so the test harness and API are stable while
    we build out full JsonLogic compilation and operator coverage.
    """

    findings: list[Finding] = []
    messages_by_row: dict[int, list[str]] = defaultdict(list)
    annotated = df.copy()

    for idx, row in annotated.iterrows():
        for rule in bundle.rules:
            if _rule_fails(row, rule):
                message = str(rule.get("message", "Rule failed"))
                findings.append(
                    Finding(
                        row_index=int(idx),
                        rule_id=str(rule.get("id", "unknown_rule")),
                        rule_name=rule.get("name"),
                        severity=str(rule.get("severity", "error")),
                        message=message,
                    )
                )
                messages_by_row[int(idx)].append(message)

    annotated["Validation Errors"] = [
        " | ".join(messages_by_row.get(int(i), [])) for i in annotated.index
    ]
    return ValidationResult(annotated=annotated, findings=findings)


def _rule_fails(row: pd.Series, rule: dict) -> bool:
    fail_when = rule.get("fail_when")
    if not isinstance(fail_when, dict):
        return False
    return _evaluate_condition(row, fail_when)


def _evaluate_condition(row: pd.Series, condition: dict) -> bool:
    if "all" in condition:
        return all(_evaluate_condition(row, child) for child in condition.get("all", []))
    if "any" in condition:
        return any(_evaluate_condition(row, child) for child in condition.get("any", []))
    if "not" in condition:
        return not _evaluate_condition(row, condition["not"])

    column = condition.get("column")
    if column is None:
        return False
    value = row.get(column)

    if "equals" in condition:
        return value == condition["equals"]
    if "is_blank" in condition:
        if not condition["is_blank"]:
            return False
        return value is None or (isinstance(value, str) and value.strip() == "") or pd.isna(value)

    return False
