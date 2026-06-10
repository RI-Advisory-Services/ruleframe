"""Spike: friendly YAML rules -> JsonLogic -> DataFrame findings.

Run from the repo root:

    .venv/bin/python future-package-design/jsonlogic_spike.py

This is deliberately not package code. It is a small proof of mechanism for the
future validation package design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dateutil import parser as date_parser
from jsonlogic import JSONLogicExpression, JSONLogicSyntaxError
from jsonlogic.core import Operator, OperatorArgument
from jsonlogic.evaluation import EvaluationContext, evaluate
from jsonlogic.operators import operator_registry
from jsonlogic.operators.operators import get_value
from jsonlogic.registry import OperatorRegistry
from jsonlogic.typechecking import typecheck
from jsonlogic.json_schema import BooleanType, JSONSchemaType


@dataclass
class UnaryOperator(Operator):
    """Small helper base for custom one-argument operators."""

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
        if value is None:
            return True
        try:
            if bool(pd.isna(value)):
                return True
        except (TypeError, ValueError):
            pass
        if isinstance(value, str):
            return value.strip() == "" or value.strip().lower() == "nan"
        return False


class IsNotBlank(IsBlank):
    """Inverse of IsBlank."""

    def evaluate(self, context: EvaluationContext) -> bool:
        return not super().evaluate(context)


@dataclass
class VariadicOperator(Operator):
    """Small helper base for operators with one or more arguments."""

    values: list[OperatorArgument]

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if not arguments:
            raise JSONLogicSyntaxError(f"{operator!r} expects at least one argument")
        return cls(operator=operator, values=arguments)


class All(VariadicOperator):
    """JsonLogic-style AND with short-circuit behavior."""

    def typecheck(self, context) -> JSONSchemaType:
        for value in self.values:
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        return all(bool(get_value(value, context)) for value in self.values)


class AnyOf(VariadicOperator):
    """JsonLogic-style OR with short-circuit behavior."""

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
class DateDaysApartGreaterThan(Operator):
    left_date: OperatorArgument
    right_date: OperatorArgument
    days: OperatorArgument

    @classmethod
    def from_expression(cls, operator: str, arguments: list[OperatorArgument]):
        if len(arguments) != 3:
            raise JSONLogicSyntaxError(f"{operator!r} expects three arguments, got {len(arguments)}")
        return cls(operator=operator, left_date=arguments[0], right_date=arguments[1], days=arguments[2])

    def typecheck(self, context) -> JSONSchemaType:
        for value in (self.left_date, self.right_date, self.days):
            if isinstance(value, Operator):
                value.typecheck(context)
        return BooleanType()

    def evaluate(self, context: EvaluationContext) -> bool:
        left = parse_date_like(get_value(self.left_date, context))
        right = parse_date_like(get_value(self.right_date, context))
        days = get_value(self.days, context)
        if left is None or right is None or days is None:
            return False
        return abs((right - left).days) > int(days)


def build_registry() -> OperatorRegistry:
    """Copy built-ins and register package-style custom operators."""

    registry = operator_registry.copy()
    registry.register("and", All)
    registry.register("or", AnyOf)
    registry.register("!", Not)
    registry.register("in", InList)
    registry.register("date_days_apart_gt", DateDaysApartGreaterThan)
    registry.register("is_blank", IsBlank)
    registry.register("is_not_blank", IsNotBlank)
    return registry


def json_pointer(column_name: str) -> str:
    """Use JSON Pointer variable paths so spaces and punctuation are safe."""

    return "/" + column_name.replace("~", "~0").replace("/", "~1")


def parse_date_like(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date_parser.parse(value).date()
    return None


def compile_condition(condition: dict[str, Any]) -> dict[str, Any]:
    """Compile friendly condition syntax to a JsonLogic expression dict."""

    if "all" in condition:
        return {"and": [compile_condition(child) for child in condition["all"]]}
    if "any" in condition:
        return {"or": [compile_condition(child) for child in condition["any"]]}
    if "not" in condition:
        return {"!": [compile_condition(condition["not"])]}

    if "column" not in condition:
        raise ValueError(f"Condition must contain 'column' or logic node: {condition}")

    column_var = {"var": json_pointer(condition["column"])}
    operator_keys = [key for key in condition if key != "column"]
    if len(operator_keys) != 1:
        raise ValueError(f"Condition must contain exactly one operator: {condition}")

    op = operator_keys[0]
    expected = condition[op]

    if op == "equals":
        return {"==": [column_var, expected]}
    if op == "not_equals":
        return {"!=": [column_var, expected]}
    if op == "greater_than":
        return {">": [column_var, expected]}
    if op == "greater_than_or_equal":
        return {">=": [column_var, expected]}
    if op == "less_than":
        return {"<": [column_var, expected]}
    if op == "less_than_or_equal":
        return {"<=": [column_var, expected]}
    if op == "in":
        return {"in": [column_var, expected]}
    if op == "not_in":
        return {"!": [{"in": [column_var, expected]}]}
    if op == "is_blank":
        return {"is_blank": [column_var]}
    if op == "is_not_blank":
        return {"is_not_blank": [column_var]}
    if op == "days_apart_greater_than":
        return {
            "date_days_apart_gt": [
                column_var,
                {"var": json_pointer(expected["column"])},
                expected["days"],
            ]
        }

    raise ValueError(f"Unsupported friendly operator: {op}")


def compile_rule(rule: dict[str, Any]) -> dict[str, Any]:
    return compile_condition(rule["fail_when"])


def collect_required_columns(condition: dict[str, Any]) -> set[str]:
    """Collect input column names referenced by friendly rule syntax."""

    if "all" in condition:
        return set().union(*(collect_required_columns(child) for child in condition["all"]))
    if "any" in condition:
        return set().union(*(collect_required_columns(child) for child in condition["any"]))
    if "not" in condition:
        return collect_required_columns(condition["not"])

    columns = {condition["column"]} if "column" in condition else set()
    for key, value in condition.items():
        if key == "column":
            continue
        if isinstance(value, dict) and "column" in value:
            columns.add(value["column"])
    return columns


def missing_rule_columns(df: pd.DataFrame, bundle: dict[str, Any]) -> list[str]:
    required: set[str] = set()
    for rule in bundle["rules"]:
        required |= collect_required_columns(rule["fail_when"])
    return sorted(required - set(df.columns))


def schema_from_columns(columns: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Build a minimal JSON Schema object for python-jsonlogic typechecking."""

    type_map = {
        "string": {"type": ["string", "null"]},
        "number": {"type": ["number", "integer", "null"]},
        "boolean": {"type": ["boolean", "null"]},
        "date": {"type": ["string", "null"], "format": "date"},
    }
    return {
        "type": "object",
        "properties": {
            name: type_map.get(spec.get("type", "string"), {})
            for name, spec in columns.items()
        },
    }


