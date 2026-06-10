from __future__ import annotations

import datetime
from typing import Any

import pandas as pd

from .dates import normalize_date_series
from .exceptions import BundleValidationError

VALID_COMPUTED_TYPES = frozenset(
    {
        "sum",
        "subtract",
        "multiply",
        "divide",
        "coalesce",
        "group_sum",
        "group_count",
        "date_diff",
        "days_since_today",
        "years_since_year",
        "all_blank_or_zero",
    }
)


def validate_computed_column_specs(specs: list[dict[str, Any]]) -> None:
    """Raise BundleValidationError if computed column specs contain structural problems.

    Checks (in order):
    1. Duplicate output names: two specs cannot generate the same column.
    2. Self-reference: a spec lists its own output name as one of its inputs.
    3. Out-of-order / undefined reference: a spec references a generated column
       that has not been declared earlier in the list.
    4. Cycles: a chain of dependencies that loops back to an earlier column
       (detected via DFS on the dependency graph).
    """
    generated_so_far: set[str] = set()
    # Build full dependency graph for cycle detection (name -> set of generated deps)
    all_names: set[str] = set()
    duplicate_names: set[str] = set()
    for spec in specs:
        name = computed_column_name(spec)
        if name in all_names:
            duplicate_names.add(name)
        all_names.add(name)

    if duplicate_names:
        names = ", ".join(sorted(duplicate_names))
        raise BundleValidationError(f"Computed column output name(s) must be unique: {names}")

    deps: dict[str, set[str]] = {}

    for spec in specs:
        name = computed_column_name(spec)
        column_type = spec.get("type")
        if column_type not in VALID_COMPUTED_TYPES:
            raise BundleValidationError(
                f"Computed column {name!r} has unsupported type: {column_type!r}. "
                f"Valid types are: {', '.join(sorted(VALID_COMPUTED_TYPES))}"
            )
        inputs = required_input_columns(spec)
        generated_deps = inputs & all_names
        deps[name] = generated_deps

        # 1. Self-reference
        if name in inputs:
            raise BundleValidationError(f"Computed column {name!r} references itself as an input.")

        # 2. Out-of-order: any generated dep not yet produced by a prior spec
        out_of_order = generated_deps - generated_so_far
        if out_of_order:
            missing_names = ", ".join(sorted(out_of_order))
            raise BundleValidationError(
                f"Computed column {name!r} depends on {missing_names}, "
                f"which must be declared earlier in computed_columns."
            )

        generated_so_far.add(name)

    # 3. Cycle detection via DFS (can only occur across specs, self-reference caught above)
    def _has_cycle(node: str, visiting: set[str], visited: set[str]) -> bool:
        visiting.add(node)
        for dep in deps.get(node, set()):
            if dep in visiting:
                return True
            if dep not in visited and _has_cycle(dep, visiting, visited):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    visited: set[str] = set()
    for name in deps:
        if name not in visited:
            if _has_cycle(name, set(), visited):
                raise BundleValidationError(
                    f"Computed columns contain a dependency cycle involving {name!r}."
                )


def apply_computed_columns(df: pd.DataFrame, specs: list[dict[str, Any]]) -> pd.DataFrame:
    """Return a copy of df with rule-bundle computed columns added."""

    computed = df.copy()
    for spec in specs:
        column_name = computed_column_name(spec)
        computed[column_name] = compute_column(computed, spec)
    return computed


