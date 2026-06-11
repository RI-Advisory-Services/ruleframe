# Computed Columns

Computed columns are generated before rule evaluation and then treated like normal input columns.
They are useful for totals, variances, group-level values, date intervals, and flags that would be
awkward to repeat inside multiple rules.

## Example

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

The computed output column name is `name` when present, otherwise `id`.

## Pipeline Position

For each validation run, RuleFrame:

1. Checks that required source columns exist.
2. Applies numeric coercion to inferred numeric columns.
3. Normalizes inferred date columns.
4. Builds computed columns in declaration order.
5. Evaluates rules against input columns plus computed columns.
6. Adds computed columns to the annotated output.

Computed columns are generated on a working copy. The original input DataFrame is not mutated.

## Supported Types

| Type | Required fields | Description |
| --- | --- | --- |
| `sum` | `columns` | Row-wise sum. Skips missing values, but returns blank when all inputs are blank. |
| `subtract` | `columns` | Row-wise left-to-right subtraction. |
| `multiply` | `columns` | Row-wise left-to-right multiplication. |
| `divide` | `columns` | Row-wise division of exactly two columns. Division by zero returns blank. |
| `coalesce` | `columns` | First non-null value across the listed columns. |
| `all_blank_or_zero` | `columns` | `1` when all listed values are blank or numeric zero, otherwise `0`. |
| `group_sum` | `group_by`, `value_column` | Group total mapped back to every row in the group. |
| `group_count` | `group_by` | Group row count mapped back to every row in the group. |
| `date_diff` | `start_column`, `end_column` | Whole days from start date to end date. |
| `days_since_today` | `column` | Whole days from the source date to the current date. |
| `years_since_year` | `column` | Current year minus an integer year column. |

## Row-Level Arithmetic

```yaml
computed_columns:
  - id: total_savings
    name: Total Savings
    type: sum
    columns:
      - kWh Savings
      - Therm Savings

  - id: savings_variance
    name: Savings Variance
    type: subtract
    columns:
      - Total Savings
      - Reported Total Savings

  - id: output_input_ratio
    name: Output Input Ratio
    type: divide
    columns:
      - Output
      - Input
```

Arithmetic inputs are inferred as numeric and coerced on the working copy before computed columns
are evaluated.

`divide` requires exactly two columns. A zero denominator produces a blank result for that row.

## Row-Level Logic

```yaml
computed_columns:
  - id: best_available_date
    name: Best Available Date
    type: coalesce
    columns:
      - Date Inspected
      - Alternative Date A
      - Alternative Date B

  - id: no_savings_reported
    name: No Savings Reported
    type: all_blank_or_zero
    columns:
      - kWh Savings
      - kW Savings
      - Therm Savings
```

`coalesce` returns the first non-null value. `all_blank_or_zero` treats nulls, NaN values, empty
strings, whitespace strings, and numeric zero as empty-equivalent values.

## Group Aggregates

```yaml
computed_columns:
  - id: project_total_kwh
    name: Project Total kWh
    type: group_sum
    group_by: Project ID
    value_column: kWh

  - id: project_bef_count
    name: Project BEF Count
    type: group_count
    group_by: Project ID
    filter:
      column: Measure Type
      equals: BEF
```

`group_sum` and `group_count` map each group result back to every row in that group.

Filters restrict which rows contribute to the aggregate:

```yaml
computed_columns:
  - id: project_bef_total_kwh
    name: Project BEF Total kWh
    type: group_sum
    group_by: Project ID
    value_column: kWh
    filter:
      column: Measure Type
      equals: BEF
```

For filtered `group_sum`, groups with no numeric contributing values receive a blank value. For
filtered `group_count`, groups with no matching rows receive `0`.

## Date Computed Columns

```yaml
computed_columns:
  - id: days_to_inspection
    name: Days to Inspection
    type: date_diff
    start_column: Installation Date
    end_column: Date Inspected

  - id: days_since_installation
    name: Days Since Installation
    type: days_since_today
    column: Installation Date

  - id: system_age
    name: System Age
    type: years_since_year
    column: Installation Year
```

`date_diff` returns `(end_column - start_column)` in whole days. Results may be negative when the
end date is before the start date.

`days_since_today` returns `(today - column)` in whole days.

`years_since_year` treats the input as a numeric year, not a date. It returns
`current_year - year`.

Date source columns are normalized automatically. Blank or unparseable dates produce blank
computed values.

## Chaining

Computed columns may reference earlier computed columns:

```yaml
computed_columns:
  - id: total_savings
    name: Total Savings
    type: sum
    columns:
      - kWh Savings
      - Therm Savings

  - id: kwh_share
    name: kWh Share
    type: divide
    columns:
      - kWh Savings
      - Total Savings
```

Order matters. A computed column that depends on another generated column must be declared after
its dependency.

## Validation Rules

RuleFrame validates computed-column specs before evaluation:

- Output names must be unique.
- Output names must not collide with existing input DataFrame columns.
- A computed column may not reference itself.
- A computed column may reference only source columns or earlier computed columns.
- Unsupported `type` values raise `BundleValidationError`.
- Missing source columns raise `InputSchemaError`.

Duplicate output names, self-references, unsupported types, out-of-order references, and dependency
cycles raise `BundleValidationError`.
