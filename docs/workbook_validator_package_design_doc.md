# RuleFrame / Py-Sheet-Rules Package Design

## Purpose

This document captures the current design direction for a future public Python package that validates Excel workbook and DataFrame data against configurable rules.

The main expected consuming application is a Django app, but the package should not be Django-specific. The goal is a general Python library that can be used from any Python application that can provide a pandas DataFrame and a YAML/JSON rule bundle. A CLI may be added later as a convenience layer, but the library API is the primary product.

The package is intended to replace repeated one-off validation notebooks and ambiguous rules spreadsheets with a reusable validation framework. Rules should be easier to author, review, test, version, and reuse across projects.

Candidate package names so far:

- `ruleframe`
- `py-sheet-rules`

## Core Goals

- Build a Python package for validating DataFrame-like tabular data with declarative rules.
- Use `python-jsonlogic` as the core expression evaluation engine.
- Extend `python-jsonlogic` with a package-owned validation operator registry.
- Make custom operators a first-class package feature, especially for blanks, nulls, dates, and domain-specific checks.
- Accept a single YAML or JSON rule bundle as the primary v1 rules input.
- Apply all configured rules to all records in an input DataFrame.
- Return structured validation findings and output tables similar to the current workflow.
- Support nested boolean logic, especially `all`, `any`, and `not`.
- Support generated/computed columns before rule evaluation.
- Separate loading, rule schema validation, input schema checking, computed column generation, rule evaluation, and output rendering.
- Make the rule format understandable to non-technical users.
- Keep the package library-first so it can be called cleanly from Django or any other Python app.
- Leave room for future multi-file rule bundles, UI-managed rule definitions, raw JsonLogic rules, and CLI workflows.

## Package Shape

The package should expose a simple library API:

```python
from ruleframe import RuleBundle, validate_dataframe

bundle = RuleBundle.from_yaml("rules.yaml")
result = validate_dataframe(df, bundle)
```

The Django application can load the rules file from S3, a file wrapper, a database field, or another source, then pass its contents into the package. The package should not assume that a folder of rule files exists.

The same API should also work from scripts, notebooks, ETL jobs, or other Python services.

## Rule Bundle

For v1, rules should live in one YAML or JSON document. Multi-file support can be added later as a loader concern that merges multiple files into the same internal `RuleBundle` model.

Example high-level structure:

```yaml
version: 1

settings:
  row_id:
    column: __validation_row_id__
    strategy: sequential
  timezone: America/Chicago
  null_policy: default
  date_parsing:
    allow_excel_serial: true
    formats:
      - "%Y-%m-%d"
      - "%m/%d/%Y"

columns:
  Installation Date:
    type: date
  Building Square Footage:
    type: number
  Customer Status:
    type: string

computed_columns:
  - id: total_measure_savings
    name: Total Measure Savings
    type: sum
    columns:
      - Total Measure Gross kWh
      - Total Measure Gross kW
      - Total Measure Gross Therms

rules:
  - id: qaqc_unresolved_issue
    name: QA/QC unresolved issue
    severity: error
    fail_when:
      all:
        - column: Selected for QA/QC
          equals: "Yes"
        - column: Issues noted during QA/QC appointment?
          equals: "Yes"
        - column: QA/QC Resolved
          is_blank: true
    message: QA/QC was selected and issues were noted, but QA/QC Resolved is blank.
```

Important YAML note: string values like `"Yes"` should be quoted. During the spike, bare `Yes` was parsed as boolean `True`, which caused an incorrect comparison. The package should document this clearly and ideally provide rule schema validation warnings for suspicious values.

## Settings Section

The `settings` section should hold run-level behavior that should not be repeated on individual rules.

Likely v1 settings:

- `row_id`: generated row id column name and strategy.
- `timezone`: timezone used for date/time parsing and "today"/"now" behavior.
- `date_parsing`: date format configuration and whether Excel serial dates are allowed.
- `null_policy`: default null/blank behavior.
- `case_sensitive`: default string comparison behavior.
- `validation_errors_column`: output column name for annotated DataFrames.

Possible future settings:

- default severity
- whether typecheck diagnostics are warnings or errors
- whether unknown rule fields are allowed
- whether missing optional columns should warn or fail
- output formatting preferences
- maximum number of findings per row or workbook

## Rule Semantics

The primary v1 rule structure should be:

```yaml
fail_when:
  all:
    - column: Some Column
      equals: Some Value
```

A rule creates a finding when its `fail_when` expression evaluates to `true` for a record.

This keeps the rule authoring model direct: "if this condition is true, the row has a problem."

The `applies_when` / `expect` pattern may still be useful later as authoring sugar:

