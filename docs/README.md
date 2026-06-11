# RuleFrame Documentation

RuleFrame validates pandas DataFrames with declarative rule bundles. A bundle describes the
conditions that should produce findings; RuleFrame evaluates those rules against each row and
returns structured results.

## Start Here

- [Rule format](rules-format.md): bundle structure, rule objects, boolean logic, settings, and
  examples.
- [Predicates](predicates.md): supported rule operators such as `equals`, `is_blank`,
  `greater_than_column`, and date comparisons.
- [Computed columns](computed-columns.md): generated columns that can be used by later computed
  columns or validation rules.
- [Validation results](validation-results.md): `ValidationResult`, findings, annotated output,
  summary output, and coercion details.

## Minimal Bundle

```yaml
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
```

## Minimal Python Usage

```python
import pandas as pd

from ruleframe import RuleBundle, validate_dataframe

df = pd.DataFrame({"Status": ["Active"], "Customer Name": [""]})
bundle = RuleBundle.from_yaml("rules.yaml")

result = validate_dataframe(df, bundle)
findings = result.to_findings_dataframe()
annotated = result.to_annotated_dataframe()
```

## Public API

The top-level package exports:

- `RuleBundle`
- `validate_dataframe`
- `ValidationResult`
- `RuleFrameError`
- `BundleValidationError`
- `InputSchemaError`
- `CoercionEvent`

## Validation Pipeline

At a high level, RuleFrame:

1. Loads and structurally validates a YAML or JSON rule bundle.
2. Checks the input DataFrame for required source columns.
3. Infers numeric and date columns from rule and computed-column structure.
4. Coerces numeric source columns on a working copy.
5. Normalizes date source columns on a working copy.
6. Builds computed columns in declaration order.
7. Evaluates every rule against every row.
8. Returns structured findings, an annotated DataFrame, and summary helpers.

`RuleBundle` construction validates basic bundle structure. DataFrame-aware validation, such as
missing source columns, computed-column name collisions, and type conflicts, happens when
`validate_dataframe()` runs.
