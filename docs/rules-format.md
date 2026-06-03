# Rules Format (v1)

Rule bundles are YAML or JSON documents with a top-level `version` and `rules` list. They may also define `computed_columns` and `settings`.

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

## Top-level Keys

| Key | Required | Description |
|---|---|---|
| `version` | Yes | Must be `1` |
| `rules` | Yes | List of rule objects |
| `computed_columns` | No | Columns generated before rule evaluation |
| `settings` | No | Bundle-level configuration |

## Settings

```yaml
settings:
  validation_errors_column: Validation Errors   # column name in annotated output (default: "Validation Errors")
  date_format: "%m/%d/%Y"                        # optional strict date format for all date columns
```

### `date_format`

When set, all inferred date columns are parsed strictly using this `strftime` pattern. Values that do not match become blank (NaT) rather than being guessed. Omit to use flexible parsing (ISO and US month-first formats accepted automatically). See [Date Handling](#date-handling).

## Rule Object

| Key | Required | Description |
|---|---|---|
| `id` | Yes | Unique rule identifier (snake_case recommended) |
| `severity` | No | `"error"` (default) or `"warning"` |
| `fail_when` | Yes | Condition that triggers a finding when true |
| `message` | No | Human-readable finding message |
| `name` | No | Display name for the rule |

## Condition Syntax

A `fail_when` value is a condition object. Conditions can be atomic (column + operator) or composite (boolean nodes).

### Boolean Nodes

```yaml
fail_when:
  all:                          # all sub-conditions must be true (AND)
    - column: Status
      equals: Active
    - column: Amount
      greater_than: 0

fail_when:
  any:                          # at least one sub-condition must be true (OR)
    - column: kWh
      is_blank: true
    - column: Therms
      is_blank: true

fail_when:
  not:                          # negates a single sub-condition
    column: Status
    equals: Active
```

Boolean nodes can be nested arbitrarily.

### Operators

All operators take the form `{ column: <name>, <operator>: <value> }`.

#### Equality and comparison

| Operator | Fires when |
|---|---|
| `equals` | column value equals the literal |
| `not_equals` | column value does not equal the literal; also fires when column is blank |
| `greater_than` | column value > literal |
| `greater_than_or_equal` | column value >= literal |
| `less_than` | column value < literal |
| `less_than_or_equal` | column value <= literal |

All comparisons are null-safe: if either side is blank, the rule does not fire (except `not_equals` — see above).

#### Column-to-column comparison

Compares two columns in the same row rather than a column against a literal.

| Operator | Fires when |
|---|---|
| `equals_column` | column == other column |
| `not_equals_column` | column != other column |
| `greater_than_column` | column > other column |
| `greater_than_or_equal_column` | column >= other column |
| `less_than_column` | column < other column |
| `less_than_or_equal_column` | column <= other column |

```yaml
fail_when:
  column: Reported kWh
  not_equals_column: Calculated kWh
```

#### Membership

| Operator | Value | Fires when |
|---|---|---|
| `in` | list | column value is in the list |
| `not_in` | list | column value is not in the list |

```yaml
fail_when:
  column: Fuel Type
  in: ["Natural Gas", "Propane", "Oil"]
```

#### String containment

| Operator | Value | Fires when |
|---|---|---|
| `contains` | string | column value contains the substring |
| `not_contains` | string | column value does not contain the substring |

#### Range

| Operator | Value | Fires when |
|---|---|---|
| `between` | `[lower, upper]` | lower <= column <= upper (inclusive) |
| `not_between` | `[lower, upper]` | column falls outside the range |

#### Blank checks

| Operator | Value | Fires when |
|---|---|---|
| `is_blank` | `true` | column is null, empty string, or whitespace |
| `is_blank` | `false` | column is not blank (same as `is_not_blank: true`) |
| `is_not_blank` | `true` | column is not blank |

#### Date operators

Date operators compare a date column against a literal date value. The column is normalized automatically (no pre-parsing required). Always write literal dates in ISO format (`YYYY-MM-DD`) in the rule file.

| Operator | Fires when |
|---|---|
| `date_equals` | column date == literal date |
| `date_greater_than` | column date is after the literal date |
| `date_greater_than_or_equal` | column date is on or after the literal date |
| `date_less_than` | column date is before the literal date |
| `date_less_than_or_equal` | column date is on or before the literal date |
| `date_between` | column date falls within `[lower, upper]` inclusive |
| `date_not_between` | column date falls outside `[lower, upper]` |

```yaml
fail_when:
  column: Installation Date
  date_greater_than: "2020-01-01"

fail_when:
  column: Event Date
  date_between: ["2024-01-01", "2024-12-31"]
```

If the column value is blank or unparseable, the rule does not fire.

#### Date distance (column-to-column)

```yaml
fail_when:
  column: Installation Date
  days_apart_greater_than:
    column: Date Inspected
    days: 30
```

Fires when the absolute difference between two date columns exceeds `days`. Either column being blank suppresses the rule.

## Computed Columns

Bundles may define `computed_columns`. They are generated before rule evaluation and can be referenced by rules like any input column. See [computed-columns.md](computed-columns.md) for the full reference.

```yaml
computed_columns:
  - id: total_savings
    name: Total Savings
    type: sum
    columns:
      - kWh Savings
      - Therm Savings
```

## Date Handling

Columns used in date computed types (`date_diff`, `days_since_today`) and date comparison operators are automatically parsed and normalized to calendar dates before evaluation. You do not need to pre-parse date columns.

**Flexible parsing (default):** ISO (`2024-03-25`), US month-first (`3/25/2024`, `03/25/2024`), and pandas datetime types are all accepted. Ambiguous values where both month and day are ≤ 12 are read as month-first (US convention).

**Strict parsing:** Set `settings.date_format` to a `strftime` pattern to reject non-conforming values rather than guess them.

Hours and minutes are always discarded. The library works with calendar dates only.

Literal date values in rule files should always use ISO format (`YYYY-MM-DD`). The `date_format` setting applies only to DataFrame column values, not to literals in the rule file.

## Notes

- Quote string values like `"Yes"` to prevent YAML boolean coercion.
- Rule IDs must be unique within a bundle.
- `severity` defaults to `"error"` if omitted.
