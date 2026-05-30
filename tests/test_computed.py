import datetime

import pandas as pd
import pytest

from ruleframe import validate_dataframe
from ruleframe.computed import (
    _compute_days_since_today,
    _compute_years_since_year,
    collect_computed_source_columns,
    compute_column,
    required_input_columns,
    validate_computed_column_specs,
)
from ruleframe.exceptions import BundleValidationError

# ===========================================================================
# Guard tests: validate_computed_column_specs and name collision
# ===========================================================================


def test_guard_self_reference_raises() -> None:
    specs = [{"type": "sum", "columns": ["A", "My Total"], "id": "my_total", "name": "My Total"}]
    with pytest.raises(BundleValidationError, match="references itself"):
        validate_computed_column_specs(specs)


def test_guard_out_of_order_raises() -> None:
    # Step 2 is declared before Step 1, which generates the column Step 2 needs
    specs = [
        {
            "type": "subtract",
            "columns": ["Total", "Reported"],
            "id": "variance",
            "name": "Variance",
        },
        {"type": "sum", "columns": ["A", "B"], "id": "total", "name": "Total"},
    ]
    with pytest.raises(BundleValidationError, match="must be declared earlier"):
        validate_computed_column_specs(specs)


def test_guard_cycle_raises() -> None:
    # A depends on B, B depends on A — impossible to resolve
    specs = [
        {"type": "subtract", "columns": ["B Col", "X"], "id": "a_col", "name": "A Col"},
        {"type": "subtract", "columns": ["A Col", "X"], "id": "b_col", "name": "B Col"},
    ]
    # Out-of-order check fires first (B Col not yet generated when A Col is declared)
    # so either BundleValidationError is acceptable here
    with pytest.raises(BundleValidationError):
        validate_computed_column_specs(specs)


def test_guard_valid_chain_does_not_raise() -> None:
    # Correct order: Total declared before Variance
    specs = [
        {"type": "sum", "columns": ["A", "B"], "id": "total", "name": "Total"},
        {
            "type": "subtract",
            "columns": ["Total", "Reported"],
            "id": "variance",
            "name": "Variance",
        },
    ]
    validate_computed_column_specs(specs)  # should not raise


def test_guard_unsupported_type_raises() -> None:
    specs = [{"type": "percentile", "columns": ["A", "B"], "id": "pct", "name": "Percentile"}]
    with pytest.raises(BundleValidationError, match="unsupported type"):
        validate_computed_column_specs(specs)


# ===========================================================================
# Unit tests: small inline DataFrames for edge cases
# ===========================================================================

# ---------------------------------------------------------------------------
# subtract
# ---------------------------------------------------------------------------


def test_subtract_two_columns() -> None:
    df = pd.DataFrame({"A": [10.0, 20.0], "B": [3.0, 5.0]})
    spec = {"type": "subtract", "columns": ["A", "B"], "id": "result"}
    result = compute_column(df, spec)
    assert result.tolist() == [7.0, 15.0]


def test_subtract_three_columns_is_left_associative() -> None:
    df = pd.DataFrame({"A": [20.0], "B": [5.0], "C": [2.0]})
    spec = {"type": "subtract", "columns": ["A", "B", "C"], "id": "result"}
    result = compute_column(df, spec)
    # 20 - 5 - 2 = 13
    assert result.tolist() == [13.0]


def test_subtract_coerces_non_numeric_to_nan() -> None:
    df = pd.DataFrame({"A": [10.0, "bad"], "B": [3.0, 2.0]})
    result = compute_column(df, {"type": "subtract", "columns": ["A", "B"], "id": "r"})
    assert result.iloc[0] == 7.0
    assert pd.isna(result.iloc[1])


# ---------------------------------------------------------------------------
# multiply
# ---------------------------------------------------------------------------


def test_multiply_two_columns() -> None:
    df = pd.DataFrame({"A": [3.0, 4.0], "B": [2.0, 5.0]})
    spec = {"type": "multiply", "columns": ["A", "B"], "id": "result"}
    result = compute_column(df, spec)
    assert result.tolist() == [6.0, 20.0]


