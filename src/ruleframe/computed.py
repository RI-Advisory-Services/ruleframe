from __future__ import annotations

from typing import Any

import pandas as pd


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
    raise ValueError(f"Unsupported computed column type: {column_type}")


def computed_column_name(spec: dict[str, Any]) -> str:
    name = spec.get("name") or spec.get("id")
    if not name:
        raise ValueError("Computed columns must define a name or id")
    return str(name)


def computed_source_columns(spec: dict[str, Any]) -> list[str]:
    columns = spec.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Computed columns must define a non-empty columns list")
    return [str(column) for column in columns]


def collect_computed_column_names(specs: list[dict[str, Any]]) -> set[str]:
    return {computed_column_name(spec) for spec in specs}


def collect_computed_source_columns(specs: list[dict[str, Any]]) -> set[str]:
    required: set[str] = set()
    for spec in specs:
        required.update(computed_source_columns(spec))
    return required
