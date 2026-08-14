# Operations Library

This document is a one-stop reference for every predicate and computed column type available in
RuleFrame. Each entry shows the syntax, describes when it fires or what it produces, and includes
a concrete example.

---

## Predicates

Predicates are the comparison operations used inside a rule's `fail_when` condition. Each atomic
predicate names a `column` and exactly one operator.

RuleFrame records a finding for a row when the predicate evaluates to **true** for that row.

### `equals`

Fires when the column value equals the literal.

```yaml
fail_when:
  column: Status
  equals: "Active"
```

### `not_equals`

Fires when the column value does not equal the literal. A blank column value fires when the
expected literal is not blank. If the expected literal is blank, this predicate does not fire.

```yaml
fail_when:
  column: Status
  not_equals: "Closed"
```

### `greater_than`

Fires when the column value is strictly greater than the literal. Blank or non-numeric values do
not fire.

```yaml
fail_when:
  column: Installed Quantity
  greater_than: 500
```

### `greater_than_or_equal`

Fires when the column value is greater than or equal to the literal. Blank or non-numeric values
do not fire.

```yaml
fail_when:
  column: kWh Savings
  greater_than_or_equal: 1000
```

### `less_than`

Fires when the column value is strictly less than the literal. Blank or non-numeric values do not
fire.

```yaml
fail_when:
  column: Efficiency Rating
  less_than: 0.80
```

### `less_than_or_equal`

Fires when the column value is less than or equal to the literal. Blank or non-numeric values do
not fire.

```yaml
fail_when:
  column: Installed Quantity
  less_than_or_equal: 0
```

### `equals_column`

Fires when the left column value equals the right column value. Values are compared as-is without
implying numeric coercion.

```yaml
fail_when:
  column: Reported kWh
  equals_column: Gross kWh
```

### `not_equals_column`

Fires when the left column value does not equal the right column value. A blank left value fires
when the right value is not blank.

```yaml
fail_when:
  column: Installed Quantity
  not_equals_column: Reported Quantity
```

### `greater_than_column`

Fires when the left column value is strictly greater than the right column value. Both columns are
coerced to numeric. Blank values do not fire.

```yaml
fail_when:
  column: Claimed Savings
  greater_than_column: Approved Savings
```

### `greater_than_or_equal_column`

Fires when the left column value is greater than or equal to the right column value. Both columns
are coerced to numeric. Blank values do not fire.

```yaml
fail_when:
  column: Final Cost
  greater_than_or_equal_column: Budget Cap
```

### `less_than_column`

Fires when the left column value is strictly less than the right column value. Both columns are
coerced to numeric. Blank values do not fire.

```yaml
fail_when:
  column: Actual Output
  less_than_column: Minimum Required Output
```

### `less_than_or_equal_column`

Fires when the left column value is less than or equal to the right column value. Both columns are
coerced to numeric. Blank values do not fire.

```yaml
fail_when:
  column: Actual kWh
  less_than_or_equal_column: Baseline kWh
```

### `in`

Fires when the column value is a member of the provided list.

```yaml
fail_when:
  column: Status
  in: ["Cancelled", "Rejected"]
```

Lists must contain values of one type (all strings, all numbers, or all booleans). Mixed-type
lists raise `BundleValidationError`.

### `not_in`

Fires when the column value is not a member of the provided list. Because blank values are not
members of ordinary lists, a blank column value fires `not_in`.

```yaml
fail_when:
  column: Fuel Type
  not_in: ["Electric", "Natural Gas", "Propane"]
```

### `contains`

Fires when the column value contains the given substring. Blank column values do not fire.

```yaml
fail_when:
  column: Notes
  contains: "manual review"
```

### `not_contains`

Fires when the column value does not contain the given substring. Blank column values fire
`not_contains`.

```yaml
fail_when:
  column: Notes
  not_contains: "approved"
```

### `between`

Fires when the column value is within an inclusive numeric range. Blank or non-numeric values do
not fire.

```yaml
fail_when:
  column: Score
  between: [90, 100]
```

### `not_between`

Fires when the column value falls outside the inclusive numeric range. Blank or non-numeric values
fire `not_between`.

```yaml
fail_when:
  column: Score
  not_between: [0, 100]
```

### `is_blank`

When the value is `true`, fires when the column is null, NaN, an empty string, or whitespace.
When the value is `false`, fires when the column has any non-blank value.

```yaml
fail_when:
  column: Customer Status
  is_blank: true
```

### `is_not_blank`

When the value is `true`, fires when the column has any non-blank value. When the value is
`false`, fires when the column is null, NaN, an empty string, or whitespace.

