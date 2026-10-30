from __future__ import annotations

import datetime
from collections.abc import Mapping
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
        "scale",
        "add_constant",
        "round",
        "alias",
        "contains_substring",
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
    5. Correct data type: each computed column should only accept valid input types for its
       operation.
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

        # 2. Self-reference
        if name in inputs:
            raise BundleValidationError(f"Computed column {name!r} references itself as an input.")

        # 3. Out-of-order: any generated dep not yet produced by a prior spec
        out_of_order = generated_deps - generated_so_far
        if out_of_order:
            missing_names = ", ".join(sorted(out_of_order))
            raise BundleValidationError(
                f"Computed column {name!r} depends on {missing_names}, "
                f"which must be declared earlier in computed_columns."
            )

        generated_so_far.add(name)

    # 4. Cycle detection via DFS (can only occur across specs, self-reference caught above)
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
    # 5. Correct data type: each computed column should only accept valid input types for
    # its operation.
    for spec in specs:
        column_type = spec.get("type")
        if column_type == "round":
            round_column = spec.get("column")
            decimals = spec.get("decimals")
            if not isinstance(round_column, str):
                raise BundleValidationError("round requires string 'column' key")
            if not isinstance(decimals, int):
                raise BundleValidationError("round requires an integer 'decimals' key")
        if column_type == "divide":
            divide_columns = computed_source_columns(spec)
            if len(divide_columns) != 2:
                raise BundleValidationError("divide requires exactly 2 columns")
        if column_type == "scale":
            scale_column = spec.get("column")
            scale_scalar = spec.get("scalar")
            if not isinstance(scale_column, str):
                raise BundleValidationError("scale requires string 'column' key")
            if not isinstance(scale_scalar, (int, float)):
                raise BundleValidationError("scale requires a numeric 'scalar' key")
        if column_type == "add_constant":
            add_constant_column = spec.get("column")
            add_constant_constant = spec.get("constant")
            if not isinstance(add_constant_column, str):
                raise BundleValidationError("add_constant requires string 'column' key")
            if not isinstance(add_constant_constant, (int, float)):
                raise BundleValidationError("add_constant requires a numeric 'constant' key")
        if column_type == "alias":
            alias_column = spec.get("column")
            if not isinstance(alias_column, str):
                raise BundleValidationError("alias requires string 'column' key")
        if column_type == "group_sum":
            group_sum_group_by: str | None = spec.get("group_by")
            group_sum_value_column: str | None = spec.get("value_column")
            group_sum_filter_spec = spec.get("filter")
            if not group_sum_group_by:
                raise BundleValidationError("group_sum requires group_by")
            if not isinstance(group_sum_group_by, str):
                raise BundleValidationError("group_sum 'group_by' must be a string")
            if not group_sum_value_column:
                raise BundleValidationError("group_sum requires value_column")
            if not isinstance(group_sum_value_column, str):
                raise BundleValidationError("group_sum 'value_column' must be a string")
            if group_sum_filter_spec is not None and not isinstance(group_sum_filter_spec, Mapping):
                raise BundleValidationError("group_sum 'filter' must be a mapping when provided")
            if group_sum_filter_spec is not None and "column" not in group_sum_filter_spec:
                raise BundleValidationError("group_sum requires 'filter.column'")
            if group_sum_filter_spec is not None and not isinstance(
                group_sum_filter_spec["column"], str
            ):
                raise BundleValidationError("group_sum requires 'filter.column' to be a string")
            if group_sum_filter_spec is not None and set(group_sum_filter_spec.keys()) != {
                "column",
                "equals",
            }:
                raise BundleValidationError(
                    "group_sum requires 'filter' to contain exactly the fields: 'column'"
                    " and 'equals'"
                )
        if column_type == "group_count":
            group_count_group_by: str | None = spec.get("group_by")
            group_count_filter_spec: dict[str, Any] | None = spec.get("filter")
            if not group_count_group_by:
                raise BundleValidationError("group_count requires group_by")
            if not isinstance(group_count_group_by, str):
                raise BundleValidationError("group_count 'group_by' must be a string")
            if group_count_filter_spec is not None and not isinstance(
                group_count_filter_spec, Mapping
            ):
                raise BundleValidationError("group_count 'filter' must be a mapping when provided")
            if group_count_filter_spec is not None and "column" not in group_count_filter_spec:
                raise BundleValidationError("group_count requires 'filter.column'")
            if group_count_filter_spec is not None and not isinstance(
                group_count_filter_spec["column"], str
            ):
                raise BundleValidationError("group_count requires 'filter.column' to be a string")
            if group_count_filter_spec is not None and set(group_count_filter_spec.keys()) != {
                "column",
                "equals",
            }:
                raise BundleValidationError(
                    "group_count requires 'filter' to contain exactly the fields: 'column' and"
                    " 'equals'"
                )
        if column_type == "date_diff":
            date_diff_start_col: str | None = spec.get("start_column")
            date_diff_end_col: str | None = spec.get("end_column")
            if not date_diff_start_col or not date_diff_end_col:
                raise BundleValidationError("date_diff requires start_column and end_column")
            if not isinstance(date_diff_start_col, str):
                raise BundleValidationError("date_diff 'start_column' must be a string")
            if not isinstance(date_diff_end_col, str):
                raise BundleValidationError("date_diff 'end_column' must be a string")
        if column_type == "days_since_today":
            days_since_today_column: str | None = spec.get("column")
            if not days_since_today_column:
                raise BundleValidationError("days_since_today requires column")
            if not isinstance(days_since_today_column, str):
                raise BundleValidationError("days_since_today 'column' must be a string")
        if column_type == "years_since_year":
            years_since_year_column: str | None = spec.get("column")
            if not years_since_year_column:
                raise BundleValidationError("years_since_year requires column")
            if not isinstance(years_since_year_column, str):
                raise BundleValidationError("years_since_year 'column' must be a string")


