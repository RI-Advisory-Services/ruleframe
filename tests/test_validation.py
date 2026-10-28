import pandas as pd
import pytest

from ruleframe import RuleBundle, validate_dataframe, validate_inputs
from ruleframe.computed import _normalize_integral_result
from ruleframe.exceptions import BundleValidationError, InputSchemaError


def _bundle_with_computed(spec: dict) -> RuleBundle:
    return RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [spec],
            "rules": [],
        }
    )


def test_validation_returns_findings(sample_df, sample_bundle) -> None:
    result = validate_dataframe(sample_df, sample_bundle)
    assert [finding.rule_id for finding in result.findings] == [
        "qaqc_unresolved_issue",
        "missing_customer_status",
        "missing_customer_status",
        "review_required_without_priority",
        "active_quantity_mismatch",
        "late_active_inspection",
    ]
    annotated = result.to_annotated_dataframe()
    assert "Validation Errors" in annotated.columns


def test_validate_inputs_accepts_valid_input_schema() -> None:
    df = pd.DataFrame({"Status": ["active"]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "status_check",
                    "fail_when": {"column": "Status", "equals": "inactive"},
                }
            ],
        }
    )

    assert validate_inputs(df, bundle) is None


def test_validate_inputs_rejects_missing_input_columns() -> None:
    df = pd.DataFrame({"Status": ["active"]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "status_check",
                    "fail_when": {"column": "Missing", "equals": "active"},
                }
            ],
        }
    )

    with pytest.raises(InputSchemaError, match="Missing"):
        validate_inputs(df, bundle)


def test_summary_dataframe_has_counts(sample_df, sample_bundle) -> None:
    result = validate_dataframe(sample_df, sample_bundle)
    summary = result.to_summary_dataframe()
    assert not summary.empty
    assert set(summary.columns) == {"rule_id", "severity", "count"}


def test_validation_supports_split_node_fixture(
    workflow_split_node_df, workflow_split_node_bundle
) -> None:
    result = validate_dataframe(workflow_split_node_df, workflow_split_node_bundle)

    assert [finding.rule_id for finding in result.findings] == [
        "manual_review_not_prioritized",
        "unresolved_priority_or_safety_issue",
        "manual_review_not_prioritized",
        "active_quantity_mismatch",
        "late_active_inspection",
    ]


def test_computed_columns_are_added_before_validation(
    computed_savings_df, computed_savings_bundle
) -> None:
    result = validate_dataframe(computed_savings_df, computed_savings_bundle)

    assert [finding.rule_id for finding in result.findings] == [
        "total_savings_mismatch",
        "unusually_high_total_savings",
    ]
    annotated = result.to_annotated_dataframe()
    assert annotated["Total Measure Savings"].tolist() == [12, 23, 8]


def test_missing_computed_source_columns_are_reported(
    computed_savings_df, computed_savings_bundle
) -> None:
    df = computed_savings_df.drop(columns=["Measure Gross Therm Savings"])

    with pytest.raises(InputSchemaError, match="Measure Gross Therm Savings"):
        validate_dataframe(df, computed_savings_bundle)


def test_validate_inputs_reports_missing_computed_source_columns(
    computed_savings_df, computed_savings_bundle
) -> None:
    df = computed_savings_df.drop(columns=["Measure Gross Therm Savings"])

    with pytest.raises(InputSchemaError, match="Measure Gross Therm Savings"):
        validate_inputs(df, computed_savings_bundle)


def test_computed_column_name_collision_raises() -> None:
    df = pd.DataFrame({"A": [1], "B": [2], "Total Savings": [3]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {
                    "type": "sum",
                    "columns": ["A", "B"],
                    "id": "total_savings",
                    "name": "Total Savings",
                }
            ],
            "rules": [],
        }
    )
    with pytest.raises(InputSchemaError, match="collide with existing input"):
        validate_dataframe(df, bundle)


def test_computed_column_name_collision_does_not_raise_when_no_overlap() -> None:
    df = pd.DataFrame({"A": [1], "B": [2]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {"type": "sum", "columns": ["A", "B"], "id": "total", "name": "Total"}
            ],
            "rules": [],
        }
    )
    validate_dataframe(df, bundle)  # should not raise