```yaml
fail_when:
  column: Reviewer Name
  is_not_blank: true
```

Neither `is_blank` nor `is_not_blank` imply any type coercion.

### `date_equals`

Fires when the column date equals the literal date. Use ISO format (`YYYY-MM-DD`) for all date
literals in rule files. Blank or unparseable date values do not fire.

```yaml
fail_when:
  column: Installation Date
  date_equals: "2024-01-01"
```

### `date_greater_than`

Fires when the column date is strictly after the literal date. Blank or unparseable date values
do not fire.

```yaml
fail_when:
  column: Completion Date
  date_greater_than: "2024-06-30"
```

### `date_greater_than_or_equal`

Fires when the column date is on or after the literal date. Blank or unparseable date values do
not fire.

```yaml
fail_when:
  column: Start Date
  date_greater_than_or_equal: "2025-01-01"
```

### `date_less_than`

Fires when the column date is strictly before the literal date. Blank or unparseable date values
do not fire.

```yaml
fail_when:
  column: Inspection Date
  date_less_than: "2023-01-01"
```

### `date_less_than_or_equal`

Fires when the column date is on or before the literal date. Blank or unparseable date values do
not fire.

```yaml
fail_when:
  column: Application Date
  date_less_than_or_equal: "2022-12-31"
```

### `date_between`

Fires when the column date is within the inclusive date range. Blank or unparseable date values
do not fire.

```yaml
fail_when:
  column: Event Date
  date_between: ["2024-01-01", "2024-12-31"]
```

### `date_not_between`

Fires when the column date falls outside the inclusive date range. Blank or unparseable date
values fire `date_not_between`.

```yaml
fail_when:
  column: Service Date
  date_not_between: ["2023-01-01", "2025-12-31"]
```

### `date_equals_column`

Fires when the left date column equals the right date column after normalization. Blank values do
not fire.

```yaml
fail_when:
  column: Scheduled Date
  date_equals_column: Actual Date
```

### `date_not_equals_column`

Fires when the left date column does not equal the right date column. A blank left value fires
when the right value is not blank.

```yaml
fail_when:
  column: Reported Date
  date_not_equals_column: System Date
```

### `date_greater_than_column`

Fires when the left date is strictly after the right date. Blank values on either side do not
fire.

```yaml
fail_when:
  column: Completion Date
  date_greater_than_column: Deadline Date
```

### `date_greater_than_or_equal_column`

Fires when the left date is on or after the right date. Blank values on either side do not fire.

```yaml
fail_when:
  column: End Date
  date_greater_than_or_equal_column: Start Date
```

### `date_less_than_column`

Fires when the left date is strictly before the right date. Blank values on either side do not
fire.

```yaml
fail_when:
  column: Installation Date
  date_less_than_column: Inspection Date
```

### `date_less_than_or_equal_column`

Fires when the left date is on or before the right date. Blank values on either side do not fire.

```yaml
fail_when:
  column: Application Date
  date_less_than_or_equal_column: Deadline Date
```

### `days_apart_greater_than`

Fires when the absolute day difference between two date columns exceeds a threshold. The
comparison is direction-agnostic — it does not matter which date is earlier. Blank or unparseable
values on either side do not fire.

```yaml
fail_when:
  column: Installation Date
  days_apart_greater_than:
    column: Date Inspected
    days: 31
```

This fires when the gap between `Installation Date` and `Date Inspected` is more than 31 days in
either direction.

---

## Computed Column Types

Computed columns are generated before rule evaluation and can be referenced by rules like any
other column. They are declared under `computed_columns` at the top level of the bundle.

The output column's name is the `name` field when present, otherwise the `id` field.

### `sum`

Row-wise sum across two or more columns. Missing values are skipped. Returns blank when all inputs
for a row are blank.

```yaml
computed_columns:
  - id: total_savings
    name: Total Savings
    type: sum
    columns:
      - kWh Savings
      - Therm Savings
      - kW Savings
```

### `subtract`

Row-wise left-to-right subtraction across two or more columns.

```yaml
computed_columns:
  - id: savings_variance
    name: Savings Variance
    type: subtract
    columns:
      - Reported Savings
      - Approved Savings
```

For more than two columns, each subsequent column is subtracted from the running result.

### `multiply`

Row-wise left-to-right multiplication across two or more columns.

```yaml
computed_columns:
  - id: total_incentive
    name: Total Incentive
    type: multiply
    columns:
      - Unit Incentive
      - Installed Quantity
```

### `divide`

Row-wise division of exactly two columns. A zero denominator produces a blank result for that row.

