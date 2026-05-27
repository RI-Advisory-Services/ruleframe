from __future__ import annotations

from typing import Any


def json_pointer(column_name: str) -> str:
    """Convert a DataFrame column name to a JSON Pointer variable path."""

    return "/" + column_name.replace("~", "~0").replace("/", "~1")


def compile_condition(condition: dict[str, Any]) -> dict[str, Any]:
    """Compile friendly rule condition syntax to a JsonLogic expression."""

    if "all" in condition:
        return {"and": [compile_condition(child) for child in condition["all"]]}
    if "any" in condition:
        return {"or": [compile_condition(child) for child in condition["any"]]}
    if "not" in condition:
        return {"!": [compile_condition(condition["not"])]}

    if "column" not in condition:
        raise ValueError(f"Condition must contain 'column' or a logic node: {condition}")

    column_var = {"var": json_pointer(str(condition["column"]))}
    operator_keys = [key for key in condition if key != "column"]
    if len(operator_keys) != 1:
        raise ValueError(f"Condition must contain exactly one operator: {condition}")

    op = operator_keys[0]
    expected = condition[op]

    if op == "equals":
        return {"==": [column_var, expected]}
    if op == "not_equals":
        return {"!=": [column_var, expected]}
    if op == "equals_column":
        return {"==": [column_var, {"var": json_pointer(str(expected))}]}
    if op == "not_equals_column":
        return {"!=": [column_var, {"var": json_pointer(str(expected))}]}
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
    if op == "contains":
        return {"contains": [column_var, expected]}
    if op == "not_contains":
        return {"!": [{"contains": [column_var, expected]}]}
    if op == "between":
        return {"between": [column_var, expected]}
    if op == "not_between":
        return {"!": [{"between": [column_var, expected]}]}
    if op == "is_blank":
        return {"is_blank": [column_var]} if expected else {"is_not_blank": [column_var]}
    if op == "is_not_blank":
        return {"is_not_blank": [column_var]} if expected else {"is_blank": [column_var]}
    if op == "days_apart_greater_than":
        return {
            "date_days_apart_gt": [
                column_var,
                {"var": json_pointer(str(expected["column"]))},
                expected["days"],
            ]
        }

    raise ValueError(f"Unsupported friendly operator: {op}")


def compile_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Compile a rule's fail_when condition to JsonLogic."""

    fail_when = rule.get("fail_when")
    if not isinstance(fail_when, dict):
        raise ValueError(f"Rule {rule.get('id', '<unknown>')!r} must contain a fail_when object")
    return compile_condition(fail_when)


def collect_required_columns(condition: dict[str, Any]) -> set[str]:
    """Collect DataFrame column names referenced by friendly condition syntax."""

    if "all" in condition:
        return set().union(*(collect_required_columns(child) for child in condition["all"]))
    if "any" in condition:
        return set().union(*(collect_required_columns(child) for child in condition["any"]))
    if "not" in condition:
        return collect_required_columns(condition["not"])

    columns = {str(condition["column"])} if "column" in condition else set()
    for key, value in condition.items():
        if key == "column":
            continue
        if key in {"equals_column", "not_equals_column"}:
            columns.add(str(value))
        elif isinstance(value, dict) and "column" in value:
            columns.add(str(value["column"]))
    return columns


def collect_rule_columns(rules: list[dict[str, Any]]) -> set[str]:
    """Collect all input columns referenced by a list of rules."""

    required: set[str] = set()
    for rule in rules:
        fail_when = rule.get("fail_when")
        if isinstance(fail_when, dict):
            required |= collect_required_columns(fail_when)
    return required
