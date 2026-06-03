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


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ({"column": "A", "equals": "x"}, {"==": [{"var": "/A"}, "x"]}),
        ({"column": "A", "not_equals": "x"}, {"!=": [{"var": "/A"}, "x"]}),
        (
            {"column": "A", "equals_column": "B"},
            {"==": [{"var": "/A"}, {"var": "/B"}]},
        ),
        (
            {"column": "A", "not_equals_column": "B"},
            {"!=": [{"var": "/A"}, {"var": "/B"}]},
        ),
        (
            {"column": "A", "greater_than_column": "B"},
            {">": [{"var": "/A"}, {"var": "/B"}]},
        ),
        (
            {"column": "A", "greater_than_or_equal_column": "B"},
            {">=": [{"var": "/A"}, {"var": "/B"}]},
        ),
        (
            {"column": "A", "less_than_column": "B"},
            {"<": [{"var": "/A"}, {"var": "/B"}]},
        ),
        (
            {"column": "A", "less_than_or_equal_column": "B"},
            {"<=": [{"var": "/A"}, {"var": "/B"}]},
        ),
        ({"column": "A", "greater_than": 10}, {">": [{"var": "/A"}, 10]}),
        (
            {"column": "A", "greater_than_or_equal": 10},
            {">=": [{"var": "/A"}, 10]},
        ),
        ({"column": "A", "less_than": 10}, {"<": [{"var": "/A"}, 10]}),
        (
            {"column": "A", "less_than_or_equal": 10},
            {"<=": [{"var": "/A"}, 10]},
        ),
        ({"column": "A", "in": ["x", "y"]}, {"in": [{"var": "/A"}, ["x", "y"]]}),
        (
            {"column": "A", "not_in": ["x", "y"]},
            {"!": [{"in": [{"var": "/A"}, ["x", "y"]]}]},
        ),
        (
            {"column": "A", "contains": "needle"},
            {"contains": [{"var": "/A"}, "needle"]},
        ),
        (
            {"column": "A", "not_contains": "needle"},
            {"!": [{"contains": [{"var": "/A"}, "needle"]}]},
        ),
        ({"column": "A", "between": [1, 5]}, {"between": [{"var": "/A"}, [1, 5]]}),
        (
            {"column": "A", "not_between": [1, 5]},
            {"!": [{"between": [{"var": "/A"}, [1, 5]]}]},
        ),
        ({"column": "A", "is_blank": True}, {"is_blank": [{"var": "/A"}]}),
        ({"column": "A", "is_blank": False}, {"is_not_blank": [{"var": "/A"}]}),
        ({"column": "A", "is_not_blank": True}, {"is_not_blank": [{"var": "/A"}]}),
        ({"column": "A", "is_not_blank": False}, {"is_blank": [{"var": "/A"}]}),
        (
            {"column": "A", "days_apart_greater_than": {"column": "B", "days": 30}},
            {"date_days_apart_gt": [{"var": "/A"}, {"var": "/B"}, 30]},
        ),
        (
            {"column": "A", "date_greater_than": "2024-01-01"},
            {"date_gt": [{"var": "/A"}, "2024-01-01"]},
        ),
        (
            {"column": "A", "date_greater_than_or_equal": "2024-01-01"},
            {"date_gte": [{"var": "/A"}, "2024-01-01"]},
        ),
        (
            {"column": "A", "date_less_than": "2024-01-01"},
            {"date_lt": [{"var": "/A"}, "2024-01-01"]},
        ),
        (
            {"column": "A", "date_less_than_or_equal": "2024-01-01"},
            {"date_lte": [{"var": "/A"}, "2024-01-01"]},
        ),
        ({"column": "A", "date_equals": "2024-01-01"}, {"date_eq": [{"var": "/A"}, "2024-01-01"]}),
        (
            {"column": "A", "date_between": ["2024-01-01", "2024-12-31"]},
            {"date_between": [{"var": "/A"}, ["2024-01-01", "2024-12-31"]]},
        ),
        (
            {"column": "A", "date_not_between": ["2024-01-01", "2024-12-31"]},
            {"!": [{"date_between": [{"var": "/A"}, ["2024-01-01", "2024-12-31"]]}]},
        ),
    ],
)
def test_compile_condition_supports_all_friendly_operators(condition, expected) -> None:
    assert compile_condition(condition) == expected


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (
            {"all": [{"column": "A", "equals": 1}, {"column": "B", "equals": 2}]},
            {"and": [{"==": [{"var": "/A"}, 1]}, {"==": [{"var": "/B"}, 2]}]},
        ),
        (
            {"any": [{"column": "A", "equals": 1}, {"column": "B", "equals": 2}]},
            {"or": [{"==": [{"var": "/A"}, 1]}, {"==": [{"var": "/B"}, 2]}]},
        ),
        (
            {"not": {"column": "A", "equals": 1}},
            {"!": [{"==": [{"var": "/A"}, 1]}]},
        ),
    ],
)
def test_compile_condition_supports_logic_nodes(condition, expected) -> None:
    assert compile_condition(condition) == expected


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
