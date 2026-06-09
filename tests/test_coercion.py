"""Tests for centralized type inference and coercion."""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from ruleframe import RuleBundle, validate_dataframe
from ruleframe.coercion import (
    CoercionEvent,
    apply_numeric_coercion,
    infer_column_types,
)
from ruleframe.exceptions import BundleValidationError, InputSchemaError


# ---------------------------------------------------------------------------
# Type inference from predicates
# ---------------------------------------------------------------------------


class TestInferColumnTypesFromPredicates:
    def test_greater_than_implies_numeric(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Age", "greater_than": 100}}]
        result = infer_column_types(rules, [])
        assert result["Age"] == "numeric"

    def test_less_than_implies_numeric(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Score", "less_than": 0}}]
        result = infer_column_types(rules, [])
        assert result["Score"] == "numeric"

    def test_between_implies_numeric(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Value", "between": [1, 10]}}]
        result = infer_column_types(rules, [])
        assert result["Value"] == "numeric"

    def test_greater_than_column_implies_both_numeric(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "A", "greater_than_column": "B"}}]
        result = infer_column_types(rules, [])
        assert result["A"] == "numeric"
        assert result["B"] == "numeric"

    def test_equals_with_int_implies_numeric(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Status", "equals": 1}}]
        result = infer_column_types(rules, [])
        assert result["Status"] == "numeric"

    def test_equals_with_string_implies_string(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Status", "equals": "Active"}}]
        result = infer_column_types(rules, [])
        assert result["Status"] == "string"

    def test_not_equals_with_string_implies_string(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Type", "not_equals": "Residential"}}]
        result = infer_column_types(rules, [])
        assert result["Type"] == "string"

    def test_in_all_numeric_implies_numeric(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Code", "in": [1, 2, 3]}}]
        result = infer_column_types(rules, [])
        assert result["Code"] == "numeric"

    def test_in_all_strings_implies_string(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Status", "in": ["A", "B", "C"]}}]
        result = infer_column_types(rules, [])
        assert result["Status"] == "string"

    def test_in_mixed_types_raises(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "X", "in": [1, "two", 3]}}]
        with pytest.raises(BundleValidationError, match="mixed types"):
            infer_column_types(rules, [])

    def test_in_mixed_types_raises_v2(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "X", "in": [1, "2", 3]}}]
        with pytest.raises(BundleValidationError, match="mixed types"):
            infer_column_types(rules, [])

    def test_not_in_all_strings_implies_string(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Status", "not_in": ["X", "Y"]}}]
        result = infer_column_types(rules, [])
        assert result["Status"] == "string"

    def test_is_blank_does_not_imply_type(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Notes", "is_blank": True}}]
        result = infer_column_types(rules, [])
        assert "Notes" not in result

    def test_nested_all_condition(self) -> None:
        rules = [
            {
                "id": "r1",
                "fail_when": {
                    "all": [
                        {"column": "A", "greater_than": 10},
                        {"column": "B", "equals": "Yes"},
                    ]
                },
            }
        ]
        result = infer_column_types(rules, [])
        assert result["A"] == "numeric"
        assert result["B"] == "string"

    def test_nested_any_condition(self) -> None:
        rules = [
            {
                "id": "r1",
                "fail_when": {
                    "any": [
                        {"column": "X", "less_than": 5},
                        {"column": "Y", "greater_than_or_equal": 100},
                    ]
                },
            }
        ]
        result = infer_column_types(rules, [])
        assert result["X"] == "numeric"
        assert result["Y"] == "numeric"

    def test_nested_not_condition(self) -> None:
        rules = [
            {
                "id": "r1",
                "fail_when": {"not": {"column": "Score", "greater_than": 50}},
            }
        ]
        result = infer_column_types(rules, [])
        assert result["Score"] == "numeric"


# ---------------------------------------------------------------------------
# Type inference from computed columns
# ---------------------------------------------------------------------------


class TestInferColumnTypesFromComputed:
    def test_sum_implies_numeric(self) -> None:
        specs = [{"type": "sum", "columns": ["A", "B"], "name": "Total"}]
        result = infer_column_types([], specs)
        assert result["A"] == "numeric"
        assert result["B"] == "numeric"

    def test_divide_implies_numeric(self) -> None:
        specs = [{"type": "divide", "columns": ["Num", "Den"], "name": "Ratio"}]
        result = infer_column_types([], specs)
        assert result["Num"] == "numeric"
        assert result["Den"] == "numeric"

    def test_group_sum_implies_value_column_numeric(self) -> None:
        specs = [
            {
                "type": "group_sum",
                "group_by": "Project",
                "value_column": "kWh",
                "name": "TotalKWh",
            }
        ]
        result = infer_column_types([], specs)
        assert result["kWh"] == "numeric"
        assert "Project" not in result  # group_by column is not inferred as numeric

    def test_years_since_year_implies_numeric(self) -> None:
        specs = [{"type": "years_since_year", "column": "Year", "name": "Age"}]
        result = infer_column_types([], specs)
        assert result["Year"] == "numeric"

    def test_date_diff_does_not_imply_numeric(self) -> None:
        specs = [
            {"type": "date_diff", "start_column": "Start", "end_column": "End", "name": "Days"}
        ]
        result = infer_column_types([], specs)
        assert "Start" not in result
        assert "End" not in result


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestConflictDetection:
    def test_numeric_and_string_conflict_raises(self) -> None:
        rules = [
            {"id": "r1", "fail_when": {"column": "X", "greater_than": 10}},
            {"id": "r2", "fail_when": {"column": "X", "equals": "Active"}},
        ]
        with pytest.raises(BundleValidationError, match="conflicting type signals"):
            infer_column_types(rules, [])

    def test_same_type_signals_do_not_conflict(self) -> None:
        rules = [
            {"id": "r1", "fail_when": {"column": "X", "greater_than": 10}},
            {"id": "r2", "fail_when": {"column": "X", "less_than": 100}},
        ]
        result = infer_column_types(rules, [])
        assert result["X"] == "numeric"

    def test_computed_and_rule_conflict_raises(self) -> None:
        rules = [{"id": "r1", "fail_when": {"column": "Value", "equals": "text"}}]
        specs = [{"type": "sum", "columns": ["Value", "Other"], "name": "Total"}]
        with pytest.raises(BundleValidationError, match="conflicting type signals"):
            infer_column_types(rules, specs)


# ---------------------------------------------------------------------------
# Coercion pass
# ---------------------------------------------------------------------------


class TestApplyNumericCoercion:
    def test_happy_path_all_values_coerce(self) -> None:
        df = pd.DataFrame({"A": ["1", "2", "3"], "B": ["x", "y", "z"]})
        column_types = {"A": "numeric", "B": "string"}
        working, log = apply_numeric_coercion(df, column_types)
        assert working["A"].tolist() == [1.0, 2.0, 3.0]
        assert working["B"].tolist() == ["x", "y", "z"]  # string columns untouched
        assert len(log) == 1
        assert log[0].column == "A"
        assert log[0].input_dtype == "object"
        assert log[0].coercion_failures == 0

    def test_input_dtype_reflects_already_numeric_column(self) -> None:
        df = pd.DataFrame({"A": [1, 2, 3]})  # int64, already numeric
        column_types = {"A": "numeric"}
        _, log = apply_numeric_coercion(df, column_types)
        assert log[0].input_dtype == "int64"
        assert log[0].coercion_failures == 0

    def test_partial_failure_warns(self) -> None:
        df = pd.DataFrame({"A": ["1", "bad", "3"]})
        column_types = {"A": "numeric"}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            working, log = apply_numeric_coercion(df, column_types, warn=True)
        assert len(w) == 1
        assert "1 non-null" in str(w[0].message)
        assert log[0].coercion_failures == 1
        assert working["A"].tolist()[0] == 1.0
        assert pd.isna(working["A"].iloc[1])

    def test_all_fail_raises_input_schema_error(self) -> None:
        df = pd.DataFrame({"A": ["bad", "worse", "terrible"]})
        column_types = {"A": "numeric"}
        with pytest.raises(InputSchemaError, match="no parseable numeric values"):
            apply_numeric_coercion(df, column_types)

    def test_warn_false_suppresses_warning(self) -> None:
        df = pd.DataFrame({"A": ["1", "bad", "3"]})
        column_types = {"A": "numeric"}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _, log = apply_numeric_coercion(df, column_types, warn=False)
        assert len(w) == 0
        assert log[0].coercion_failures == 1  # log still populated

    def test_all_null_column_no_error(self) -> None:
        df = pd.DataFrame({"A": [None, None, None]})
        column_types = {"A": "numeric"}
        working, log = apply_numeric_coercion(df, column_types)
        assert log[0].total_non_null == 0
        assert log[0].coercion_failures == 0

    def test_missing_column_skipped(self) -> None:
        df = pd.DataFrame({"A": [1, 2]})
        column_types = {"NotPresent": "numeric"}
        working, log = apply_numeric_coercion(df, column_types)
        assert len(log) == 0  # column not in df, not logged


# ---------------------------------------------------------------------------
# Integration: validate_dataframe with coercion
# ---------------------------------------------------------------------------


class TestValidateDataframeCoercion:
    def test_numeric_columns_auto_coerced_from_strings(self) -> None:
        """String numeric values are coerced before rule evaluation."""
        df = pd.DataFrame({"Amount": ["150", "50", "200"]})
        bundle = RuleBundle.from_json_dict(
            {
                "rules": [
                    {
                        "id": "high_amount",
                        "fail_when": {"column": "Amount", "greater_than": 100},
                        "message": "Amount too high",
                    }
                ]
            }
        )
        result = validate_dataframe(df, bundle)
        # Rows 0 and 2 have Amount > 100
        rule_ids = [f.rule_id for f in result.findings]
        assert rule_ids.count("high_amount") == 2
        # Original dtype preserved in annotated output
        assert result.annotated["Amount"].dtype == object
        # Working df has numeric
        assert pd.api.types.is_numeric_dtype(result.working_dataframe["Amount"])

    def test_coercion_log_populated(self) -> None:
        df = pd.DataFrame({"Score": ["10", "20"]})
        bundle = RuleBundle.from_json_dict(
            {
                "rules": [
                    {
                        "id": "r1",
                        "fail_when": {"column": "Score", "greater_than": 50},
                        "message": "Too high",
                    }
                ]
            }
        )
        result = validate_dataframe(df, bundle)
        assert len(result.coercion_log) == 1
        assert result.coercion_log[0].column == "Score"
        assert result.coercion_log[0].coercion_failures == 0

    def test_string_column_not_coerced(self) -> None:
        """Columns inferred as string should not be coerced to numeric."""
        df = pd.DataFrame({"Status": ["Active", "Inactive", "Active"]})
        bundle = RuleBundle.from_json_dict(
            {
                "rules": [
                    {
                        "id": "r1",
                        "fail_when": {"column": "Status", "equals": "Inactive"},
                        "message": "Inactive status",
                    }
                ]
            }
        )
        result = validate_dataframe(df, bundle)
        assert len(result.findings) == 1
        assert result.findings[0].row_index == 1

    def test_mixed_in_list_raises_at_validation_time(self) -> None:
        df = pd.DataFrame({"X": ["a", "b"]})
        bundle = RuleBundle.from_json_dict(
            {
                "rules": [
                    {
                        "id": "r1",
                        "fail_when": {"column": "X", "in": [1, "two", 3]},
                        "message": "bad",
                    }
                ]
            }
        )
        with pytest.raises(BundleValidationError, match="mixed types"):
            validate_dataframe(df, bundle)

    def test_conflict_raises_at_validation_time(self) -> None:
        df = pd.DataFrame({"X": ["1", "2"]})
        bundle = RuleBundle.from_json_dict(
            {
                "rules": [
                    {
                        "id": "r1",
                        "fail_when": {"column": "X", "greater_than": 10},
                        "message": "too high",
                    },
                    {
                        "id": "r2",
                        "fail_when": {"column": "X", "equals": "Active"},
                        "message": "wrong status",
                    },
                ]
            }
        )
        with pytest.raises(BundleValidationError, match="conflicting type signals"):
            validate_dataframe(df, bundle)

    def test_warn_false_suppresses_coercion_warnings(self) -> None:
        df = pd.DataFrame({"Score": ["10", "bad", "30"]})
        bundle = RuleBundle.from_json_dict(
            {
                "rules": [
                    {
                        "id": "r1",
                        "fail_when": {"column": "Score", "greater_than": 50},
                        "message": "high",
                    }
                ]
            }
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = validate_dataframe(df, bundle, warn=False)
        assert len(w) == 0
        assert result.coercion_log[0].coercion_failures == 1

    def test_computed_columns_work_with_coercion(self) -> None:
        """Arithmetic computed columns work when source data is strings."""
        df = pd.DataFrame({"A": ["10", "20"], "B": ["3", "5"]})
        bundle = RuleBundle.from_json_dict(
            {
                "computed_columns": [
                    {"type": "sum", "columns": ["A", "B"], "name": "Total"}
                ],
                "rules": [
                    {
                        "id": "r1",
                        "fail_when": {"column": "Total", "greater_than": 20},
                        "message": "Total too high",
                    }
                ],
            }
        )
        result = validate_dataframe(df, bundle)
        # Total for row 1: 20+5=25 > 20
        assert len(result.findings) == 1
        assert result.findings[0].row_index == 1
