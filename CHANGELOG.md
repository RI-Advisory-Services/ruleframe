# Changelog

All notable changes to this project will be documented in this file.

This project is still alpha. Before `1.0.0`, minor releases such as `0.2.0` may include breaking
changes; patch releases such as `0.1.1` should be reserved for compatible bug fixes.

## [0.1.0] - Unreleased

### Added

- Core DataFrame validation pipeline using YAML or JSON rule bundles.
- `RuleBundle` loaders for YAML files, JSON files, YAML strings, JSON strings, and dictionaries.
- `validate_dataframe()` public API.
- `ValidationResult` with findings, annotated DataFrame output, summary output, working DataFrame
  access, and numeric coercion events.
- Predicate support for equality, comparison, column-to-column comparison, membership, string
  containment, ranges, blank checks, date comparisons, and date distance checks.
- Computed columns for row-level arithmetic, row-level logic, group aggregates, and date-derived
  values.
- Numeric type inference and coercion with conflict detection.
- Date normalization for date predicates and date computed columns.
- Custom JsonLogic operator registry for RuleFrame validation behavior.
- Inline type marker via `py.typed`.
- GitHub Actions workflows for linting, testing, and release publishing.
