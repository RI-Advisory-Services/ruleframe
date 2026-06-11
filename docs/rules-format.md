# Rule Format

RuleFrame rule bundles are YAML or JSON documents with a top-level `version` and a `rules` list.
Bundles may also define `computed_columns` and `settings`.

## Simple Example

```yaml
version: 1
settings:
  validation_errors_column: RuleFrame Messages
computed_columns:
  - id: total_savings
    name: Total Savings
    type: sum
    columns:
      - kWh Savings
      - Therm Savings
rules:
  - id: active_high_savings_missing_review
    name: Active high savings missing review
    severity: error
    fail_when:
      all:
        - column: Status
          equals: "Active"
        - column: Total Savings
          greater_than: 1000
        - column: Reviewed By
          is_blank: true
    message: Active high-savings rows must be reviewed.
```

## Top-Level Keys

| Key | Required | Description |
| --- | --- | --- |
| `version` | Recommended | Current bundle format version. Use `1`. |
| `rules` | Yes | List of validation rule objects. |
| `computed_columns` | No | Columns generated before rule evaluation. |
| `settings` | No | Bundle-level configuration. |

`rules` and `computed_columns`, when present, must be lists.

## Settings

```yaml
settings:
  validation_errors_column: Validation Errors
  date_format: "%m/%d/%Y"
```

| Setting | Description |
| --- | --- |
| `validation_errors_column` | Column name added to annotated output. Defaults to `Validation Errors`. |
| `date_format` | Optional strict `strftime` format for DataFrame date values. Omit for flexible parsing. |

`date_format` applies to DataFrame source values, not date literals in rule files. Literal date
values in rules should use ISO format, such as `"2024-03-01"`.

## Rule Objects

```yaml
- id: missing_customer_status
  name: Customer status missing
  severity: warning
  fail_when:
    column: Customer Status
    is_blank: true
  message: Customer Status is blank.
```

| Key | Required | Description |
| --- | --- | --- |
| `id` | Yes | Unique rule identifier. Snake case is recommended. |
| `fail_when` | Yes | Condition that triggers a finding when it evaluates to true. |
| `severity` | No | Finding severity. Defaults to `error`. |
| `message` | No | Human-readable finding message. Defaults to `Rule failed`. |
| `name` | No | Display name included in findings. |

RuleFrame records a finding when `fail_when` is true. Write rules from the perspective of a
failure condition, not a passing condition.

Supported severities are `error` and `warning`. If omitted, severity defaults to `error`.

## Conditions

A condition is either an atomic predicate or a boolean node.

### Atomic Predicates

Atomic predicates refer to one DataFrame column and one operator:

```yaml
fail_when:
  column: Amount
  greater_than: 1000
```

Each atomic condition must contain exactly one operator besides `column`.

### Boolean Nodes

Use `all`, `any`, and `not` to combine conditions.

```yaml
fail_when:
  all:
    - column: Status
      equals: "Active"
    - column: Amount
      greater_than: 1000
```

```yaml
fail_when:
  any:
    - column: kWh Savings
      is_blank: true
    - column: Therm Savings
      is_blank: true
```

```yaml
fail_when:
  not:
    column: Status
    equals: "Closed"
```

`not` applies to exactly one child condition. The example above fires when `Status` is anything
other than `"Closed"`.

Boolean nodes can be nested:

```yaml
fail_when:
  all:
    - any:
        - column: Status
          equals: "Active"
        - column: Status
          equals: "Pending"
    - not:
        column: Priority Review
        equals: "Yes"
```

See [Predicates](predicates.md) for the full list of operators that can be used in atomic
conditions.

## Column Names

`column` values must match DataFrame column names exactly. Column names may contain spaces,
slashes, punctuation, or mixed case:

```yaml
fail_when:
  column: Installed Quantity
  not_equals_column: Reported Quantity
```

If a rule references a missing source column, `validate_dataframe()` raises `InputSchemaError`.

## Computed Columns

Computed columns are declared at the top level and generated before rules run:

```yaml
version: 1
computed_columns:
  - id: total_measure_savings
    name: Total Measure Savings
    type: sum
    columns:
      - Measure Gross kWh Savings
      - Measure Gross Therm Savings
rules:
  - id: total_savings_mismatch
    fail_when:
      column: Total Measure Savings
      not_equals_column: Reported Total Savings
    message: Total Measure Savings does not match Reported Total Savings.
```

Computed columns can be referenced by rules like normal DataFrame columns. See
[Computed columns](computed-columns.md) for the full reference.

## Date Handling

Date predicates and date computed columns automatically normalize the relevant source columns on
RuleFrame's working copy of the DataFrame.

Flexible parsing is the default. It accepts values such as:

- `2024-03-25`
- `2024-3-5`
- `3/25/2024`
- `03/25/2024`
- `2024-03-25 14:32:00`
- `2024-03-25T09:00:00`
- pandas datetime values
- Python `date` or `datetime` values
- timezone-aware datetime values

Ambiguous month/day strings are interpreted month-first. Timezone-aware values are converted to
UTC before timezone information is removed, so values near midnight may shift calendar dates. To
require a specific format, set `settings.date_format`.

```yaml
settings:
  date_format: "%m/%d/%Y"
```

Unparseable date values become blank values for validation purposes. Time components are
discarded; RuleFrame works with calendar dates.

## Type Inference And Coercion

RuleFrame infers source column intent from rules and computed columns:

- Numeric predicates and numeric computed columns imply numeric source columns.
- Date predicates and date computed columns imply date source columns.
- Literal `equals`, `not_equals`, `in`, and `not_in` values may imply string, numeric, or boolean
  source columns.

Numeric source columns are coerced on a working copy before evaluation. Partially unparseable
numeric columns produce coercion events and, by default, warnings. A numeric column where every
non-null value fails to parse raises `InputSchemaError`.

If a column receives conflicting type signals, such as numeric in one rule and string in another,
`validate_dataframe()` raises `BundleValidationError`.

## YAML Tips

- Quote strings such as `"Yes"`, `"No"`, `"On"`, `"Off"`, `"True"`, and `"False"` when you intend
  them to be text. YAML may otherwise parse some words as booleans instead of strings.
- Quote ISO date literals, such as `"2024-03-01"`.
- Keep rule IDs stable so downstream reporting can group findings by rule.
- Put computed columns before rules that reference them.