```text
fail_when = applies_when AND NOT expect
```

But it should not be the v1 primitive.

## Nested Logic

Rules should support recursive boolean logic:

```yaml
fail_when:
  all:
    - column: Program
      equals: Retrofits
    - any:
        - column: Fuel Type Heat
          in: [Natural Gas, Propane]
        - column: Fuel Type DHW
          in: [Natural Gas, Propane]
    - column: Customer Status
      is_blank: true
```

Supported boolean nodes:

- `all`
- `any`
- `not`

This gives the package a clean way to represent `AND`, `OR`, and negation without ambiguous spreadsheet precedence.

## JsonLogic Evaluation Engine

The chosen engine direction is `python-jsonlogic`.

The package should not evaluate YAML directly. Instead:

```text
friendly YAML/JSON rule bundle
  -> validated RuleBundle object
  -> compiled JsonLogic expression
  -> evaluated against each record by python-jsonlogic
  -> findings
```

Example friendly rule:

```yaml
fail_when:
  all:
    - column: QA/QC Resolved
      is_blank: true
```

Compiled JsonLogic-style expression:

```json
{
  "and": [
    {
      "is_blank": [
        {
          "var": "/QA~1QC Resolved"
        }
      ]
    }
  ]
}
```

Using JsonLogic means the package does not need to implement a custom recursive boolean evaluator. JsonLogic evaluates the operator tree. The package still needs to compile friendly syntax into JsonLogic and register a validation-oriented operator registry.

## Why `python-jsonlogic`

A spike was completed to test whether `python-jsonlogic` can support this design.

The spike tested:

- friendly YAML -> JsonLogic compilation
- row-wise DataFrame evaluation
- custom operators
- JSON Pointer column paths
- required column extraction
- generated row ids
- annotated output DataFrame
- structured findings output
- rules summary output

The spike supports choosing `python-jsonlogic` as the core engine.

Reasons to choose it:

- It parses JsonLogic into an operator tree.
- It supports an `OperatorRegistry`.
- Custom operators are straightforward to implement as classes.
- It supports typechecking against JSON Schema-style data schemas.
- It supports JSON Pointer variable paths, which worked well for Excel column names containing spaces, slashes, punctuation, and question marks.
- It is a better architectural fit for rule schema validation, input schema checking, date handling, and package-owned semantics around blanks/nulls.

Tradeoffs:

- The API is more involved than the older direct `jsonLogic(rule, data)` style.
- Its default operator registry is intentionally minimal.
- The package will need to provide its own default validation operator registry.
- Typecheck diagnostics around nullable numeric columns need package-level policy decisions.

## Other Packages To Extend Or Reference

### `python-jsonlogic`

Primary package to extend.

The package should use `python-jsonlogic` for JsonLogic parsing, operator-tree construction, typechecking, and expression evaluation.

### `json-logic`

Repository: `https://github.com/nadirizr/json-logic-py`

This is an older direct Python port of the original JsonLogic idea.

Pros:

- Simple.
- Easy mental model.
- Direct `jsonLogic(rule, data)` style.

Cons:

- Older package.
- Less structured support for type checking and schema-aware validation.
- Custom behavior appears to be added by mutating a module-level `operations` dictionary.
- More date/null/type behavior would likely need to be implemented by us without as much framework support.

This package remains useful as a reference, but it is not the preferred v1 engine.

### `jsonlogic-py`

This appears more focused on generating JsonLogic expressions from Python expressions. It may be useful later for a Python-native rule builder API, but it is not currently expected to be needed for v1.

## Package-Owned Operator Registry

The spike showed that `python-jsonlogic`'s default registry is minimal. It includes operators such as:

- `var`
- `==`
- `!=`
- `>`
- `>=`
- `<`
- `<=`
- arithmetic operators
- `if`
- `map`

It does not include all convenience operators we want to use directly. The package should therefore provide a default validation registry that includes:

- `and`
- `or`
- `!`
- `in`
- `is_blank`
- `is_not_blank`
- date operators
- potentially null-safe numeric comparisons
- future group-aware operators, if needed

The friendly YAML compiler can map user-friendly names to this registry:

```yaml
less_than: 500
```

to:

```json
{
  "<": [
    {
      "var": "/Building Square Footage"
    },
    500
  ]
}
```

## Custom Operators

Custom operators are a core package feature, not an edge case.

The current rules and expected future rules need operators beyond plain JsonLogic primitives. Examples:

- `is_blank`
- `is_not_blank`
- date comparisons
- date distance checks
- custom null/NaN/zero handling
- group-aware checks
- domain-specific checks