def test_multiply_three_columns() -> None:
    df = pd.DataFrame({"A": [2.0], "B": [3.0], "C": [4.0]})
    result = compute_column(df, {"type": "multiply", "columns": ["A", "B", "C"], "id": "r"})
    assert result.tolist() == [24.0]


# ---------------------------------------------------------------------------
# divide
# ---------------------------------------------------------------------------


def test_divide_two_columns() -> None:
    df = pd.DataFrame({"A": [10.0, 20.0], "B": [2.0, 4.0]})
    result = compute_column(df, {"type": "divide", "columns": ["A", "B"], "id": "r"})
    assert result.tolist() == [5.0, 5.0]


def test_divide_returns_nan_for_zero_denominator() -> None:
    df = pd.DataFrame({"A": [10.0, 20.0], "B": [0.0, 4.0]})
    result = compute_column(df, {"type": "divide", "columns": ["A", "B"], "id": "r"})
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == 5.0


def test_divide_requires_exactly_two_columns() -> None:
    df = pd.DataFrame({"A": [1.0], "B": [2.0], "C": [3.0]})
    with pytest.raises(ValueError, match="exactly 2"):
        compute_column(df, {"type": "divide", "columns": ["A", "B", "C"], "id": "r"})


# ---------------------------------------------------------------------------
# coalesce
# ---------------------------------------------------------------------------


def test_coalesce_returns_first_non_null_per_row() -> None:
    df = pd.DataFrame(
        {
            "A": [None, 2.0, None],
            "B": [1.0, None, None],
            "C": [3.0, 4.0, 5.0],
        }
    )
    result = compute_column(df, {"type": "coalesce", "columns": ["A", "B", "C"], "id": "r"})
    assert result.iloc[0] == 1.0  # A is null, B=1.0 wins
    assert result.iloc[1] == 2.0  # A=2.0 wins
    assert result.iloc[2] == 5.0  # A and B are null, C=5.0 wins


def test_coalesce_returns_nan_when_all_null() -> None:
    df = pd.DataFrame({"A": [None], "B": [None]})
    result = compute_column(df, {"type": "coalesce", "columns": ["A", "B"], "id": "r"})
    assert pd.isna(result.iloc[0])


def test_coalesce_works_with_string_columns() -> None:
    df = pd.DataFrame({"A": [None, "hello"], "B": ["world", None]})
    result = compute_column(df, {"type": "coalesce", "columns": ["A", "B"], "id": "r"})
    assert result.iloc[0] == "world"
    assert result.iloc[1] == "hello"


# ---------------------------------------------------------------------------
# group_sum
# ---------------------------------------------------------------------------


def test_group_sum_without_filter_maps_total_to_all_rows() -> None:
    df = pd.DataFrame(
        {
            "Project ID": ["P1", "P1", "P2"],
            "kWh": [5.0, 3.0, 7.0],
        }
    )
    spec = {"type": "group_sum", "group_by": "Project ID", "value_column": "kWh", "id": "r"}
    result = compute_column(df, spec)
    # P1 total = 8, P2 total = 7; every row in the group gets the group total
    assert result.tolist() == [8.0, 8.0, 7.0]


def test_group_sum_with_filter_only_returns_value_on_matching_rows() -> None:
    df = pd.DataFrame(
        {
            "Project ID": ["P1", "P1", "P2"],
            "Measure": ["BEF", "LED", "BEF"],
            "kWh": [5.0, 3.0, 7.0],
        }
    )
    spec = {
        "type": "group_sum",
        "group_by": "Project ID",
        "value_column": "kWh",
        "filter": {"column": "Measure", "equals": "BEF"},
        "id": "r",
    }
    result = compute_column(df, spec)
    assert result.iloc[0] == 5.0  # P1 BEF total = 5
    assert pd.isna(result.iloc[1])  # LED row — not matching filter
    assert result.iloc[2] == 7.0  # P2 BEF total = 7


def test_group_sum_coerces_non_numeric_to_zero() -> None:
    df = pd.DataFrame(
        {
            "Project ID": ["P1", "P1"],
            "kWh": [5.0, "bad"],
        }
    )
    spec = {"type": "group_sum", "group_by": "Project ID", "value_column": "kWh", "id": "r"}
    result = compute_column(df, spec)
    # "bad" coerces to NaN; groupby sum skips NaN by default → P1 total = 5
    assert result.tolist() == [5.0, 5.0]


