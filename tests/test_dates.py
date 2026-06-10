"""Tests for the canonical date normalization and parsing utilities in dates.py."""

import datetime

import pandas as pd

from ruleframe.dates import normalize_date_series, parse_date_value

# ===========================================================================
# normalize_date_series — flexible parsing (no fmt)
# ===========================================================================


def test_normalize_iso_strings() -> None:
    s = pd.Series(["2024-01-15", "2024-03-25"])
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.iloc[1] == pd.Timestamp("2024-03-25")


def test_normalize_us_format_month_first() -> None:
    # MM/DD/YYYY — standard US form; dayfirst=False means month is first
    s = pd.Series(["03/25/2024", "01/05/2024"])
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-03-25")
    assert result.iloc[1] == pd.Timestamp("2024-01-05")


def test_normalize_variable_width_month_day() -> None:
    # Single-digit month and day are handled correctly
    s = pd.Series(["3/5/2024", "3/25/2024", "03/05/2024"])
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-03-05")
    assert result.iloc[1] == pd.Timestamp("2024-03-25")
    assert result.iloc[2] == pd.Timestamp("2024-03-05")


def test_normalize_drops_time_component() -> None:
    s = pd.Series(["2024-01-15 14:32:00", "2024-03-25T09:00:00"])
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.iloc[0].hour == 0
    assert result.iloc[1] == pd.Timestamp("2024-03-25")


def test_normalize_unparseable_becomes_nat() -> None:
    s = pd.Series(["not-a-date", "2024-01-15"])
    result = normalize_date_series(s)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pd.Timestamp("2024-01-15")


def test_normalize_null_values_become_nat() -> None:
    s = pd.Series([None, "2024-01-15", float("nan")])
    result = normalize_date_series(s)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pd.Timestamp("2024-01-15")
    assert pd.isna(result.iloc[2])


def test_normalize_already_datetime64_passthrough() -> None:
    s = pd.to_datetime(pd.Series(["2024-01-15", "2024-03-25"]))
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.dtype == "datetime64[ns]"


def test_normalize_already_datetime64_drops_time() -> None:
    s = pd.to_datetime(pd.Series(["2024-01-15 14:32:00"]))
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.iloc[0].hour == 0


def test_normalize_tz_aware_strips_timezone() -> None:
    # tz-aware series: timezone is stripped, only calendar date is kept
    s = pd.to_datetime(pd.Series(["2024-01-15T14:00:00-05:00"]), utc=True)
    result = normalize_date_series(s)
    assert result.dt.tz is None
    assert result.dtype == "datetime64[ns]"
    # UTC conversion: 14:00 ET = 19:00 UTC → still 2024-01-15 calendar date
    assert result.iloc[0] == pd.Timestamp("2024-01-15")


def test_normalize_tz_aware_date_boundary() -> None:
    # 23:00 EST = 04:00 UTC next day — calendar date shifts, we keep the UTC date
    s = pd.to_datetime(pd.Series(["2024-01-15T23:00:00-05:00"]), utc=True)
    result = normalize_date_series(s)
    assert result.dt.tz is None
    # UTC conversion: 23:00 EST = 04:00 UTC on 2024-01-16
    assert result.iloc[0] == pd.Timestamp("2024-01-16")


def test_normalize_empty_series() -> None:
    s = pd.Series([], dtype=object)
    result = normalize_date_series(s)
    assert len(result) == 0


def test_normalize_mixed_formats_in_same_series() -> None:
    # ISO and US formats mixed — both should parse in flexible mode
    s = pd.Series(["2024-03-25", "03/25/2024"])
    result = normalize_date_series(s)
    assert result.iloc[0] == pd.Timestamp("2024-03-25")
    assert result.iloc[1] == pd.Timestamp("2024-03-25")


def test_normalize_returns_datetime64_dtype() -> None:
    s = pd.Series(["2024-01-15"])
    result = normalize_date_series(s)
    assert pd.api.types.is_datetime64_any_dtype(result)


# ===========================================================================
# normalize_date_series — strict format (fmt supplied)
# ===========================================================================


def test_normalize_strict_format_us() -> None:
    s = pd.Series(["01/15/2024", "03/25/2024", "3/5/2024"])
    result = normalize_date_series(s, fmt="%m/%d/%Y")
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.iloc[1] == pd.Timestamp("2024-03-25")
    assert result.iloc[2] == pd.Timestamp("2024-03-05")


def test_normalize_strict_format_rejects_iso_when_us_declared() -> None:
    # ISO format does not match %m/%d/%Y → NaT
    s = pd.Series(["2024-01-15", "01/15/2024"])
    result = normalize_date_series(s, fmt="%m/%d/%Y")
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pd.Timestamp("2024-01-15")


def test_normalize_strict_format_iso() -> None:
    s = pd.Series(["2024-01-15", "2024-03-25"])
    result = normalize_date_series(s, fmt="%Y-%m-%d")
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.iloc[1] == pd.Timestamp("2024-03-25")


def test_normalize_strict_format_drops_time() -> None:
    # Even with strict format, time component is discarded
    s = pd.Series(["01/15/2024"])
    result = normalize_date_series(s, fmt="%m/%d/%Y")
    assert result.iloc[0] == pd.Timestamp("2024-01-15")
    assert result.iloc[0].hour == 0


# ===========================================================================
# parse_date_value
# ===========================================================================


def test_parse_date_value_from_timestamp() -> None:
    ts = pd.Timestamp("2024-03-15")
    assert parse_date_value(ts) == datetime.date(2024, 3, 15)


def test_parse_date_value_from_iso_string() -> None:
    assert parse_date_value("2024-03-15") == datetime.date(2024, 3, 15)


def test_parse_date_value_from_us_string() -> None:
    assert parse_date_value("3/25/2024") == datetime.date(2024, 3, 25)


def test_parse_date_value_from_datetime_date() -> None:
    d = datetime.date(2024, 3, 15)
    assert parse_date_value(d) == d


def test_parse_date_value_from_datetime_datetime() -> None:
    dt = datetime.datetime(2024, 3, 15, 14, 32)
    assert parse_date_value(dt) == datetime.date(2024, 3, 15)


def test_parse_date_value_strips_time_from_string() -> None:
    assert parse_date_value("2024-03-15 14:32:00") == datetime.date(2024, 3, 15)


def test_parse_date_value_returns_none_for_none() -> None:
    assert parse_date_value(None) is None


def test_parse_date_value_returns_none_for_nat() -> None:
    assert parse_date_value(pd.NaT) is None


def test_parse_date_value_returns_none_for_nan() -> None:
    assert parse_date_value(float("nan")) is None


def test_parse_date_value_returns_none_for_unparseable() -> None:
    assert parse_date_value("not-a-date") is None


def test_parse_date_value_returns_none_for_empty_string() -> None:
    assert parse_date_value("") is None
    assert parse_date_value("   ") is None
