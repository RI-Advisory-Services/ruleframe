from ruleframe import validate_dataframe


def test_validation_returns_findings(sample_df, sample_bundle) -> None:
    result = validate_dataframe(sample_df, sample_bundle)
    assert len(result.findings) == 3
    assert [finding.rule_id for finding in result.findings] == [
        "qaqc_unresolved_issue",
        "missing_customer_status",
        "missing_customer_status",
    ]
    annotated = result.to_annotated_dataframe()
    assert "Validation Errors" in annotated.columns


def test_summary_dataframe_has_counts(sample_df, sample_bundle) -> None:
    result = validate_dataframe(sample_df, sample_bundle)
    summary = result.to_summary_dataframe()
    assert not summary.empty
    assert set(summary.columns) == {"rule_id", "severity", "count"}