# ---------------------------------------------------------------------------
# group_count
# ---------------------------------------------------------------------------


def test_group_count_without_filter() -> None:
    df = pd.DataFrame(
        {
            "Project ID": ["P1", "P1", "P2"],
            "Value": [1, 2, 3],
        }
    )
    spec = {"type": "group_count", "group_by": "Project ID", "id": "r"}
    result = compute_column(df, spec)
    assert result.tolist() == [2, 2, 1]


def test_group_count_with_filter_returns_nan_on_non_matching_rows() -> None:
    df = pd.DataFrame(
        {
            "Project ID": ["P1", "P1", "P2"],
            "Status": ["Active", "Pending", "Active"],
        }
    )
    spec = {
        "type": "group_count",
        "group_by": "Project ID",
        "filter": {"column": "Status", "equals": "Active"},
        "id": "r",
    }
    result = compute_column(df, spec)
    assert result.iloc[0] == 1  # P1 has 1 Active row
    assert pd.isna(result.iloc[1])  # Pending row — not matching filter
    assert result.iloc[2] == 1  # P2 has 1 Active row


# ---------------------------------------------------------------------------
# required_input_columns / collect_computed_source_columns
# ---------------------------------------------------------------------------


def test_required_input_columns_for_sum_type() -> None:
    spec = {"type": "sum", "columns": ["A", "B"], "id": "r"}
    assert required_input_columns(spec) == {"A", "B"}


def test_required_input_columns_for_group_sum() -> None:
    spec = {
        "type": "group_sum",
        "group_by": "Project ID",
        "value_column": "kWh",
        "filter": {"column": "Measure", "equals": "BEF"},
        "id": "r",
    }
    assert required_input_columns(spec) == {"Project ID", "kWh", "Measure"}


def test_required_input_columns_for_group_count_no_filter() -> None:
    spec = {"type": "group_count", "group_by": "Project ID", "id": "r"}
    assert required_input_columns(spec) == {"Project ID"}


def test_collect_computed_source_columns_handles_mixed_types() -> None:
    specs = [
        {"type": "sum", "columns": ["A", "B"], "id": "sum_col"},
        {
            "type": "group_sum",
            "group_by": "Group",
            "value_column": "Amount",
            "filter": {"column": "Type", "equals": "X"},
            "id": "group_col",
        },
    ]
    assert collect_computed_source_columns(specs) == {"A", "B", "Group", "Amount", "Type"}


# ---------------------------------------------------------------------------
# date_diff
# ---------------------------------------------------------------------------


def test_date_diff_returns_days_between_columns() -> None:
    df = pd.DataFrame(
        {
            "Start": ["2024-01-01", "2024-03-01"],
            "End": ["2024-01-11", "2024-03-01"],
        }
    )
    spec = {"type": "date_diff", "start_column": "Start", "end_column": "End", "id": "r"}
    result = compute_column(df, spec)
    assert result.tolist() == [10.0, 0.0]


