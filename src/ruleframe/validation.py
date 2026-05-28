from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd
from jsonlogic import JSONLogicExpression
from jsonlogic.evaluation import evaluate

from .bundle import RuleBundle
from .compiler import collect_rule_columns, compile_rule
from .computed import (
    apply_computed_columns,
    collect_computed_column_names,
    collect_computed_source_columns,
)
from .exceptions import InputSchemaError
from .operators import build_registry
from .result import Finding, ValidationResult


def validate_dataframe(df: pd.DataFrame, bundle: RuleBundle) -> ValidationResult:
    """Validate a DataFrame by compiling friendly rules to JsonLogic."""

    missing = missing_rule_columns(df, bundle)
    if missing:
        raise InputSchemaError("Input is missing required rule column(s): " + ", ".join(missing))

    working_df = apply_computed_columns(df, bundle.computed_columns)

    registry = build_registry()
    compiled_rules = [
        (rule, JSONLogicExpression.from_json(compile_rule(rule)).as_operator_tree(registry))
        for rule in bundle.rules
    ]

    findings: list[Finding] = []
    messages_by_row: dict[int, list[str]] = defaultdict(list)
    annotated = _with_row_id(working_df, bundle)

    for row_pos, (_, row) in enumerate(annotated.iterrows()):
        row_data = _row_to_json_data(row)
        for rule, operator_tree in compiled_rules:
            if not bool(evaluate(operator_tree, row_data, None)):
                continue

            message = str(rule.get("message", "Rule failed"))
            findings.append(
                Finding(
                    row_index=row_pos,
                    rule_id=str(rule.get("id", "unknown_rule")),
                    rule_name=rule.get("name"),
                    severity=str(rule.get("severity", "error")),
                    message=message,
                )
            )
            messages_by_row[row_pos].append(message)

    annotated[_validation_errors_column(bundle)] = [
        " | ".join(messages_by_row.get(i, [])) for i, _ in enumerate(annotated.index)
    ]
    return ValidationResult(annotated=annotated, findings=findings)


def missing_rule_columns(df: pd.DataFrame, bundle: RuleBundle) -> list[str]:
    required = collect_rule_columns(bundle.rules)
    generated = collect_computed_column_names(bundle.computed_columns)
    if row_id_column := _row_id_column(bundle):
        generated.add(row_id_column)

    source_columns = collect_computed_source_columns(bundle.computed_columns)
    required_input_columns = (required - generated) | source_columns
    return sorted(required_input_columns - set(df.columns))


def _row_to_json_data(row: pd.Series) -> dict[str, Any]:
    return row.where(pd.notna(row), None).to_dict()


def _with_row_id(df: pd.DataFrame, bundle: RuleBundle) -> pd.DataFrame:
    row_id_column = _row_id_column(bundle)
    annotated = df.copy()
    if row_id_column and row_id_column not in annotated.columns:
        annotated.insert(0, row_id_column, range(1, len(annotated) + 1))
    return annotated


def _row_id_column(bundle: RuleBundle) -> str | None:
    settings = bundle.raw.get("settings")
    if not isinstance(settings, dict):
        return None
    row_id = settings.get("row_id")
    if not isinstance(row_id, dict):
        return None
    column = row_id.get("column")
    return str(column) if column else None


def _validation_errors_column(bundle: RuleBundle) -> str:
    settings = bundle.raw.get("settings")
    if isinstance(settings, dict) and settings.get("validation_errors_column"):
        return str(settings["validation_errors_column"])
    return "Validation Errors"
