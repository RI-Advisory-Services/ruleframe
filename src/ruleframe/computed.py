from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
from dateutil import parser as date_parser


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
        numeric = df[columns].apply(pd.to_numeric, errors="coerce")
        return numeric.sum(axis=1, min_count=1)
    if column_type == "subtract":
        columns = computed_source_columns(spec)
        numeric = df[columns].apply(pd.to_numeric, errors="coerce")
        result = numeric.iloc[:, 0].copy()
        for i in range(1, len(columns)):
            result = result - numeric.iloc[:, i]
        return result
    if column_type == "multiply":
        columns = computed_source_columns(spec)
        numeric = df[columns].apply(pd.to_numeric, errors="coerce")
        result = numeric.iloc[:, 0].copy()
        for i in range(1, len(columns)):
            result = result * numeric.iloc[:, i]
        return result
    if column_type == "divide":
        columns = computed_source_columns(spec)
        if len(columns) != 2:
            raise ValueError("divide requires exactly 2 columns")
        numerator = pd.to_numeric(df[columns[0]], errors="coerce")
        denominator = pd.to_numeric(df[columns[1]], errors="coerce")
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
    raise ValueError(f"Unsupported computed column type: {column_type}")


def _compute_group_sum(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    group_by: str | None = spec.get("group_by")
    value_column: str | None = spec.get("value_column")
    if not group_by or not value_column:
        raise ValueError("group_sum requires group_by and value_column")

    numeric_values = pd.to_numeric(df[value_column], errors="coerce")
    filter_spec: dict[str, Any] | None = spec.get("filter")
    if filter_spec:
        mask: pd.Series = df[filter_spec["column"]] == filter_spec["equals"]
        group_totals = numeric_values[mask].groupby(df.loc[mask, group_by]).sum()
        result = df[group_by].map(group_totals)
        return result.where(mask)
    else:
        group_totals = numeric_values.groupby(df[group_by]).sum()
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
        return result.where(mask)
    else:
        group_counts = df.groupby(group_by).size()
        return df[group_by].map(group_counts)


def _parse_date(value: Any) -> datetime.datetime | None:
    """Parse a value to datetime, returning None if null or unparseable."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    try:
        return date_parser.parse(str(value).strip())
    except (ValueError, OverflowError):
        return None


def _compute_date_diff(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    """Return (end_column - start_column) in whole days."""
    start_col: str | None = spec.get("start_column")
    end_col: str | None = spec.get("end_column")
    if not start_col or not end_col:
        raise ValueError("date_diff requires start_column and end_column")

    def _diff(row: pd.Series) -> float | None:
        start = _parse_date(row[start_col])
        end = _parse_date(row[end_col])
        if start is None or end is None:
            return None
        return float((end - start).days)

    return df.apply(_diff, axis=1)


def _compute_days_since_today(
    df: pd.DataFrame,
    spec: dict[str, Any],
    today: datetime.date | None = None,
) -> pd.Series:
    """Return (today - column) in whole days."""
    column: str | None = spec.get("column")
    if not column:
        raise ValueError("days_since_today requires column")

    reference = datetime.datetime(
        *(today or datetime.date.today()).timetuple()[:3]
    )

    def _diff(value: Any) -> float | None:
        parsed = _parse_date(value)
        if parsed is None:
            return None
        return float((reference - parsed).days)

    return df[column].apply(_diff)


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

    def _diff(value: Any) -> float | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            return float(year - int(float(str(value).strip())))
        except (ValueError, TypeError):
            return None

    return df[column].apply(_diff)


def _compute_all_blank_or_zero(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    """Return 1 if all listed columns are blank or zero for the row, else 0."""
    columns = computed_source_columns(spec)

    def _check(row: pd.Series) -> int:
        for col in columns:
            val = row[col]
            if pd.isna(val):
                continue
            try:
                if float(val) != 0.0:
                    return 0
            except (ValueError, TypeError):
                if str(val).strip() != "":
                    return 0
        return 1

    return df.apply(_check, axis=1)


def computed_column_name(spec: dict[str, Any]) -> str:
    name = spec.get("name") or spec.get("id")
    if not name:
        raise ValueError("Computed columns must define a name or id")
    return str(name)


def computed_source_columns(spec: dict[str, Any]) -> list[str]:
    """Return the ``columns`` list for types that use it (sum, subtract, multiply, divide, coalesce)."""
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
