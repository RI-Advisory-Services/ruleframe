# Type Coercion Design

## Problem

Callers currently must preprocess DataFrames before passing them to `validate_dataframe`. The common pattern (seen in `scratch/pilot_verification/run_pilot.py`) is:

```python
df = pd.read_excel(path, dtype=str)
for col in df.columns:
    converted = pd.to_numeric(df[col], errors="coerce")
    if converted.notna().sum() >= df[col].notna().sum():
        df[col] = converted
```

This is error-prone, hard to debug, and defeats the purpose of a self-contained validation library. The package should handle type coercion internally using information it already has — the rule and computed column structure.

## Design Principles

- **Infer types from rule structure** — same pattern already used for date columns.
- **One centralized coercion pass** — not scattered across operators and computed column functions.
- **Preserve original data in output** — coercion is an internal evaluation detail.
- **Clear feedback** — never silently change data semantics without telling the user.
- **No over-engineering** — don't force the user to declare schemas for every column.

## Type Inference Rules

### Predicates That Imply Numeric

These predicates always imply the left-hand column must be numeric:

- `greater_than` (literal)
- `greater_than_or_equal` (literal)
- `less_than` (literal)
- `less_than_or_equal` (literal)
- `between` (literal bounds)
- `greater_than_column` (both columns)
- `greater_than_or_equal_column` (both columns)
- `less_than_column` (both columns)
- `less_than_or_equal_column` (both columns)

### Predicates That Infer Type From the Literal

- `equals` with a YAML-parsed int/float → column is numeric
- `equals` with a YAML-parsed string → column is string
- `equals` with a YAML-parsed bool (`true`/`false`) → **no type signal** (see Boolean Columns below)
- `not_equals` — same logic as `equals`

### `in` Predicate

- All list items are numeric (int, float, or mix of both) → column is numeric
- All list items are strings → column is string
- All list items are bools → no type signal (see Boolean Columns below)
- Mixed types (strings AND numbers) → `BundleValidationError` at bundle validation time: the rule is invalid

### Boolean Columns

YAML `true`/`false` are Python `bool` values. Because `bool` is a subclass of `int` in Python, they would incorrectly match `isinstance(value, int)` if not handled first. ruleframe explicitly checks for `bool` before `int` in type inference, so boolean literals produce a `"boolean"` type signal — the column is tracked, participates in conflict detection, and is left as-is (no coercion).

**The rule literal is the contract for boolean columns:**
- `equals: true` → the column contains Python `True`/`False` (pandas `bool` or `object` dtype with bool values)
- `equals: 1` → the column contains integers (numeric coercion applies)
- `equals: "True"` → the column contains the string `"True"` (no coercion, string comparison)

If the data source stores booleans as integers (`1`/`0`) or strings (`"TRUE"`/`"FALSE"`), the rule author is responsible for writing the literal to match the actual representation in the DataFrame. ruleframe does not attempt to reconcile mixed boolean representations — this is a rule authoring responsibility.

### Computed Columns That Imply Numeric

Arithmetic computed column types imply their source columns are numeric:

- `sum` → all `columns` are numeric
- `subtract` → all `columns` are numeric
- `multiply` → all `columns` are numeric
- `divide` → both `columns` are numeric
- `group_sum` → `value_column` is numeric
- `years_since_year` → `column` is numeric (integer year)

Date types (`date_diff`, `days_since_today`) already have their own normalization path and are unaffected.

### `columns:` Schema — Deferred to v2

An explicit `columns:` schema was considered for v1 to allow users to override inferred types. After analysis, we determined that:

- If inference produces no signal for a column, an explicit declaration has no behavioral effect (string/date columns are not coerced regardless).
- If inference produces a signal and the explicit declaration agrees, it's a no-op.
- If inference produces a signal and the explicit declaration contradicts it, the override silently hides what is almost certainly a rule authoring error.

Rather than providing a mechanism that silently suppresses errors, we defer this feature. If a future use case demonstrates that explicit column declarations add value beyond inference, we will revisit with semantics that raise on contradiction rather than silently overriding.

## Conflicting Signals

Any column inferred as more than one type raises `BundleValidationError` at validation time. This covers all combinations: numeric vs string, numeric vs boolean, string vs boolean. The fix is always to correct the rule definitions so all predicates agree on the column type.

### Date vs Numeric/String Cross-Check

