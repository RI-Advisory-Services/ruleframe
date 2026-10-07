import pandas as pd
import pytest

from ruleframe import RuleBundle, validate_dataframe, validate_inputs
from ruleframe.computed import _normalize_integral_result
from ruleframe.exceptions import BundleValidationError, InputSchemaError


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
