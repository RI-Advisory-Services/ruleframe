from ruleframe import RuleBundle


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
