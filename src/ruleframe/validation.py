from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd
from jsonlogic import JSONLogicExpression
from jsonlogic.evaluation import evaluate

from .bundle import RuleBundle
from .coercion import (
    apply_numeric_coercion,
    infer_column_types,
)
from .compiler import collect_rule_columns, compile_rule
from .computed import (
    apply_computed_columns,
    collect_computed_column_names,
    collect_computed_source_columns,
    validate_computed_column_specs,
)
from .dates import normalize_date_series
from .exceptions import BundleValidationError, InputSchemaError
from .operators import build_registry
from .predicates import PREDICATE_REGISTRY
from .result import Finding, ValidationResult


def validate_dataframe(
    df: pd.DataFrame, bundle: RuleBundle, *, warn: bool = True
) -> ValidationResult:
    """Validate a DataFrame by compiling friendly rules to JsonLogic."""

    validate_computed_column_specs(bundle.computed_columns)

    collisions = computed_column_name_collisions(df, bundle)
    if collisions:
        raise InputSchemaError(
            "Computed column name(s) collide with existing input column(s): "
            + ", ".join(collisions)
        )

    missing = missing_rule_columns(df, bundle)
    if missing:
        raise InputSchemaError("Input is missing required rule column(s): " + ", ".join(missing))

    # --- Type inference and coercion ---
    column_types = infer_column_types(bundle.rules, bundle.computed_columns)

    # --- Cross-check: date columns must not also have numeric/string signals ---
    date_fmt = _date_format(bundle)
    date_cols = _infer_date_columns(bundle)
    overlap = date_cols & set(column_types.keys())
    if overlap:
        raise BundleValidationError(
            f"Column(s) {sorted(overlap)} are used with both date predicates and "
            f"numeric/string predicates. A column cannot serve two roles."
        )

    working_df, coercion_log = apply_numeric_coercion(df, column_types, warn=warn)

    # --- Date normalization ---
    for col in date_cols:
        if col in working_df.columns:
            working_df[col] = normalize_date_series(working_df[col], fmt=date_fmt)

    # --- Computed columns ---
    working_df = apply_computed_columns(working_df, bundle.computed_columns)

    # --- Compile and evaluate rules ---
    registry = build_registry()
    compiled_rules = [
        (rule, JSONLogicExpression.from_json(compile_rule(rule)).as_operator_tree(registry))
        for rule in bundle.rules
    ]

    findings: list[Finding] = []
    messages_by_row: dict[int, list[str]] = defaultdict(list)

    for row_pos, (_, row) in enumerate(working_df.iterrows()):
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

    # --- Build annotated output from original df + computed columns ---
    annotated = df.copy()
    # Add computed columns to the annotated output (from working_df)
    computed_names = collect_computed_column_names(bundle.computed_columns)
    for col_name in computed_names:
        if col_name in working_df.columns:
            annotated[col_name] = working_df[col_name].values

    annotated[_validation_errors_column(bundle)] = [
        " | ".join(messages_by_row.get(i, [])) for i, _ in enumerate(annotated.index)
    ]
    return ValidationResult(
        annotated=annotated,
        findings=findings,
        working_dataframe=working_df,
        coercion_log=coercion_log,
    )


def missing_rule_columns(df: pd.DataFrame, bundle: RuleBundle) -> list[str]:
    required = collect_rule_columns(bundle.rules)
    generated = collect_computed_column_names(bundle.computed_columns)
    source_columns = collect_computed_source_columns(bundle.computed_columns)
    # A generated column may be used as input to a later computed column (chained).
    # Only columns that are NOT themselves generated must be present in the input DataFrame.
    required_input_columns = (required - generated) | (source_columns - generated)
    return sorted(required_input_columns - set(df.columns))


def computed_column_name_collisions(df: pd.DataFrame, bundle: RuleBundle) -> list[str]:
    """Return generated column names that already exist in the input DataFrame."""
    generated = collect_computed_column_names(bundle.computed_columns)
    return sorted(generated & set(df.columns))


def _row_to_json_data(row: pd.Series) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, val in row.items():
        data[str(key)] = None if pd.isna(val) else val
    return data


def _validation_errors_column(bundle: RuleBundle) -> str:
    settings = bundle.raw.get("settings")
    if isinstance(settings, dict) and settings.get("validation_errors_column"):
        return str(settings["validation_errors_column"])
    return "Validation Errors"


def _date_format(bundle: RuleBundle) -> str | None:
    """Return the bundle-level date_format string, or None for flexible parsing."""
    settings = bundle.raw.get("settings")
    if isinstance(settings, dict):
        fmt = settings.get("date_format")
        return str(fmt) if fmt else None
    return None


def _date_columns_from_condition(condition: dict) -> set[str]:
    """Recursively collect date columns implied by a condition tree."""
    cols: set[str] = set()

    if "all" in condition:
        for child in condition["all"]:
            cols |= _date_columns_from_condition(child)
        return cols
    if "any" in condition:
        for child in condition["any"]:
            cols |= _date_columns_from_condition(child)
        return cols
    if "not" in condition:
        return _date_columns_from_condition(condition["not"])

    col = condition.get("column")
    if not col:
        return cols

    for op_key, value in condition.items():
        if op_key == "column":
            continue
        if cls := PREDICATE_REGISTRY.get(op_key):
            cols |= cls.date_columns(str(col), value)
    return cols


def _infer_date_columns(bundle: RuleBundle) -> set[str]:
    """Return column names that are structurally implied to be date columns.

    Sources:
    - ``date_diff`` computed specs: ``start_column`` and ``end_column``
    - ``days_since_today`` computed specs: ``column``
    - Rule conditions using date-aware predicates (``date_greater_than``,
      ``date_greater_than_or_equal_column``, etc.)
    """
    cols: set[str] = set()

    for spec in bundle.computed_columns:
        t = spec.get("type")
        if t == "date_diff":
            if c := spec.get("start_column"):
                cols.add(str(c))
            if c := spec.get("end_column"):
                cols.add(str(c))
        elif t == "days_since_today":
            if c := spec.get("column"):
                cols.add(str(c))

    for rule in bundle.rules:
        fail_when = rule.get("fail_when")
        if isinstance(fail_when, dict):
            cols |= _date_columns_from_condition(fail_when)

    return cols
