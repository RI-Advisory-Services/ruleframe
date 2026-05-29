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
    bundle = RuleBundle(raw={"rules": "not a list"})
    with pytest.raises(BundleValidationError, match="rules must be a list"):
        _ = bundle.rules


def test_computed_columns_property_non_list_raises() -> None:
    bundle = RuleBundle(raw={"computed_columns": "not a list"})
    with pytest.raises(BundleValidationError, match="computed_columns must be a list"):
        _ = bundle.computed_columns
