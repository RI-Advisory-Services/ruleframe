# Computed Columns (v1)

Computed columns are generated before rule evaluation and then treated like normal input columns.

## Example

```yaml
computed_columns:
  - id: total_measure_savings
    name: Total Measure Savings
    type: sum
    columns:
      - Total Measure Gross kWh
      - Total Measure Gross kW
      - Total Measure Gross Therms
```

## Supported Types

- `sum`

## Planned Types

- `subtract`
- `multiply`
- `divide`
- `date_diff`
- `coalesce`
- `group_sum`
- `group_count`

## Pipeline Position

1. Validate required source columns.
2. Compute generated columns.
3. Evaluate rules using input plus computed columns.