Date columns are inferred by a separate path (`_infer_date_columns`) that looks for date predicates (`date_equals`, `date_greater_than_column`, etc.) and date-type computed specs (`date_diff`, `days_since_today`). After both inference passes run, ruleframe checks for overlap: if any column appears in both the date set and the numeric/string map, a `BundleValidationError` is raised. A column cannot be used as both a date and a numeric/string value.

## Pipeline Position

The coercion pass runs inside `validate_dataframe`:

1. Validate bundle structure
2. Check for missing required columns
3. Check for computed column name collisions
4. **Infer column types from rules + computed column specs**
5. **Infer date columns; cross-check for date/numeric-string overlap**
6. **Coerce numeric columns on a working copy** (not the original)
7. Normalize date columns (existing behavior)
8. Apply computed columns (existing behavior, simplified — see below)
9. Evaluate rules
10. Build output

## Internal Architecture

### Two DataFrames

- **Original df** — preserved unmodified for output
- **Working df** — coerced copy used for evaluation

`result.to_annotated_dataframe()` returns: original columns (original dtypes/values) + computed columns + validation errors column.

`result.working_dataframe` (new attribute) provides access to the coerced working copy for debugging/inspection. This is not a default output.

### Coercion Implementation

For each column inferred as numeric:

```python
converted = pd.to_numeric(working_df[col], errors="coerce")
```

Track:
- Pre-existing NaN count (before coercion)
- Post-coercion NaN count
- Delta = values that became NaN due to coercion

## Feedback Layer

### CoercionEvent

```python
@dataclass
class CoercionEvent:
    column: str
    target_type: str  # "numeric" or "date"
    total_non_null: int
    coerced_successfully: int
    coercion_failures: int  # non-null values that became NaN
```

### Coercion Log

`ValidationResult` gains a `coercion_log: list[CoercionEvent]` attribute. Always populated, regardless of warning settings.

### Tiered Response

| Coercion outcome | Behavior |
|---|---|
| All non-null values coerce successfully | Log entry only (happy path) |
| Some values fail to coerce | `warnings.warn()` — *"Column 'X' used with `greater_than`: 3 non-null values could not be parsed as numeric and are now NaN. This may affect downstream rules evaluating blanks."* |
| ALL non-null values fail to coerce | Raise `InputSchemaError` — *"Column 'X' is used as numeric (greater_than in rule Y) but contains no parseable numeric values."* Same class of error as "missing required column." |

### Suppressing Warnings

`validate_dataframe(df, bundle, warn=True)` — default emits `warnings.warn()` for partial failures.

`validate_dataframe(df, bundle, warn=False)` — suppresses `warnings.warn()` calls but still populates `result.coercion_log`.

## Computed Column Simplification

After the centralized coercion pass, computed column source columns are already numeric when they arrive at `compute_column()`. The per-column `pd.to_numeric(..., errors="coerce")` calls inside `sum`, `subtract`, `multiply`, `divide`, `group_sum`, and `years_since_year` implementations can be removed. The computed column code can trust its inputs are properly typed.

This is a light refactor to align with the new design — not a behavior change.

## Output Contract

| Output | Contents |
|---|---|
| `result.to_annotated_dataframe()` | Original input columns (original dtypes) + computed columns + validation errors column |
| `result.to_findings_dataframe()` | One row per finding (unchanged) |
| `result.working_dataframe` | Coerced working copy (for debugging) |
| `result.coercion_log` | List of `CoercionEvent` objects |

## Examples

### Happy Path — No User Action Needed

ruleframe accepts a DataFrame in any state. Do your own prep work first — fix decimals, rename columns, filter rows — then pass it in. ruleframe uses the rules file to determine which columns need to be numeric and coerces them if needed. If pandas already inferred them correctly during read, the coercion pass is a no-op.

```python
# Works whether pandas inferred dtypes or you read with dtype=str
df = pd.read_excel("input.xlsx")
bundle = RuleBundle.from_yaml("rules.yaml")
result = validate_dataframe(df, bundle)
# result.coercion_log shows what ruleframe did (or didn't need to do).
# event.input_dtype tells you what dtype each column had when it arrived.
```

### Debugging Coercion Issues

```python
result = validate_dataframe(df, bundle)
for event in result.coercion_log:
    print(f"{event.column}: input dtype={event.input_dtype}, failures={event.coercion_failures}")
```

## Out of Scope

- File loading (ruleframe receives a DataFrame, not a file path)
- Global "always preprocess this way" settings
- `columns:` schema for explicit type declarations (deferred to v2 — see above)
- `nullable`, `allowed_values`, or other schema constraints beyond `type`
- Auto-sorting or resolving conflicting type signals (these are authoring errors)
