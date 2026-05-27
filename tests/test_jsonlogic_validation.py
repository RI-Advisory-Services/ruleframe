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