def apply_computed_columns(df: pd.DataFrame, specs: list[dict[str, Any]]) -> pd.DataFrame:
    """Return a copy of df with rule-bundle computed columns added."""

    computed = df.copy()
    for spec in specs:
        column_name = computed_column_name(spec)
        computed[column_name] = compute_column(computed, spec)
    return computed


def _normalize_integral_result(result: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(result, errors="coerce")

    non_null = numeric.dropna()
    if not non_null.empty and (non_null % 1 == 0).all():
        return numeric.astype("Int64")

    return result


def compute_column(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    column_type = spec.get("type")
    if column_type == "sum":
        columns = computed_source_columns(spec)
        result = pd.Series(df[columns].sum(axis=1, min_count=1), index=df.index)
        return _normalize_integral_result(result)
    if column_type == "subtract":
        columns = computed_source_columns(spec)
        sub_result: pd.Series = df[columns[0]].copy()
        for i in range(1, len(columns)):
            sub_result = sub_result - df[columns[i]]
        return _normalize_integral_result(sub_result)
    if column_type == "multiply":
        columns = computed_source_columns(spec)
        mul_result: pd.Series = df[columns[0]].copy()
        for i in range(1, len(columns)):
            mul_result = mul_result * df[columns[i]]
        return _normalize_integral_result(mul_result)
    if column_type == "divide":
        columns = computed_source_columns(spec)
        numerator = df[columns[0]]
        denominator = df[columns[1]]
        return numerator / denominator.where(denominator != 0)
    if column_type == "coalesce":
        columns = computed_source_columns(spec)
        return df[columns].bfill(axis=1).iloc[:, 0]
    if column_type == "group_sum":
        result = _compute_group_sum(df, spec)
        return _normalize_integral_result(result)
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
    if column_type == "scale":
        scale_column = spec.get("column")
        scalar = spec.get("scalar")

        if not isinstance(scale_column, str):
            raise BundleValidationError("scale requires string 'column' key")
        if not isinstance(scalar, (int, float)):
            raise BundleValidationError("scale requires a numeric 'scalar' key")

        result = pd.Series(df[scale_column] * scalar, index=df.index)
        return _normalize_integral_result(result)
    if column_type == "add_constant":
        add_constant_column = spec.get("column")
        add_constant_constant = spec.get("constant")

        if not isinstance(add_constant_column, str):
            raise BundleValidationError("add_constant requires string 'column' key")
        if not isinstance(add_constant_constant, (int, float)):
            raise BundleValidationError("add_constant requires a numeric 'constant' key")

        result = pd.Series(df[add_constant_column] + add_constant_constant, index=df.index)
        return _normalize_integral_result(result)
    if column_type == "round":
        round_column = spec.get("column")
        round_decimals = spec.get("decimals")

        if not isinstance(round_column, str):
            raise BundleValidationError("round requires string 'column' key")
        if not isinstance(round_decimals, int):
            raise BundleValidationError("round requires an integer 'decimals' key")

        return pd.Series(df[round_column].round(round_decimals), index=df.index)
    if column_type == "alias":
        column = spec.get("column")
        return df[column].copy()
    if column_type == "contains_substring":
        return _compute_contains_substring(df, spec)
    raise BundleValidationError(f"Unsupported computed column type: {column_type}")


def _compute_group_sum(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    group_by: str | None = spec.get("group_by")
    value_column: str | None = spec.get("value_column")
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


def _compute_contains_substring(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    """Check if any listed column contains the specified substring for the row."""
    columns = computed_source_columns(spec)
    substring = spec.get("substring")
    case_sense_flag = spec.get("case_sense_flag", False)

    if not substring:
        raise ValueError("contains_substring requires a substring")

    contains = pd.Series(False, index=df.index)

    for col in columns:
        s = df[col].astype(str)

        if case_sense_flag:
            # Case-sensitive: "Apple" matches "Apple pie", but not "apple pie"
            contains = contains | s.astype(str).str.contains(substring, regex=False)
        else:
            # Case-insensitive prefix match
            contains = contains | s.astype(str).str.contains(substring, case=False, regex=False)

    return contains.astype(int)


def computed_column_name(spec: dict[str, Any]):
    name = spec.get("name") or spec.get("id")
    if not name:
        raise BundleValidationError("Computed columns must define a name or id")
    return name


def computed_source_columns(spec: dict[str, Any]) -> list[str]:
    """Return the ``columns`` list for arithmetic/coalesce types."""
    columns = spec.get("columns")
    if not isinstance(columns, list) or not columns:
        raise BundleValidationError("Computed columns must define a non-empty columns list")
    if not all(isinstance(column, str) for column in columns):
        raise BundleValidationError("Computed columns 'columns' list must contain only strings")
    return [column for column in columns]


def required_input_columns(spec: dict[str, Any]) -> set[str]:
    """Return all input column names referenced by a computed column spec."""
    column_type = spec.get("type")
    if column_type in {"sum", "subtract", "multiply", "divide", "coalesce"}:
        return set(computed_source_columns(spec))
    if column_type == "group_sum":
        refs: set[str] = set()
        if group_by := spec.get("group_by"):
            refs.add(group_by)
        if value_column := spec.get("value_column"):
            refs.add(value_column)
        filter_spec = spec.get("filter")
        if isinstance(filter_spec, Mapping):
            if col := filter_spec.get("column"):
                refs.add(col)
        return refs
    if column_type == "group_count":
        refs = set()
        if group_by := spec.get("group_by"):
            refs.add(group_by)
        filter_spec = spec.get("filter")
        if isinstance(filter_spec, Mapping):
            if col := filter_spec.get("column"):
                refs.add(col)
        return refs
    if column_type == "date_diff":
        refs = set()
        if start_col := spec.get("start_column"):
            refs.add(start_col)
        if end_col := spec.get("end_column"):
            refs.add(end_col)
        return refs
    if column_type == "days_since_today":
        if col := spec.get("column"):
            return {col}
        return set()
    if column_type == "years_since_year":
        if col := spec.get("column"):
            return {col}
        return set()
    if column_type == "all_blank_or_zero":
        return set(computed_source_columns(spec))
    if column_type in {"scale", "add_constant", "round", "alias"}:
        if col := spec.get("column"):
            return {col}
        return set()
    return set()


def collect_computed_column_names(specs: list[dict[str, Any]]) -> set[str]:
    return {computed_column_name(spec) for spec in specs}


def collect_computed_source_columns(specs: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for spec in specs:
        result.update(required_input_columns(spec))
    return result