```yaml
computed_columns:
  - id: efficiency_ratio
    name: Efficiency Ratio
    type: divide
    columns:
      - Output kWh
      - Input kWh
```

### `coalesce`

Returns the first non-null value across the listed columns for each row. Useful for filling in a
preferred value from a fallback chain. Empty strings are not treated as null and will be returned
if they appear before a non-empty value.

```yaml
computed_columns:
  - id: best_available_date
    name: Best Available Date
    type: coalesce
    columns:
      - Date Inspected
      - Alternative Date A
      - Alternative Date B
```

### `all_blank_or_zero`

Returns `1` when every listed column value for a row is blank or numeric zero, otherwise returns
`0`. Treats null, NaN, empty strings, whitespace, and zero as empty-equivalent.

```yaml
computed_columns:
  - id: no_savings_reported
    name: No Savings Reported
    type: all_blank_or_zero
    columns:
      - kWh Savings
      - kW Savings
      - Therm Savings
```

The resulting column can then be checked in a rule:

```yaml
rules:
  - id: no_savings_present
    fail_when:
      column: No Savings Reported
      equals: 1
    message: At least one savings value is required.
```

### `group_sum`

Maps the sum of a value column for each group back to every row in that group. Rows that share the
same `group_by` value receive the same group total.

```yaml
computed_columns:
  - id: project_total_kwh
    name: Project Total kWh
    type: group_sum
    group_by: Project ID
    value_column: kWh Savings
```

An optional `filter` restricts which rows contribute to each group total. Rows that do not match
the filter are still assigned the group total; they just do not contribute to it.

```yaml
computed_columns:
  - id: project_approved_kwh
    name: Project Approved kWh
    type: group_sum
    group_by: Project ID
    value_column: kWh Savings
    filter:
      column: Status
      equals: "Approved"
```

Groups with no numeric contributing values (after filtering) receive a blank result.

### `group_count`

Maps the row count for each group back to every row in that group.

```yaml
computed_columns:
  - id: project_measure_count
    name: Project Measure Count
    type: group_count
    group_by: Project ID
```

An optional `filter` restricts which rows are counted. Groups with no matching rows receive `0`.

```yaml
computed_columns:
  - id: project_bef_count
    name: Project BEF Count
    type: group_count
    group_by: Project ID
    filter:
      column: Measure Type
      equals: BEF
```

### `date_diff`

Returns the number of whole days from `start_column` to `end_column`
(`end_column - start_column`). Results may be negative when the end date is before the start
date. Blank or unparseable dates on either side produce a blank result.

```yaml
computed_columns:
  - id: days_to_inspection
    name: Days to Inspection
    type: date_diff
    start_column: Installation Date
    end_column: Date Inspected
```

### `days_since_today`

Returns the number of whole days from the source column to today (`today - column`). Blank or
unparseable dates produce a blank result.

```yaml
computed_columns:
  - id: days_since_installation
    name: Days Since Installation
    type: days_since_today
    column: Installation Date
```

### `years_since_year`

Treats the source column as a numeric calendar year and returns `current_year - year`. This is an
integer subtraction, not a date calculation.

```yaml
computed_columns:
  - id: system_age
    name: System Age
    type: years_since_year
    column: Installation Year
```

### `scale`

Multiplies every value in a column by a numeric constant. Blank values remain blank.

```yaml
computed_columns:
  - id: adjusted_kwh
    name: Adjusted kWh
    type: scale
    column: Gross kWh
    scalar: 0.85
```

### `add_constant`

Adds a numeric constant to every value in a column. Use a negative constant to subtract. Blank
values remain blank.

```yaml
computed_columns:
  - id: adjusted_incentive
    name: Adjusted Incentive
    type: add_constant
    column: Base Incentive
    constant: 50
```

### `round`

Rounds each value in a column to the given number of decimal places. Pass a negative `decimals`
value to round to the nearest ten, hundred, etc.

```yaml
computed_columns:
  - id: rounded_savings
    name: Rounded Savings
    type: round
    column: Adjusted kWh
    decimals: 2
```

```yaml
computed_columns:
  - id: rounded_to_nearest_ten
    name: Rounded to Nearest Ten
    type: round
    column: Raw Value
    decimals: -1
```

### `alias`

Copies a column under a new name without transforming any values. Null and blank values are
preserved as-is.

```yaml
computed_columns:
  - id: reported_kwh_copy
    name: Reported kWh
    type: alias
    column: Gross kWh
```

`alias` is useful when a downstream rule or a second computed column needs to reference the same
data under a different name.
