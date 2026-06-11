# RuleFrame

RuleFrame validates pandas DataFrames with readable YAML or JSON rule bundles.

RuleFrame is useful when validation rules need to live outside application code: in files,
database records, admin screens, or workflow configuration. A rule bundle describes the
conditions that should produce findings, and RuleFrame returns both row-level findings and an
annotated DataFrame.

## Status

RuleFrame is in alpha. The core validation API is usable, but public APIs and rule syntax may
change before a stable `1.0.0` release.

## Install

```bash
pip install ruleframe
```

## Quick Start

```python
import pandas as pd

from ruleframe import RuleBundle, validate_dataframe

rules_yaml = """
version: 1
rules:
  - id: active_customer_missing_name
    severity: error
    fail_when:
      all:
        - column: Status
          equals: "Active"
        - column: Customer Name
          is_blank: true
    message: Active customers must have a name.
"""

df = pd.DataFrame(
    {
        "Status": ["Active", "Closed", "Active"],
        "Customer Name": ["", "Grace Hopper", "Ada Lovelace"],
    }
)

bundle = RuleBundle.from_yaml_string(rules_yaml)
result = validate_dataframe(df, bundle)

print(result.to_findings_dataframe())
print(result.to_annotated_dataframe())
```

Expected output:

```text
 row_index                      rule_id rule_name severity                            message
         0 active_customer_missing_name      None    error Active customers must have a name.

   Status Customer Name                       Validation Errors
0  Active               Active customers must have a name.
1  Closed  Grace Hopper
2  Active  Ada Lovelace
```

`validate_dataframe()` returns a `ValidationResult` with:

- `to_findings_dataframe()`: one row per rule finding.
- `to_annotated_dataframe()`: the original DataFrame plus computed columns and a validation
  message column.
- `to_summary_dataframe()`: finding counts grouped by rule and severity.

## Rule Bundles

Rule bundles can be loaded from YAML, JSON, strings, or pre-parsed dictionaries:

```python
from ruleframe import RuleBundle

bundle = RuleBundle.from_yaml("rules.yaml")
bundle = RuleBundle.from_json("rules.json")
bundle = RuleBundle.from_yaml_string(yaml_text)
bundle = RuleBundle.from_json_string(json_text)
bundle = RuleBundle.from_json_dict(data)
```

Rules support boolean nesting, literal comparisons, column-to-column comparisons, date
comparisons, blank checks, membership checks, string containment, ranges, and generated
computed columns.

## Documentation

- [Documentation index](https://github.com/RI-Advisory-Services/ruleframe/tree/main/docs)
- [Rule format](https://github.com/RI-Advisory-Services/ruleframe/blob/main/docs/rules-format.md)
- [Predicates](https://github.com/RI-Advisory-Services/ruleframe/blob/main/docs/predicates.md)
- [Computed columns](https://github.com/RI-Advisory-Services/ruleframe/blob/main/docs/computed-columns.md)
- [Validation results](https://github.com/RI-Advisory-Services/ruleframe/blob/main/docs/validation-results.md)
