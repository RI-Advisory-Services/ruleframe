# Rules Format (v1 draft)

Rule bundles are YAML or JSON documents with a top-level version and rules list.

## Minimal Example

```yaml
version: 1
rules:
  - id: qaqc_unresolved_issue
    severity: error
    fail_when:
      all:
        - column: Selected for QA/QC
          equals: "Yes"
        - column: QA/QC Resolved
          is_blank: true
    message: QA/QC was selected but not resolved.
```


## Computed Columns

Bundles may define `computed_columns`. They are generated before rule evaluation and can be referenced by rules like input columns. The current supported type is `sum`.

```yaml
computed_columns:
  - id: total_measure_savings
    name: Total Measure Savings
    type: sum
    columns:
      - Measure Gross kWh Savings
      - Measure Gross Therm Savings
```

## Notes

- Quote string values such as `"Yes"` to avoid YAML boolean coercion.
- Preferred v1 boolean nodes are `all`, `any`, and `not`.
- Friendly syntax will compile to JsonLogic internally.
