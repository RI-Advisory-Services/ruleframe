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
- `equals` with a YAML-parsed string → no coercion (column stays as-is)
- `not_equals` — same logic as `equals`

### `in` Predicate

- All list items are numeric (int, float, or mix of both) → column is numeric
- All list items are strings → no coercion
- Mixed types (strings AND numbers) → `BundleValidationError` at bundle validation time: the rule is invalid

### Computed Columns That Imply Numeric

Arithmetic computed column types imply their source columns are numeric:

- `sum` → all `columns` are numeric
- `subtract` → all `columns` are numeric
- `multiply` → all `columns` are numeric
- `divide` → both `columns` are numeric
- `group_sum` → `value_column` is numeric
- `years_since_year` → `column` is numeric (integer year)

Date types (`date_diff`, `days_since_today`) already have their own normalization path and are unaffected.

### `columns:` Schema (Optional Explicit Override)

Users may declare column types in the bundle for explicit control:

```yaml
columns:
  Zip Code:
    type: string
  Building Square Footage:
    type: number
```

Rules:
- Partial lists only — declare only what you need to override or clarify.
- Undeclared columns use inference from rule/computed column structure.
- Explicit declaration wins over inference (e.g., declare `type: string` to prevent numeric coercion on a column that looks numeric but shouldn't be coerced).
- v1 supports `type: number | string | date` only. Future versions may add more.

## Conflicting Signals

If a column is used with both string semantics (`equals: "Yes"`) and numeric semantics (`greater_than: 100`) across different rules, raise `BundleValidationError` at bundle validation time with a message identifying the conflicting rules and column.

## Pipeline Position

The coercion pass runs inside `validate_dataframe`:

1. Validate bundle structure
2. Check for missing required columns
3. Check for computed column name collisions
4. **Infer column types from rules + computed column specs**
5. **Coerce columns on a working copy** (not the original)
6. Normalize date columns (existing behavior)
7. Apply computed columns (existing behavior, simplified — see below)
8. Evaluate rules
9. Build output

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

```python
df = pd.read_excel("input.xlsx", dtype=str)
bundle = RuleBundle.from_yaml("rules.yaml")
result = validate_dataframe(df, bundle)
# Numeric columns auto-coerced based on rule structure.
# result.coercion_log shows what happened.
```

### Explicit Override — Zip Code Protection

```yaml
columns:
  Zip Code:
    type: string

rules:
  - id: check_zip
    fail_when:
      column: Zip Code
      is_blank: true
```

### Debugging Coercion Issues

```python
result = validate_dataframe(df, bundle)
for event in result.coercion_log:
    if event.coercion_failures > 0:
        print(f"{event.column}: {event.coercion_failures} values could not be coerced")
```

## Out of Scope

- File loading (ruleframe receives a DataFrame, not a file path)
- Global "always preprocess this way" settings
- `nullable`, `allowed_values`, or other schema constraints beyond `type`
- Auto-sorting or resolving conflicting type signals (these are authoring errors)
