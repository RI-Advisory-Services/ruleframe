from __future__ import annotations

from typing import Any

from .exceptions import BundleValidationError
from .predicates import PREDICATE_REGISTRY, json_pointer


def compile_condition(condition: dict[str, Any]) -> dict[str, Any]:
    """Compile friendly rule condition syntax to a JsonLogic expression."""

    if "all" in condition:
        return {"and": [compile_condition(child) for child in condition["all"]]}
    if "any" in condition:
        return {"or": [compile_condition(child) for child in condition["any"]]}
    if "not" in condition:
        return {"!": [compile_condition(condition["not"])]}

    if "column" not in condition:
        raise BundleValidationError(f"Condition must contain 'column' or a logic node: {condition}")

    column_var = {"var": json_pointer(str(condition["column"]))}
    operator_keys = [key for key in condition if key != "column"]
    if len(operator_keys) != 1:
        raise BundleValidationError(f"Condition must contain exactly one operator: {condition}")

    op = operator_keys[0]

    predicate_cls = PREDICATE_REGISTRY.get(op)
    if predicate_cls is None:
        raise BundleValidationError(f"Unsupported predicate: {op}")
    return predicate_cls.compile(column_var, condition[op])


def compile_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Compile a rule's fail_when condition to JsonLogic."""

    fail_when = rule.get("fail_when")
    if not isinstance(fail_when, dict):
        rule_id = rule.get("id", "<unknown>")
        raise BundleValidationError(f"Rule {rule_id!r} must contain a fail_when object")
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
    col = str(condition["column"]) if "column" in condition else ""
    for key, value in condition.items():
        if key == "column":
            continue
        if cls := PREDICATE_REGISTRY.get(key):
            columns |= cls.referenced_columns(col, value)
    return columns


def collect_rule_columns(rules: list[dict[str, Any]]) -> set[str]:
    """Collect all input columns referenced by a list of rules."""

    required: set[str] = set()
    for rule in rules:
        fail_when = rule.get("fail_when")
        if isinstance(fail_when, dict):
            required |= collect_required_columns(fail_when)
    return required
