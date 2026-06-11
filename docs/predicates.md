# Predicates

Predicates are the authoring-layer operators used inside a rule's `fail_when` condition.

```yaml
fail_when:
  column: Amount
  greater_than: 1000
```

In this example, `greater_than` is the predicate. `column` names the DataFrame column to inspect,
and `1000` is the predicate value.

RuleFrame records a finding when the predicate evaluates to true.

## Boolean Composition

| Node | Meaning |
| --- | --- |
| `all` | All child conditions must be true. |
| `any` | At least one child condition must be true. |
| `not` | Wraps one condition and flips its result. |

```yaml
fail_when:
  all:
    - column: Status
      equals: "Active"
    - column: Total
      greater_than: 1000
```

## Equality

| Predicate | Value | Fires when |
| --- | --- | --- |
| `equals` | scalar | Column value equals the literal. |
| `not_equals` | scalar | Column value does not equal the literal. |

```yaml
fail_when:
  column: Status
  equals: "Active"
```

`not_equals` fires when the left-side column value is blank and the expected literal is not blank.
If the expected literal is blank, `not_equals` does not fire.

## Numeric Comparison

| Predicate | Value | Fires when |
| --- | --- | --- |
| `greater_than` | number | Column value is greater than the literal. |
| `greater_than_or_equal` | number | Column value is greater than or equal to the literal. |
| `less_than` | number | Column value is less than the literal. |
| `less_than_or_equal` | number | Column value is less than or equal to the literal. |

```yaml
fail_when:
  column: Installed Quantity
  less_than_or_equal: 0
```

Numeric comparison predicates imply numeric source columns. RuleFrame coerces those columns on a
working copy before evaluation. Blank or unparseable values do not fire these positive comparison
predicates.

## Column-To-Column Comparison

| Predicate | Value | Fires when |
| --- | --- | --- |
| `equals_column` | column name | Left column equals right column. |
| `not_equals_column` | column name | Left column does not equal right column. |
| `greater_than_column` | column name | Left column is greater than right column. |
| `greater_than_or_equal_column` | column name | Left column is greater than or equal to right column. |
| `less_than_column` | column name | Left column is less than right column. |
| `less_than_or_equal_column` | column name | Left column is less than or equal to right column. |

```yaml
fail_when:
  column: Installed Quantity
  not_equals_column: Reported Quantity
```

Numeric column comparisons imply numeric source columns on both sides, except `equals_column` and
`not_equals_column`, which compare the current values without implying numeric coercion.

For `not_equals_column`, a blank left value fires when the right value is not blank. If the right
value is blank, the predicate does not fire.

## Membership

| Predicate | Value | Fires when |
| --- | --- | --- |
| `in` | list | Column value is in the list. |
| `not_in` | list | Column value is not in the list. |

```yaml
fail_when:
  column: Fuel Type
  not_in: ["Electric", "Natural Gas", "Propane"]
```

Lists should contain values of one type. Mixed string, numeric, and boolean lists raise
`BundleValidationError`.

`not_in` is implemented as the negation of `in`. Because blank values are not members of ordinary
lists such as `["Electric", "Gas"]`, a blank column value fires `not_in` in that case.

## String Containment

| Predicate | Value | Fires when |
| --- | --- | --- |
| `contains` | string | Column value contains the substring. |
| `not_contains` | string | Column value does not contain the substring. |

```yaml
fail_when:
  column: Notes
  contains: "manual review"
```

Blank values do not fire `contains`. `not_contains` is implemented as the negation of `contains`,
so a blank column value fires `not_contains`.

## Ranges

| Predicate | Value | Fires when |
| --- | --- | --- |
| `between` | `[lower, upper]` | Lower bound <= column value <= upper bound. |
| `not_between` | `[lower, upper]` | Column value falls outside the inclusive range. |

```yaml
fail_when:
  column: Score
  not_between: [0, 100]
```

Range predicates imply numeric source columns. Blank or unparseable values do not fire `between`.
`not_between` is implemented as the negation of `between`, so blank or unparseable values fire
`not_between`.

## Blank Checks

| Predicate | Value | Fires when |
| --- | --- | --- |
| `is_blank` | `true` | Column is null, NaN, an empty string, or whitespace. |
| `is_blank` | `false` | Column has any non-blank value. |
| `is_not_blank` | `true` | Column has any non-blank value. |
| `is_not_blank` | `false` | Column is null, NaN, an empty string, or whitespace. |

```yaml
fail_when:
  column: Customer Status
  is_blank: true
```

Blank checks do not imply numeric, string, boolean, or date coercion.

## Date Literal Comparison

Date literal predicates compare a DataFrame column to a literal date. Use ISO date literals in
rule files.

| Predicate | Value | Fires when |
| --- | --- | --- |
| `date_equals` | `"YYYY-MM-DD"` | Column date equals the literal date. |
| `date_greater_than` | `"YYYY-MM-DD"` | Column date is after the literal date. |
| `date_greater_than_or_equal` | `"YYYY-MM-DD"` | Column date is on or after the literal date. |
| `date_less_than` | `"YYYY-MM-DD"` | Column date is before the literal date. |
| `date_less_than_or_equal` | `"YYYY-MM-DD"` | Column date is on or before the literal date. |
| `date_between` | `[start, end]` | Column date is within the inclusive date range. |
| `date_not_between` | `[start, end]` | Column date is outside the inclusive date range. |

```yaml
fail_when:
  column: Installation Date
  date_greater_than: "2024-03-01"
```

```yaml
fail_when:
  column: Event Date
  date_between: ["2024-01-01", "2024-12-31"]
```

Blank or unparseable date values do not fire the positive date literal comparisons.
`date_not_between` is implemented as the negation of `date_between`, so blank or unparseable date
values fire `date_not_between`.

## Date Column-To-Column Comparison

Date column predicates compare two source columns after date normalization.

| Predicate | Value | Fires when |
| --- | --- | --- |
| `date_equals_column` | column name | Left date equals right date. |
| `date_not_equals_column` | column name | Left date does not equal right date. |
| `date_greater_than_column` | column name | Left date is after right date. |
| `date_greater_than_or_equal_column` | column name | Left date is on or after right date. |
| `date_less_than_column` | column name | Left date is before right date. |
| `date_less_than_or_equal_column` | column name | Left date is on or before right date. |

```yaml
fail_when:
  column: Installation Date
  date_greater_than_column: Date Inspected
```

Blank values do not fire date ordering predicates. For `date_not_equals_column`, a blank left
value fires when the right value is not blank.

## Date Distance

`days_apart_greater_than` compares the absolute day difference between two date columns.

```yaml
fail_when:
  column: Installation Date
  days_apart_greater_than:
    column: Date Inspected
    days: 31
```

This fires when the absolute difference between the two dates is greater than `days`. Blank or
unparseable values on either side do not fire.
