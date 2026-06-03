import pandas as pd
import pytest

from ruleframe import RuleBundle, validate_dataframe
from ruleframe.exceptions import InputSchemaError


def test_validate_dataframe_supports_jsonlogic_operator_registry() -> None:
    df = pd.DataFrame(
        [
            {
                "Fuel Type Heat": "Natural Gas",
                "Customer Status": pd.NA,
                "Building Square Footage": 450,
                "Notes": "needs follow up",
                "Installation Date": "2026-02-01",
                "Date Inspected": "2026-03-10",
            },
            {
                "Fuel Type Heat": "Electric",
                "Customer Status": "Active",
                "Building Square Footage": 1200,
                "Notes": "complete",
                "Installation Date": "2026-01-01",
                "Date Inspected": "2026-01-20",
            },
        ]
    )
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "settings": {
                "row_id": {"column": "__validation_row_id__", "strategy": "sequential"},
                "validation_errors_column": "Rule Messages",
            },
            "rules": [
                {
                    "id": "fossil_fuel_missing_customer_status",
                    "severity": "warning",
                    "fail_when": {
                        "all": [
                            {"column": "Fuel Type Heat", "in": ["Natural Gas", "Propane"]},
                            {"column": "Customer Status", "is_blank": True},
                        ]
                    },
                    "message": "Customer Status is required for fossil fuel rows.",
                },
                {
                    "id": "small_building",
                    "severity": "error",
                    "fail_when": {"column": "Building Square Footage", "between": [0, 500]},
                    "message": "Building square footage is smaller than expected.",
                },
                {
                    "id": "notes_need_follow_up",
                    "severity": "warning",
                    "fail_when": {"column": "Notes", "contains": "follow up"},
                    "message": "Notes indicate follow up is needed.",
                },
                {
                    "id": "late_inspection",
                    "severity": "error",
                    "fail_when": {
                        "column": "Installation Date",
                        "days_apart_greater_than": {"column": "Date Inspected", "days": 31},
                    },
                    "message": "Inspection happened more than 31 days from installation.",
                },
            ],
        }
    )

    result = validate_dataframe(df, bundle)

    assert [finding.rule_id for finding in result.findings] == [
        "fossil_fuel_missing_customer_status",
        "small_building",
        "notes_need_follow_up",
        "late_inspection",
    ]
    annotated = result.to_annotated_dataframe()
    assert annotated["__validation_row_id__"].tolist() == [1, 2]
    assert "Rule Messages" in annotated.columns
    assert annotated.loc[1, "Rule Messages"] == ""


def test_not_equals_fires_when_column_is_blank() -> None:
    """A blank (NaN→None) value must trigger a not_equals rule.

    Regression: NullSafeNotEq was previously short-circuiting to False
    whenever the left operand was None, silently swallowing findings for
    rules of the form "field must equal X".
    """
    df = pd.DataFrame(
        [
            {"EER": float("nan"), "Fuel Type": "Electric"},  # blank — should fire
            {"EER": 0.0, "Fuel Type": "Electric"},  # correct — should not fire
            {"EER": 5.0, "Fuel Type": "Electric"},  # wrong value — should fire
        ]
    )
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "eer_must_be_zero",
                    "severity": "error",
                    "fail_when": {"column": "EER", "not_equals": 0},
                    "message": "EER must be 0",
                }
            ],
        }
    )

    result = validate_dataframe(df, bundle)
    firing_rows = [f.row_index for f in result.findings if f.rule_id == "eer_must_be_zero"]
    assert firing_rows == [0, 2]  # blank and wrong-value rows, not the correct row


def test_not_equals_column_both_blank_does_not_fire() -> None:
    """When both sides of a not_equals_column comparison are blank, do not fire."""
    df = pd.DataFrame(
        [
            {"A": float("nan"), "B": float("nan")},  # both blank — should not fire
            {"A": 1.0, "B": 2.0},  # different values — should fire
            {"A": 1.0, "B": 1.0},  # equal — should not fire
        ]
    )
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "a_must_equal_b",
                    "severity": "error",
                    "fail_when": {"column": "A", "not_equals_column": "B"},
                    "message": "A must equal B",
                }
            ],
        }
    )

    result = validate_dataframe(df, bundle)
    firing_rows = [f.row_index for f in result.findings if f.rule_id == "a_must_equal_b"]
    assert firing_rows == [1]  # only the differing-values row


def _single_rule_bundle(condition: dict) -> RuleBundle:
    return RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "r",
                    "severity": "error",
                    "fail_when": condition,
                    "message": "rule fired",
                }
            ],
        }
    )


