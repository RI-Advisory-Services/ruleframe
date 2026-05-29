import pytest

from ruleframe.compiler import (
    COLUMN_REFERENCE_OPERATORS,
    collect_required_columns,
    collect_rule_columns,
    compile_condition,
    compile_rule,
    json_pointer,
)
from ruleframe.exceptions import BundleValidationError


def test_json_pointer_escapes_excel_column_names() -> None:
    assert json_pointer("QA/QC ~ Resolved?") == "/QA~1QC ~0 Resolved?"


def test_compile_condition_uses_json_pointer_vars() -> None:
    compiled = compile_condition(
        {
            "all": [
                {"column": "Selected for QA/QC", "equals": "Yes"},
                {"column": "QA/QC Resolved", "is_blank": True},
            ]
        }
    )
    assert compiled == {
        "and": [
            {"==": [{"var": "/Selected for QA~1QC"}, "Yes"]},
            {"is_blank": [{"var": "/QA~1QC Resolved"}]},
        ]
    }


def test_collect_required_columns_includes_column_to_column_references() -> None:
    columns = collect_required_columns(
        {
            "all": [
                {"column": "Installed Quantity", "equals_column": "Reported Quantity"},
                {
                    "column": "Installation Date",
                    "days_apart_greater_than": {"column": "Date Inspected", "days": 31},
                },
            ]
        }
    )
    assert columns == {
        "Installed Quantity",
        "Reported Quantity",
        "Installation Date",
        "Date Inspected",
    }


def test_column_reference_operators_are_centralized() -> None:
    assert COLUMN_REFERENCE_OPERATORS == {
        "equals_column": "==",
        "not_equals_column": "!=",
        "greater_than_column": ">",
        "greater_than_or_equal_column": ">=",
        "less_than_column": "<",
        "less_than_or_equal_column": "<=",
    }


# ===========================================================================
# compile_rule direct tests
# ===========================================================================


def test_compile_rule_produces_jsonlogic() -> None:
    rule = {
        "id": "r1",
        "fail_when": {"column": "Status", "equals": "Error"},
    }
    assert compile_rule(rule) == {"==": [{"var": "/Status"}, "Error"]}


def test_compile_rule_missing_fail_when_raises() -> None:
    with pytest.raises(BundleValidationError, match="fail_when"):
        compile_rule({"id": "r1", "message": "no fail_when here"})


def test_compile_rule_non_dict_fail_when_raises() -> None:
    with pytest.raises(BundleValidationError, match="fail_when"):
        compile_rule({"id": "r1", "fail_when": "column: Status"})


# ===========================================================================
# compile_condition error cases
# ===========================================================================


def test_compile_condition_unsupported_operator_raises() -> None:
    with pytest.raises(BundleValidationError, match="Unsupported friendly operator"):
        compile_condition({"column": "Status", "fuzzy_match": "Active"})


def test_compile_condition_missing_column_raises() -> None:
    with pytest.raises(BundleValidationError, match="'column'"):
        compile_condition({"equals": "something"})


def test_compile_condition_multiple_operators_raises() -> None:
    with pytest.raises(BundleValidationError, match="exactly one operator"):
        compile_condition({"column": "Status", "equals": "A", "not_equals": "B"})


# ===========================================================================
# collect_rule_columns direct tests
# ===========================================================================


def test_collect_rule_columns_aggregates_across_rules() -> None:
    rules = [
        {"id": "r1", "fail_when": {"column": "A", "equals": "Yes"}},
        {"id": "r2", "fail_when": {"column": "B", "greater_than": 0}},
    ]
    assert collect_rule_columns(rules) == {"A", "B"}


def test_collect_rule_columns_skips_rules_without_fail_when() -> None:
    rules = [
        {"id": "r1", "fail_when": {"column": "A", "equals": "Yes"}},
        {"id": "r2"},  # no fail_when
    ]
    assert collect_rule_columns(rules) == {"A"}


def test_collect_rule_columns_empty_rules() -> None:
    assert collect_rule_columns([]) == set()