def load_bundle(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def sample_input_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Selected for QA/QC": "Yes",
                "Issues noted during QA/QC appointment?": "Yes",
                "QA/QC Resolved": None,
                "Fuel Type Heat": "Electric",
                "Fuel Type DHW": "Electric",
                "Customer Status": "Active",
                "Building Square Footage": 1200,
                "Installation Date": "2026-01-01",
                "Date Inspected": "2026-01-20",
            },
            {
                "Selected for QA/QC": "No",
                "Issues noted during QA/QC appointment?": "",
                "QA/QC Resolved": "",
                "Fuel Type Heat": "Natural Gas",
                "Fuel Type DHW": "",
                "Customer Status": pd.NA,
                "Building Square Footage": 450,
                "Installation Date": "2026-02-01",
                "Date Inspected": "2026-03-10",
            },
            {
                "Selected for QA/QC": "Yes",
                "Issues noted during QA/QC appointment?": "Yes",
                "QA/QC Resolved": "Yes",
                "Fuel Type Heat": "Propane",
                "Fuel Type DHW": "Electric",
                "Customer Status": "Complete",
                "Building Square Footage": 4500,
                "Installation Date": pd.Timestamp("2026-03-01"),
                "Date Inspected": pd.Timestamp("2026-03-20"),
            },
        ]
    )


def validate_dataframe(df: pd.DataFrame, bundle: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    registry = build_registry()
    schema = schema_from_columns(bundle.get("columns", {}))

    missing = missing_rule_columns(df, bundle)
    if missing:
        raise ValueError("Input is missing required rule column(s): " + ", ".join(missing))

    working_df = df.copy()
    row_id_column = bundle["settings"]["row_id"]["column"]
    working_df.insert(0, row_id_column, range(1, len(working_df) + 1))

    findings: list[dict[str, Any]] = []

    for rule in bundle["rules"]:
        compiled = compile_rule(rule)
        expression = JSONLogicExpression.from_json(compiled)
        operator_tree = expression.as_operator_tree(registry)
        _, diagnostics = typecheck(operator_tree, schema)

        print(f"\nRULE {rule['id']}")
        print(f"  compiled: {compiled}")
        print(f"  typecheck diagnostics: {len(diagnostics)}")
        for diagnostic in diagnostics:
            print(f"    - {diagnostic.message}")

        for row_index, row in working_df.iterrows():
            row_data = row.where(pd.notna(row), None).to_dict()
            did_fail = bool(evaluate(operator_tree, row_data, schema))
            if not did_fail:
                continue

            findings.append(
                {
                    "row_id": row_data[row_id_column],
                    "row_index": int(row_index),
                    "excel_row": int(row_index) + 2,
                    "rule_id": rule["id"],
                    "rule_name": rule.get("name", rule["id"]),
                    "severity": rule.get("severity", "error"),
                    "message": rule["message"],
                }
            )

    findings_df = pd.DataFrame(findings)

    messages_by_row_id = {}
    for finding in findings:
        messages_by_row_id.setdefault(finding["row_id"], []).append(finding["message"])

    annotated_df = working_df.copy()
    annotated_df["Validation Errors"] = [
        "; ".join(messages_by_row_id.get(row_id, [])) for row_id in annotated_df[row_id_column]
    ]

    return annotated_df, findings_df


def summary_dataframe(findings_df: pd.DataFrame) -> pd.DataFrame:
    if findings_df.empty:
        return pd.DataFrame(columns=["rule_id", "rule_name", "severity", "error_count", "affected_rows"])

    return (
        findings_df.groupby(["rule_id", "rule_name", "severity"], dropna=False)
        .agg(error_count=("rule_id", "size"), affected_rows=("row_id", lambda s: ", ".join(map(str, sorted(s)))))
        .reset_index()
        .sort_values("error_count", ascending=False)
    )


def main() -> None:
    bundle = load_bundle(Path(__file__).with_name("sample_rules.yaml"))
    df = sample_input_dataframe()

    print("MISSING RULE COLUMNS")
    print(missing_rule_columns(df, bundle))

    annotated_df, findings_df = validate_dataframe(df, bundle)
    summary_df = summary_dataframe(findings_df)

    print("\nANNOTATED DATAFRAME")
    print(annotated_df.to_string(index=False))
    print("\nFINDINGS")
    print(findings_df.to_string(index=False))
    print("\nSUMMARY")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