@pytest.mark.parametrize(
    ("condition", "records", "expected_rows"),
    [
        (
            {"column": "A", "equals_column": "B"},
            [{"A": 1, "B": 1}, {"A": 1, "B": 2}],
            [0],
        ),
        (
            {"column": "A", "greater_than_column": "B"},
            [{"A": 3, "B": 2}, {"A": 2, "B": 3}],
            [0],
        ),
        (
            {"column": "A", "greater_than_or_equal_column": "B"},
            [{"A": 3, "B": 3}, {"A": 2, "B": 3}],
            [0],
        ),
        (
            {"column": "A", "less_than_column": "B"},
            [{"A": 2, "B": 3}, {"A": 3, "B": 2}],
            [0],
        ),
        (
            {"column": "A", "less_than_or_equal_column": "B"},
            [{"A": 3, "B": 3}, {"A": 3, "B": 2}],
            [0],
        ),
        (
            {"column": "A", "greater_than_or_equal": 10},
            [{"A": 10}, {"A": 9}],
            [0],
        ),
        ({"column": "A", "less_than": 10}, [{"A": 9}, {"A": 10}], [0]),
        (
            {"column": "A", "less_than_or_equal": 10},
            [{"A": 10}, {"A": 11}],
            [0],
        ),
        (
            {"column": "A", "not_in": ["x", "y"]},
            [{"A": "z"}, {"A": "x"}],
            [0],
        ),
        (
            {"column": "A", "not_contains": "needle"},
            [{"A": "plain text"}, {"A": "has needle"}],
            [0],
        ),
        (
            {"column": "A", "not_between": [1, 5]},
            [{"A": 0}, {"A": 3}, {"A": 6}],
            [0, 2],
        ),
        (
            {"column": "A", "is_not_blank": True},
            [{"A": "value"}, {"A": ""}, {"A": None}, {"A": "   "}],
            [0],
        ),
    ],
)
def test_validate_dataframe_supports_remaining_friendly_operators(
    condition, records, expected_rows
) -> None:
    result = validate_dataframe(pd.DataFrame(records), _single_rule_bundle(condition))
    firing_rows = [finding.row_index for finding in result.findings]
    assert firing_rows == expected_rows


def test_validate_dataframe_reports_missing_rule_columns() -> None:
    df = pd.DataFrame([{"A": "Yes"}])
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "missing_b",
                    "fail_when": {"column": "B", "equals": "Yes"},
                    "message": "B is required.",
                }
            ],
        }
    )

    with pytest.raises(InputSchemaError, match="B"):
        validate_dataframe(df, bundle)


# ===========================================================================
# New date comparison operators
# ===========================================================================


def _date_op_bundle(rule_id: str, op: str, value) -> RuleBundle:
    """Helper: build a minimal bundle with a single date operator rule."""
    return RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": rule_id,
                    "severity": "error",
                    "fail_when": {"column": "Event Date", op: value},
                    "message": f"{op} rule fired",
                }
            ],
        }
    )


def test_date_greater_than_fires_when_date_exceeds_threshold() -> None:
    df = pd.DataFrame({"Event Date": ["2024-06-01", "2024-01-01", None]})
    bundle = _date_op_bundle("r", "date_greater_than", "2024-03-01")
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0]  # June > March; January is not; None does not fire


def test_date_less_than_fires_when_date_precedes_threshold() -> None:
    df = pd.DataFrame({"Event Date": ["2024-01-01", "2024-06-01", None]})
    bundle = _date_op_bundle("r", "date_less_than", "2024-03-01")
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0]  # January < March; June is not; None does not fire


def test_date_greater_than_or_equal_fires_on_match_and_above() -> None:
    df = pd.DataFrame({"Event Date": ["2024-03-01", "2024-03-02", "2024-02-28"]})
    bundle = _date_op_bundle("r", "date_greater_than_or_equal", "2024-03-01")
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0, 1]  # exact match and above; Feb 28 does not fire


def test_date_less_than_or_equal_fires_on_match_and_below() -> None:
    df = pd.DataFrame({"Event Date": ["2024-03-01", "2024-02-28", "2024-03-02"]})
    bundle = _date_op_bundle("r", "date_less_than_or_equal", "2024-03-01")
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0, 1]  # exact match and below; March 2 does not fire


def test_date_equals_fires_only_on_exact_match() -> None:
    df = pd.DataFrame({"Event Date": ["2024-03-01", "2024-03-02", None]})
    bundle = _date_op_bundle("r", "date_equals", "2024-03-01")
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0]


def test_date_between_fires_within_inclusive_range() -> None:
    df = pd.DataFrame(
        {"Event Date": ["2024-01-01", "2024-03-01", "2024-06-01", "2024-12-31", None]}
    )
    bundle = _date_op_bundle("r", "date_between", ["2024-03-01", "2024-06-01"])
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [1, 2]  # Jan and Dec are outside; boundaries are inclusive; None does not fire


def test_date_not_between_fires_outside_range() -> None:
    df = pd.DataFrame(
        {"Event Date": ["2024-01-01", "2024-03-01", "2024-06-01", "2024-12-31"]}
    )
    bundle = _date_op_bundle("r", "date_not_between", ["2024-03-01", "2024-06-01"])
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0, 3]  # Jan and Dec are outside range


