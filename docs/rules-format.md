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

## Notes

- Quote string values such as `"Yes"` to avoid YAML boolean coercion.
- Preferred v1 boolean nodes are `all`, `any`, and `not`.
- Friendly syntax will compile to JsonLogic internally.
