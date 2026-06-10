"""Structural and end-to-end tests for the predicate registry."""

import pandas as pd
import pytest

from ruleframe import RuleBundle, validate_dataframe
from ruleframe.predicates import (
    PREDICATE_REGISTRY,
    ColumnPredicate,
    DateColumnPredicate,
    DateScalarPredicate,
    DaysApartGreaterThan,
    Predicate,
)

# ===========================================================================
# Group 1 — structural / registry tests
# ===========================================================================


@pytest.mark.parametrize("key,cls", list(PREDICATE_REGISTRY.items()))
def test_predicate_key_matches_registry(key, cls) -> None:
    assert cls.key == key
    assert isinstance(cls.key, str) and cls.key != ""


@pytest.mark.parametrize("key,cls", list(PREDICATE_REGISTRY.items()))
def test_predicate_compile_returns_dict(key, cls) -> None:
    col_var = {"var": "/Col"}
    # Provide a reasonable sample value per predicate type
    sample = _sample_value(cls)
    result = cls.compile(col_var, sample)
    assert isinstance(result, dict)


@pytest.mark.parametrize(
    "key,cls",
    [(k, c) for k, c in PREDICATE_REGISTRY.items() if issubclass(c, DateScalarPredicate)],
)
def test_date_scalar_predicates_report_left_column(key, cls) -> None:
    assert cls.date_columns("Col", "2024-01-01") == {"Col"}


@pytest.mark.parametrize(
    "key,cls",
    [(k, c) for k, c in PREDICATE_REGISTRY.items() if issubclass(c, DateColumnPredicate)],
)
def test_date_column_predicates_report_both_columns(key, cls) -> None:
    assert cls.date_columns("Col", "Other") == {"Col", "Other"}


@pytest.mark.parametrize(
    "key,cls",
    [(k, c) for k, c in PREDICATE_REGISTRY.items() if issubclass(c, ColumnPredicate)],
)
def test_column_predicates_report_referenced_column(key, cls) -> None:
    assert cls.referenced_columns("Col", "Other") == {"Other"}


def test_days_apart_greater_than_date_columns() -> None:
    value = {"column": "End", "days": 30}
    assert DaysApartGreaterThan.date_columns("Start", value) == {"Start", "End"}


def test_days_apart_greater_than_referenced_columns() -> None:
    value = {"column": "End", "days": 30}
    assert DaysApartGreaterThan.referenced_columns("Start", value) == {"End"}


def test_all_predicates_are_subclasses_of_predicate() -> None:
    for cls in PREDICATE_REGISTRY.values():
        assert issubclass(cls, Predicate)


# ===========================================================================
# Group 2 — end-to-end validate_dataframe tests for ALL predicates
# ===========================================================================


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


# ---------------------------------------------------------------------------
# Scalar predicates
# ---------------------------------------------------------------------------


class TestScalarPredicatesEndToEnd:
    """End-to-end tests for scalar predicates (column vs. literal)."""

    def test_equals(self) -> None:
        df = pd.DataFrame({"A": ["Yes", "No"]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "equals": "Yes"}))
        assert [f.row_index for f in result.findings] == [0]

    def test_not_equals(self) -> None:
        df = pd.DataFrame({"A": ["Yes", "No", None]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "not_equals": "Yes"}))
        # "No" fires, None fires (NullSafeNotEq: blank left + non-blank right)
        assert [f.row_index for f in result.findings] == [1, 2]

    def test_greater_than(self) -> None:
        df = pd.DataFrame({"A": [11, 10, 9]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "greater_than": 10}))
        assert [f.row_index for f in result.findings] == [0]

    def test_greater_than_or_equal(self) -> None:
        df = pd.DataFrame({"A": [10, 9]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "greater_than_or_equal": 10})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_less_than(self) -> None:
        df = pd.DataFrame({"A": [9, 10]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "less_than": 10}))
        assert [f.row_index for f in result.findings] == [0]

    def test_less_than_or_equal(self) -> None:
        df = pd.DataFrame({"A": [10, 11]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "less_than_or_equal": 10})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_in(self) -> None:
        df = pd.DataFrame({"A": ["x", "y", "z"]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "in": ["x", "y"]}))
        assert [f.row_index for f in result.findings] == [0, 1]

    def test_not_in(self) -> None:
        df = pd.DataFrame({"A": ["z", "x"]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "not_in": ["x", "y"]}))
        assert [f.row_index for f in result.findings] == [0]

    def test_contains(self) -> None:
        df = pd.DataFrame({"A": ["hello world", "goodbye"]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "contains": "world"}))
        assert [f.row_index for f in result.findings] == [0]

    def test_not_contains(self) -> None:
        df = pd.DataFrame({"A": ["plain text", "has needle"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "not_contains": "needle"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_between(self) -> None:
        df = pd.DataFrame({"A": [3, 0, 6]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "between": [1, 5]}))
        assert [f.row_index for f in result.findings] == [0]

    def test_not_between(self) -> None:
        df = pd.DataFrame({"A": [0, 3, 6]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "not_between": [1, 5]}))
        assert [f.row_index for f in result.findings] == [0, 2]

    def test_is_blank_true(self) -> None:
        df = pd.DataFrame({"A": [None, "", "value"]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "is_blank": True}))
        assert [f.row_index for f in result.findings] == [0, 1]

    def test_is_blank_false(self) -> None:
        df = pd.DataFrame({"A": ["value", None, ""]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "is_blank": False}))
        assert [f.row_index for f in result.findings] == [0]

    def test_is_not_blank_true(self) -> None:
        df = pd.DataFrame({"A": ["value", None, ""]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "is_not_blank": True}))
        assert [f.row_index for f in result.findings] == [0]

    def test_is_not_blank_false(self) -> None:
        df = pd.DataFrame({"A": [None, "", "value"]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "is_not_blank": False}))
        assert [f.row_index for f in result.findings] == [0, 1]

    def test_null_suppression_scalar(self) -> None:
        """Null on left side does not fire for comparison predicates."""
        df = pd.DataFrame({"A": [None]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "greater_than": 0}))
        assert result.findings == []


