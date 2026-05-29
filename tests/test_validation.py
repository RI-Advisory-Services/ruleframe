import pandas as pd
import pytest

from ruleframe import RuleBundle, validate_dataframe
from ruleframe.exceptions import InputSchemaError


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


def test_computed_column_name_collision_raises() -> None:
    df = pd.DataFrame({"A": [1], "B": [2], "Total Savings": [3]})
    bundle = RuleBundle.from_json_dict({
        "version": 1,
        "computed_columns": [
            {"type": "sum", "columns": ["A", "B"], "id": "total_savings", "name": "Total Savings"}
        ],
        "rules": [],
    })
    with pytest.raises(InputSchemaError, match="collide with existing input"):
        validate_dataframe(df, bundle)


def test_computed_column_name_collision_does_not_raise_when_no_overlap() -> None:
    df = pd.DataFrame({"A": [1], "B": [2]})
    bundle = RuleBundle.from_json_dict({
        "version": 1,
        "computed_columns": [
            {"type": "sum", "columns": ["A", "B"], "id": "total", "name": "Total"}
        ],
        "rules": [],
    })
    validate_dataframe(df, bundle)  # should not raise
