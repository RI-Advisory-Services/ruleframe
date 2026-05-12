from ruleframe import validate_dataframe


def test_validation_returns_findings(sample_df, sample_bundle) -> None:
    result = validate_dataframe(sample_df, sample_bundle)
    assert len(result.findings) == 3
    annotated = result.to_annotated_dataframe()
    assert "Validation Errors" in annotated.columns


def test_summary_dataframe_has_counts(sample_df, sample_bundle) -> None:
    result = validate_dataframe(sample_df, sample_bundle)
    summary = result.to_summary_dataframe()
    assert not summary.empty
    assert set(summary.columns) == {"rule_id", "severity", "count"}
