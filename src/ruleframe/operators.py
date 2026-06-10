from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from jsonlogic import JSONLogicSyntaxError
from jsonlogic.core import Operator, OperatorArgument
from jsonlogic.evaluation import EvaluationContext
from jsonlogic.json_schema import BooleanType, JSONSchemaType
from jsonlogic.operators import operator_registry
from jsonlogic.operators.operators import get_value
from jsonlogic.registry import OperatorRegistry

from .dates import parse_date_value


@dataclass
class UnaryOperator(Operator):
    value: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 1:
            raise JSONLogicSyntaxError(f"{operator!r} expects one argument, got {len(arguments)}")
        return cls(operator=operator, value=arguments[0])


class IsBlank(UnaryOperator):
    """Return true for None, pandas NA/NaN, empty strings, and whitespace strings."""

    def typecheck(self, context) -> JSONSchemaType:
        if isinstance(self.value, Operator):
            self.value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        value = get_value(self.value, context)
        return is_blank(value)


class IsNotBlank(IsBlank):
    def evaluate(self, context: EvaluationContext) -> bool:
        return not super().evaluate(context)


@dataclass
class VariadicOperator(Operator):
    values: list[OperatorArgument]

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if not arguments:
            raise JSONLogicSyntaxError(f"{operator!r} expects at least one argument")
        return cls(operator=operator, values=arguments)


class All(VariadicOperator):
    def typecheck(self, context) -> JSONSchemaType:
        for value in self.values:
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        return all(bool(get_value(value, context)) for value in self.values)


class AnyOf(VariadicOperator):
    def typecheck(self, context) -> JSONSchemaType:
        for value in self.values:
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        return any(bool(get_value(value, context)) for value in self.values)


@dataclass
class Not(Operator):
    value: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 1:
            raise JSONLogicSyntaxError(f"{operator!r} expects one argument, got {len(arguments)}")
        return cls(operator=operator, value=arguments[0])

    def typecheck(self, context) -> JSONSchemaType:
        if isinstance(self.value, Operator):
            self.value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        return not bool(get_value(self.value, context))


@dataclass
class InList(Operator):
    needle: OperatorArgument
    haystack: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 2:
            raise JSONLogicSyntaxError(f"{operator!r} expects two arguments, got {len(arguments)}")
        return cls(operator=operator, needle=arguments[0], haystack=arguments[1])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.needle, self.haystack):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        needle = get_value(self.needle, context)
        haystack = get_value(self.haystack, context)
        if haystack is None:
            return False
        return needle in haystack


@dataclass
class Contains(Operator):
    value: OperatorArgument
    expected: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 2:
            raise JSONLogicSyntaxError(f"{operator!r} expects two arguments, got {len(arguments)}")
        return cls(operator=operator, value=arguments[0], expected=arguments[1])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.value, self.expected):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        value = get_value(self.value, context)
        expected = get_value(self.expected, context)
        if value is None or expected is None:
            return False
        return expected in value


@dataclass
class Between(Operator):
    value: OperatorArgument
    bounds: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 2:
            raise JSONLogicSyntaxError(f"{operator!r} expects two arguments, got {len(arguments)}")
        return cls(operator=operator, value=arguments[0], bounds=arguments[1])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.value, self.bounds):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        value = get_value(self.value, context)
        bounds = get_value(self.bounds, context)
        if value is None or not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            return False
        lower, upper = bounds
        if lower is None or upper is None:
            return False
        return bool(lower <= value <= upper)


@dataclass
class DateDaysApartGreaterThan(Operator):
    left_date: OperatorArgument
    right_date: OperatorArgument
    days: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 3:
            raise JSONLogicSyntaxError(
                f"{operator!r} expects three arguments, got {len(arguments)}"
            )
        return cls(
            operator=operator,
            left_date=arguments[0],
            right_date=arguments[1],
            days=arguments[2],
        )

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.left_date, self.right_date, self.days):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        left = parse_date_value(get_value(self.left_date, context))
        right = parse_date_value(get_value(self.right_date, context))
        days = get_value(self.days, context)
        if left is None or right is None or days is None:
            return False
        return abs((right - left).days) > int(days)


@dataclass
class NullSafeComparison(Operator):
    """Wraps a two-argument comparison so that None on either side returns False."""

    left: OperatorArgument
    right: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 2:
            raise JSONLogicSyntaxError(f"{operator!r} expects two arguments, got {len(arguments)}")
        return cls(operator=operator, left=arguments[0], right=arguments[1])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.left, self.right):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def _compare(self, left: Any, right: Any) -> bool:
        raise NotImplementedError

    def evaluate(self, context: EvaluationContext) -> bool:
        left = get_value(self.left, context)
        right = get_value(self.right, context)
        if left is None or right is None:
            return False
        try:
            return self._compare(left, right)
        except TypeError:
            return False


class NullSafeEq(NullSafeComparison):
    def _compare(self, left: Any, right: Any) -> bool:
        return bool(left == right)


