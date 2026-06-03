"""Canonical date parsing and normalization utilities for RuleFrame.

All date handling in the library flows through this module. The internal
representation for date columns is tz-naive ``datetime64[ns]`` with the time
component truncated to midnight. Hours, minutes, and timezone offsets are
intentionally discarded — the library works with calendar dates only.

Parsing strategy (flexible mode, no ``fmt`` supplied):
- ``pd.to_datetime`` with ``dayfirst=False`` handles the vast majority of
  formats including ISO (``YYYY-MM-DD``) and US month-first (``MM/DD/YYYY``,
  ``M/D/YYYY``).
- A ``dateutil`` fallback covers edge cases that pandas cannot infer.
- Ambiguous day-first formats (e.g. ``DD/MM/YYYY``) will be read as month-first
  in the flexible mode. Use ``date_format`` in bundle settings for strict
  format enforcement when the source is known to be day-first.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
from dateutil import parser as date_parser


def normalize_date_series(series: pd.Series, fmt: str | None = None) -> pd.Series:
    """Parse and normalize a Series to tz-naive ``datetime64[ns]`` at midnight.

    Args:
        series: Input series — may contain strings, ``pd.Timestamp`` objects,
                ``datetime.date``/``datetime.datetime`` objects, or a mix.
        fmt:    Optional ``strftime`` format string for strict parsing (e.g.
                ``"%m/%d/%Y"``). When provided, values that do not match the
                format become ``NaT`` rather than being guessed. When omitted,
                flexible parsing is used (``dayfirst=False``).

    Returns:
        A ``datetime64[ns]`` Series. Unparseable values and nulls become ``NaT``.
        The time component is always truncated to midnight.
    """
    # Already a datetime dtype — only need to strip timezone and normalize
    if pd.api.types.is_datetime64_any_dtype(series):
        result = series
        if hasattr(result, "dt") and result.dt.tz is not None:
            result = result.dt.tz_convert("UTC").dt.tz_localize(None)
        return result.dt.normalize()

    if fmt is not None:
        result = pd.to_datetime(series, format=fmt, errors="coerce")
    else:
        result = pd.to_datetime(series, dayfirst=False, errors="coerce")
        # Fallback: try dateutil for any non-null values pandas could not parse
        failed_mask = result.isna() & series.notna()
        if failed_mask.any():
            for idx in series.index[failed_mask]:
                val = series.at[idx]
                parsed = _parse_single_value(val)
                if parsed is not None:
                    result.at[idx] = pd.Timestamp(parsed)

    return result.dt.normalize()


def parse_date_value(value: Any) -> datetime.date | None:
    """Parse a single value to a ``datetime.date``, returning ``None`` on failure.

    Used by operators for per-row evaluation. Accepts ``pd.Timestamp``,
    ``datetime.datetime``, ``datetime.date``, and ISO/US date strings.
    Timezone info is stripped; only the calendar date is returned.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date_parser.parse(value.strip(), dayfirst=False).date()
        except (ValueError, OverflowError):
            return None
    return None


def _parse_single_value(value: Any) -> datetime.datetime | None:
    """Parse a single value to ``datetime.datetime`` for use in the dateutil fallback."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, str) and value.strip():
        try:
            return date_parser.parse(value.strip(), dayfirst=False)
        except (ValueError, OverflowError):
            return None
    return None