# ---------------------------------------------------------------------------
# Column predicates (column vs. column, raw comparison)
# ---------------------------------------------------------------------------


class TestColumnPredicatesEndToEnd:
    """End-to-end tests for column-to-column predicates."""

    def test_equals_column(self) -> None:
        df = pd.DataFrame({"A": [1, 1], "B": [1, 2]})
        result = validate_dataframe(df, _single_rule_bundle({"column": "A", "equals_column": "B"}))
        assert [f.row_index for f in result.findings] == [0]

    def test_not_equals_column(self) -> None:
        df = pd.DataFrame({"A": [1, 1], "B": [2, 1]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "not_equals_column": "B"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_greater_than_column(self) -> None:
        df = pd.DataFrame({"A": [3, 2], "B": [2, 3]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "greater_than_column": "B"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_greater_than_or_equal_column(self) -> None:
        df = pd.DataFrame({"A": [3, 2], "B": [3, 3]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "greater_than_or_equal_column": "B"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_less_than_column(self) -> None:
        df = pd.DataFrame({"A": [2, 3], "B": [3, 2]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "less_than_column": "B"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_less_than_or_equal_column(self) -> None:
        df = pd.DataFrame({"A": [3, 4], "B": [3, 3]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "less_than_or_equal_column": "B"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_null_suppression_column(self) -> None:
        """Null on either side does not fire for column comparison."""
        df = pd.DataFrame({"A": [None, 5], "B": [3, None]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "greater_than_column": "B"})
        )
        assert result.findings == []


# ---------------------------------------------------------------------------
# Date scalar predicates (column vs. literal date)
# ---------------------------------------------------------------------------


class TestDateScalarPredicatesEndToEnd:
    """End-to-end tests for date scalar predicates."""

    def test_date_equals(self) -> None:
        df = pd.DataFrame({"A": ["2024-03-01", "2024-03-02"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_equals": "2024-03-01"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_date_greater_than(self) -> None:
        df = pd.DataFrame({"A": ["2024-06-01", "2024-01-01"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than": "2024-03-01"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_date_greater_than_or_equal(self) -> None:
        df = pd.DataFrame({"A": ["2024-03-01", "2024-02-28"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than_or_equal": "2024-03-01"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_date_less_than(self) -> None:
        df = pd.DataFrame({"A": ["2024-01-01", "2024-06-01"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_less_than": "2024-03-01"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_date_less_than_or_equal(self) -> None:
        df = pd.DataFrame({"A": ["2024-03-01", "2024-03-02"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_less_than_or_equal": "2024-03-01"})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_date_between(self) -> None:
        df = pd.DataFrame({"A": ["2024-03-15", "2024-01-01", "2024-12-31"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_between": ["2024-03-01", "2024-06-01"]})
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_date_not_between(self) -> None:
        df = pd.DataFrame({"A": ["2024-01-01", "2024-03-15", "2024-12-31"]})
        result = validate_dataframe(
            df,
            _single_rule_bundle({"column": "A", "date_not_between": ["2024-03-01", "2024-06-01"]}),
        )
        assert [f.row_index for f in result.findings] == [0, 2]

    def test_date_scalar_null_does_not_fire(self) -> None:
        df = pd.DataFrame({"A": [None, ""]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than": "2000-01-01"})
        )
        assert result.findings == []

    def test_date_scalar_us_format(self) -> None:
        df = pd.DataFrame({"A": ["06/01/2024", "01/01/2024"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than": "2024-03-01"})
        )
        assert [f.row_index for f in result.findings] == [0]


# ---------------------------------------------------------------------------
# Date column predicates (column vs. column, date-aware)
# ---------------------------------------------------------------------------


class TestDateColumnPredicatesEndToEnd:
    """End-to-end tests for the date_*_column predicates."""

    def test_date_greater_than_column_iso(self) -> None:
        df = pd.DataFrame(
            {
                "A": ["2024-06-01", "2024-01-01", None],
                "B": ["2024-03-01", "2024-03-01", "2024-03-01"],
            }
        )
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0]

    def test_date_greater_than_column_us_format(self) -> None:
        # Non-ISO format — requires normalization to work correctly
        df = pd.DataFrame({"A": ["06/01/2024", "01/01/2024"], "B": ["03/01/2024", "03/01/2024"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0]

    def test_date_greater_than_or_equal_column(self) -> None:
        df = pd.DataFrame(
            {
                "A": ["2024-03-01", "2024-03-01", "2024-02-28"],
                "B": ["2024-03-01", "2024-02-01", "2024-03-01"],
            }
        )
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than_or_equal_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0, 1]

    def test_date_less_than_column(self) -> None:
        df = pd.DataFrame({"A": ["2024-01-01", "2024-06-01"], "B": ["2024-03-01", "2024-03-01"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_less_than_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0]

    def test_date_less_than_or_equal_column(self) -> None:
        df = pd.DataFrame(
            {
                "A": ["2024-03-01", "2024-02-28", "2024-03-02"],
                "B": ["2024-03-01", "2024-03-01", "2024-03-01"],
            }
        )
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_less_than_or_equal_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0, 1]

    def test_date_equals_column(self) -> None:
        df = pd.DataFrame({"A": ["2024-03-01", "2024-03-02"], "B": ["2024-03-01", "2024-03-01"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_equals_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0]

    def test_date_not_equals_column(self) -> None:
        df = pd.DataFrame(
            {
                "A": ["2024-03-01", "2024-03-02", None],
                "B": ["2024-03-01", "2024-03-01", "2024-03-01"],
            }
        )
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_not_equals_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        # Row 1: different dates → fires. Row 2: left blank + right non-blank → fires (NullSafeNotEq).
        assert firing == [1, 2]

    def test_date_column_predicates_null_suppression(self) -> None:
        """Blank on either side does not fire for date_greater_than_column."""
        df = pd.DataFrame({"A": [None, "2024-06-01"], "B": ["2024-03-01", None]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than_column": "B"})
        )
        assert result.findings == []

    def test_date_greater_than_or_equal_column_us_format(self) -> None:
        # Verifies the gap fix: US-format dates in column-to-column comparison
        df = pd.DataFrame({"A": ["06/01/2024", "01/01/2024"], "B": ["03/01/2024", "03/01/2024"]})
        result = validate_dataframe(
            df, _single_rule_bundle({"column": "A", "date_greater_than_or_equal_column": "B"})
        )
        firing = [f.row_index for f in result.findings]
        assert firing == [0]


# ---------------------------------------------------------------------------
# days_apart_greater_than
# ---------------------------------------------------------------------------


class TestDaysApartGreaterThanEndToEnd:
    """End-to-end tests for the days_apart_greater_than predicate."""

    def test_fires_when_gap_exceeds_threshold(self) -> None:
        df = pd.DataFrame({"A": ["2024-01-01", "2024-01-01"], "B": ["2024-06-01", "2024-01-15"]})
        result = validate_dataframe(
            df,
            _single_rule_bundle(
                {"column": "A", "days_apart_greater_than": {"column": "B", "days": 30}}
            ),
        )
        assert [f.row_index for f in result.findings] == [0]

    def test_null_suppression(self) -> None:
        df = pd.DataFrame({"A": [None, "2024-01-01"], "B": ["2024-06-01", None]})
        result = validate_dataframe(
            df,
            _single_rule_bundle(
                {"column": "A", "days_apart_greater_than": {"column": "B", "days": 1}}
            ),
        )
        assert result.findings == []

    def test_us_format_dates(self) -> None:
        df = pd.DataFrame({"A": ["01/01/2024"], "B": ["06/01/2024"]})
        result = validate_dataframe(
            df,
            _single_rule_bundle(
                {"column": "A", "days_apart_greater_than": {"column": "B", "days": 30}}
            ),
        )
        assert [f.row_index for f in result.findings] == [0]


# ===========================================================================
# Helpers
# ===========================================================================


def _sample_value(cls: type[Predicate]):
    """Return a reasonable sample value for compiling a predicate."""
    if issubclass(cls, (ColumnPredicate, DateColumnPredicate)):
        return "OtherCol"
    if cls.key == "days_apart_greater_than":
        return {"column": "Other", "days": 30}
    if cls.key in ("is_blank", "is_not_blank"):
        return True
    if cls.key in ("between", "not_between", "date_between", "date_not_between"):
        return ["2024-01-01", "2024-12-31"]
    if cls.key in ("in", "not_in"):
        return ["a", "b"]
    return "test_value"
