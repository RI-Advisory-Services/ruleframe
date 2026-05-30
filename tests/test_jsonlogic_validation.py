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