The spike successfully tested:

- `is_blank`
- `is_not_blank`
- `date_days_apart_gt`

The custom operator layer should own messy interpretation details:

- What counts as blank?
- Are whitespace strings blank?
- Are `NaN`, `None`, and empty strings treated the same?
- Should the string `"nan"` count as blank?
- Should missing numeric values be treated as zero for this specific rule?
- How are Excel serial dates, pandas timestamps, Python `datetime` values, and strings parsed?

Blank/null/zero behavior may need to be configurable per operator or per rule.

## Date And Timestamp Handling

Date and timestamp columns are expected to be one of the harder parts of the package.

Input workbooks may contain:

- Excel serial dates
- pandas timestamps
- Python `date` or `datetime` objects
- ISO date strings
- US-formatted date strings
- mixed date formats in the same column
- blanks or malformed date values

The package should make it easy to add date formats and date parsing behavior over time. Date parsing should likely be centralized in package utilities and used by custom date operators and computed columns.

Possible rule bundle configuration:

```yaml
settings:
  timezone: America/Chicago
  date_parsing:
    allow_excel_serial: true
    formats:
      - "%Y-%m-%d"
      - "%m/%d/%Y"
      - "%m/%d/%y"
```

Column-level overrides may also be useful:

```yaml
columns:
  Installation Date:
    type: date
    formats:
      - "%Y-%m-%d"
      - "%m/%d/%Y"
```

Date parse failures should be visible. The package should avoid silently coercing bad date values without giving users a finding, warning, or diagnostic.

The validation run should also have one stable `now` or `today` value. Operators and computed columns should not call `datetime.now()` independently for every row.

### Date Handling — Implementation Status (2026-05-30)

**What's implemented:**
- `_to_datetime_series()` in `computed.py`: hybrid approach using `pd.to_datetime(errors='coerce')` with per-cell `dateutil.parse` fallback for failures. Handles mixed formats in the same column.
- `_parse_date_like()` in `operators.py`: per-value parser for rule evaluation (Timestamp, datetime, date, string via dateutil).
- `days_since_today` and `date_diff` computed columns use vectorized datetime ops.
- `date_days_apart_gt` operator for rule evaluation.

**What's NOT implemented (from settings spec above):**
- `settings.timezone` — `days_since_today` uses naive `date.today()`, no timezone awareness.
- `settings.date_parsing.formats` — we don't constrain or prioritize formats; dateutil guesses freely. This means `01/02/2024` is ambiguous (Jan 2 vs Feb 1) and we have no way to tell it which to prefer.
- `settings.date_parsing.allow_excel_serial` — Excel serial dates (e.g., `45292`) are not detected or converted.
- Column-level `type: date` declarations — no pre-parsing or type coercion happens based on column schema.
- **No parse-failure diagnostics** — if a date can't be parsed, computed columns silently produce NaN and rules silently don't fire. There's no finding or warning surfaced to the user.
- **No stable `today`** at the run level — `days_since_today` accepts an injected `today` parameter internally (for testing), but there's no bundle-settings-driven mechanism to set it once per run. The operator-level `parse_date_like` has no equivalent.

**Design decisions still needed:**
1. **Format priority vs. auto-detect:** Should `settings.date_parsing.formats` be a strict whitelist (reject anything that doesn't match), a priority list (try in order, fall back to dateutil), or a hint (influence dateutil's `dayfirst`/`yearfirst` params)?
2. **Parse failure behavior:** Should unparseable dates produce a `Finding` (like a rule failure), a separate diagnostic list, or a logged warning? What severity?
3. **Excel serial dates:** Detection heuristic — a bare integer like `45292` in a date column could be a year or a serial date. Do we require `allow_excel_serial: true` + column-level `type: date` to trigger conversion?
4. **Timezone for "today":** Should `settings.timezone` affect only `days_since_today`/`now` behavior, or should it also be used when parsing timezone-naive strings?
5. **Stable run clock:** Should `validate_dataframe` accept an optional `now` parameter, or should it be derived from `settings.timezone` automatically? The operator registry currently has no way to receive run-level context.

### applies_when / expect — Future Consideration

**Status:** Not implemented. `fail_when` is the only v1 rule trigger.

**Open questions:**
1. If we add `applies_when` + `expect`, does the bundle validator reject rules that have both `fail_when` AND `applies_when`? Or allow both patterns per-rule?
2. Should unknown top-level keys on a rule dict (e.g., a typo like `faile_when`) produce a warning or be silently ignored? Currently silently ignored because we only check for `id` + `fail_when` presence.
3. Does adding `applies_when` change the compilation strategy? (`fail_when` compiles to one JsonLogic expression; `applies_when + expect` compiles to `and(applies_when, not(expect))`.)

