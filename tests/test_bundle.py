import pytest

from ruleframe import RuleBundle
from ruleframe.exceptions import BundleValidationError


def test_from_yaml_parses_rules(tmp_path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        """
version: 1
rules:
  - id: r1
    fail_when:
      column: A
      equals: "Yes"
"""
    )

    bundle = RuleBundle.from_yaml(path)

    assert bundle.version == 1
    assert len(bundle.rules) == 1
    assert bundle.rules[0]["id"] == "r1"


def test_sample_rules_yaml_fixture_parses(sample_bundle) -> None:
    assert sample_bundle.version == 1
    assert [rule["id"] for rule in sample_bundle.rules] == [
        "qaqc_unresolved_issue",
        "missing_customer_status",
        "review_required_without_priority",
        "active_quantity_mismatch",
        "late_active_inspection",
    ]
    assert sample_bundle.rules[0]["fail_when"]["all"][0]["equals"] == "Yes"


# ===========================================================================
# Guard tests: bundle loading validation
# ===========================================================================


def test_from_yaml_non_dict_raises(tmp_path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("- item1\n- item2\n")
    with pytest.raises(BundleValidationError, match="must deserialize to a dictionary"):
        RuleBundle.from_yaml(path)


def test_from_json_dict_non_dict_raises() -> None:
    with pytest.raises(BundleValidationError, match="must be a dictionary"):
        RuleBundle.from_json_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_rules_property_non_list_raises() -> None:
    with pytest.raises(BundleValidationError, match="rules must be a list"):
        RuleBundle(raw={"rules": "not a list"})


def test_computed_columns_property_non_list_raises() -> None:
    with pytest.raises(BundleValidationError, match="computed_columns must be a list"):
        RuleBundle(raw={"computed_columns": "not a list"})


# ===========================================================================
# from_yaml_string tests
# ===========================================================================


def test_from_yaml_string_parses_valid_content() -> None:
    content = """
version: 1
rules:
  - id: r1
    fail_when:
      column: Status
      equals: "Error"
    message: Status is Error.
"""
    bundle = RuleBundle.from_yaml_string(content)
    assert bundle.version == 1
    assert len(bundle.rules) == 1
    assert bundle.rules[0]["id"] == "r1"


def test_from_yaml_string_non_dict_raises() -> None:
    with pytest.raises(BundleValidationError, match="must deserialize to a dictionary"):
        RuleBundle.from_yaml_string("- item1\n- item2\n")


# ===========================================================================
# from_json_string tests
# ===========================================================================


def test_from_json_string_parses_valid_content() -> None:
    content = '{"version": 1, "rules": [{"id": "r1", "fail_when": {"column": "A", "equals": "X"}}]}'
    bundle = RuleBundle.from_json_string(content)
    assert bundle.version == 1
    assert bundle.rules[0]["id"] == "r1"


def test_from_json_string_invalid_json_raises() -> None:
    with pytest.raises(BundleValidationError, match="JSON is invalid"):
        RuleBundle.from_json_string("{not valid json")


def test_from_json_string_non_dict_raises() -> None:
    with pytest.raises(BundleValidationError, match="must deserialize to a dictionary"):
        RuleBundle.from_json_string("[1, 2, 3]")


# ===========================================================================
# from_json tests
# ===========================================================================


def test_from_json_parses_rules(sample_json_bundle) -> None:
    assert sample_json_bundle.version == 1
    assert [rule["id"] for rule in sample_json_bundle.rules] == [
        "qaqc_unresolved_issue",
        "missing_customer_status",
        "review_required_without_priority",
        "active_quantity_mismatch",
        "late_active_inspection",
    ]
    # first rule: nested all condition and severity
    assert sample_json_bundle.rules[0]["severity"] == "error"
    assert sample_json_bundle.rules[0]["fail_when"]["all"][0]["equals"] == "Yes"
    # second rule: warning severity and simple is_blank condition
    assert sample_json_bundle.rules[1]["severity"] == "warning"
    assert sample_json_bundle.rules[1]["fail_when"]["is_blank"] is True
    # third rule: not node is parsed correctly
    assert "not" in sample_json_bundle.rules[2]["fail_when"]["all"][1]
    # fifth rule: days_apart_greater_than days value
    assert (
        sample_json_bundle.rules[4]["fail_when"]["all"][1]["days_apart_greater_than"]["days"] == 31
    )


def test_from_json_missing_file_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        RuleBundle.from_json(tmp_path / "nonexistent.json")


# ===========================================================================
# Eager structural validation tests
# ===========================================================================


def test_rule_missing_id_raises() -> None:
    with pytest.raises(BundleValidationError, match="missing required field 'id'"):
        RuleBundle.from_json_dict(
            {
                "version": 1,
                "rules": [{"fail_when": {"column": "A", "equals": "X"}}],
            }
        )


def test_rule_missing_fail_when_raises() -> None:
    with pytest.raises(BundleValidationError, match="missing required field 'fail_when'"):
        RuleBundle.from_json_dict(
            {
                "version": 1,
                "rules": [{"id": "r1", "message": "no fail_when"}],
            }
        )


def test_rule_fail_when_not_dict_raises() -> None:
    with pytest.raises(BundleValidationError, match="'fail_when' must be a dictionary"):
        RuleBundle.from_json_dict(
            {
                "version": 1,
                "rules": [{"id": "r1", "fail_when": "column: A"}],
            }
        )


def test_rule_not_a_dict_raises() -> None:
    with pytest.raises(BundleValidationError, match="must be a dictionary"):
        RuleBundle.from_json_dict(
            {
                "version": 1,
                "rules": ["not a dict"],
            }
        )
