"""Centralized type inference and coercion for RuleFrame.

Mirrors the date-inference pattern: infer column types from rule structure and
computed column specs, then apply a single coercion pass before evaluation.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .exceptions import BundleValidationError, InputSchemaError

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
    target_type: str  # "integer", "numeric", or "date"
    input_dtype: str  # pandas dtype string before coercion (e.g. "object", "int64")
    total_non_null: int
    coerced_successfully: int
    coercion_failures: int  # non-null values that became NaN


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------


def _infer_type_from_literal(value: Any) -> str | None:
    """Return 'numeric', 'string', 'boolean', 'integer' or
    None based on a YAML-parsed literal value.
    bool must be checked before int because bool is a subclass of int in Python.
    """
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "numeric"
    if isinstance(value, str):
        return "string"
    return None


def _infer_type_from_in_list(items: list) -> str | None:
    """Return 'numeric', 'string', 'boolean', or 'mixed' based on list item types.

    bool must be checked before int — bool is a subclass of int in Python.
    """
    if not items:
        return None
    has_bool = any(isinstance(v, bool) for v in items)
    has_integer = any(isinstance(v, int) and not isinstance(v, bool) for v in items)
    has_numeric = any(isinstance(v, float) for v in items)
    has_string = any(isinstance(v, str) for v in items)

    type_groups = sum(
        [
            has_bool,
            has_integer or has_numeric,
            has_string,
        ]
    )

    if type_groups > 1:
        return "mixed"

    if has_bool:
        return "boolean"
    if has_integer and has_numeric:
        return "numeric"
    if has_integer:
        return "integer"
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

        # Comparison predicates accept both integers and fractional numbers.
        if op_key in NUMERIC_PREDICATES:
            signals.setdefault(col, []).append(("numeric", f"{op_key} in rule {rule_id!r}"))

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
                signals.setdefault(col, []).append((inferred, f"{op_key} in rule {rule_id!r}"))
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
                    signals.setdefault(col, []).append((inferred, f"{op_key} in rule {rule_id!r}"))
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
        elif col_type in {"scale", "add_constant"}:
            if c := spec.get("column"):
                signals.setdefault(str(c), []).append(
                    ("numeric", f"computed column {name!r} ({col_type})")
                )
        elif col_type in {"round"}:
            if c := spec.get("column"):
                signals.setdefault(str(c), []).append(
                    ("numeric", f"computed column {name!r} ({col_type})")
                )


def _resolve_type_signals(
    col: str,
    type_signals: list[tuple[str, str]],
) -> str:
    """Resolve multiple type signals for one column."""
    types_seen = {inferred_type for inferred_type, _ in type_signals}

    if types_seen <= {"integer"}:
        return "integer"

    if types_seen <= {"integer", "numeric"}:
        return "numeric"

    if len(types_seen) > 1:
        by_type: dict[str, list[str]] = {}

        for inferred_type, source in type_signals:
            by_type.setdefault(inferred_type, []).append(source)

        details = "; ".join(
            f"{inferred_type} (from {', '.join(sources)})"
            for inferred_type, sources in by_type.items()
        )

        raise BundleValidationError(
            f"Column {col!r} has conflicting type signals: {details}. "
            "Fix the rule definitions so all predicates agree on the column type."
        )

    return next(iter(types_seen))


def infer_column_types(
    rules: list[dict[str, Any]],
    computed_columns: list[dict[str, Any]],
) -> dict[str, str]:
    """Infer column types from rule structure and computed column specs.

    Returns a dict mapping column_name -> "integer" | "numeric" | "string" | "boolean".
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
        resolved[col] = _resolve_type_signals(col, type_signals)

    return resolved


# ---------------------------------------------------------------------------
# Coercion pass
# ---------------------------------------------------------------------------


def _coerce_integer_series(
    series: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Coerce a series to nullable integers.

    Returns:
        converted: Nullable Int64 series.
        invalid: Boolean mask for non-null values that are invalid integers.
    """
    parsed = pd.to_numeric(series, errors="coerce")

    is_boolean = series.map(lambda value: isinstance(value, bool))
    is_fractional = parsed.notna() & (parsed % 1 != 0)

    invalid = series.notna() & (parsed.isna() | is_fractional | is_boolean)

    converted = parsed.mask(invalid).astype("Int64")
    return converted, invalid


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
        if target_type not in {"integer", "numeric"}:
            continue

        if col not in working.columns:
            continue

        series = working[col]
        pre_non_null = int(series.notna().sum())
        input_dtype = str(series.dtype)

        if pre_non_null == 0:
            log.append(
                CoercionEvent(
                    column=col,
                    target_type=target_type,
                    input_dtype=input_dtype,
                    total_non_null=0,
                    coerced_successfully=0,
                    coercion_failures=0,
                )
            )
            continue

        if target_type == "integer":
            converted, invalid_mask = _coerce_integer_series(series)
        else:
            converted = pd.to_numeric(series, errors="coerce")
            invalid_mask = series.notna() & converted.isna()

        post_non_null = int(converted.notna().sum())
        failures = int(invalid_mask.sum())

        log.append(
            CoercionEvent(
                column=col,
                target_type=target_type,
                input_dtype=input_dtype,
                total_non_null=pre_non_null,
                coerced_successfully=post_non_null,
                coercion_failures=failures,
            )
        )

        if post_non_null == 0 and pre_non_null > 0:
            raise InputSchemaError(
                f"Column {col!r} is used as {target_type} but contains no "
                f"parseable {target_type} values "
                f"({pre_non_null} non-null values all failed to coerce)."
            )

        if failures > 0 and warn:
            warnings.warn(
                f"Column {col!r}: {failures} non-null value(s) could not be "
                f"parsed as {target_type} and are now NaN. This may affect "
                "downstream rules evaluating blanks.",
                stacklevel=3,
            )

        working[col] = converted

    return working, log
