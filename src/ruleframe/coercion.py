"""Centralized type inference and coercion for RuleFrame.

Mirrors the date-inference pattern: infer column types from rule structure and
computed column specs, then apply a single coercion pass before evaluation.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .exceptions import BundleValidationError, InputSchemaError
from .predicates import PREDICATE_REGISTRY


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

NUMERIC_PREDICATES = frozenset(
    {
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
        "between",
        "not_between",
        "greater_than_column",
        "greater_than_or_equal_column",
        "less_than_column",
        "less_than_or_equal_column",
    }
)

NUMERIC_COMPUTED_TYPES = frozenset(
    {
        "sum",
        "subtract",
        "multiply",
        "divide",
        "group_sum",
        "years_since_year",
    }
)


@dataclass(frozen=True)
class CoercionEvent:
    """Record of a coercion applied to a single column."""

    column: str
    target_type: str  # "numeric" or "date"
    input_dtype: str  # pandas dtype string before coercion (e.g. "object", "int64")
    total_non_null: int
    coerced_successfully: int
    coercion_failures: int  # non-null values that became NaN


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------


def _infer_type_from_literal(value: Any) -> str | None:
    """Return 'numeric' or 'string' based on a YAML-parsed literal value."""
    if isinstance(value, (int, float)):
        return "numeric"
    if isinstance(value, str):
        return "string"
    return None


def _infer_type_from_in_list(items: list) -> str | None:
    """Return 'numeric', 'string', or raise BundleValidationError for mixed."""
    if not items:
        return None
    has_numeric = any(isinstance(v, (int, float)) for v in items)
    has_string = any(isinstance(v, str) for v in items)
    if has_numeric and has_string:
        return "mixed"  # caller will raise
    if has_numeric:
        return "numeric"
    if has_string:
        return "string"
    return None


def _infer_types_from_condition(
    condition: dict,
    signals: dict[str, list[tuple[str, str]]],
    rule_id: str,
) -> None:
    """Walk a condition tree and record type signals for each column.

    signals maps column_name -> [(inferred_type, source_description), ...]
    """
    if "all" in condition:
        for child in condition["all"]:
            _infer_types_from_condition(child, signals, rule_id)
        return
    if "any" in condition:
        for child in condition["any"]:
            _infer_types_from_condition(child, signals, rule_id)
        return
    if "not" in condition:
        _infer_types_from_condition(condition["not"], signals, rule_id)
        return

    col = condition.get("column")
    if not col:
        return
    col = str(col)

    for op_key, value in condition.items():
        if op_key == "column":
            continue

        # Predicates that always imply numeric
        if op_key in NUMERIC_PREDICATES:
            signals.setdefault(col, []).append(("numeric", f"{op_key} in rule {rule_id!r}"))
            # Column predicates also imply the RHS column is numeric
            if op_key.endswith("_column"):
                rhs = str(value)
                signals.setdefault(rhs, []).append(
                    ("numeric", f"{op_key} (right-hand) in rule {rule_id!r}")
                )
            continue

        # equals / not_equals — infer from literal type
        if op_key in ("equals", "not_equals"):
            inferred = _infer_type_from_literal(value)
            if inferred:
                signals.setdefault(col, []).append(
                    (inferred, f"{op_key} in rule {rule_id!r}")
                )
            continue

        # in / not_in — infer from list item types
        if op_key in ("in", "not_in"):
            if isinstance(value, list):
                inferred = _infer_type_from_in_list(value)
                if inferred == "mixed":
                    raise BundleValidationError(
                        f"Rule {rule_id!r}: '{op_key}' list for column {col!r} "
                        f"contains mixed types (both strings and numbers). "
                        f"All items must be the same type."
                    )
                if inferred:
                    signals.setdefault(col, []).append(
                        (inferred, f"{op_key} in rule {rule_id!r}")
                    )
            continue


def _infer_types_from_computed(
    specs: list[dict[str, Any]],
    signals: dict[str, list[tuple[str, str]]],
) -> None:
    """Record numeric signals from computed column specs."""
    for spec in specs:
        col_type = spec.get("type")
        name = spec.get("name") or spec.get("id") or "unknown"

        if col_type in ("sum", "subtract", "multiply", "divide"):
            columns = spec.get("columns", [])
            for c in columns:
                signals.setdefault(str(c), []).append(
                    ("numeric", f"computed column {name!r} ({col_type})")
                )
        elif col_type == "group_sum":
            if vc := spec.get("value_column"):
                signals.setdefault(str(vc), []).append(
                    ("numeric", f"computed column {name!r} (group_sum)")
                )
        elif col_type == "years_since_year":
            if c := spec.get("column"):
                signals.setdefault(str(c), []).append(
                    ("numeric", f"computed column {name!r} (years_since_year)")
                )


def infer_column_types(
    rules: list[dict[str, Any]],
    computed_columns: list[dict[str, Any]],
) -> dict[str, str]:
    """Infer column types from rule structure and computed column specs.

    Returns a dict mapping column_name -> "numeric" | "string".
    Raises BundleValidationError if conflicting signals are detected.
    """
    # signals: column_name -> [(type, source_description), ...]
    signals: dict[str, list[tuple[str, str]]] = {}

    # Gather signals from rules
    for rule in rules:
        rule_id = str(rule.get("id", "unknown"))
        fail_when = rule.get("fail_when")
        if isinstance(fail_when, dict):
            _infer_types_from_condition(fail_when, signals, rule_id)

    # Gather signals from computed columns
    _infer_types_from_computed(computed_columns, signals)

    # Resolve each column to a single type
    resolved: dict[str, str] = {}
    for col, type_signals in signals.items():
        types_seen = {t for t, _ in type_signals}
        if "numeric" in types_seen and "string" in types_seen:
            numeric_sources = [src for t, src in type_signals if t == "numeric"]
            string_sources = [src for t, src in type_signals if t == "string"]
            raise BundleValidationError(
                f"Column {col!r} has conflicting type signals: "
                f"numeric (from {numeric_sources[0]}) vs "
                f"string (from {string_sources[0]}). "
                f"Fix the rule definitions so all predicates agree on the column type."
            )
        if "numeric" in types_seen:
            resolved[col] = "numeric"
        elif "string" in types_seen:
            resolved[col] = "string"

    return resolved


# ---------------------------------------------------------------------------
# Coercion pass
# ---------------------------------------------------------------------------


def apply_numeric_coercion(
    df: pd.DataFrame,
    column_types: dict[str, str],
    warn: bool = True,
) -> tuple[pd.DataFrame, list[CoercionEvent]]:
    """Apply numeric coercion to a working copy of the DataFrame.

    Returns (working_df, coercion_log).
    Raises InputSchemaError if ALL non-null values in a numeric column fail to coerce.
    """
    working = df.copy()
    log: list[CoercionEvent] = []

    for col, target_type in column_types.items():
        if target_type != "numeric":
            continue
        if col not in working.columns:
            continue

        series = working[col]
        pre_non_null = series.notna().sum()

        input_dtype = str(series.dtype)

        if pre_non_null == 0:
            # Column is entirely null — nothing to coerce
            log.append(
                CoercionEvent(
                    column=col,
                    target_type="numeric",
                    input_dtype=input_dtype,
                    total_non_null=0,
                    coerced_successfully=0,
                    coercion_failures=0,
                )
            )
            continue

        converted = pd.to_numeric(series, errors="coerce")
        post_non_null = converted.notna().sum()
        failures = int(pre_non_null - post_non_null)

        log.append(
            CoercionEvent(
                column=col,
                target_type="numeric",
                input_dtype=input_dtype,
                total_non_null=int(pre_non_null),
                coerced_successfully=int(post_non_null),
                coercion_failures=failures,
            )
        )

        if post_non_null == 0 and pre_non_null > 0:
            raise InputSchemaError(
                f"Column {col!r} is used as numeric but contains no parseable "
                f"numeric values ({pre_non_null} non-null values all failed to coerce)."
            )

        if failures > 0 and warn:
            warnings.warn(
                f"Column {col!r}: {failures} non-null value(s) could not be parsed "
                f"as numeric and are now NaN. This may affect downstream rules "
                f"evaluating blanks.",
                stacklevel=3,
            )

        working[col] = converted

    return working, log

