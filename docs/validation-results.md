# Validation Results

`validate_dataframe()` returns a `ValidationResult`.

```python
from ruleframe import RuleBundle, validate_dataframe

bundle = RuleBundle.from_yaml("rules.yaml")
result = validate_dataframe(df, bundle)
```

The result contains row-level findings, an annotated DataFrame, summary helpers, and coercion
details.

## Findings

`result.findings` is a list of finding objects. Each finding has:

| Field | Description |
| --- | --- |
| `row_index` | Zero-based row position in the validation run. |
| `rule_id` | Rule identifier from the bundle. |
| `rule_name` | Optional rule display name. |
| `severity` | Rule severity, defaulting to `error`. |
| `message` | Rule message, defaulting to `Rule failed`. |

Use `to_findings_dataframe()` to get a pandas DataFrame:

```python
findings = result.to_findings_dataframe()
```

The DataFrame columns are:

```text
row_index, rule_id, rule_name, severity, message
```

When there are no findings, the returned DataFrame is empty.

## Annotated DataFrame

Use `to_annotated_dataframe()` to get the original DataFrame plus validation output:

```python
annotated = result.to_annotated_dataframe()
```

The annotated DataFrame includes:

- All original input columns.
- Computed columns declared in the bundle.
- A validation message column.

The default validation message column is `Validation Errors`. Override it with bundle settings:

```yaml
settings:
  validation_errors_column: RuleFrame Messages
```

If multiple rules fire on a row, their messages are joined with ` | ` in the validation message
column. Rows with no findings receive an empty string in that column.

`to_annotated_dataframe()` returns a copy.

## Summary DataFrame

Use `to_summary_dataframe()` to count findings by rule and severity:

```python
summary = result.to_summary_dataframe()
```

The summary DataFrame columns are:

```text
rule_id, severity, count
```

When there are no findings, the summary DataFrame is empty with those columns.

## Working DataFrame

`result.working_dataframe` contains RuleFrame's internal working DataFrame. It may include:

- Numeric coercions.
- Date-normalized source columns.
- Computed columns.

This is primarily useful for debugging. For normal reporting, prefer
`to_annotated_dataframe()`.

## Coercion Log

`result.coercion_log` records numeric coercions applied before validation. Each `CoercionEvent`
has:

| Field | Description |
| --- | --- |
| `column` | Column that was coerced. |
| `target_type` | Currently `numeric`. |
| `input_dtype` | pandas dtype before coercion. |
| `total_non_null` | Non-null values before coercion. |
| `coerced_successfully` | Values that remained non-null after coercion. |
| `coercion_failures` | Non-null values that became NaN during coercion. |

```python
for event in result.coercion_log:
    print(event.column, event.coercion_failures)
```

By default, partial numeric coercion failures also emit warnings. Pass `warn=False` to suppress
warnings while keeping the coercion log:

```python
result = validate_dataframe(df, bundle, warn=False)
```

If every non-null value in an inferred numeric column fails to parse, validation raises
`InputSchemaError`.

## Exceptions

RuleFrame exposes a small exception hierarchy:

| Exception | Typical cause |
| --- | --- |
| `RuleFrameError` | Base class for RuleFrame errors. |
| `BundleValidationError` | Invalid bundle structure, unsupported predicates, conflicting type signals, or invalid computed-column specs. |
| `InputSchemaError` | Input DataFrame is missing required columns, computed columns collide with input columns, or numeric input cannot be parsed. |

`RuleBundle` construction catches basic structural problems, such as missing `id` or `fail_when`.
DataFrame-dependent checks happen when `validate_dataframe()` runs.