class NullSafeNotEq(NullSafeComparison):
    """Fires when left != right.

    If right is blank the rule cannot be evaluated (return False).
    If left is blank but right is not, the column has no value and therefore
    does not equal the expected value (return True).
    """

    def _compare(self, left: Any, right: Any) -> bool:
        return bool(left != right)

    def evaluate(self, context: EvaluationContext) -> bool:
        left = get_value(self.left, context)
        right = get_value(self.right, context)
        if is_blank(right):
            return False
        if is_blank(left):
            return True
        try:
            return self._compare(left, right)
        except TypeError:
            return False


class NullSafeGt(NullSafeComparison):
    def _compare(self, left: Any, right: Any) -> bool:
        return bool(left > right)


class NullSafeGte(NullSafeComparison):
    def _compare(self, left: Any, right: Any) -> bool:
        return bool(left >= right)


class NullSafeLt(NullSafeComparison):
    def _compare(self, left: Any, right: Any) -> bool:
        return bool(left < right)


class NullSafeLte(NullSafeComparison):
    def _compare(self, left: Any, right: Any) -> bool:
        return bool(left <= right)


# ---------------------------------------------------------------------------
# Date literal comparison operators
# ---------------------------------------------------------------------------
# These operators compare a (pre-normalized) date column against a literal
# date value declared in the rule. Both sides are resolved to datetime.date
# via parse_date_value; either side being None returns False (no fire).
# The operator name in the rule file (e.g. "date_greater_than") is compiled
# to the JsonLogic key (e.g. "date_gt") by the compiler.
# ---------------------------------------------------------------------------


@dataclass
class DateLiteralComparison(Operator):
    """Base for date column vs. literal date comparisons."""

    column_value: OperatorArgument
    date_literal: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 2:
            raise JSONLogicSyntaxError(f"{operator!r} expects two arguments, got {len(arguments)}")
        return cls(operator=operator, column_value=arguments[0], date_literal=arguments[1])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.column_value, self.date_literal):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def _compare(self, col_date: date, lit_date: date) -> bool:
        raise NotImplementedError

    def evaluate(self, context: EvaluationContext) -> bool:
        col_date = parse_date_value(get_value(self.column_value, context))
        lit_date = parse_date_value(get_value(self.date_literal, context))
        if col_date is None or lit_date is None:
            return False
        return self._compare(col_date, lit_date)


class DateGt(DateLiteralComparison):
    def _compare(self, col_date: date, lit_date: date) -> bool:
        return col_date > lit_date


class DateGte(DateLiteralComparison):
    def _compare(self, col_date: date, lit_date: date) -> bool:
        return col_date >= lit_date


class DateLt(DateLiteralComparison):
    def _compare(self, col_date: date, lit_date: date) -> bool:
        return col_date < lit_date


class DateLte(DateLiteralComparison):
    def _compare(self, col_date: date, lit_date: date) -> bool:
        return col_date <= lit_date


class DateEq(DateLiteralComparison):
    def _compare(self, col_date: date, lit_date: date) -> bool:
        return col_date == lit_date


@dataclass
class DateBetween(Operator):
    """True when column date falls within [lower, upper] inclusive.

    The literal operand must be a two-element list: ["YYYY-MM-DD", "YYYY-MM-DD"].
    """

    column_value: OperatorArgument
    bounds: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 2:
            raise JSONLogicSyntaxError(f"{operator!r} expects two arguments, got {len(arguments)}")
        return cls(operator=operator, column_value=arguments[0], bounds=arguments[1])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.column_value, self.bounds):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        col_date = parse_date_value(get_value(self.column_value, context))
        bounds = get_value(self.bounds, context)
        if col_date is None or not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            return False
        lower = parse_date_value(bounds[0])
        upper = parse_date_value(bounds[1])
        if lower is None or upper is None:
            return False
        return lower <= col_date <= upper


def build_registry() -> OperatorRegistry:
    """Build RuleFrame's default validation-oriented JsonLogic registry."""

    registry = operator_registry.copy()
    registry.register("and", All)
    registry.register("or", AnyOf)
    registry.register("!", Not)
    registry.register("in", InList)
    registry.register("contains", Contains)
    registry.register("between", Between)
    registry.register("date_days_apart_gt", DateDaysApartGreaterThan)
    registry.register("date_gt", DateGt)
    registry.register("date_gte", DateGte)
    registry.register("date_lt", DateLt)
    registry.register("date_lte", DateLte)
    registry.register("date_eq", DateEq)
    registry.register("date_between", DateBetween)
    registry.register("is_blank", IsBlank)
    registry.register("is_not_blank", IsNotBlank)
    # Null-safe comparisons: if either operand is None the rule does not fire.
    registry.register("==", NullSafeEq, force=True)
    registry.register("!=", NullSafeNotEq, force=True)
    registry.register(">", NullSafeGt, force=True)
    registry.register(">=", NullSafeGte, force=True)
    registry.register("<", NullSafeLt, force=True)
    registry.register("<=", NullSafeLte, force=True)
    return registry


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip() == ""
    return False