def test_duplicate_computed_column_output_names_raise() -> None:
    df = pd.DataFrame({"A": [1], "B": [2], "C": [3], "D": [4]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {"type": "sum", "columns": ["A", "B"], "id": "total_a", "name": "Total"},
                {"type": "sum", "columns": ["C", "D"], "id": "total_b", "name": "Total"},
            ],
            "rules": [],
        }
    )

    with pytest.raises(BundleValidationError, match="must be unique: Total"):
        validate_dataframe(df, bundle)


def test_validate_inputs_rejects_round_with_non_integer_decimals() -> None:
    df = pd.DataFrame({"A": [1.0]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {
                    "type": "round",
                    "column": "A",
                    "decimals": "two",
                    "id": "result",
                }
            ],
            "rules": [],
        }
    )

    with pytest.raises(BundleValidationError, match="round requires an integer 'decimals' key"):
        validate_inputs(df, bundle)


def test_validate_inputs_rejects_scale_with_non_numeric_scalar() -> None:
    df = pd.DataFrame({"A": [1.0]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {
                    "type": "scale",
                    "column": "A",
                    "scalar": "not-a-number",
                    "id": "result",
                }
            ],
            "rules": [],
        }
    )

    with pytest.raises(BundleValidationError, match="scale requires a numeric 'scalar' key"):
        validate_inputs(df, bundle)


def test_validate_inputs_rejects_divide_with_more_than_two_columns() -> None:
    df = pd.DataFrame({"A": [1.0], "B": [2.0], "C": [3.0]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [{"type": "divide", "columns": ["A", "B", "C"], "id": "r"}],
            "rules": [],
        }
    )

    with pytest.raises(BundleValidationError, match="exactly 2"):
        validate_inputs(df, bundle)


def _assert_invalid_computed_spec(spec: dict, message: str) -> None:
    df = pd.DataFrame(
        {
            "A": [1],
            "B": [2],
            "Group": ["A"],
            "Value": [1],
            "Status": ["active"],
            "Start": ["2024-01-01"],
            "End": ["2024-01-02"],
        }
    )

    with pytest.raises(BundleValidationError, match=message):
        validate_inputs(df, _bundle_with_computed(spec))


def test_validate_inputs_rejects_group_sum_without_group_by() -> None:
    _assert_invalid_computed_spec(
        {"type": "group_sum", "value_column": "Value", "id": "result"},
        "group_sum requires group_by",
    )


def test_validate_inputs_rejects_group_sum_without_value_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "group_sum", "group_by": "Group", "id": "result"},
        "group_sum requires value_column",
    )


def test_validate_inputs_rejects_date_diff_without_start_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "date_diff", "end_column": "End", "id": "result"},
        "date_diff requires start_column and end_column",
    )


def test_validate_inputs_rejects_date_diff_without_end_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "date_diff", "start_column": "Start", "id": "result"},
        "date_diff requires start_column and end_column",
    )


def test_validate_inputs_rejects_non_string_days_since_today_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "days_since_today", "column": 123, "id": "result"},
        r"days_since_today 'column' must be a string",
    )


def test_validate_inputs_rejects_non_string_years_since_year_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "years_since_year", "column": 123, "id": "result"},
        r"years_since_year 'column' must be a string",
    )


def test_validate_inputs_rejects_non_string_date_diff_start_column() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "date_diff",
            "start_column": 123,
            "end_column": "End",
            "id": "result",
        },
        r"date_diff 'start_column' must be a string",
    )


def test_validate_inputs_rejects_non_string_date_diff_end_column() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "date_diff",
            "start_column": "Start",
            "end_column": 123,
            "id": "result",
        },
        r"date_diff 'end_column' must be a string",
    )


def test_validate_inputs_rejects_non_string_group_sum_group_by() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_sum",
            "group_by": 123,
            "value_column": "Value",
            "id": "result",
        },
        r"group_sum 'group_by' must be a string",
    )


def test_validate_inputs_rejects_non_string_group_sum_value_column() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_sum",
            "group_by": "Group",
            "value_column": 123,
            "id": "result",
        },
        r"group_sum 'value_column' must be a string",
    )


def test_validate_inputs_rejects_non_string_group_count_group_by() -> None:
    _assert_invalid_computed_spec(
        {"type": "group_count", "group_by": 123, "id": "result"},
        r"group_count 'group_by' must be a string",
    )


def test_validate_inputs_rejects_non_string_sum_source_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "sum", "columns": ["A", 123], "id": "result"},
        r"'columns' list must contain only strings",
    )


def test_validate_inputs_rejects_non_string_subtract_source_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "subtract", "columns": ["A", 123], "id": "result"},
        r"'columns' list must contain only strings",
    )