def compute_column(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    column_type = spec.get("type")
    if column_type == "sum":
        columns = computed_source_columns(spec)
        return pd.Series(df[columns].sum(axis=1, min_count=1), index=df.index)
    if column_type == "subtract":
        columns = computed_source_columns(spec)
        result: pd.Series = df[columns[0]].copy()
        for i in range(1, len(columns)):
            result = result - df[columns[i]]
        return result
    if column_type == "multiply":
        columns = computed_source_columns(spec)
        mul_result: pd.Series = df[columns[0]].copy()
        for i in range(1, len(columns)):
            mul_result = mul_result * df[columns[i]]
        return mul_result
    if column_type == "divide":
        columns = computed_source_columns(spec)
        if len(columns) != 2:
            raise ValueError("divide requires exactly 2 columns")
        numerator = df[columns[0]]
        denominator = df[columns[1]]
        return numerator / denominator.where(denominator != 0)
    if column_type == "coalesce":
        columns = computed_source_columns(spec)
        return df[columns].bfill(axis=1).iloc[:, 0]
    if column_type == "group_sum":
        return _compute_group_sum(df, spec)
    if column_type == "group_count":
        return _compute_group_count(df, spec)
    if column_type == "date_diff":
        return _compute_date_diff(df, spec)
    if column_type == "days_since_today":
        return _compute_days_since_today(df, spec)
    if column_type == "years_since_year":
        return _compute_years_since_year(df, spec)
    if column_type == "all_blank_or_zero":
        return _compute_all_blank_or_zero(df, spec)
    raise BundleValidationError(f"Unsupported computed column type: {column_type}")


def _compute_group_sum(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    group_by: str | None = spec.get("group_by")
    value_column: str | None = spec.get("value_column")
    if not group_by or not value_column:
        raise ValueError("group_sum requires group_by and value_column")

    values = df[value_column]
    filter_spec: dict[str, Any] | None = spec.get("filter")
    if filter_spec:
        mask: pd.Series = df[filter_spec["column"]] == filter_spec["equals"]
        group_totals = values[mask].groupby(df.loc[mask, group_by]).sum(min_count=1)
        return df[group_by].map(group_totals)
    else:
        group_totals = values.groupby(df[group_by]).sum(min_count=1)
        return df[group_by].map(group_totals)


def _compute_group_count(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    group_by: str | None = spec.get("group_by")
    if not group_by:
        raise ValueError("group_count requires group_by")

    filter_spec: dict[str, Any] | None = spec.get("filter")
    if filter_spec:
        mask: pd.Series = df[filter_spec["column"]] == filter_spec["equals"]
        group_counts = df.loc[mask].groupby(group_by).size()
        result = df[group_by].map(group_counts)
        return result.fillna(0)
    else:
        group_counts = df.groupby(group_by).size()
        return df[group_by].map(group_counts)


def _compute_date_diff(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    """Return (end_column - start_column) in whole days."""
    start_col: str | None = spec.get("start_column")
    end_col: str | None = spec.get("end_column")
    if not start_col or not end_col:
        raise ValueError("date_diff requires start_column and end_column")

    start_dt = normalize_date_series(df[start_col])
    end_dt = normalize_date_series(df[end_col])
    delta = (end_dt - start_dt).dt.days
    return pd.Series(delta.astype("Float64"), index=df.index)


def _compute_days_since_today(
    df: pd.DataFrame,
    spec: dict[str, Any],
    today: datetime.date | None = None,
) -> pd.Series:
    """Return (today - column) in whole days."""
    column: str | None = spec.get("column")
    if not column:
        raise ValueError("days_since_today requires column")

    reference = pd.Timestamp(*(today or datetime.date.today()).timetuple()[:3])
    col_dt = normalize_date_series(df[column])
    delta = (reference - col_dt).dt.days
    return pd.Series(delta.astype("Float64"), index=df.index)


def _compute_years_since_year(
    df: pd.DataFrame,
    spec: dict[str, Any],
    current_year: int | None = None,
) -> pd.Series:
    """Return (current_year - year_column) as an integer number of years."""
    column: str | None = spec.get("column")
    if not column:
        raise ValueError("years_since_year requires column")

    year = current_year if current_year is not None else datetime.date.today().year
    col_values = df[column].astype("Float64").round(0)
    result = (year - col_values).astype("Float64")
    return result


def _compute_all_blank_or_zero(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    """Return 1 if all listed columns are blank or zero for the row, else 0."""
    columns = computed_source_columns(spec)

    # For each column: True if cell is null/blank or numerically zero
    all_blank_or_zero = pd.Series(True, index=df.index)
    for col in columns:
        s = df[col]
        is_null = s.isna()
        # Try numeric comparison for zero
        numeric = pd.to_numeric(s, errors="coerce")
        is_zero = numeric == 0.0
        # For non-numeric non-null values: check if empty string
        is_empty_str = s.apply(lambda v: isinstance(v, str) and v.strip() == "")
        col_ok = is_null | is_zero | is_empty_str
        all_blank_or_zero = all_blank_or_zero & col_ok

    return all_blank_or_zero.astype(int)


def computed_column_name(spec: dict[str, Any]) -> str:
    name = spec.get("name") or spec.get("id")
    if not name:
        raise ValueError("Computed columns must define a name or id")
    return str(name)


def computed_source_columns(spec: dict[str, Any]) -> list[str]:
    """Return the ``columns`` list for arithmetic/coalesce types."""
    columns = spec.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Computed columns must define a non-empty columns list")
    return [str(column) for column in columns]


def required_input_columns(spec: dict[str, Any]) -> set[str]:
    """Return all input column names referenced by a computed column spec."""
    column_type = spec.get("type")
    if column_type in {"sum", "subtract", "multiply", "divide", "coalesce"}:
        return set(computed_source_columns(spec))
    if column_type == "group_sum":
        refs: set[str] = set()
        if group_by := spec.get("group_by"):
            refs.add(str(group_by))
        if value_column := spec.get("value_column"):
            refs.add(str(value_column))
        if filter_spec := spec.get("filter"):
            if col := filter_spec.get("column"):
                refs.add(str(col))
        return refs
    if column_type == "group_count":
        refs = set()
        if group_by := spec.get("group_by"):
            refs.add(str(group_by))
        if filter_spec := spec.get("filter"):
            if col := filter_spec.get("column"):
                refs.add(str(col))
        return refs
    if column_type == "date_diff":
        refs = set()
        if start_col := spec.get("start_column"):
            refs.add(str(start_col))
        if end_col := spec.get("end_column"):
            refs.add(str(end_col))
        return refs
    if column_type == "days_since_today":
        if col := spec.get("column"):
            return {str(col)}
        return set()
    if column_type == "years_since_year":
        if col := spec.get("column"):
            return {str(col)}
        return set()
    if column_type == "all_blank_or_zero":
        return set(computed_source_columns(spec))
    return set()


def collect_computed_column_names(specs: list[dict[str, Any]]) -> set[str]:
    return {computed_column_name(spec) for spec in specs}


def collect_computed_source_columns(specs: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for spec in specs:
        result.update(required_input_columns(spec))
    return result