def test_date_operators_accept_us_format_strings() -> None:
    # Columns in MM/DD/YYYY format — should parse via normalization before operator runs
    df = pd.DataFrame({"Event Date": ["06/01/2024", "01/01/2024"]})
    bundle = _date_op_bundle("r", "date_greater_than", "2024-03-01")
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0]  # June > March


def test_date_operators_null_column_value_does_not_fire() -> None:
    df = pd.DataFrame({"Event Date": [None, pd.NaT, ""]})
    bundle = _date_op_bundle("r", "date_greater_than", "2000-01-01")
    result = validate_dataframe(df, bundle)
    assert result.findings == []


def test_date_operators_infer_date_column_normalization() -> None:
    # Verify that the Event Date column is normalized to Timestamps in the working df;
    # the rule uses a date operator so normalization should happen automatically.
    df = pd.DataFrame({"Event Date": ["2024-06-01 14:32:00"]})
    bundle = _date_op_bundle("r", "date_greater_than", "2024-01-01")
    result = validate_dataframe(df, bundle)
    # Time component stripped; date comparison should still fire
    assert len(result.findings) == 1


# ===========================================================================
# bundle-level date_format setting
# ===========================================================================


def test_date_format_setting_parses_strict_format() -> None:
    # Source data is in MM/DD/YYYY; declare it via date_format
    df = pd.DataFrame({"Event Date": ["06/01/2024", "01/01/2024"]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "settings": {"date_format": "%m/%d/%Y"},
            "rules": [
                {
                    "id": "r",
                    "severity": "error",
                    "fail_when": {"column": "Event Date", "date_greater_than": "2024-03-01"},
                    "message": "late",
                }
            ],
        }
    )
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    assert firing == [0]


def test_date_format_setting_rejects_non_conforming_values() -> None:
    # ISO values don't match %m/%d/%Y → NaT after normalization → operator does not fire
    df = pd.DataFrame({"Event Date": ["2024-06-01"]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "settings": {"date_format": "%m/%d/%Y"},
            "rules": [
                {
                    "id": "r",
                    "severity": "error",
                    "fail_when": {"column": "Event Date", "date_greater_than": "2024-01-01"},
                    "message": "late",
                }
            ],
        }
    )
    result = validate_dataframe(df, bundle)
    # ISO string doesn't match declared format → treated as null → no firing
    assert result.findings == []


# ===========================================================================
# _infer_date_columns coverage via validate_dataframe
# ===========================================================================


def test_date_diff_columns_are_normalized_before_computation() -> None:
    # US-format date strings in columns used by date_diff — should parse correctly
    df = pd.DataFrame(
        {
            "Start": ["01/01/2024", "03/01/2024"],
            "End": ["03/31/2024", "03/01/2024"],
        }
    )
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {
                    "id": "diff",
                    "name": "Diff",
                    "type": "date_diff",
                    "start_column": "Start",
                    "end_column": "End",
                }
            ],
            "rules": [
                {
                    "id": "r",
                    "severity": "error",
                    "fail_when": {"column": "Diff", "greater_than": 30},
                    "message": "too long",
                }
            ],
        }
    )
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    # Row 0: Jan 1 to Mar 31 = 90 days → fires; Row 1: same date = 0 days → no fire
    assert firing == [0]


def test_days_since_today_column_is_normalized_before_computation() -> None:
    # US-format date strings in days_since_today column — should parse correctly
    df = pd.DataFrame({"Install Date": ["01/01/2020", "01/01/2025"]})
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "computed_columns": [
                {"id": "age", "name": "Age", "type": "days_since_today", "column": "Install Date"}
            ],
            "rules": [
                {
                    "id": "r",
                    "severity": "error",
                    "fail_when": {"column": "Age", "greater_than": 1000},
                    "message": "old",
                }
            ],
        }
    )
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    # 2020-01-01 is ~2340 days ago → fires; 2025-01-01 is ~517 days ago → no fire
    assert firing == [0]


def test_days_apart_greater_than_columns_are_normalized() -> None:
    # Both columns in days_apart_greater_than should be inferred and normalized
    df = pd.DataFrame(
        {
            "Start": ["01/01/2024", "01/01/2024"],
            "End": ["06/01/2024", "01/15/2024"],
        }
    )
    bundle = RuleBundle.from_json_dict(
        {
            "version": 1,
            "rules": [
                {
                    "id": "r",
                    "severity": "error",
                    "fail_when": {
                        "column": "Start",
                        "days_apart_greater_than": {"column": "End", "days": 30},
                    },
                    "message": "too far apart",
                }
            ],
        }
    )
    result = validate_dataframe(df, bundle)
    firing = [f.row_index for f in result.findings]
    # Row 0: Jan 1 to Jun 1 = 152 days → fires; Row 1: 14 days → no fire
    assert firing == [0]
