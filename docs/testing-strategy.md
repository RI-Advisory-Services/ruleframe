# Testing Strategy

RuleFrame will use layered tests:

- Unit tests for compiler pieces and custom operators.
- Integration tests for bundle + DataFrame end-to-end behavior.
- Fixture-driven tests using CSV and YAML files for realistic scenarios.

## Fixture Layout

- `tests/fixtures/data/` for sample datasets.
- `tests/fixtures/rules/` for sample bundles.

## Coverage

Coverage reports show which lines run during tests. We care about quality of assertions first, then coverage thresholds as a guardrail.