def test_date_diff_end_before_start_returns_negative() -> None:
    df = pd.DataFrame({"Start": ["2024-06-01"], "End": ["2024-05-25"]})
    spec = {"type": "date_diff", "start_column": "Start", "end_column": "End", "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] == -7.0


def test_date_diff_handles_pandas_timestamps() -> None:
    df = pd.DataFrame(
        {
            "Start": pd.to_datetime(["2024-01-01"]),
            "End": pd.to_datetime(["2024-01-06"]),
        }
    )
    spec = {"type": "date_diff", "start_column": "Start", "end_column": "End", "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] == 5.0


def test_date_diff_returns_none_when_either_date_is_null() -> None:
    df = pd.DataFrame(
        {
            "Start": ["2024-01-01", None],
            "End": [None, "2024-01-06"],
        }
    )
    spec = {"type": "date_diff", "start_column": "Start", "end_column": "End", "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] is None or pd.isna(result.iloc[0])
    assert result.iloc[1] is None or pd.isna(result.iloc[1])


def test_date_diff_returns_none_for_unparseable_date() -> None:
    df = pd.DataFrame({"Start": ["not-a-date"], "End": ["2024-01-06"]})
    spec = {"type": "date_diff", "start_column": "Start", "end_column": "End", "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] is None or pd.isna(result.iloc[0])


def test_date_diff_required_input_columns() -> None:
    spec = {
        "type": "date_diff",
        "start_column": "Installation Date",
        "end_column": "Date Inspected",
        "id": "r",
    }
    assert required_input_columns(spec) == {"Installation Date", "Date Inspected"}


# ---------------------------------------------------------------------------
# days_since_today
# ---------------------------------------------------------------------------


def test_days_since_today_uses_injected_today() -> None:
    df = pd.DataFrame({"Install Date": ["2024-01-01", "2024-01-11"]})
    spec = {"type": "days_since_today", "column": "Install Date", "id": "r"}
    today = datetime.date(2024, 1, 21)
    result = _compute_days_since_today(df, spec, today=today)
    assert result.tolist() == [20.0, 10.0]


def test_days_since_today_returns_none_for_null() -> None:
    df = pd.DataFrame({"Install Date": [None, "2024-01-01"]})
    spec = {"type": "days_since_today", "column": "Install Date", "id": "r"}
    today = datetime.date(2024, 1, 11)
    result = _compute_days_since_today(df, spec, today=today)
    assert result.iloc[0] is None or pd.isna(result.iloc[0])
    assert result.iloc[1] == 10.0


def test_days_since_today_returns_none_for_unparseable() -> None:
    df = pd.DataFrame({"Install Date": ["not-a-date"]})
    spec = {"type": "days_since_today", "column": "Install Date", "id": "r"}
    today = datetime.date(2024, 1, 11)
    result = _compute_days_since_today(df, spec, today=today)
    assert result.iloc[0] is None or pd.isna(result.iloc[0])


def test_days_since_today_required_input_columns() -> None:
    spec = {"type": "days_since_today", "column": "Installation Date", "id": "r"}
    assert required_input_columns(spec) == {"Installation Date"}


# ---------------------------------------------------------------------------
# years_since_year
# ---------------------------------------------------------------------------


def test_years_since_year_returns_age() -> None:
    df = pd.DataFrame({"Year": [2000, 2010, 2020]})
    spec = {"type": "years_since_year", "column": "Year", "id": "r"}
    result = _compute_years_since_year(df, spec, current_year=2024)
    assert result.tolist() == [24.0, 14.0, 4.0]


def test_years_since_year_returns_none_for_null() -> None:
    df = pd.DataFrame({"Year": [None, 2010]})
    spec = {"type": "years_since_year", "column": "Year", "id": "r"}
    result = _compute_years_since_year(df, spec, current_year=2024)
    assert result.iloc[0] is None or pd.isna(result.iloc[0])
    assert result.iloc[1] == 14.0


def test_years_since_year_returns_none_for_unparseable() -> None:
    df = pd.DataFrame({"Year": ["not-a-year"]})
    spec = {"type": "years_since_year", "column": "Year", "id": "r"}
    result = _compute_years_since_year(df, spec, current_year=2024)
    assert result.iloc[0] is None or pd.isna(result.iloc[0])


def test_years_since_year_accepts_float_year_values() -> None:
    # CSVs often read integer years as floats
    df = pd.DataFrame({"Year": [2005.0, 2015.0]})
    spec = {"type": "years_since_year", "column": "Year", "id": "r"}
    result = _compute_years_since_year(df, spec, current_year=2025)
    assert result.tolist() == [20.0, 10.0]


def test_years_since_year_required_input_columns() -> None:
    spec = {"type": "years_since_year", "column": "Installation Year", "id": "r"}
    assert required_input_columns(spec) == {"Installation Year"}


# ---------------------------------------------------------------------------
# all_blank_or_zero
# ---------------------------------------------------------------------------


def test_all_blank_or_zero_returns_1_when_all_zero() -> None:
    df = pd.DataFrame({"A": [0.0], "B": [0.0], "C": [0.0]})
    spec = {"type": "all_blank_or_zero", "columns": ["A", "B", "C"], "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] == 1


def test_all_blank_or_zero_returns_1_when_all_null() -> None:
    df = pd.DataFrame({"A": [None], "B": [None]})
    result = compute_column(df, {"type": "all_blank_or_zero", "columns": ["A", "B"], "id": "r"})
    assert result.iloc[0] == 1


def test_all_blank_or_zero_returns_1_when_mix_of_zero_and_null() -> None:
    df = pd.DataFrame({"A": [0.0], "B": [None], "C": [0.0]})
    spec = {"type": "all_blank_or_zero", "columns": ["A", "B", "C"], "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] == 1


def test_all_blank_or_zero_returns_0_when_any_nonzero() -> None:
    df = pd.DataFrame({"A": [0.0], "B": [5.0], "C": [0.0]})
    spec = {"type": "all_blank_or_zero", "columns": ["A", "B", "C"], "id": "r"}
    result = compute_column(df, spec)
    assert result.iloc[0] == 0


def test_all_blank_or_zero_required_input_columns() -> None:
    spec = {"type": "all_blank_or_zero", "columns": ["kWh", "kW", "Therms"], "id": "r"}
    assert required_input_columns(spec) == {"kWh", "kW", "Therms"}


# ===========================================================================
# Fixture-driven integration tests (YAML rules + CSV data)
# ===========================================================================

# ---------------------------------------------------------------------------
# Arithmetic: sum, subtract, multiply, divide (arithmetic_rules.yaml)
# ---------------------------------------------------------------------------


def test_arithmetic_divide_produces_correct_ratio(arithmetic_df, arithmetic_bundle) -> None:
    result = validate_dataframe(arithmetic_df, arithmetic_bundle)
    annotated = result.to_annotated_dataframe()
    # R1: 1000/500 = 2.0, R2: 800/400 = 2.0, R3: 600/0 → NaN, R4: 0/200 = 0.0
    assert annotated["Output Input Ratio"].iloc[0] == 2.0
    assert annotated["Output Input Ratio"].iloc[1] == 2.0
    assert pd.isna(annotated["Output Input Ratio"].iloc[2])
    assert annotated["Output Input Ratio"].iloc[3] == 0.0


def test_arithmetic_sum_adds_all_savings(arithmetic_df, arithmetic_bundle) -> None:
    result = validate_dataframe(arithmetic_df, arithmetic_bundle)
    annotated = result.to_annotated_dataframe()
    # R1: 10+5+2=17, R2: 8+0+1=9, R3: 6+3+0=9, R4: NaN+4+1 → 5 (min_count=1 skips NaN)
    assert annotated["Total Savings"].iloc[0] == 17.0
    assert annotated["Total Savings"].iloc[1] == 9.0
    assert annotated["Total Savings"].iloc[2] == 9.0
    assert annotated["Total Savings"].iloc[3] == 5.0


def test_arithmetic_subtract_produces_variance(arithmetic_df, arithmetic_bundle) -> None:
    result = validate_dataframe(arithmetic_df, arithmetic_bundle)
    annotated = result.to_annotated_dataframe()
    # R1: 17-17=0, R2: 9-9=0, R3: 9-9=0, R4: 5-5=0
    assert annotated["Savings Variance"].tolist() == [0.0, 0.0, 0.0, 0.0]


def test_arithmetic_multiply_produces_product(arithmetic_df, arithmetic_bundle) -> None:
    result = validate_dataframe(arithmetic_df, arithmetic_bundle)
    annotated = result.to_annotated_dataframe()
    # R1: 1000*500=500000, R2: 800*400=320000, R3: 600*0=0, R4: 0*200=0
    assert annotated["Output Times Input"].iloc[0] == 500000.0
    assert annotated["Output Times Input"].iloc[1] == 320000.0
    assert annotated["Output Times Input"].iloc[2] == 0.0
    assert annotated["Output Times Input"].iloc[3] == 0.0


def test_arithmetic_divide_triggers_ratio_warning(arithmetic_df, arithmetic_bundle) -> None:
    # No row has Output/Input > 2.5 in our data, so no findings for ratio_too_high
    result = validate_dataframe(arithmetic_df, arithmetic_bundle)
    ratio_findings = [f for f in result.findings if f.rule_id == "ratio_too_high"]
    assert ratio_findings == []


def test_arithmetic_variance_zero_triggers_no_findings(arithmetic_df, arithmetic_bundle) -> None:
    result = validate_dataframe(arithmetic_df, arithmetic_bundle)
    variance_findings = [f for f in result.findings if f.rule_id == "savings_variance_nonzero"]
    assert variance_findings == []


# ---------------------------------------------------------------------------
# Group aggregates: group_sum, group_count (group_aggregate_rules.yaml)
# ---------------------------------------------------------------------------


def test_group_sum_bef_kwh_correct_per_project(group_aggregate_df, group_aggregate_bundle) -> None:
    result = validate_dataframe(group_aggregate_df, group_aggregate_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Project BEF Total kWh"
    # P1 BEF rows (R1=100, R2=50) → 150; P1 LED row → NaN; P2 BEF row → 80; P2 H&S row → NaN
    p1_bef = annotated.loc[annotated["Project ID"] == "P1"]
    assert p1_bef.loc[p1_bef["Measure Type"] == "BEF", col].iloc[0] == 150.0
    assert p1_bef.loc[p1_bef["Measure Type"] == "BEF", col].iloc[1] == 150.0
    assert pd.isna(p1_bef.loc[p1_bef["Measure Type"] == "LED", col].iloc[0])


def test_group_sum_hs_incentive_correct_per_project(
    group_aggregate_df, group_aggregate_bundle
) -> None:
    result = validate_dataframe(group_aggregate_df, group_aggregate_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Project H&S Total Incentive"
    # P2 H&S row: incentive=300; P3 H&S rows: 150+100=250
    p2_hs = annotated.loc[(annotated["Project ID"] == "P2") & (annotated["Measure Type"] == "H&S")]
    assert p2_hs[col].iloc[0] == 300.0
    p3_hs = annotated.loc[(annotated["Project ID"] == "P3") & (annotated["Measure Type"] == "H&S")]
    assert (p3_hs[col] == 250.0).all()


def test_group_sum_total_kwh_covers_all_rows(group_aggregate_df, group_aggregate_bundle) -> None:
    result = validate_dataframe(group_aggregate_df, group_aggregate_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Project Total kWh"
    # P1 total: 100+50+30=180; P2 total: 80+0=80; P3 total: 20+0+0=20
    assert annotated.loc[annotated["Project ID"] == "P1", col].iloc[0] == 180.0
    assert annotated.loc[annotated["Project ID"] == "P2", col].iloc[0] == 80.0
    assert annotated.loc[annotated["Project ID"] == "P3", col].iloc[0] == 20.0


def test_group_count_bef_per_project(group_aggregate_df, group_aggregate_bundle) -> None:
    result = validate_dataframe(group_aggregate_df, group_aggregate_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Project BEF Count"
    # P1 has 2 BEF rows, P2 has 1 BEF row; non-BEF rows → NaN
    p1_bef = annotated.loc[(annotated["Project ID"] == "P1") & (annotated["Measure Type"] == "BEF")]
    assert (p1_bef[col] == 2).all()
    p2_bef = annotated.loc[(annotated["Project ID"] == "P2") & (annotated["Measure Type"] == "BEF")]
    assert p2_bef[col].iloc[0] == 1
    p1_led = annotated.loc[(annotated["Project ID"] == "P1") & (annotated["Measure Type"] == "LED")]
    assert pd.isna(p1_led[col].iloc[0])


def test_group_count_row_count_per_project(group_aggregate_df, group_aggregate_bundle) -> None:
    result = validate_dataframe(group_aggregate_df, group_aggregate_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Project Row Count"
    # P1=3 rows, P2=2 rows, P3=3 rows
    assert (annotated.loc[annotated["Project ID"] == "P1", col] == 3).all()
    assert (annotated.loc[annotated["Project ID"] == "P2", col] == 2).all()
    assert (annotated.loc[annotated["Project ID"] == "P3", col] == 3).all()


def test_group_sum_triggers_high_bef_finding(group_aggregate_df, group_aggregate_bundle) -> None:
    result = validate_dataframe(group_aggregate_df, group_aggregate_bundle)
    # P1 BEF total kWh = 150 > 100 → 2 findings (one per BEF row in P1)
    findings = [f for f in result.findings if f.rule_id == "high_bef_kwh"]
    assert len(findings) == 2


# ---------------------------------------------------------------------------
# Date types: date_diff, days_since_today, years_since_year, coalesce
# (date_rules.yaml)
# ---------------------------------------------------------------------------


def test_date_diff_days_to_inspection(date_df, date_bundle) -> None:
    result = validate_dataframe(date_df, date_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Days to Inspection"
    # R1: 2020-01-01 → 2020-01-15 = 14 days
    # R2: 2019-06-01 → 2019-06-01 = 0 days
    # R3: start is blank → NaN
    # R4: end is blank → NaN
    # R5: 2022-03-15 → 2022-04-14 = 30 days
    assert annotated[col].iloc[0] == 14.0
    assert annotated[col].iloc[1] == 0.0
    assert pd.isna(annotated[col].iloc[2])
    assert pd.isna(annotated[col].iloc[3])
    assert annotated[col].iloc[4] == 30.0


def test_years_since_year_system_age(date_df, date_bundle) -> None:
    result = validate_dataframe(date_df, date_bundle)
    annotated = result.to_annotated_dataframe()
    col = "System Age"
    current_year = datetime.date.today().year
    # CSV years: R1=1990, R2=1985, R3=1980, R4=1975, R5=2022
    assert annotated[col].iloc[0] == float(current_year - 1990)
    assert annotated[col].iloc[1] == float(current_year - 1985)
    assert annotated[col].iloc[2] == float(current_year - 1980)
    assert annotated[col].iloc[3] == float(current_year - 1975)
    assert annotated[col].iloc[4] == float(current_year - 2022)


def test_coalesce_best_available_date(date_df, date_bundle) -> None:
    result = validate_dataframe(date_df, date_bundle)
    annotated = result.to_annotated_dataframe()
    col = "Best Available Date"
    # R1: Date Inspected = 2020-01-15
    # R2: Date Inspected = 2019-06-01
    # R3: Date Inspected is blank, Alt A = 2021-03-01
    # R4: Date Inspected is blank, Alt A blank, Alt B blank → NaN
    # R5: Date Inspected = 2022-04-14
    assert annotated[col].iloc[0] == "2020-01-15"
    assert annotated[col].iloc[1] == "2019-06-01"
    assert annotated[col].iloc[2] == "2021-03-01"
    assert pd.isna(annotated[col].iloc[3])
    assert annotated[col].iloc[4] == "2022-04-14"


def test_date_rules_trigger_correct_findings(date_df, date_bundle) -> None:
    result = validate_dataframe(date_df, date_bundle)
    # inspection_too_late: Days to Inspection > 30 → none qualify (max is 30, not >30)
    # R3 and R4 have no date_diff value (NaN) → null-safe operator returns False, no finding
    late_findings = [f for f in result.findings if f.rule_id == "inspection_too_late"]
    assert late_findings == []
    # old_system: System Age > 20 → R1(1990), R2(1985), R3(1980), R4(1975) all >20 years old
    # R5(2022) is only ~4 years old → no finding
    old_findings = [f for f in result.findings if f.rule_id == "old_system"]
    assert len(old_findings) == 4


# ---------------------------------------------------------------------------
# all_blank_or_zero (savings_flag_rules.yaml)
# ---------------------------------------------------------------------------


def test_all_blank_or_zero_flag_column_values(savings_flag_df, savings_flag_bundle) -> None:
    result = validate_dataframe(savings_flag_df, savings_flag_bundle)
    annotated = result.to_annotated_dataframe()
    col = "All Savings Zero or Blank"
    # R1: 0,0,0 → 1
    # R2: blank,blank,blank → 1
    # R3: 0,blank,0 → 1
    # R4: 1,0,0 → 0 (kWh=1 is nonzero)
    # R5: 0,0,5 → 0 (Therms=5 is nonzero)
    # R6: 0,0,blank → 1
    assert annotated[col].tolist() == [1, 1, 1, 0, 0, 1]


def test_all_blank_or_zero_triggers_findings_on_correct_rows(
    savings_flag_df, savings_flag_bundle
) -> None:
    result = validate_dataframe(savings_flag_df, savings_flag_bundle)
    findings = [f for f in result.findings if f.rule_id == "no_savings_recorded"]
    # Rows 0,1,2,5 (R1,R2,R3,R6) should produce findings
    assert len(findings) == 4
    assert {f.row_index for f in findings} == {0, 1, 2, 5}