## Column References

The spike used JSON Pointer variable paths for column references:

```json
{
  "var": "/Selected for QA~1QC"
}
```

This matters because Excel column names often include spaces, slashes, parentheses, punctuation, and question marks.

The compiler should hide this from rule authors. Users should write:

```yaml
column: Selected for QA/QC
```

The compiler should convert that to the correct JsonLogic variable path.

## Input Schema Check

The package should include a preprocessing function that inspects the rule bundle and input DataFrame before evaluation.

The spike included a simple recursive column collector that walks friendly rule syntax and extracts required column names. This supports:

```text
RuleBundle + input DataFrame -> missing required columns
```

The full pipeline should distinguish:

1. Columns needed to compute generated columns.
2. Columns produced by generated columns.
3. Columns needed by rules after computed columns are available.

Type checking should also live near this layer, but it may initially report warnings rather than hard failures because Excel data is often messy.

## Type Checking

`python-jsonlogic` supports typechecking against JSON Schema-style schemas, which is a major reason to prefer it.

Spike finding:

When a numeric column schema allowed nulls, numeric comparisons produced diagnostics:

```text
Operator "<" not supported for types union(null, number, integer) and integer
Operator ">" not supported for types union(null, number, integer) and integer
```

Runtime evaluation still worked for the sample rows.

Possible design responses:

- Keep nullable schemas and treat these diagnostics as warnings.
- Use stricter non-null schemas and handle nulls in custom operators.
- Create package-specific null-safe comparison operators.
- Let rules declare whether null should fail, pass, or be ignored.

This should be considered a known design area, not a blocker.

## Proposed V1 Operators

The first iteration should likely support:

- `equals`
- `not_equals`
- `is_blank`
- `is_not_blank`
- `in`
- `not_in`
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `less_than_or_equal`
- `equals_column`
- `not_equals_column`
- `contains`
- `not_contains`
- `between`
- `not_between`

Potential date-specific operators:

- `date_before`
- `date_after`
- `date_on_or_before`
- `date_on_or_after`
- `within_days`
- `older_than_days`
- `days_apart_greater_than`

These may be implemented as custom JsonLogic operators or compiled into lower-level JsonLogic where possible.

## Computed Columns

Some validations depend on columns that are not present in the input workbook.

Examples:

- `Days Between Inspection and Installation`
- `Days Since Installation`
- output/input ratios
- system age
- all savings zero or blank flags
- project-level totals
- group-level counts or flags

Computed columns should be defined separately from rules:

```yaml
computed_columns:
  - id: days_since_installation
    name: Days Since Installation
    type: date_diff
    start: Installation Date
    end: today
    unit: days

  - id: project_hs_total_incentive
    name: Project H&S Total Incentive
    type: group_sum
    group_by: Project ID
    value: Total Incentive
    where:
      column: Measure Detail: Measure Description
      equals: Health & Safety Services
```

Potential v1 computed column types:

- `sum`
- `subtract`
- `multiply`
- `divide`
- `date_diff`
- `year_diff`
- `coalesce`
- `group_sum`
- `group_count`
- `group_any`
- `group_min`
- `group_max`

Computed fields should be available to rules the same way as input columns.

## Internal Data Model

The package should use DataFrames at the boundary but avoid making the rule evaluator directly depend on pandas.

Proposed internal concepts:

- `RuleBundle`: loaded and validated rules/config.
- `Dataset`: prepared tabular data, likely backed by a DataFrame.
- `Record`: one input row.
- `Group`: related records, such as all rows for one `Project ID`.
- `EvaluationContext`: run-level context available during rule evaluation.
- `Finding`: one rule violation.
- `ValidationResult`: final result object.

The evaluator can process each `Record` and attach findings, then render results back into DataFrames.

## Evaluation Context

Even though JsonLogic will handle expression-tree evaluation, the context concept remains useful.

The context should contain run-level information beyond the current record:

- the full dataset
- grouped records
- loaded rule bundle
- column schema
- computed column definitions
- run start timestamp
- timezone/settings
- null/blank handling settings
- registered custom operators

The run start timestamp matters for date rules. The package should avoid calling `datetime.now()` repeatedly during row evaluation. One stable `now` should be created for the validation run.

## Row IDs

The package should generate or preserve a primary key for each input row.

This should be first-class:

```yaml
settings:
  row_id:
    column: __validation_row_id__
    strategy: sequential
```

The spike successfully generated `__validation_row_id__` before rule evaluation.

Findings should include:

- generated row id
- DataFrame row index
- Excel row number, when known
- rule id
- rule name
- severity
- message
- involved columns
- original values

This is useful for Django display, auditing, and stable references in outputs.

## Processing Pipeline

Preferred v1 pipeline:

1. Load YAML or JSON into a raw config object.
2. Validate the rule bundle schema.
3. Compile friendly rule syntax into JsonLogic expressions.
4. Validate raw input columns needed for computed columns.
5. Generate row ids.
6. Generate computed columns.
7. Validate columns needed by rules.
8. Evaluate all rules against all records using `python-jsonlogic`.
9. Collect findings.
10. Return a `ValidationResult`.
11. Render output DataFrames or Excel files as needed.

## Naming and Namespace

The word "validation" can become overloaded, so the package should use consistent terms.

Recommended names:

- **Rule Bundle**: the loaded YAML/JSON rules config.
- **Rule Schema Validation**: checks whether the rules file itself is structurally valid.
- **Input Schema Check**: checks whether the input DataFrame has required columns and acceptable types.
- **Computed Columns**: generated fields added before rule evaluation.
- **Rule Evaluation**: applies rules to records.
- **Finding**: one rule violation.
- **Validation Result**: the full returned object from a validation run.

Avoid using "column validation" and "dataframe validation" as canonical names because they are easy to confuse.

## Outputs

For v1, keep outputs close to the current workflow.

Primary output:

- input table plus a new `Validation Errors` column

Secondary output:

- rules summary table with one row per rule

Internally, the package should also keep a structured findings table or list:

- row id
- row index
- Excel row number
- rule id
- rule name
- severity
- message
- involved columns
- values

The spike successfully produced:

- annotated DataFrame
- findings DataFrame
- summary DataFrame

Potential result API:

```python
result.to_annotated_dataframe()
result.to_summary_dataframe()
result.to_findings_dataframe()
result.to_json()
```

Excel writing can be a renderer layered on top of the core result object.

## Library First, CLI Later

Because the main runtime will be inside a Python application, the package should be library-first.

The CLI can be added later as a thin wrapper around the same API:

```bash
ruleframe validate input.xlsx --rules rules.yaml --out output.xlsx
```

The CLI should not contain behavior that is unavailable through the Python API.

## Public Package Direction

The end goal is a public deployed pip package.

Design implications:

- Keep project-specific rules out of the core package.
- Keep project-specific calculations configurable where possible.
- Provide clear public APIs.
- Provide typed result objects.
- Provide good error messages for malformed rule bundles and missing input columns.
- Include testable examples.
- Avoid hard-coding Django assumptions into the core package.

## Spike Summary

The spike was created to test the riskiest assumptions in this design before committing to the architecture. Specifically, it tested whether a friendly YAML rule format could be compiled into JsonLogic, whether `python-jsonlogic` could evaluate those expressions against DataFrame records, and whether custom validation operators would be practical enough to treat as a core package feature.

What the spike proved:

- Friendly YAML can compile to JsonLogic.
- `python-jsonlogic` can evaluate compiled rules against DataFrame rows.
- Custom operators are viable.
- JSON Pointer variable paths solve awkward Excel column names.
- Required rule columns can be collected before evaluation.
- Row ids can be generated before evaluation.
- The preferred v1 outputs are feasible.

Known findings from the spike:

- Bare YAML strings like `Yes` can become booleans. Quote string values or validate suspicious values.
- `python-jsonlogic`'s built-in operator registry is intentionally minimal. We need a package-owned registry.
- Nullable numeric schemas can create typecheck diagnostics for comparisons. This needs a package-level policy.
- Computed columns and group-level operations were not modeled in the spike and should be covered in the next prototype.

## Future Design Areas

The following are important but do not need to block the v1 architecture:

- Exceptions may become normal boolean expressions, metadata, or a dedicated `unless` node.
- Possible future rule shape:

  ```yaml
  fail_when:
    all:
      - ...
  unless:
    any:
      - ...
  ```

- Rule authors may eventually use stable logical column IDs instead of exact input column names.
- Column aliases may belong in the `columns` section rather than repeated throughout individual rules.
- Cross-row rules may need a clearer model than row rules with group context.
- Excel styling/highlighting is useful but should be a renderer, not part of core evaluation.
- Multi-file rule folders can be added later by merging into the same internal `RuleBundle`.
- Raw JsonLogic could be accepted directly for advanced users.
- A Python-native rule builder API may be useful later.
- `jsonlogic-py` may be useful for Python-native expression generation later, but is not currently part of the preferred v1 path.
- Performance should be checked on realistic workbook sizes, although row-wise evaluation is likely acceptable for initial use cases.