def test_validate_inputs_rejects_non_string_multiply_source_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "multiply", "columns": ["A", 123], "id": "result"},
        r"'columns' list must contain only strings",
    )


def test_validate_inputs_rejects_non_string_divide_source_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "divide", "columns": ["A", 123], "id": "result"},
        r"'columns' list must contain only strings",
    )


def test_validate_inputs_rejects_non_string_coalesce_source_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "coalesce", "columns": ["A", 123], "id": "result"},
        r"'columns' list must contain only strings",
    )


def test_validate_inputs_rejects_non_string_all_blank_or_zero_source_column() -> None:
    _assert_invalid_computed_spec(
        {"type": "all_blank_or_zero", "columns": ["A", 123], "id": "result"},
        r"'columns' list must contain only strings",
    )


def test_validate_inputs_rejects_group_sum_filter_without_column() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_sum",
            "group_by": "Group",
            "value_column": "Value",
            "filter": {"equals": "active"},
            "id": "result",
        },
        r"requires 'filter\.column'",
    )


def test_validate_inputs_rejects_group_sum_filter_without_equals() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_sum",
            "group_by": "Group",
            "value_column": "Value",
            "filter": {"column": "Status"},
            "id": "result",
        },
        r"requires 'filter' to contain exactly the fields",
    )


def test_validate_inputs_rejects_group_sum_filter_with_unexpected_key() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_sum",
            "group_by": "Group",
            "value_column": "Value",
            "filter": {
                "column": "Status",
                "equals": "active",
                "unexpected": True,
            },
            "id": "result",
        },
        r"requires 'filter' to contain exactly the fields",
    )


def test_validate_inputs_rejects_group_count_filter_without_column() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_count",
            "group_by": "Group",
            "filter": {"equals": "active"},
            "id": "result",
        },
        r"requires 'filter\.column'",
    )


def test_validate_inputs_rejects_group_count_filter_without_equals() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_count",
            "group_by": "Group",
            "filter": {"column": "Status"},
            "id": "result",
        },
        r"requires 'filter' to contain exactly the fields",
    )


def test_validate_inputs_rejects_group_count_filter_with_unexpected_key() -> None:
    _assert_invalid_computed_spec(
        {
            "type": "group_count",
            "group_by": "Group",
            "filter": {
                "column": "Status",
                "equals": "active",
                "unexpected": True,
            },
            "id": "result",
        },
        r"requires 'filter' to contain exactly the fields",
    )


def test_validate_inputs_rejects_group_count_without_group_by() -> None:
    df = pd.DataFrame({"A": [1.0]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [{"type": "group_count", "id": "result"}],
            "rules": [],
        }
    )

    with pytest.raises(BundleValidationError, match="group_count requires group_by"):
        validate_inputs(df, bundle)


def test_validate_inputs_rejects_computed_spec_without_name_or_id() -> None:
    df = pd.DataFrame({"A": [1], "B": [2]})
    bundle = _bundle_with_computed(
        {
            "type": "sum",
            "columns": ["A", "B"],
        }
    )

    with pytest.raises(
        BundleValidationError,
        match="Computed columns must define a name or id",
    ):
        validate_inputs(df, bundle)


def test_validate_inputs_reports_computed_name_collision() -> None:
    df = pd.DataFrame({"A": [1], "B": [2], "Total": [3]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {
                    "type": "sum",
                    "columns": ["A", "B"],
                    "id": "total",
                    "name": "Total",
                }
            ],
            "rules": [],
        }
    )

    with pytest.raises(InputSchemaError, match="collide with existing input"):
        validate_inputs(df, bundle)


def test_validate_inputs_rejects_malformed_computed_operation_spec() -> None:
    df = pd.DataFrame({"A": [1.0]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [{"type": "sum", "id": "result"}],
            "rules": [],
        }
    )

    with pytest.raises(BundleValidationError, match="non-empty columns list"):
        validate_inputs(df, bundle)


def test_normalize_integral_result_returns_nullable_integer_series() -> None:
    result = _normalize_integral_result(pd.Series([1.0, None, 3.0]))

    assert str(result.dtype) == "Int64"
    assert result.tolist() == [1, pd.NA, 3]


def test_normalize_integral_result_preserves_fractional_float_series() -> None:
    result = _normalize_integral_result(pd.Series([1.5, None, 3.0]))

    assert pd.api.types.is_float_dtype(result)
    assert result.iloc[0] == 1.5
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 3.0
