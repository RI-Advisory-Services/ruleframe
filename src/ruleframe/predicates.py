"""Predicate registry — the single source of truth for authoring-layer keywords.

A *predicate* is a boolean test that rule authors write in YAML. Each concrete
subclass maps one YAML keyword to a compiled JsonLogic expression.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


# ---------------------------------------------------------------------------
# JSON Pointer helper (used by predicates and imported by compiler)
# ---------------------------------------------------------------------------


def json_pointer(column_name: str) -> str:
    """Convert a DataFrame column name to a JSON Pointer variable path."""
    return "/" + column_name.replace("~", "~0").replace("/", "~1")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PREDICATE_REGISTRY: dict[str, type[Predicate]] = {}


def predicate(cls: type[Predicate]) -> type[Predicate]:
    """Class decorator that registers a Predicate by its key."""
    PREDICATE_REGISTRY[cls.key] = cls
    return cls


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class Predicate(ABC):
    """Base class for all authoring-layer predicates."""

    key: ClassVar[str]

    @classmethod
    @abstractmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        """Return a JsonLogic expression dict."""

    @classmethod
    def date_columns(cls, left: str, value: Any) -> set[str]:
        """Column names that must be date-normalized before evaluation."""
        return set()

    @classmethod
    def referenced_columns(cls, left: str, value: Any) -> set[str]:
        """Right-hand column names that must exist in the DataFrame."""
        return set()


# ---------------------------------------------------------------------------
# Intermediate base classes
# ---------------------------------------------------------------------------


class ScalarPredicate(Predicate):
    """Column vs. literal, single JsonLogic op."""

    jsonlogic_op: ClassVar[str]

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {cls.jsonlogic_op: [column_var, value]}


class DateScalarPredicate(ScalarPredicate):
    """Column vs. literal date — also marks the left column for normalization."""

    @classmethod
    def date_columns(cls, left: str, value: Any) -> set[str]:
        return {left}


class ColumnPredicate(Predicate):
    """Column vs. column, single JsonLogic op."""

    jsonlogic_op: ClassVar[str]

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {cls.jsonlogic_op: [column_var, {"var": json_pointer(str(value))}]}

    @classmethod
    def referenced_columns(cls, left: str, value: Any) -> set[str]:
        return {str(value)}


class DateColumnPredicate(ColumnPredicate):
    """Column vs. column, date-aware — marks both columns for normalization."""

    @classmethod
    def date_columns(cls, left: str, value: Any) -> set[str]:
        return {left, str(value)}


# ---------------------------------------------------------------------------
# Concrete ScalarPredicate subclasses
# ---------------------------------------------------------------------------


@predicate
class Equals(ScalarPredicate):
    key = "equals"
    jsonlogic_op = "=="


@predicate
class NotEquals(ScalarPredicate):
    key = "not_equals"
    jsonlogic_op = "!="


@predicate
class GreaterThan(ScalarPredicate):
    key = "greater_than"
    jsonlogic_op = ">"


@predicate
class GreaterThanOrEqual(ScalarPredicate):
    key = "greater_than_or_equal"
    jsonlogic_op = ">="


@predicate
class LessThan(ScalarPredicate):
    key = "less_than"
    jsonlogic_op = "<"


@predicate
class LessThanOrEqual(ScalarPredicate):
    key = "less_than_or_equal"
    jsonlogic_op = "<="


@predicate
class In(ScalarPredicate):
    key = "in"
    jsonlogic_op = "in"


@predicate
class Contains(ScalarPredicate):
    key = "contains"
    jsonlogic_op = "contains"


@predicate
class Between(ScalarPredicate):
    key = "between"
    jsonlogic_op = "between"


# ---------------------------------------------------------------------------
# Concrete ColumnPredicate subclasses
# ---------------------------------------------------------------------------


@predicate
class EqualsColumn(ColumnPredicate):
    key = "equals_column"
    jsonlogic_op = "=="


@predicate
class NotEqualsColumn(ColumnPredicate):
    key = "not_equals_column"
    jsonlogic_op = "!="


@predicate
class GreaterThanColumn(ColumnPredicate):
    key = "greater_than_column"
    jsonlogic_op = ">"


@predicate
class GreaterThanOrEqualColumn(ColumnPredicate):
    key = "greater_than_or_equal_column"
    jsonlogic_op = ">="


@predicate
class LessThanColumn(ColumnPredicate):
    key = "less_than_column"
    jsonlogic_op = "<"


@predicate
class LessThanOrEqualColumn(ColumnPredicate):
    key = "less_than_or_equal_column"
    jsonlogic_op = "<="


# ---------------------------------------------------------------------------
# Concrete DateScalarPredicate subclasses
# ---------------------------------------------------------------------------


@predicate
class DateEquals(DateScalarPredicate):
    key = "date_equals"
    jsonlogic_op = "date_eq"


@predicate
class DateGreaterThan(DateScalarPredicate):
    key = "date_greater_than"
    jsonlogic_op = "date_gt"


@predicate
class DateGreaterThanOrEqual(DateScalarPredicate):
    key = "date_greater_than_or_equal"
    jsonlogic_op = "date_gte"


@predicate
class DateLessThan(DateScalarPredicate):
    key = "date_less_than"
    jsonlogic_op = "date_lt"


@predicate
class DateLessThanOrEqual(DateScalarPredicate):
    key = "date_less_than_or_equal"
    jsonlogic_op = "date_lte"


@predicate
class DateBetween(DateScalarPredicate):
    key = "date_between"
    jsonlogic_op = "date_between"


# ---------------------------------------------------------------------------
# Concrete DateColumnPredicate subclasses (NEW)
# ---------------------------------------------------------------------------


@predicate
class DateEqualsColumn(DateColumnPredicate):
    key = "date_equals_column"
    jsonlogic_op = "date_eq"


@predicate
class DateNotEqualsColumn(DateColumnPredicate):
    key = "date_not_equals_column"
    jsonlogic_op = "!="


@predicate
class DateGreaterThanColumn(DateColumnPredicate):
    key = "date_greater_than_column"
    jsonlogic_op = "date_gt"


@predicate
class DateGreaterThanOrEqualColumn(DateColumnPredicate):
    key = "date_greater_than_or_equal_column"
    jsonlogic_op = "date_gte"


@predicate
class DateLessThanColumn(DateColumnPredicate):
    key = "date_less_than_column"
    jsonlogic_op = "date_lt"


@predicate
class DateLessThanOrEqualColumn(DateColumnPredicate):
    key = "date_less_than_or_equal_column"
    jsonlogic_op = "date_lte"


# ---------------------------------------------------------------------------
# Concrete overrides (irregular — own their compile)
# ---------------------------------------------------------------------------


@predicate
class NotIn(Predicate):
    key = "not_in"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {"!": [{"in": [column_var, value]}]}


@predicate
class NotContains(Predicate):
    key = "not_contains"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {"!": [{"contains": [column_var, value]}]}


@predicate
class NotBetween(Predicate):
    key = "not_between"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {"!": [{"between": [column_var, value]}]}


@predicate
class DateNotBetween(Predicate):
    key = "date_not_between"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {"!": [{"date_between": [column_var, value]}]}

    @classmethod
    def date_columns(cls, left: str, value: Any) -> set[str]:
        return {left}


@predicate
class IsBlank(Predicate):
    key = "is_blank"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {"is_blank": [column_var]} if value else {"is_not_blank": [column_var]}


@predicate
class IsNotBlank(Predicate):
    key = "is_not_blank"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {"is_not_blank": [column_var]} if value else {"is_blank": [column_var]}


@predicate
class DaysApartGreaterThan(Predicate):
    key = "days_apart_greater_than"

    @classmethod
    def compile(cls, column_var: dict, value: Any) -> dict:
        return {
            "date_days_apart_gt": [
                column_var,
                {"var": json_pointer(str(value["column"]))},
                value["days"],
            ]
        }

    @classmethod
    def date_columns(cls, left: str, value: Any) -> set[str]:
        return {left, str(value["column"])}

    @classmethod
    def referenced_columns(cls, left: str, value: Any) -> set[str]:
        return {str(value["column"])}
