from ruleframe import RuleBundle


def test_from_yaml_parses_rules() -> None:
    bundle = RuleBundle.from_yaml(
        """
version: 1
rules:
  - id: r1
    fail_when:
      column: A
      equals: "Yes"
"""
    )
    assert bundle.version == 1
    assert len(bundle.rules) == 1
    assert bundle.rules[0]["id"] == "r1"
