# JsonLogic Spike Notes

## Files

- `sample_rules.yaml`: small friendly rule bundle in the proposed v1 shape.
- `jsonlogic_spike.py`: prototype compiler/evaluator.

Run from the repo root:

```bash
.venv/bin/python future-package-design/jsonlogic_spike.py
```

## What This Spike Proves

- A friendly YAML rule shape can be compiled into JsonLogic expressions.
- `python-jsonlogic` can evaluate those compiled expressions row-by-row against DataFrame records.
- Custom operators are straightforward to register through `OperatorRegistry`.
- Column names with spaces, slashes, punctuation, and question marks work when converted to JSON Pointer paths.
- We can generate a validation row id before evaluation.
- We can produce the two output surfaces currently preferred for v1:
  - annotated input DataFrame with `Validation Errors`
  - rule summary DataFrame
- We can also keep a structured findings table for Django/API use.

## Custom Operators Tested

The spike registers these custom operators:

- `and`
- `or`
- `!`
- `in`
- `is_blank`
- `is_not_blank`
- `date_days_apart_gt`

Important finding: the installed `python-jsonlogic` default registry is intentionally minimal. It includes operators such as `var`, equality/comparison operators, arithmetic, `if`, and `map`, but not all JsonLogic-standard convenience operators. Our package should therefore own a default validation operator registry.

## Column Checking

The spike includes a simple `collect_required_columns()` function that walks the friendly rule syntax and extracts referenced input columns.

This supports the planned **Input Schema Check** stage:

```text
RuleBundle + input DataFrame -> missing required columns
```

Computed columns are not modeled in this spike yet, but the same idea should apply:

1. Check source columns needed by computed columns.
2. Generate computed columns.
3. Check columns needed by rules.

## YAML Footgun

Bare values like `Yes` may be parsed by YAML as booleans depending on parser/schema behavior.

Example:

```yaml
equals: Yes
```

can become:

```python
True
```

This caused a real first-run bug in the spike. The sample rules now quote string values:

```yaml
equals: "Yes"
```

The future package should either document this clearly, normalize common YAML booleans carefully, or provide rule schema validation warnings for suspicious values.

## Typecheck Finding

`python-jsonlogic` typechecking reported diagnostics for numeric comparisons when the schema allowed nulls:

```text
Operator "<" not supported for types union(null, number, integer) and integer
Operator ">" not supported for types union(null, number, integer) and integer
```

Runtime evaluation still worked for the sample rows.

This is useful but needs design attention. Possible approaches:

- keep nullable schemas and treat diagnostics as warnings
- use stricter non-null schemas and handle nulls in custom operators
- create custom comparison operators with package-specific null behavior
- let rules declare whether null should fail, pass, or be ignored

## `json-logic` Custom Operator Note

The older `json-logic` package from `nadirizr/json-logic-py` has a module-level `operations` dictionary. It appears custom behavior could be added by mutating that dictionary, but that is less structured than `python-jsonlogic`'s registry and operator classes.

This supports the current preference for `python-jsonlogic`.

## Current Recommendation

Continue with `python-jsonlogic` as the preferred evaluator candidate.

The package should provide:

- a friendly YAML/JSON authoring format
- a compiler to JsonLogic
- a package-owned default operator registry
- custom operators for blank/null/date behavior
- input schema checking
- computed columns
- structured findings
- output renderers

The spike supports the design direction but leaves computed columns, group-level operations, richer date handling, and full schema validation for the next prototype.
